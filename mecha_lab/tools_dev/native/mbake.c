/* mbake: Mecha Lab's own map baker (high poly -> low poly), plain arrays, multi-threaded, loaded with ctypes.
 * Built into the same library as mdecim / mquad.
 *
 * 0.24.340 (user: "베이크를 좀 더 빠르게 ... 4번으로 가자 빠르게 해 줘 최대한"): the texture-space ray projection of
 * GPU Gems 3 ch. 22 / AssetGen (arXiv 2605.26137) on the CPU: the low poly rasterised in its own UV space (a texel's
 * point, normal, tangent and cage point), one ray a texel from the cage through the low into the high (a BVH, binned
 * SAH), the high's smooth normal at the hit put into the low's tangent space.  No sampling noise (one ray a texel is
 * exact), no Cycles scene to build - the same rule as Blender's Selected to Active bake with a cage.
 *
 * int mbake_normal(int nlt, const float *luv, const float *lP, const float *lN, const float *lT, const float *lS,
 *                  const float *lC, int nhv, const float *hV, int nht, const int *hT, const float *hN,
 *                  int w, int h, float maxdist, int green_neg, int margin, int threads,
 *                  float *out, unsigned char *mask)
 *   low: nlt triangles, per corner: luv (2), lP point (3, world), lN normal (3), lT tangent (3), lS bitangent sign
 *   (1), lC cage point (3);  high: nhv points hV (3), nht triangles hT (3 indices), hN normal per corner (9 a tri).
 *   out: w * h RGBA (row 0 = v 0), mask: 1 where a texel of the low was baked (others filled by the margin).
 *   Returns 0, 1 bad input, 2 out of memory. */
#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
#else
#include <pthread.h>
#define EXPORT __attribute__((visibility("default")))
#endif

typedef struct { float mn[3], mx[3]; int left, count; } Node;   /* count > 0: leaf, left = first prim */

typedef struct { float mn[3], mx[3], c[3]; int id; } Prim;   /* a triangle's box, centre (moved in place) */

typedef struct {
  const float *V; const int *T; int nt;
  Prim *pr;
  int *idx;                    /* (after the build: the triangle of each leaf slot) */
  Node *nodes; int nn, cap;
} BVH;

static void box_tri(const float *V, const int *t, float *mn, float *mx) {
  for (int a = 0; a < 3; a++) {
    float x0 = V[t[0] * 3 + a], x1 = V[t[1] * 3 + a], x2 = V[t[2] * 3 + a];
    mn[a] = fminf(x0, fminf(x1, x2));
    mx[a] = fmaxf(x0, fmaxf(x1, x2));
  }
}

static int new_node(BVH *b) {
  if (b->nn == b->cap) {
    int c = b->cap * 2;
    Node *n = (Node *)realloc(b->nodes, sizeof(Node) * c);
    if (!n) return -1;
    b->nodes = n; b->cap = c;
  }
  return b->nn++;
}

static float area(const float *mn, const float *mx) {
  float d0 = mx[0] - mn[0], d1 = mx[1] - mn[1], d2 = mx[2] - mn[2];
  if (d0 < 0 || d1 < 0 || d2 < 0) return 0.f;
  return d0 * d1 + d1 * d2 + d2 * d0;
}

#define NB 12
static int build(BVH *b, int first, int count) {
  int ni = new_node(b);
  if (ni < 0) return -1;
  Prim *P = b->pr;
  float mn[3] = {1e30f, 1e30f, 1e30f}, mx[3] = {-1e30f, -1e30f, -1e30f};
  float cmn[3] = {1e30f, 1e30f, 1e30f}, cmx[3] = {-1e30f, -1e30f, -1e30f};
  for (int i = first; i < first + count; i++) {
    const Prim *p = &P[i];
    for (int a = 0; a < 3; a++) {
      if (p->mn[a] < mn[a]) mn[a] = p->mn[a];
      if (p->mx[a] > mx[a]) mx[a] = p->mx[a];
      if (p->c[a] < cmn[a]) cmn[a] = p->c[a];
      if (p->c[a] > cmx[a]) cmx[a] = p->c[a];
    }
  }
  Node *n = &b->nodes[ni];
  memcpy(n->mn, mn, sizeof mn); memcpy(n->mx, mx, sizeof mx);
  if (count <= 4) { n->left = first; n->count = count; return ni; }
  int ax = 0;
  float ext[3] = {cmx[0] - cmn[0], cmx[1] - cmn[1], cmx[2] - cmn[2]};
  if (ext[1] > ext[ax]) ax = 1;
  if (ext[2] > ext[ax]) ax = 2;
  if (ext[ax] <= 1e-12f) { n->left = first; n->count = count; return ni; }
  float sc = NB / ext[ax], base = cmn[ax];
  int split = -1;
  if (count > 16) {                  /* binned SAH, one sweep each way */
    int bc[NB] = {0};
    float bmn[NB][3], bmx[NB][3];
    for (int k = 0; k < NB; k++) for (int a = 0; a < 3; a++) { bmn[k][a] = 1e30f; bmx[k][a] = -1e30f; }
    for (int i = first; i < first + count; i++) {
      const Prim *p = &P[i];
      int k = (int)((p->c[ax] - base) * sc);
      if (k >= NB) k = NB - 1;
      bc[k]++;
      for (int a = 0; a < 3; a++) {
        if (p->mn[a] < bmn[k][a]) bmn[k][a] = p->mn[a];
        if (p->mx[a] > bmx[k][a]) bmx[k][a] = p->mx[a];
      }
    }
    float best = 1e30f, rarea[NB]; int rcnt[NB];
    float rmn[3] = {1e30f, 1e30f, 1e30f}, rmx[3] = {-1e30f, -1e30f, -1e30f};
    int rc = 0;
    for (int k = NB - 1; k >= 1; k--) {
      rc += bc[k];
      for (int a = 0; a < 3; a++) { rmn[a] = fminf(rmn[a], bmn[k][a]); rmx[a] = fmaxf(rmx[a], bmx[k][a]); }
      rarea[k] = area(rmn, rmx); rcnt[k] = rc;
    }
    float lmn[3] = {1e30f, 1e30f, 1e30f}, lmx[3] = {-1e30f, -1e30f, -1e30f};
    int lc = 0;
    for (int s2 = 1; s2 < NB; s2++) {
      lc += bc[s2 - 1];
      for (int a = 0; a < 3; a++) { lmn[a] = fminf(lmn[a], bmn[s2 - 1][a]); lmx[a] = fmaxf(lmx[a], bmx[s2 - 1][a]); }
      if (!lc || !rcnt[s2]) continue;
      float c = lc * area(lmn, lmx) + rcnt[s2] * rarea[s2];
      if (c < best) { best = c; split = s2; }
    }
  } else {
    split = NB / 2;                  /* (small: the middle of the centres) */
  }
  int i = first, j = first + count - 1;
  while (i <= j) {
    int k = (int)((P[i].c[ax] - base) * sc);
    if (k >= NB) k = NB - 1;
    if (k < split) i++;
    else { Prim tmp = P[i]; P[i] = P[j]; P[j] = tmp; j--; }
  }
  int mid = i;
  if (mid == first || mid == first + count) mid = first + count / 2;
  int l = build(b, first, mid - first);
  int r = build(b, mid, first + count - mid);
  if (l < 0 || r < 0) return -1;
  b->nodes[ni].left = l;           /* (inner: left child; the right one is stored as count = -right) */
  b->nodes[ni].count = -r;
  return ni;
}

