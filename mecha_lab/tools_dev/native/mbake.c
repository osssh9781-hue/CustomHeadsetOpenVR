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

typedef struct {
  const BVH *bvh;
  const float *lP, *lN, *lT, *lS, *lC, *hN, *hA;
  const int *ptri; const float *pbar; const int *plist;
  int n0, n1, green_neg; float maxdist;
  float *out, *outh, *outa;
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
    } else {
      const float *hn = j->hN + h * 9;
      float w0 = 1.f - u - v;
      for (int a = 0; a < 3; a++) n[a] = w0 * hn[a] + u * hn[3 + a] + v * hn[6 + a];
      norm3(n);
      if (j->outh) {                   /* height: the hit over the low's point, along the low's normal */
        float q[3] = {o[0] + d[0] * tt - P[0], o[1] + d[1] * tt - P[1], o[2] + d[2] * tt - P[2]};
        j->outh[px] = q[0] * N[0] + q[1] * N[1] + q[2] * N[2];
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

EXPORT int mbake_version(void) { return 2; }

/* v2: the Normal map and, in the same rays, the Height (hit distance along the low's normal, world units; NULL: not
 * wanted) and a value of the high's points (hA, e.g. its curvature, between the hit triangle's corners; NULL: not
 * wanted).  out may be NULL too (only Height / the value). */
EXPORT int mbake_maps(int nlt, const float *luv, const float *lP, const float *lN, const float *lT, const float *lS,
                      const float *lC, int nhv, const float *hV, int nht, const int *hT, const float *hN,
                      const float *hA, int w, int h, float maxdist, int green_neg, int margin, int threads,
                      float *out, float *outh, float *outa, unsigned char *mask)
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
  if (outa && !hA) { rc = 1; goto done; }
  {
    int nt = threads < 1 ? 1 : (threads > 64 ? 64 : threads);
    if (n < 4096) nt = 1;
    Job jobs[64];
    for (int k = 0; k < nt; k++) {
      Job jb = {&b, lP, lN, lT, lS, lC, hN, hA, ptri, pbar, plist, (int)((long long)n * k / nt),
                (int)((long long)n * (k + 1) / nt), green_neg, maxdist, out, outh, outa};
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
                    threads, out, NULL, NULL, mask);
}