static inline int ray_box(const float *o, const float *inv, const Node *n, float tmax, float *tn) {
  float t0 = 0.f, t1 = tmax;
  for (int a = 0; a < 3; a++) {
    float ta = (n->mn[a] - o[a]) * inv[a], tb = (n->mx[a] - o[a]) * inv[a];
    if (ta > tb) { float x = ta; ta = tb; tb = x; }
    if (ta > t0) t0 = ta;
    if (tb < t1) t1 = tb;
    if (t0 > t1) return 0;
  }
  *tn = t0;
  return 1;
}

/* the nearest hit of the ray (o, d) within (0, tmax]: its triangle and barycentrics, or -1 */
static int trace(const BVH *b, const float *o, const float *d, float tmax, float *tout, float *uo, float *vo) {
  float inv[3];
  for (int a = 0; a < 3; a++) inv[a] = 1.f / (fabsf(d[a]) > 1e-20f ? d[a] : (d[a] < 0 ? -1e-20f : 1e-20f));
  int stack[96]; float snear[96]; int sp = 0, hit = -1;
  float best = tmax, tn;
  if (!ray_box(o, inv, &b->nodes[0], best, &tn)) return -1;
  stack[sp] = 0; snear[sp++] = tn;
  while (sp) {
    --sp;
    if (snear[sp] > best) continue;              /* (a nearer hit found since it was pushed) */
    const Node *n = &b->nodes[stack[sp]];
    if (n->count > 0) {
      for (int i = n->left; i < n->left + n->count; i++) {
        int t = b->idx[i];
        const float *p0 = b->V + b->T[t * 3] * 3, *p1 = b->V + b->T[t * 3 + 1] * 3, *p2 = b->V + b->T[t * 3 + 2] * 3;
        float e1[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]};
        float e2[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
        float pv[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
        float det = e1[0] * pv[0] + e1[1] * pv[1] + e1[2] * pv[2];
        if (fabsf(det) < 1e-20f) continue;
        float id = 1.f / det;
        float tv[3] = {o[0] - p0[0], o[1] - p0[1], o[2] - p0[2]};
        float u = (tv[0] * pv[0] + tv[1] * pv[1] + tv[2] * pv[2]) * id;
        if (u < -1e-6f || u > 1.f + 1e-6f) continue;
        float qv[3] = {tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2], tv[0] * e1[1] - tv[1] * e1[0]};
        float v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) * id;
        if (v < -1e-6f || u + v > 1.f + 1e-6f) continue;
        float tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * id;
        if (tt > 0.f && tt < best) { best = tt; hit = t; *uo = u; *vo = v; }
      }
    } else {
      int l = n->left, r = -n->count;
      float tl, tr;
      int hl = ray_box(o, inv, &b->nodes[l], best, &tl), hr = ray_box(o, inv, &b->nodes[r], best, &tr);
      if (sp > 92) continue;
      if (hl && hr) {                            /* (the nearer child on top) */
        if (tl < tr) { stack[sp] = r; snear[sp++] = tr; stack[sp] = l; snear[sp++] = tl; }
        else { stack[sp] = l; snear[sp++] = tl; stack[sp] = r; snear[sp++] = tr; }
      } else if (hl) { stack[sp] = l; snear[sp++] = tl; }
      else if (hr) { stack[sp] = r; snear[sp++] = tr; }
    }
  }
  *tout = best;
  return hit;
}

/* is anything hit by the ray (o, d) within (tmin, tmax]?  (the first hit ends it: AO needs no nearest) */
static int occluded(const BVH *b, const float *o, const float *d, float tmin, float tmax) {
  float inv[3];
  for (int a = 0; a < 3; a++) inv[a] = 1.f / (fabsf(d[a]) > 1e-20f ? d[a] : (d[a] < 0 ? -1e-20f : 1e-20f));
  int stack[96], sp = 0;
  float tn;
  if (!ray_box(o, inv, &b->nodes[0], tmax, &tn)) return 0;
  stack[sp++] = 0;
  while (sp) {
    const Node *n = &b->nodes[stack[--sp]];
    if (n->count > 0) {
      for (int i = n->left; i < n->left + n->count; i++) {
        int t = b->idx[i];
        const float *p0 = b->V + b->T[t * 3] * 3, *p1 = b->V + b->T[t * 3 + 1] * 3, *p2 = b->V + b->T[t * 3 + 2] * 3;
        float e1[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]};
        float e2[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
        float pv[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
        float det = e1[0] * pv[0] + e1[1] * pv[1] + e1[2] * pv[2];
        if (fabsf(det) < 1e-20f) continue;
        float id = 1.f / det;
        float tv[3] = {o[0] - p0[0], o[1] - p0[1], o[2] - p0[2]};
        float u = (tv[0] * pv[0] + tv[1] * pv[1] + tv[2] * pv[2]) * id;
        if (u < 0.f || u > 1.f) continue;
        float qv[3] = {tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2], tv[0] * e1[1] - tv[1] * e1[0]};
        float v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) * id;
        if (v < 0.f || u + v > 1.f) continue;
        float tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * id;
        if (tt > tmin && tt <= tmax) return 1;
      }
    } else {
      int l = n->left, r = -n->count;
      float tl, tr;
      if (sp > 92) continue;
      if (ray_box(o, inv, &b->nodes[l], tmax, &tl)) stack[sp++] = l;
      if (ray_box(o, inv, &b->nodes[r], tmax, &tr)) stack[sp++] = r;
    }
  }
  return 0;
}

static inline unsigned int hash32(unsigned int x) {
  x ^= x >> 16; x *= 0x7feb352dU; x ^= x >> 15; x *= 0x846ca68bU; x ^= x >> 16;
  return x;
}

typedef struct {
  const BVH *bvh;
  const float *lP, *lN, *lT, *lS, *lC, *hN, *hA;
  const int *ptri; const float *pbar; const int *plist;
  int n0, n1, green_neg; float maxdist;
  float *out, *outh, *outa, *outo;
  int ao_n; float ao_dist;
} Job;

static void norm3(float *v) {
  float l = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
  if (l > 1e-20f) { v[0] /= l; v[1] /= l; v[2] /= l; }
}

static void run_job(Job *j) {
  for (int q = j->n0; q < j->n1; q++) {
    int px = j->plist[q];
    int t = j->ptri[px];
    const float *w = j->pbar + px * 3;
    float P[3] = {0}, N[3] = {0}, T[3] = {0}, Cg[3] = {0}, S = 0;
    for (int c = 0; c < 3; c++) {
      int k = t * 3 + c;
      for (int a = 0; a < 3; a++) {
        P[a] += w[c] * j->lP[k * 3 + a]; N[a] += w[c] * j->lN[k * 3 + a];
        T[a] += w[c] * j->lT[k * 3 + a]; Cg[a] += w[c] * j->lC[k * 3 + a];
      }
      S += w[c] * j->lS[k];
    }
    norm3(N);
    float d[3] = {P[0] - Cg[0], P[1] - Cg[1], P[2] - Cg[2]};
    float dl = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    float o[3];
    if (dl < 1e-12f) {               /* (no cage offset: from the outside along the normal) */
      for (int a = 0; a < 3; a++) { o[a] = P[a] + N[a] * j->maxdist * 0.5f; d[a] = -N[a]; }
    } else {
      for (int a = 0; a < 3; a++) { o[a] = Cg[a]; d[a] /= dl; }
    }
    float tt, u, v, n[3];
    int h = trace(j->bvh, o, d, j->maxdist, &tt, &u, &v);
    if (h < 0) {
      n[0] = N[0]; n[1] = N[1]; n[2] = N[2];
      if (j->outh) j->outh[px] = 0.f;
      if (j->outa) j->outa[px] = 0.5f;
      if (j->outo) j->outo[px] = 1.f;
    } else {
      const float *hn = j->hN + h * 9;
      float w0 = 1.f - u - v;
      for (int a = 0; a < 3; a++) n[a] = w0 * hn[a] + u * hn[3 + a] + v * hn[6 + a];
      norm3(n);
      if (j->outh) {                   /* height: the hit over the low's point, along the low's normal */
        float q[3] = {o[0] + d[0] * tt - P[0], o[1] + d[1] * tt - P[1], o[2] + d[2] * tt - P[2]};
        j->outh[px] = q[0] * N[0] + q[1] * N[1] + q[2] * N[2];
      }
      if (j->outo) {                   /* ambient occlusion at the hit: the share of a cosine hemisphere open */
        const int *tri = j->bvh->T + h * 3;
        const float *p0 = j->bvh->V + tri[0] * 3, *p1 = j->bvh->V + tri[1] * 3, *p2 = j->bvh->V + tri[2] * 3;
        float e1[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]}, e2[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
        float g[3] = {e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]};
        norm3(g);
        if (g[0] * n[0] + g[1] * n[1] + g[2] * n[2] < 0) { g[0] = -g[0]; g[1] = -g[1]; g[2] = -g[2]; }
        float Q[3] = {o[0] + d[0] * tt, o[1] + d[1] * tt, o[2] + d[2] * tt};
        float eps = j->ao_dist * 1e-4f + 1e-7f;
        float O[3] = {Q[0] + g[0] * eps, Q[1] + g[1] * eps, Q[2] + g[2] * eps};
        float ta[3], tb[3];                       /* a frame round the smooth normal */
        if (fabsf(n[0]) > 0.9f) { ta[0] = 0; ta[1] = 1; ta[2] = 0; } else { ta[0] = 1; ta[1] = 0; ta[2] = 0; }
        tb[0] = n[1] * ta[2] - n[2] * ta[1]; tb[1] = n[2] * ta[0] - n[0] * ta[2]; tb[2] = n[0] * ta[1] - n[1] * ta[0];
        norm3(tb);
        ta[0] = tb[1] * n[2] - tb[2] * n[1]; ta[1] = tb[2] * n[0] - tb[0] * n[2]; ta[2] = tb[0] * n[1] - tb[1] * n[0];
        int ns = j->ao_n, sq = (int)sqrtf((float)ns);
        if (sq < 1) sq = 1;
        unsigned int hs = hash32((unsigned int)px * 9781u + 1u);
        float r0 = (hs & 0xffff) / 65536.f, r1 = (hs >> 16) / 65536.f;   /* (a turn of the pattern a texel) */
        int open = 0, tot = 0;
        for (int k = 0; k < ns; k++) {
          float u1 = ((k % sq) + 0.5f) / sq, u2 = (((k / sq) % sq) + 0.5f) / sq;
          if (k >= sq * sq) { unsigned int hk = hash32(hs + k * 747796405u); u1 = (hk & 0xffff) / 65536.f; u2 = (hk >> 16) / 65536.f; }
          u1 = u1 + r0; if (u1 >= 1.f) u1 -= 1.f;
          u2 = u2 + r1; if (u2 >= 1.f) u2 -= 1.f;
          float rr = sqrtf(u1), ph = 6.2831853f * u2;
          float lx = rr * cosf(ph), ly = rr * sinf(ph), lz = sqrtf(fmaxf(0.f, 1.f - u1));
          float dir[3] = {ta[0] * lx + tb[0] * ly + n[0] * lz, ta[1] * lx + tb[1] * ly + n[1] * lz,
                          ta[2] * lx + tb[2] * ly + n[2] * lz};
          if (dir[0] * g[0] + dir[1] * g[1] + dir[2] * g[2] <= 0.f) continue;   /* (under the face itself) */
          tot++;
          if (!occluded(j->bvh, O, dir, 0.f, j->ao_dist)) open++;
        }
        j->outo[px] = tot ? (float)open / tot : 1.f;
      }
      if (j->outa) {                   /* the high's own value there (curvature), between its corners */
        const int *tri = j->bvh->T + h * 3;
        j->outa[px] = w0 * j->hA[tri[0]] + u * j->hA[tri[1]] + v * j->hA[tri[2]];
      }
    }
    if (!j->out) continue;
    /* the low's tangent space: T, B = sign * N x T, N */
    float B[3] = {N[1] * T[2] - N[2] * T[1], N[2] * T[0] - N[0] * T[2], N[0] * T[1] - N[1] * T[0]};
    float sg = S < 0 ? -1.f : 1.f;
    float x = n[0] * T[0] + n[1] * T[1] + n[2] * T[2];
    float y = sg * (n[0] * B[0] + n[1] * B[1] + n[2] * B[2]);
    float z = n[0] * N[0] + n[1] * N[1] + n[2] * N[2];
    if (j->green_neg) y = -y;
    float *op = j->out + px * 4;
    op[0] = 0.5f * x + 0.5f; op[1] = 0.5f * y + 0.5f; op[2] = 0.5f * z + 0.5f; op[3] = 1.f;
  }
}

#ifdef _WIN32
static DWORD WINAPI job_thread(LPVOID p) { run_job((Job *)p); return 0; }
#else
static void *job_thread(void *p) { run_job((Job *)p); return NULL; }
#endif

static void margin_fill(float *out, int ch, const unsigned char *mask, int w, int h, int margin) {
  /* EXTEND: each ring outside the baked texels takes the average of its baked / filled neighbours */
  unsigned char *m = (unsigned char *)malloc((size_t)w * h);
  if (!m) return;
  memcpy(m, mask, (size_t)w * h);
  int *ring = (int *)malloc(sizeof(int) * (size_t)w * h);
  if (!ring) { free(m); return; }
  for (int it = 0; it < margin; it++) {
    int nr = 0;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
      int i = y * w + x;
      if (m[i]) continue;
      float acc[4] = {0}; int c = 0;
      for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
        int xx = x + dx, yy = y + dy;
        if ((dx || dy) && xx >= 0 && yy >= 0 && xx < w && yy < h && m[yy * w + xx] == 1) {
          for (int a = 0; a < ch; a++) acc[a] += out[(yy * w + xx) * ch + a];
          c++;
        }
      }
      if (c) { for (int a = 0; a < ch; a++) out[i * ch + a] = acc[a] / c; ring[nr++] = i; }
    }
    if (!nr) break;
    for (int k = 0; k < nr; k++) m[ring[k]] = 1;
  }
  free(ring); free(m);
}

EXPORT int mbake_version(void) { return 6; }

/* v2: the Normal map and, in the same rays, the Height (hit distance along the low's normal, world units; NULL: not
 * wanted) and a value of the high's points (hA, e.g. its curvature, between the hit triangle's corners; NULL: not
 * wanted).  out may be NULL too (only Height / the value). */
EXPORT int mbake_maps(int nlt, const float *luv, const float *lP, const float *lN, const float *lT, const float *lS,
                      const float *lC, int nhv, const float *hV, int nht, const int *hT, const float *hN,
                      const float *hA, int w, int h, float maxdist, int green_neg, int margin, int threads,
                      float *out, float *outh, float *outa, float *outo, int ao_n, float ao_dist,
                      unsigned char *mask)
{
  if (nlt <= 0 || nht <= 0 || nhv <= 0 || w <= 0 || h <= 0) return 1;
  for (int i = 0; i < nht * 3; i++) if (hT[i] < 0 || hT[i] >= nhv) return 1;
  size_t np = (size_t)w * h;
  BVH b; memset(&b, 0, sizeof b);
  b.V = hV; b.T = hT; b.nt = nht;
  b.pr = (Prim *)malloc(sizeof(Prim) * nht); b.idx = (int *)malloc(sizeof(int) * nht);
  b.cap = nht + 16; b.nodes = (Node *)malloc(sizeof(Node) * b.cap);
  int *ptri = (int *)malloc(sizeof(int) * np);
  float *pbar = (float *)malloc(sizeof(float) * 3 * np);
  int *plist = (int *)malloc(sizeof(int) * np);
  int rc = 0;
  if (!b.pr || !b.idx || !b.nodes || !ptri || !pbar || !plist) { rc = 2; goto done; }
  for (int t = 0; t < nht; t++) {
    Prim *p = &b.pr[t];
    box_tri(hV, hT + t * 3, p->mn, p->mx);
    for (int a = 0; a < 3; a++) p->c[a] = 0.5f * (p->mn[a] + p->mx[a]);
    p->id = t;
  }
  if (build(&b, 0, nht) < 0) { rc = 2; goto done; }
  for (int t = 0; t < nht; t++) b.idx[t] = b.pr[t].id;
  /* rasterise the low in UV space: texel centres, the last triangle covering a texel wins (as Blender) */
  memset(mask, 0, np);
  for (size_t i = 0; i < np; i++) ptri[i] = -1;
  for (int t = 0; t < nlt; t++) {
    float x[3], y[3];
    for (int c = 0; c < 3; c++) { x[c] = luv[(t * 3 + c) * 2] * w - 0.5f; y[c] = luv[(t * 3 + c) * 2 + 1] * h - 0.5f; }
    float den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]);
    if (fabsf(den) < 1e-12f) continue;
    int x0 = (int)floorf(fminf(x[0], fminf(x[1], x[2]))), x1 = (int)ceilf(fmaxf(x[0], fmaxf(x[1], x[2])));
    int y0 = (int)floorf(fminf(y[0], fminf(y[1], y[2]))), y1 = (int)ceilf(fmaxf(y[0], fmaxf(y[1], y[2])));
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > w - 1) x1 = w - 1;
    if (y1 > h - 1) y1 = h - 1;
    for (int py = y0; py <= y1; py++) for (int px = x0; px <= x1; px++) {
      float a = ((y[1] - y[2]) * (px - x[2]) + (x[2] - x[1]) * (py - y[2])) / den;
      float bb = ((y[2] - y[0]) * (px - x[2]) + (x[0] - x[2]) * (py - y[2])) / den;
      float c = 1.f - a - bb;
      const float e = -1e-5f;
      if (a < e || bb < e || c < e) continue;
      size_t i = (size_t)py * w + px;
      ptri[i] = t;
      pbar[i * 3] = a; pbar[i * 3 + 1] = bb; pbar[i * 3 + 2] = c;
    }
  }
  int n = 0;
  for (size_t i = 0; i < np; i++) if (ptri[i] >= 0) { plist[n++] = (int)i; mask[i] = 1; }
  if (out) for (size_t i = 0; i < np; i++) { out[i * 4] = 0.5f; out[i * 4 + 1] = 0.5f; out[i * 4 + 2] = 1.f; out[i * 4 + 3] = 1.f; }
  if (outh) for (size_t i = 0; i < np; i++) outh[i] = 0.f;
  if (outa) for (size_t i = 0; i < np; i++) outa[i] = 0.5f;
  if (outo) for (size_t i = 0; i < np; i++) outo[i] = 1.f;
  if (outa && !hA) { rc = 1; goto done; }
  {
    int nt = threads < 1 ? 1 : (threads > 64 ? 64 : threads);
    if (n < 4096) nt = 1;
    Job jobs[64];
    for (int k = 0; k < nt; k++) {
      Job jb = {&b, lP, lN, lT, lS, lC, hN, hA, ptri, pbar, plist, (int)((long long)n * k / nt),
                (int)((long long)n * (k + 1) / nt), green_neg, maxdist, out, outh, outa, outo,
                ao_n < 1 ? 1 : ao_n, ao_dist};
      jobs[k] = jb;
    }
#ifdef _WIN32
    HANDLE th[64];
    for (int k = 1; k < nt; k++) th[k] = CreateThread(NULL, 0, job_thread, &jobs[k], 0, NULL);
    run_job(&jobs[0]);
    for (int k = 1; k < nt; k++) if (th[k]) { WaitForSingleObject(th[k], INFINITE); CloseHandle(th[k]); } else run_job(&jobs[k]);
#else
    pthread_t th[64]; int ok[64];
    for (int k = 1; k < nt; k++) ok[k] = pthread_create(&th[k], NULL, job_thread, &jobs[k]) == 0;
    run_job(&jobs[0]);
    for (int k = 1; k < nt; k++) { if (ok[k]) pthread_join(th[k], NULL); else run_job(&jobs[k]); }
#endif
  }
  if (margin > 0) {
    if (out) margin_fill(out, 4, mask, w, h, margin);
    if (outh) margin_fill(outh, 1, mask, w, h, margin);
    if (outa) margin_fill(outa, 1, mask, w, h, margin);
    if (outo) margin_fill(outo, 1, mask, w, h, margin);
  }
done:
  free(b.pr); free(b.idx); free(b.nodes); free(ptri); free(pbar); free(plist);
  return rc;
}

EXPORT int mbake_normal(int nlt, const float *luv, const float *lP, const float *lN, const float *lT, const float *lS,
                        const float *lC, int nhv, const float *hV, int nht, const int *hT, const float *hN,
                        int w, int h, float maxdist, int green_neg, int margin, int threads,
                        float *out, unsigned char *mask) {
  return mbake_maps(nlt, luv, lP, lN, lT, lS, lC, nhv, hV, nht, hT, hN, NULL, w, h, maxdist, green_neg, margin,
                    threads, out, NULL, NULL, NULL, 0, 0.f, mask);
}


/* ------------------------------------------------------------------------------------------------------------------
 * v4 (0.24.341, user: "노하이폴리도 느려서 만들라는거야"): the No High Poly bake without Cycles - the pieces the shader
 * evaluator (fast_shade.py) needs: the low rasterised in its UVs, image lookups, and the two ray nodes of a material
 * (Ambient Occlusion, Bevel) on the object itself, as Cycles' svm_ao / svm_bevel do them.
 * ------------------------------------------------------------------------------------------------------------------ */

typedef void (*WorkFn)(void *ctx, int i0, int i1);
typedef struct { WorkFn f; void *ctx; int i0, i1; } Work;
#ifdef _WIN32
static DWORD WINAPI work_thread(LPVOID p) { Work *w = (Work *)p; w->f(w->ctx, w->i0, w->i1); return 0; }
#else
static void *work_thread(void *p) { Work *w = (Work *)p; w->f(w->ctx, w->i0, w->i1); return NULL; }
#endif
static void parallel(WorkFn f, void *ctx, int n, int threads) {
  int nt = threads < 1 ? 1 : (threads > 64 ? 64 : threads);
  if (n < 2048) nt = 1;
  Work w[64];
  for (int k = 0; k < nt; k++) { w[k].f = f; w[k].ctx = ctx; w[k].i0 = (int)((long long)n * k / nt); w[k].i1 = (int)((long long)n * (k + 1) / nt); }
#ifdef _WIN32
  HANDLE th[64];
  for (int k = 1; k < nt; k++) th[k] = CreateThread(NULL, 0, work_thread, &w[k], 0, NULL);
  f(ctx, w[0].i0, w[0].i1);
  for (int k = 1; k < nt; k++) if (th[k]) { WaitForSingleObject(th[k], INFINITE); CloseHandle(th[k]); } else f(ctx, w[k].i0, w[k].i1);
#else
  pthread_t th[64]; int ok[64];
  for (int k = 1; k < nt; k++) ok[k] = pthread_create(&th[k], NULL, work_thread, &w[k]) == 0;
  f(ctx, w[0].i0, w[0].i1);
  for (int k = 1; k < nt; k++) { if (ok[k]) pthread_join(th[k], NULL); else f(ctx, w[k].i0, w[k].i1); }
#endif
}

/* the low in its UVs (w x h): each covered texel's triangle (-1: none) and barycentrics; returns how many */
EXPORT int mbake_raster(int nlt, const float *luv, int w, int h, int *ptri, float *pbar, unsigned char *mask) {
  size_t np = (size_t)w * h;
  memset(mask, 0, np);
  for (size_t i = 0; i < np; i++) ptri[i] = -1;
  for (int t = 0; t < nlt; t++) {
    float x[3], y[3];
    for (int c = 0; c < 3; c++) { x[c] = luv[(t * 3 + c) * 2] * w - 0.5f; y[c] = luv[(t * 3 + c) * 2 + 1] * h - 0.5f; }
    float den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]);
    if (fabsf(den) < 1e-12f) continue;
    int x0 = (int)floorf(fminf(x[0], fminf(x[1], x[2]))), x1 = (int)ceilf(fmaxf(x[0], fmaxf(x[1], x[2])));
    int y0 = (int)floorf(fminf(y[0], fminf(y[1], y[2]))), y1 = (int)ceilf(fmaxf(y[0], fmaxf(y[1], y[2])));
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > w - 1) x1 = w - 1;
    if (y1 > h - 1) y1 = h - 1;
    for (int py = y0; py <= y1; py++) for (int px = x0; px <= x1; px++) {
      float a = ((y[1] - y[2]) * (px - x[2]) + (x[2] - x[1]) * (py - y[2])) / den;
      float bb = ((y[2] - y[0]) * (px - x[2]) + (x[0] - x[2]) * (py - y[2])) / den;
      float c = 1.f - a - bb;
      const float e = -1e-5f;
      if (a < e || bb < e || c < e) continue;
      size_t i = (size_t)py * w + px;
      ptri[i] = t; mask[i] = 1;
      pbar[i * 3] = a; pbar[i * 3 + 1] = bb; pbar[i * 3 + 2] = c;
    }
  }
  int n = 0;
  for (size_t i = 0; i < np; i++) n += mask[i];
  return n;
}

EXPORT void mbake_margin(float *out, int ch, const unsigned char *mask, int w, int h, int margin) {
  if (margin > 0 && ch > 0 && ch <= 4) margin_fill(out, ch, mask, w, h, margin);
}

/* -- images: Cycles' lookups (texel centres at (i + 0.5) / size; Linear = bilinear) ------------------------------ */
typedef struct { const float *img; int iw, ih, ch, interp, ext; const float *uv; float *out; } ImgJob;

static inline int wrap_i(int i, int n, int ext, int *ok) {
  if (ext == 0) { i %= n; if (i < 0) i += n; return i; }              /* REPEAT */
  if (ext == 2) { if (i < 0 || i >= n) *ok = 0; return i < 0 ? 0 : (i >= n ? n - 1 : i); }   /* CLIP */
  if (ext == 3) { int p = 2 * n; i %= p; if (i < 0) i += p; return i < n ? i : p - 1 - i; }  /* MIRROR */
  return i < 0 ? 0 : (i >= n ? n - 1 : i);                             /* EXTEND */
}

static void img_work(void *c, int i0, int i1) {
  ImgJob *j = (ImgJob *)c;
  for (int i = i0; i < i1; i++) {
    float u = j->uv[i * 2], v = j->uv[i * 2 + 1];
    float *o = j->out + (size_t)i * 4;
    o[0] = o[1] = o[2] = 0.f; o[3] = 0.f;
    if (!(u == u) || !(v == v)) continue;
    if (j->interp == 0) {
      int ok = 1;
      int x = wrap_i((int)floorf(u * j->iw), j->iw, j->ext, &ok), y = wrap_i((int)floorf(v * j->ih), j->ih, j->ext, &ok);
      if (!ok) continue;
      const float *p = j->img + ((size_t)y * j->iw + x) * j->ch;
      for (int a = 0; a < 4; a++) o[a] = a < j->ch ? p[a] : 1.f;
      continue;
    }
    float fx = u * j->iw - 0.5f, fy = v * j->ih - 0.5f;
    int x0 = (int)floorf(fx), y0 = (int)floorf(fy);
    float tx = fx - x0, ty = fy - y0;
    float acc[4] = {0}, wsum = 0.f;
    for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
      int ok = 1;
      int x = wrap_i(x0 + dx, j->iw, j->ext, &ok), y = wrap_i(y0 + dy, j->ih, j->ext, &ok);
      float wt = (dx ? tx : 1.f - tx) * (dy ? ty : 1.f - ty);
      if (!ok) continue;             /* (CLIP: outside is transparent black) */
      const float *p = j->img + ((size_t)y * j->iw + x) * j->ch;
      for (int a = 0; a < 4; a++) acc[a] += wt * (a < j->ch ? p[a] : 1.f);
      wsum += wt;
    }
    (void)wsum;
    for (int a = 0; a < 4; a++) o[a] = acc[a];
  }
}

EXPORT void mbake_image(const float *img, int iw, int ih, int ch, int interp, int ext, int n, const float *uv,
                        float *out, int threads) {
  ImgJob j = {img, iw, ih, ch, interp, ext, uv, out};
  if (iw <= 0 || ih <= 0 || n <= 0) return;
  parallel(img_work, &j, n, threads);
}

/* -- a scene: the object's triangles (world space) and their corner normals, for its AO / Bevel nodes ------------ */
typedef struct { BVH b; float *V; int *T; float *N; } Scene;

EXPORT void *mbake_scene_new(int nv, const float *V, int nt, const int *T, const float *N) {
  if (nv <= 0 || nt <= 0) return NULL;
  for (int i = 0; i < nt * 3; i++) if (T[i] < 0 || T[i] >= nv) return NULL;
  Scene *s = (Scene *)calloc(1, sizeof(Scene));
  if (!s) return NULL;
  s->V = (float *)malloc(sizeof(float) * 3 * nv); s->T = (int *)malloc(sizeof(int) * 3 * nt);
  s->N = (float *)malloc(sizeof(float) * 9 * nt);
  BVH *b = &s->b;
  b->pr = (Prim *)malloc(sizeof(Prim) * nt); b->idx = (int *)malloc(sizeof(int) * nt);
  b->cap = nt + 16; b->nodes = (Node *)malloc(sizeof(Node) * b->cap);
  if (!s->V || !s->T || !s->N || !b->pr || !b->idx || !b->nodes) goto fail;
  memcpy(s->V, V, sizeof(float) * 3 * nv); memcpy(s->T, T, sizeof(int) * 3 * nt); memcpy(s->N, N, sizeof(float) * 9 * nt);
  b->V = s->V; b->T = s->T; b->nt = nt;
  for (int t = 0; t < nt; t++) {
    Prim *p = &b->pr[t];
    box_tri(s->V, s->T + t * 3, p->mn, p->mx);
    for (int a = 0; a < 3; a++) p->c[a] = 0.5f * (p->mn[a] + p->mx[a]);
    p->id = t;
  }
  if (build(b, 0, nt) < 0) goto fail;
  for (int t = 0; t < nt; t++) b->idx[t] = b->pr[t].id;
  free(b->pr); b->pr = NULL;
  return s;
fail:
  free(s->V); free(s->T); free(s->N); free(b->pr); free(b->idx); free(b->nodes); free(s);
  return NULL;
}

EXPORT void mbake_scene_free(void *p) {
  Scene *s = (Scene *)p;
  if (!s) return;
  free(s->V); free(s->T); free(s->N); free(s->b.idx); free(s->b.nodes); free(s);
}

/* every hit of (o, d) within (0, tmax] - up to ``cap`` (triangle, t, u, v); returns how many there were in all */
static int hits_all(const BVH *b, const float *o, const float *d, float tmax, int skip, int cap, int *ht, float *htt,
                    float *hu, float *hv) {
  float inv[3];
  for (int a = 0; a < 3; a++) inv[a] = 1.f / (fabsf(d[a]) > 1e-20f ? d[a] : (d[a] < 0 ? -1e-20f : 1e-20f));
  int stack[96], sp = 0, nh = 0;
  float tn;
  if (!ray_box(o, inv, &b->nodes[0], tmax, &tn)) return 0;
  stack[sp++] = 0;
  while (sp) {
    const Node *n = &b->nodes[stack[--sp]];
    if (n->count > 0) {
      for (int i = n->left; i < n->left + n->count; i++) {
        int t = b->idx[i];
        if (t == skip) continue;
        const float *p0 = b->V + b->T[t * 3] * 3, *p1 = b->V + b->T[t * 3 + 1] * 3, *p2 = b->V + b->T[t * 3 + 2] * 3;
        float e1[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]};
        float e2[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
        float pv[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
        float det = e1[0] * pv[0] + e1[1] * pv[1] + e1[2] * pv[2];
        if (fabsf(det) < 1e-20f) continue;
        float id = 1.f / det;
        float tv[3] = {o[0] - p0[0], o[1] - p0[1], o[2] - p0[2]};
        float u = (tv[0] * pv[0] + tv[1] * pv[1] + tv[2] * pv[2]) * id;
        if (u < 0.f || u > 1.f) continue;
        float qv[3] = {tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2], tv[0] * e1[1] - tv[1] * e1[0]};
        float v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) * id;
        if (v < 0.f || u + v > 1.f) continue;
        float tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * id;
        if (tt > 0.f && tt <= tmax) {
          if (nh < cap) { ht[nh] = t; htt[nh] = tt; hu[nh] = u; hv[nh] = v; }
          nh++;
        }
      }
    } else {
      int l = n->left, r = -n->count;
      float tl, tr;
      if (sp > 92) continue;
      if (ray_box(o, inv, &b->nodes[l], tmax, &tl)) stack[sp++] = l;
      if (ray_box(o, inv, &b->nodes[r], tmax, &tr)) stack[sp++] = r;
    }
  }
  return nh;
}

static int occluded_skip(const BVH *b, const float *o, const float *d, float tmax, int skip) {
  int ht[1]; float a[1], bb[1], c[1];
  /* (first-hit traversal is enough; hits_all with cap 1 stops collecting but walks on - use the plain one when
   *  nothing is skipped) */
  if (skip < 0) return occluded(b, o, d, 0.f, tmax);
  return hits_all(b, o, d, tmax, skip, 1, ht, a, bb, c) > 0;
}

static void frame(const float *n, float *t, float *b) {     /* Cycles' make_orthonormals */
  if (n[0] != n[1] || n[0] != n[2]) { t[0] = n[2] - n[1]; t[1] = n[0] - n[2]; t[2] = n[1] - n[0]; }
  else { t[0] = n[2] - n[1]; t[1] = n[0] + n[2]; t[2] = -n[0] - n[1]; }
  norm3(t);
  b[0] = n[1] * t[2] - n[2] * t[1]; b[1] = n[2] * t[0] - n[0] * t[2]; b[2] = n[0] * t[1] - n[1] * t[0];
}

static inline float rnd(unsigned int *s) { *s = hash32(*s + 0x9e3779b9u); return (*s >> 8) * (1.f / 16777216.f); }

typedef struct { const Scene *s; const float *P, *N, *Ng; const int *tri; const unsigned int *seed; int ns; float dist;
                 const float *radius; int inside; float *out; } RayJob;

/* AO node: the share of a cosine hemisphere round N (the node's Normal) open within dist; the ray starts a hair off
 * the surface along Ng and skips its own triangle (as Cycles' self-intersection test) */
static void ao_work(void *c, int i0, int i1) {
  RayJob *j = (RayJob *)c;
  const BVH *b = &j->s->b;
  int sq = (int)sqrtf((float)j->ns); if (sq < 1) sq = 1;
  for (int i = i0; i < i1; i++) {
    float n[3] = {j->N[i * 3], j->N[i * 3 + 1], j->N[i * 3 + 2]};
    if (j->inside) { n[0] = -n[0]; n[1] = -n[1]; n[2] = -n[2]; }
    norm3(n);
    const float *g = j->Ng + i * 3;
    float sgn = (g[0] * n[0] + g[1] * n[1] + g[2] * n[2]) < 0 ? -1.f : 1.f;
    float eps = 1e-5f * (1.f + fabsf(j->P[i * 3]) + fabsf(j->P[i * 3 + 1]) + fabsf(j->P[i * 3 + 2]));
    float O[3] = {j->P[i * 3] + sgn * g[0] * eps, j->P[i * 3 + 1] + sgn * g[1] * eps, j->P[i * 3 + 2] + sgn * g[2] * eps};
    float ta[3], tb[3];
    frame(n, ta, tb);
    unsigned int s = j->seed ? j->seed[i] : hash32((unsigned int)i * 9781u + 7u);
    float r0 = rnd(&s), r1 = rnd(&s);
    int open = 0;
    for (int k = 0; k < j->ns; k++) {
      float u1, u2;
      if (k < sq * sq) { u1 = ((k % sq) + 0.5f) / sq; u2 = ((k / sq) + 0.5f) / sq; }
      else { u1 = rnd(&s); u2 = rnd(&s); }
      u1 += r0; if (u1 >= 1.f) u1 -= 1.f;
      u2 += r1; if (u2 >= 1.f) u2 -= 1.f;
      float rr = sqrtf(u1), ph = 6.2831853f * u2;
      float lx = rr * cosf(ph), ly = rr * sinf(ph), lz = sqrtf(fmaxf(0.f, 1.f - u1));
      float d[3] = {ta[0] * lx + tb[0] * ly + n[0] * lz, ta[1] * lx + tb[1] * ly + n[1] * lz, ta[2] * lx + tb[2] * ly + n[2] * lz};
      if (!occluded_skip(b, O, d, j->dist, j->tri ? j->tri[i] : -1)) open++;
    }
    j->out[i] = j->ns > 0 ? (float)open / j->ns : 1.f;
  }
}

EXPORT void mbake_ao(void *scene, int n, const float *P, const float *N, const float *Ng, const int *tri,
                     const unsigned int *seed, int samples, float dist, int inside, float *out, int threads) {
  if (!scene || n <= 0) return;
  RayJob j = {(const Scene *)scene, P, N, Ng, tri, seed, samples < 1 ? 1 : samples, dist, NULL, inside, out};
  parallel(ao_work, &j, n, threads);
}

/* Bevel node: Cycles' svm_bevel - rays through a cubic-weighted disk round P (on the Ng plane and the two planes
 * across it), every hit's smooth normal summed with its MIS weight */
static float cubic_eval(float R, float r) {
  if (r >= R) return 0.f;
  float R5 = R * R * R * R * R, f = R - r;
  return 10.f * f * f * f / (R5 * 3.14159265f);
}
static float quintic_root(float xi) {
  float x = 0.25f;
  for (int i = 0; i < 10; i++) {
    float x2 = x * x, x3 = x2 * x, nx = 1.f - x;
    float f = 10.f * x2 - 20.f * x3 + 15.f * x2 * x2 - 4.f * x2 * x3 - xi;
    float f_ = 20.f * (x * nx) * (nx * nx);
    if (fabsf(f) < 1e-6f || f_ == 0.f) break;
    x = x - f / f_;
    if (x < 0.f) x = 0.f;
    if (x > 1.f) x = 1.f;
  }
  return x;
}

static void bevel_work(void *c, int i0, int i1) {
  RayJob *j = (RayJob *)c;
  const Scene *sc = j->s;
  const BVH *b = &sc->b;
  enum { CAP = 8 };
  int ht[CAP]; float htt[CAP], hu[CAP], hv[CAP];
  for (int i = i0; i < i1; i++) {
    const float *P = j->P + i * 3;
    float R = j->radius[i];
    float *o = j->out + i * 3;
    const float *n0 = j->N + i * 3;
    if (!(R > 0.f)) { o[0] = n0[0]; o[1] = n0[1]; o[2] = n0[2]; continue; }
    float Ng[3] = {j->Ng[i * 3], j->Ng[i * 3 + 1], j->Ng[i * 3 + 2]};
    float T0[3], B0[3];
    frame(Ng, T0, B0);
    unsigned int s = j->seed ? j->seed[i] : hash32((unsigned int)i * 2654435761u + 3u);
    float sum[3] = {0, 0, 0};
    int sq = (int)sqrtf((float)j->ns); if (sq < 1) sq = 1;
    float r0 = rnd(&s), r1 = rnd(&s);
    for (int k = 0; k < j->ns; k++) {
      float du, dv;
      if (k < sq * sq) { du = ((k % sq) + 0.5f) / sq; dv = ((k / sq) + 0.5f) / sq; }
      else { du = rnd(&s); dv = rnd(&s); }
      du += r0; if (du >= 1.f) du -= 1.f;
      dv += r1; if (dv >= 1.f) dv -= 1.f;
      float dN[3], dT[3], dB[3], pN, pT, pB;
      if (du < 0.5f) { memcpy(dN, Ng, 12); memcpy(dT, T0, 12); memcpy(dB, B0, 12); pN = 0.5f; pT = 0.25f; pB = 0.25f; du *= 2.f; }
      else if (du < 0.75f) { memcpy(dN, T0, 12); memcpy(dT, Ng, 12); memcpy(dB, B0, 12); pN = 0.25f; pT = 0.5f; pB = 0.25f; du = (du - 0.5f) * 4.f; }
      else { memcpy(dN, B0, 12); memcpy(dT, T0, 12); memcpy(dB, Ng, 12); pN = 0.25f; pT = 0.25f; pB = 0.5f; du = (du - 0.75f) * 4.f; }
      float phi = 6.2831853f * du;
      float dr = quintic_root(dv) * R;
      float hgt = sqrtf(fmaxf(0.f, R * R - dr * dr));
      float O[3], D[3] = {-dN[0], -dN[1], -dN[2]};
      for (int a = 0; a < 3; a++) O[a] = P[a] + dN[a] * hgt + dr * cosf(phi) * dT[a] + dr * sinf(phi) * dB[a];
      int nh = hits_all(b, O, D, 2.f * hgt, -1, CAP, ht, htt, hu, hv);
      int ne = nh < CAP ? nh : CAP;
      float disk_pdf = cubic_eval(R, dr);
      if (disk_pdf <= 0.f) continue;
      for (int q = 0; q < ne; q++) {
        int t = ht[q];
        const float *p0 = sc->V + sc->T[t * 3] * 3, *p1 = sc->V + sc->T[t * 3 + 1] * 3, *p2 = sc->V + sc->T[t * 3 + 2] * 3;
        float e1[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]}, e2[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
        float hg[3] = {e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]};
        norm3(hg);
        const float *cn = sc->N + t * 9;
        float w0 = 1.f - hu[q] - hv[q];
        float hn[3];
        for (int a = 0; a < 3; a++) hn[a] = w0 * cn[a] + hu[q] * cn[3 + a] + hv[q] * cn[6 + a];
        norm3(hn);
        float qN = pN * fabsf(dN[0] * hg[0] + dN[1] * hg[1] + dN[2] * hg[2]);
        float qT = pT * fabsf(dT[0] * hg[0] + dT[1] * hg[1] + dT[2] * hg[2]);
        float qB = pB * fabsf(dB[0] * hg[0] + dB[1] * hg[1] + dB[2] * hg[2]);
        float den = qN * qN + qT * qT + qB * qB;
        if (den <= 0.f) continue;
        float w = qN / den;
        if (nh > CAP) w *= (float)nh / CAP;
        float hp[3] = {O[0] + D[0] * htt[q] - P[0], O[1] + D[1] * htt[q] - P[1], O[2] + D[2] * htt[q] - P[2]};
        float r = sqrtf(hp[0] * hp[0] + hp[1] * hp[1] + hp[2] * hp[2]);
        w *= cubic_eval(R, r) / disk_pdf;
        for (int a = 0; a < 3; a++) sum[a] += w * hn[a];
      }
    }
    float l = sqrtf(sum[0] * sum[0] + sum[1] * sum[1] + sum[2] * sum[2]);
    if (l < 1e-20f) { o[0] = n0[0]; o[1] = n0[1]; o[2] = n0[2]; }
    else { o[0] = sum[0] / l; o[1] = sum[1] / l; o[2] = sum[2] / l; }
  }
}

EXPORT void mbake_bevel(void *scene, int n, const float *P, const float *N, const float *Ng, const float *radius,
                        const unsigned int *seed, int samples, float *out, int threads) {
  if (!scene || n <= 0) return;
  RayJob j = {(const Scene *)scene, P, N, Ng, NULL, seed, samples < 1 ? 1 : samples, 0.f, radius, 0, out};
  parallel(bevel_work, &j, n, threads);
}


/* v5 (0.24.343): nearest hit of rays (O, D) within (0, tmax] - each texel's look for a decal over it.  out_tri -1:
 * none; out_t / out_u / out_v the hit. */
typedef struct { const Scene *s; const float *O, *D; float tmax; int *tri; float *t, *u, *v; } CastJob;
static void cast_work(void *c, int i0, int i1) {
  CastJob *j = (CastJob *)c;
  for (int i = i0; i < i1; i++) {
    float tt, uu, vv;
    int h = trace(&j->s->b, j->O + i * 3, j->D + i * 3, j->tmax, &tt, &uu, &vv);
    j->tri[i] = h;
    if (h >= 0) { j->t[i] = tt; j->u[i] = uu; j->v[i] = vv; }
  }
}
EXPORT void mbake_cast(void *scene, int n, const float *O, const float *D, float tmax, int *tri, float *t, float *u,
                       float *v, int threads) {
  if (!scene || n <= 0) return;
  CastJob j = {(const Scene *)scene, O, D, tmax, tri, t, u, v};
  parallel(cast_work, &j, n, threads);
}


/* v6 (0.24.343): Cycles' box-projected image lookup (svm_node_tex_image_box) in one go: weights from the object-space
 * normal and the blend, up to three planar lookups */
static void sample_one(const ImgJob *j, float u, float v, float *o) {
  o[0] = o[1] = o[2] = o[3] = 0.f;
  if (!(u == u) || !(v == v)) return;
  if (j->interp == 0) {
    int ok = 1;
    int x = wrap_i((int)floorf(u * j->iw), j->iw, j->ext, &ok), y = wrap_i((int)floorf(v * j->ih), j->ih, j->ext, &ok);
    if (!ok) return;
    const float *p = j->img + ((size_t)y * j->iw + x) * j->ch;
    for (int a = 0; a < 4; a++) o[a] = a < j->ch ? p[a] : 1.f;
    return;
  }
  float fx = u * j->iw - 0.5f, fy = v * j->ih - 0.5f;
  int x0 = (int)floorf(fx), y0 = (int)floorf(fy);
  float tx = fx - x0, ty = fy - y0;
  for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
    int ok = 1;
    int x = wrap_i(x0 + dx, j->iw, j->ext, &ok), y = wrap_i(y0 + dy, j->ih, j->ext, &ok);
    float wt = (dx ? tx : 1.f - tx) * (dy ? ty : 1.f - ty);
    if (!ok) continue;
    const float *p = j->img + ((size_t)y * j->iw + x) * j->ch;
    for (int a = 0; a < 4; a++) o[a] += wt * (a < j->ch ? p[a] : 1.f);
  }
}

typedef struct { ImgJob im; const float *co, *N; float blend; } BoxJob;
static float satf(float x) { return x < 0.f ? 0.f : (x > 1.f ? 1.f : x); }
static void box_work(void *c, int i0, int i1) {
  BoxJob *j = (BoxJob *)c;
  float blend = j->blend, limit = 0.5f * (1.f + blend);
  for (int i = i0; i < i1; i++) {
    const float *sn = j->N + i * 3, *co = j->co + i * 3;
    float x = fabsf(sn[0]), y = fabsf(sn[1]), z = fabsf(sn[2]);
    float sum = x + y + z;
    if (sum > 0.f) { x /= sum; y /= sum; z /= sum; }
    float w[3] = {0, 0, 0};
    if (x > limit * (x + y) && x > limit * (x + z)) w[0] = 1.f;
    else if (y > limit * (x + y) && y > limit * (y + z)) w[1] = 1.f;
    else if (z > limit * (x + z) && z > limit * (y + z)) w[2] = 1.f;
    else if (blend > 0.f) {
      if (z < (1.f - limit) * (y + x)) { w[0] = satf((x / (x + y) - 0.5f * (1.f - blend)) / blend); w[1] = 1.f - w[0]; }
      else if (x < (1.f - limit) * (y + z)) { w[1] = satf((y / (y + z) - 0.5f * (1.f - blend)) / blend); w[2] = 1.f - w[1]; }
      else if (y < (1.f - limit) * (x + z)) { w[0] = satf((x / (x + z) - 0.5f * (1.f - blend)) / blend); w[2] = 1.f - w[0]; }
      else {
        float den = 2.f * limit - 1.f;
        w[0] = ((2.f - limit) * x + (limit - 1.f)) / den;
        w[1] = ((2.f - limit) * y + (limit - 1.f)) / den;
        w[2] = ((2.f - limit) * z + (limit - 1.f)) / den;
      }
    } else w[0] = 1.f;
    float *o = j->im.out + (size_t)i * 4, t[4];
    o[0] = o[1] = o[2] = o[3] = 0.f;
    if (w[0] > 0.f) { sample_one(&j->im, sn[0] < 0.f ? 1.f - co[1] : co[1], co[2], t); for (int a = 0; a < 4; a++) o[a] += w[0] * t[a]; }
    if (w[1] > 0.f) { sample_one(&j->im, sn[1] > 0.f ? 1.f - co[0] : co[0], co[2], t); for (int a = 0; a < 4; a++) o[a] += w[1] * t[a]; }
    if (w[2] > 0.f) { sample_one(&j->im, sn[2] > 0.f ? 1.f - co[1] : co[1], co[0], t); for (int a = 0; a < 4; a++) o[a] += w[2] * t[a]; }
  }
}

EXPORT void mbake_image_box(const float *img, int iw, int ih, int ch, int interp, int ext, int n, const float *co,
                            const float *N, float blend, float *out, int threads) {
  if (iw <= 0 || ih <= 0 || n <= 0) return;
  BoxJob j;
  j.im.img = img; j.im.iw = iw; j.im.ih = ih; j.im.ch = ch; j.im.interp = interp; j.im.ext = ext; j.im.uv = NULL;
  j.im.out = out; j.co = co; j.N = N; j.blend = blend;
  parallel(box_work, &j, n, threads);
}
