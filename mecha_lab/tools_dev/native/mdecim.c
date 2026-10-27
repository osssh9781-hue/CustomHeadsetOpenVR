/* mdecim: quadric-error edge-collapse decimation on plain arrays, multi-threaded (loaded with ctypes, no Python API).
 *
 * int mdecim_run(const float *V, int nv, const int *F, int nf, int target_faces, const MdecimOpts *opt,
 *                const unsigned char *locked, const float *weight, const int *feat, int nfeat,
 *                float *outV, int *outF, int *outVsrc, int *outFsrc, int *out_nv, int *out_nf)
 *   V: nv*3 floats, F: nf*3 vertex indices (triangles).
 *   locked (may be NULL): 1 = this point never moves and is never removed.
 *   weight (may be NULL): >= 1, a point's collapse cost is multiplied by it (keeps more detail there).
 *   feat (may be NULL): nfeat triples (point, point, triangle): sides to keep like open borders (polygroup borders).
 *   outV must hold nv*3 floats, outF nf*3 ints, outVsrc nv ints (the input point each output point is),
 *   outFsrc nf ints (the input triangle each output triangle is). Returns 0 on success.
 *
 * Every collapse keeps one of its two points (moved to the best place), so points and triangles keep their identity:
 * attributes can be copied over from outVsrc / outFsrc.
 *
 * Big meshes are cut into one block per thread; each block is decimated with its cut points held still, then one
 * pass over the whole mesh finishes the job (and the cuts). Quadrics carry over, so the error is always measured
 * against the original surface.
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
#else
#include <pthread.h>
#define EXPORT __attribute__((visibility("default")))
#endif

typedef struct {
  float boundary_weight; /* how hard open borders hold their shape (planes along each border edge) */
  float min_quality;     /* 0..1: a collapse may not leave a triangle thinner than this (if it got thinner) */
  float quality_weight;  /* extra cost for thin triangles: rounder triangles, nicer topology */
  int lock_boundary;     /* 1: points on open borders never move */
  int threads;           /* <= 1: one thread */
} MdecimOpts;

typedef struct {
  int *f;
  int n, cap;
} List;

typedef struct {
  double cost;
  int a, b;
  uint32_t va, vb;
} Entry;

typedef struct {
  Entry *e;
  size_t n, cap;
} Heap;

typedef struct {
  int nv, nf, nf_alive;
  double *V;
  int *F;
  double *Q;
  List *vf;
  uint32_t *ver;
  uint8_t *alive, *border, *locked, *fdead;
  const float *weight;
  int *mark;
  int stamp;
  Heap h;
  MdecimOpts o;
  double scale2; /* mean squared edge length */
} Ctx;

/* ---------- small helpers ---------- */

static int list_push(List *l, int v) {
  if (l->n == l->cap) {
    int nc = l->cap ? l->cap * 2 : 8;
    int *nf = (int *)realloc(l->f, sizeof(int) * nc);
    if (!nf) return -1;
    l->f = nf;
    l->cap = nc;
  }
  l->f[l->n++] = v;
  return 0;
}

static void list_remove(List *l, int v) {
  for (int i = 0; i < l->n; i++)
    if (l->f[i] == v) {
      l->f[i] = l->f[--l->n];
      return;
    }
}

static int heap_push(Heap *h, Entry x) {
  if (h->n == h->cap) {
    size_t nc = h->cap ? h->cap * 2 : 1024;
    Entry *ne = (Entry *)realloc(h->e, sizeof(Entry) * nc);
    if (!ne) return -1;
    h->e = ne;
    h->cap = nc;
  }
  size_t i = h->n++;
  while (i > 0) {
    size_t p = (i - 1) / 2;
    if (h->e[p].cost <= x.cost) break;
    h->e[i] = h->e[p];
    i = p;
  }
  h->e[i] = x;
  return 0;
}

static Entry heap_pop(Heap *h) {
  Entry top = h->e[0];
  Entry x = h->e[--h->n];
  size_t i = 0, n = h->n;
  for (;;) {
    size_t c = 2 * i + 1;
    if (c >= n) break;
    if (c + 1 < n && h->e[c + 1].cost < h->e[c].cost) c++;
    if (x.cost <= h->e[c].cost) break;
    h->e[i] = h->e[c];
    i = c;
  }
  if (n) h->e[i] = x;
  return top;
}

static void sub3(const double *a, const double *b, double *r) {
  r[0] = a[0] - b[0];
  r[1] = a[1] - b[1];
  r[2] = a[2] - b[2];
}
static void cross3(const double *a, const double *b, double *r) {
  r[0] = a[1] * b[2] - a[2] * b[1];
  r[1] = a[2] * b[0] - a[0] * b[2];
  r[2] = a[0] * b[1] - a[1] * b[0];
}
static double dot3(const double *a, const double *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

static void quad_add_plane(double *q, const double *n, double d, double w) {
  q[0] += w * n[0] * n[0]; q[1] += w * n[0] * n[1]; q[2] += w * n[0] * n[2]; q[3] += w * n[0] * d;
  q[4] += w * n[1] * n[1]; q[5] += w * n[1] * n[2]; q[6] += w * n[1] * d;
  q[7] += w * n[2] * n[2]; q[8] += w * n[2] * d;
  q[9] += w * d * d;
}

static double quad_eval(const double *q, const double *p) {
  double x = p[0], y = p[1], z = p[2];
  return q[0] * x * x + 2 * q[1] * x * y + 2 * q[2] * x * z + 2 * q[3] * x + q[4] * y * y + 2 * q[5] * y * z +
         2 * q[6] * y + q[7] * z * z + 2 * q[8] * z + q[9];
}

/* triangle shape: 1 = equilateral, 0 = flat */
static double tri_quality(const double *p0, const double *p1, const double *p2) {
  double e0[3], e1[3], e2[3], n[3];
  sub3(p1, p0, e0);
  sub3(p2, p1, e1);
  sub3(p0, p2, e2);
  cross3(e0, e1, n);
  double l = dot3(e0, e0) + dot3(e1, e1) + dot3(e2, e2);
  if (l <= 0) return 0;
  return 2.0 * sqrt(3.0) * sqrt(dot3(n, n)) / l;
}

/* LSD radix sort of n keys below 2^bits (tmp: n more) */
static void radix_sort(uint64_t *k, uint64_t *tmp, size_t n, int bits) {
  enum { D = 11, R = 1 << D };
  size_t *cnt = (size_t *)malloc(sizeof(size_t) * R);
  if (!cnt) return;
  for (int shift = 0; shift < bits; shift += D) {
    memset(cnt, 0, sizeof(size_t) * R);
    for (size_t i = 0; i < n; i++) cnt[(k[i] >> shift) & (R - 1)]++;
    size_t s = 0;
    for (int r = 0; r < R; r++) {
      size_t c = cnt[r];
      cnt[r] = s;
      s += c;
    }
    for (size_t i = 0; i < n; i++) tmp[cnt[(k[i] >> shift) & (R - 1)]++] = k[i];
    uint64_t *t = k; k = tmp; tmp = t;
    if (shift + D >= bits && ((shift / D) % 2 == 0)) memcpy(tmp, k, sizeof(uint64_t) * n); /* result back in place */
  }
  free(cnt);
}

static int bits_for(uint64_t x) {
  int b = 1;
  while (b < 64 && (x >> b)) b++;
  return b;
}

/* sorted keys lo*nv+hi of every triangle side (3*nf, dead triangles get UINT64_MAX at the end) */
static uint64_t *side_keys(const int *F, int nf, int nv, const uint8_t *fdead) {
  size_t n = 3 * (size_t)nf;
  uint64_t *k = (uint64_t *)malloc(sizeof(uint64_t) * n), *tmp = (uint64_t *)malloc(sizeof(uint64_t) * n);
  if (!k || !tmp) {
    free(k); free(tmp);
    return NULL;
  }
  size_t m = 0;
  for (int f = 0; f < nf; f++) {
    if (fdead && fdead[f]) continue;
    const int *t = &F[3 * f];
    for (int j = 0; j < 3; j++) {
      uint64_t x = (uint64_t)t[j], y = (uint64_t)t[(j + 1) % 3];
      if (x > y) { uint64_t s = x; x = y; y = s; }
      k[m++] = x * (uint64_t)nv + y;
    }
  }
  radix_sort(k, tmp, m, bits_for((uint64_t)nv * (uint64_t)nv));
  for (size_t i = m; i < n; i++) k[i] = UINT64_MAX;
  free(tmp);
  return k;
}

/* plane quadrics of the triangles (area weighted) and of the open borders; border flags */
static void border_plane(const double *V, const int *t, int x, int y, double w, double *Q) {
  double e0[3], e1[3], fn[3], d[3], bn[3];
  sub3(&V[3 * t[1]], &V[3 * t[0]], e0);
  sub3(&V[3 * t[2]], &V[3 * t[0]], e1);
  cross3(e0, e1, fn);
  sub3(&V[3 * y], &V[3 * x], d);
  cross3(d, fn, bn);
  double bl = sqrt(dot3(bn, bn));
  if (bl <= 0) return;
  bn[0] /= bl; bn[1] /= bl; bn[2] /= bl;
  double dd = -dot3(bn, &V[3 * x]);
  w *= dot3(d, d);
  quad_add_plane(&Q[10 * x], bn, dd, w);
  quad_add_plane(&Q[10 * y], bn, dd, w);
}

static int make_quadrics(const double *V, int nv, const int *F, int nf, const uint8_t *fdead, float boundary_weight,
                         const int *feat, int nfeat, double *Q, uint8_t *border) {
  uint64_t *keys = side_keys(F, nf, nv, fdead);
  if (!keys) return -1;
  memset(Q, 0, sizeof(double) * 10 * (size_t)nv);
  memset(border, 0, nv);
  for (int f = 0; f < nf; f++) {
    if (fdead && fdead[f]) continue;
    const int *t = &F[3 * f];
    double e0[3], e1[3], n[3];
    sub3(&V[3 * t[1]], &V[3 * t[0]], e0);
    sub3(&V[3 * t[2]], &V[3 * t[0]], e1);
    cross3(e0, e1, n);
    double l = sqrt(dot3(n, n));
    if (l > 0) {
      n[0] /= l; n[1] /= l; n[2] /= l;
      double d = -dot3(n, &V[3 * t[0]]);
      for (int k = 0; k < 3; k++) quad_add_plane(&Q[10 * t[k]], n, d, 0.5 * l);
    }
  }
  /* border sides: count 1. Their plane goes along the side, upright on its triangle */
  size_t ne = 3 * (size_t)nf;
  int has_border = 0;
  for (size_t i = 0; i < ne && keys[i] != UINT64_MAX;) {
    size_t j = i;
    while (j < ne && keys[j] == keys[i]) j++;
    if (j - i == 1) {
      int x = (int)(keys[i] / (uint64_t)nv), y = (int)(keys[i] % (uint64_t)nv);
      border[x] = border[y] = 1;
      has_border = 1;
    }
    i = j;
  }
  if (has_border && boundary_weight > 0) {
    for (int f = 0; f < nf; f++) {
      if (fdead && fdead[f]) continue;
      const int *t = &F[3 * f];
      for (int j = 0; j < 3; j++) {
        int x = t[j], y = t[(j + 1) % 3];
        if (!border[x] || !border[y]) continue;
        uint64_t lo = x < y ? x : y, hi = x < y ? y : x, key = lo * (uint64_t)nv + hi;
        /* binary search: is it a border side (count 1)? */
        size_t a = 0, b = ne;
        while (a < b) {
          size_t m = (a + b) / 2;
          if (keys[m] < key) a = m + 1; else b = m;
        }
        if (a + 1 < ne && keys[a + 1] == key) continue;
        if (a > 0 && keys[a - 1] == key) continue;
        border_plane(V, t, x, y, boundary_weight, Q);
      }
    }
  }
  /* sides kept like borders (polygroup borders) */
  for (int i = 0; i < nfeat; i++) {
    int x = feat[3 * i], y = feat[3 * i + 1], f = feat[3 * i + 2];
    if (x < 0 || x >= nv || y < 0 || y >= nv || f < 0 || f >= nf || x == y) continue;
    border[x] = border[y] = 1;
    border_plane(V, &F[3 * f], x, y, boundary_weight > 0 ? boundary_weight : 1000.0f, Q);
  }
  free(keys);
  return 0;
}

/* ---------- edge cost ---------- */

/* faces of a and b after moving to p: none may flip or (with min_quality) get too thin. worst shape, or -1 */
static double check_ring(Ctx *c, int a, int b, const double *p) {
  double worst = 1.0;
  for (int pass = 0; pass < 2; pass++) {
    int u = pass ? b : a;
    List *l = &c->vf[u];
    for (int i = 0; i < l->n; i++) {
      int f = l->f[i];
      int *t = &c->F[3 * f];
      int ha = (t[0] == a) + (t[1] == a) + (t[2] == a);
      int hb = (t[0] == b) + (t[1] == b) + (t[2] == b);
      if (ha && hb) continue; /* this face goes away */
      const double *q[3], *o[3];
      for (int k = 0; k < 3; k++) {
        o[k] = &c->V[3 * t[k]];
        q[k] = (t[k] == u) ? p : o[k];
      }
      double e0[3], e1[3], n0[3], n1[3];
      sub3(o[1], o[0], e0);
      sub3(o[2], o[0], e1);
      cross3(e0, e1, n0);
      sub3(q[1], q[0], e0);
      sub3(q[2], q[0], e1);
      cross3(e0, e1, n1);
      double l0 = sqrt(dot3(n0, n0)), l1 = sqrt(dot3(n1, n1));
      if (l1 <= 1e-30 * c->scale2) return -1.0;
      if (dot3(n0, n1) < 0.3 * l0 * l1) return -1.0;
      double qn = tri_quality(q[0], q[1], q[2]);
      if (qn < c->o.min_quality) {
        double qo = tri_quality(o[0], o[1], o[2]);
        if (qn < qo) return -1.0;
      }
      if (qn < worst) worst = qn;
    }
  }
  return worst;
}

static int solve3(const double *q, double *x) {
  double a00 = q[0], a01 = q[1], a02 = q[2], a11 = q[4], a12 = q[5], a22 = q[7];
  double c00 = a11 * a22 - a12 * a12, c01 = a02 * a12 - a01 * a22, c02 = a01 * a12 - a02 * a11;
  double det = a00 * c00 + a01 * c01 + a02 * c02;
  double s = (fabs(a00) + fabs(a11) + fabs(a22) + 2 * (fabs(a01) + fabs(a02) + fabs(a12))) / 3.0;
  if (s == 0 || fabs(det) <= 1e-9 * s * s * s) return 0;
  double c11 = a00 * a22 - a02 * a02, c12 = a01 * a02 - a00 * a12, c22 = a00 * a11 - a01 * a01;
  double b0 = -q[3], b1 = -q[6], b2 = -q[8];
  x[0] = (c00 * b0 + c01 * b1 + c02 * b2) / det;
  x[1] = (c01 * b0 + c11 * b1 + c12 * b2) / det;
  x[2] = (c02 * b0 + c12 * b1 + c22 * b2) / det;
  return 1;
}

/* the best point for collapsing (a, b), its cost (HUGE_VAL: may not collapse) and *keep_b = b should survive */
static double edge_cost(Ctx *c, int a, int b, double *p, int *keep_b) {
  double q[10];
  for (int k = 0; k < 10; k++) q[k] = c->Q[10 * a + k] + c->Q[10 * b + k];
  const double *pa = &c->V[3 * a], *pb = &c->V[3 * b];
  int fa = c->locked[a] || (c->o.lock_boundary && c->border[a]);
  int fb = c->locked[b] || (c->o.lock_boundary && c->border[b]);
  double best = HUGE_VAL, x[3];
  *keep_b = 0;
  if ((fa && fb) || c->locked[a] == 2 || c->locked[b] == 2) return HUGE_VAL; /* 2: nothing touching it goes */
  if (fa || fb) {
    memcpy(p, fa ? pa : pb, sizeof(double) * 3);
    *keep_b = fb;
    best = quad_eval(q, p);
  } else {
    double mid[3] = {0.5 * (pa[0] + pb[0]), 0.5 * (pa[1] + pb[1]), 0.5 * (pa[2] + pb[2])};
    const double *cand[3] = {pa, pb, mid};
    for (int k = 0; k < 3; k++) {
      double e = quad_eval(q, cand[k]);
      if (e < best) {
        best = e;
        memcpy(p, cand[k], sizeof(double) * 3);
        *keep_b = k == 1;
      }
    }
    if (solve3(q, x)) {
      double d[3], el[3];
      sub3(x, mid, d);
      sub3(pa, pb, el);
      if (dot3(d, d) < 4.0 * dot3(el, el)) {
        double e = quad_eval(q, x);
        if (e < best) {
          best = e;
          memcpy(p, x, sizeof(double) * 3);
          *keep_b = 0;
        }
      }
    }
  }
  if (best < 0) best = 0;
  if (c->weight) {
    float w = c->weight[a] > c->weight[b] ? c->weight[a] : c->weight[b];
    best *= w;
  }
  return best;
}

static int push_edge(Ctx *c, int a, int b) {
  double p[3];
  int kb;
  double cost = edge_cost(c, a, b, p, &kb);
  if (cost == HUGE_VAL) return 0;
  if (c->o.quality_weight > 0) {
    double w = check_ring(c, a, b, p);
    if (w < 0) return 0;
    /* thin triangles cost more (in the same units as the quadric error: length^4) */
    double el[3];
    sub3(&c->V[3 * a], &c->V[3 * b], el);
    double l2 = dot3(el, el);
    cost += c->o.quality_weight * (1.0 - w) * l2 * l2 * 1e-2;
  }
  Entry e = {cost, a, b, c->ver[a], c->ver[b]};
  return heap_push(&c->h, e);
}

/* ---------- topology ---------- */

static int next_stamp(Ctx *c) {
  if (++c->stamp >= 0x7ffffff0) {
    memset(c->mark, 0, sizeof(int) * c->nv);
    c->stamp = 1;
  }
  return c->stamp;
}

/* edge (a, b) on 1 or 2 faces, and a, b share exactly that many neighbours (the surface stays manifold) */
static int link_ok(Ctx *c, int a, int b) {
  int nfab = 0;
  int s1 = next_stamp(c);
  List *la = &c->vf[a];
  for (int i = 0; i < la->n; i++) {
    int *t = &c->F[3 * la->f[i]];
    int hb = 0;
    for (int k = 0; k < 3; k++) {
      if (t[k] == b) hb = 1;
      if (t[k] != a) c->mark[t[k]] = s1;
    }
    nfab += hb;
  }
  if (nfab == 0 || nfab > 2) return 0;
  int common = 0;
  int s2 = next_stamp(c);
  if (s2 != s1 + 1) return 0; /* (stamps wrapped: try again later) */
  List *lb = &c->vf[b];
  for (int i = 0; i < lb->n; i++) {
    int *t = &c->F[3 * lb->f[i]];
    for (int k = 0; k < 3; k++) {
      int v = t[k];
      if (v == a || v == b) continue;
      if (c->mark[v] == s1) {
        common++;
        c->mark[v] = s2;
      }
    }
  }
  if (common != nfab) return 0;
  if (nfab == 2 && c->border[a] && c->border[b]) return 0; /* would pinch the surface */
  return 1;
}

/* b goes into a, a moves to p */
static int collapse(Ctx *c, int a, int b, const double *p) {
  List *lb = &c->vf[b];
  for (int i = 0; i < lb->n; i++) {
    int f = lb->f[i];
    int *t = &c->F[3 * f];
    if (t[0] == a || t[1] == a || t[2] == a) {
      c->fdead[f] = 1;
      c->nf_alive--;
      for (int k = 0; k < 3; k++)
        if (t[k] != a && t[k] != b) list_remove(&c->vf[t[k]], f);
      list_remove(&c->vf[a], f);
    } else {
      for (int k = 0; k < 3; k++)
        if (t[k] == b) t[k] = a;
      if (list_push(&c->vf[a], f)) return -1;
    }
  }
  lb->n = 0;
  memcpy(&c->V[3 * a], p, sizeof(double) * 3);
  for (int k = 0; k < 10; k++) c->Q[10 * a + k] += c->Q[10 * b + k];
  c->alive[b] = 0;
  c->border[a] |= c->border[b];
  c->ver[a]++;
  c->ver[b]++;
  return 0;
}

static void ctx_free(Ctx *c) {
  if (c->vf)
    for (int i = 0; i < c->nv; i++) free(c->vf[i].f);
  free(c->V); free(c->F); free(c->Q); free(c->vf); free(c->ver); free(c->alive); free(c->border); free(c->locked);
  free(c->fdead); free(c->mark); free(c->h.e);
  memset(c, 0, sizeof(*c));
}

/* a context over (V, F) with the given quadrics / border flags (copied), ready to decimate */
static int ctx_init(Ctx *c, int nv, const double *V, int nf, const int *F, const double *Q, const uint8_t *border,
                    const uint8_t *locked, const float *weight, const MdecimOpts *o) {
  memset(c, 0, sizeof(*c));
  c->o = *o;
  c->nv = nv;
  c->nf = nf;
  c->nf_alive = nf;
  c->weight = weight;
  c->V = (double *)malloc(sizeof(double) * 3 * (size_t)nv);
  c->F = (int *)malloc(sizeof(int) * 3 * (size_t)nf);
  c->Q = (double *)malloc(sizeof(double) * 10 * (size_t)nv);
  c->vf = (List *)calloc(nv, sizeof(List));
  c->ver = (uint32_t *)calloc(nv, sizeof(uint32_t));
  c->alive = (uint8_t *)malloc(nv);
  c->border = (uint8_t *)malloc(nv);
  c->locked = (uint8_t *)calloc(nv, 1);
  c->fdead = (uint8_t *)calloc(nf ? nf : 1, 1);
  c->mark = (int *)calloc(nv, sizeof(int));
  if (!c->V || !c->F || !c->Q || !c->vf || !c->ver || !c->alive || !c->border || !c->locked || !c->fdead || !c->mark)
    return -1;
  memcpy(c->V, V, sizeof(double) * 3 * (size_t)nv);
  memcpy(c->F, F, sizeof(int) * 3 * (size_t)nf);
  memset(c->alive, 1, nv);
  if (locked) memcpy(c->locked, locked, nv);
  double sum_l2 = 0;
  for (int f = 0; f < nf; f++) {
    int *t = &c->F[3 * f];
    if (t[0] == t[1] || t[1] == t[2] || t[2] == t[0]) {
      c->fdead[f] = 1;
      c->nf_alive--;
      continue;
    }
    double e[3];
    sub3(&c->V[3 * t[1]], &c->V[3 * t[0]], e);
    sum_l2 += dot3(e, e);
    for (int k = 0; k < 3; k++)
      if (list_push(&c->vf[t[k]], f)) return -1;
  }
  c->scale2 = nf ? sum_l2 / nf : 1.0;
  if (Q) {
    memcpy(c->Q, Q, sizeof(double) * 10 * (size_t)nv);
    memcpy(c->border, border, nv);
  } else if (make_quadrics(c->V, nv, c->F, nf, c->fdead, o->boundary_weight, NULL, 0, c->Q, c->border)) {
    return -1;
  }
  /* every edge once in the heap */
  uint64_t *keys = side_keys(c->F, nf, nv, c->fdead);
  if (!keys) return -1;
  size_t ne = 3 * (size_t)nf;
  int rc = 0;
  for (size_t i = 0; i < ne && keys[i] != UINT64_MAX;) {
    size_t j = i;
    while (j < ne && keys[j] == keys[i]) j++;
    if (push_edge(c, (int)(keys[i] / (uint64_t)nv), (int)(keys[i] % (uint64_t)nv))) {
      rc = -1;
      break;
    }
    i = j;
  }
  free(keys);
  return rc;
}

/* cheapest collapse first, until target_faces are left (or nothing can go) */
static int ctx_decimate(Ctx *c, int target_faces) {
  while (c->nf_alive > target_faces && c->h.n) {
    Entry e = heap_pop(&c->h);
    int a = e.a, b = e.b;
    if (!c->alive[a] || !c->alive[b] || c->ver[a] != e.va || c->ver[b] != e.vb) continue; /* out of date */
    if (!link_ok(c, a, b)) continue;
    double p[3];
    int kb;
    if (edge_cost(c, a, b, p, &kb) == HUGE_VAL) continue;
    if (check_ring(c, a, b, p) < 0) continue;
    if (kb) { int t = a; a = b; b = t; }
    if (collapse(c, a, b, p)) return -1;
    /* new costs for the edges around the merged point */
    int s = next_stamp(c);
    List *la = &c->vf[a];
    for (int i = 0; i < la->n; i++) {
      int *t = &c->F[3 * la->f[i]];
      for (int k = 0; k < 3; k++) {
        int v = t[k];
        if (v == a || c->mark[v] == s) continue;
        c->mark[v] = s;
        if (push_edge(c, a, v)) return -1;
      }
    }
  }
  return 0;
}

/* ---------- blocks (one per thread) ---------- */

typedef struct {
  int nf, nv;    /* block size */
  int *faces;    /* global face ids */
  int *verts;    /* local -> global point */
  int *F;        /* local triangles */
  int target;
  const double *gV, *gQ;
  const uint8_t *gborder, *glocked, *gseam;
  const float *gweight;
  MdecimOpts o;
  Ctx c;
  float *weight;
  int rc;
} Block;

static void block_work(Block *k) {
  int nv = k->nv;
  double *V = (double *)malloc(sizeof(double) * 3 * (size_t)nv);
  double *Q = (double *)malloc(sizeof(double) * 10 * (size_t)nv);
  uint8_t *bd = (uint8_t *)malloc(nv), *lk = (uint8_t *)malloc(nv);
  k->rc = -1;
  if (k->gweight) k->weight = (float *)malloc(sizeof(float) * nv);
  if (V && Q && bd && lk && (!k->gweight || k->weight)) {
    for (int i = 0; i < nv; i++) {
      int g = k->verts[i];
      memcpy(&V[3 * i], &k->gV[3 * g], sizeof(double) * 3);
      memcpy(&Q[10 * i], &k->gQ[10 * g], sizeof(double) * 10);
      bd[i] = k->gborder[g];
      /* a block cannot see all of a seam point's neighbours, so nothing touching it collapses there */
      lk[i] = k->gseam[g] ? 2 : (k->glocked && k->glocked[g]);
      if (k->weight) k->weight[i] = k->gweight[g];
    }
    if (!ctx_init(&k->c, nv, V, k->nf, k->F, Q, bd, lk, k->weight, &k->o)) k->rc = ctx_decimate(&k->c, k->target);
  }
  free(V); free(Q); free(bd); free(lk);
  free(k->c.h.e); /* the heap is done with */
  k->c.h.e = NULL;
}

#ifdef _WIN32
static DWORD WINAPI block_thread(LPVOID p) {
  block_work((Block *)p);
  return 0;
}
#else
static void *block_thread(void *p) {
  block_work((Block *)p);
  return NULL;
}
#endif

/* split faces[0..n) into `parts` blocks of about equal size along the longest side (centroids cen) */
static void split_blocks(int *faces, int n, int parts, const float *cen, int *block_of, int first) {
  if (parts <= 1 || n < 2) {
    for (int i = 0; i < n; i++) block_of[faces[i]] = first;
    return;
  }
  float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
  for (int i = 0; i < n; i++)
    for (int k = 0; k < 3; k++) {
      float v = cen[3 * faces[i] + k];
      if (v < lo[k]) lo[k] = v;
      if (v > hi[k]) hi[k] = v;
    }
  int ax = 0;
  for (int k = 1; k < 3; k++)
    if (hi[k] - lo[k] > hi[ax] - lo[ax]) ax = k;
  enum { NB = 4096 };
  int *hist = (int *)calloc(NB, sizeof(int));
  int left_parts = parts / 2;
  float cut = 0.5f * (lo[ax] + hi[ax]);
  float span = hi[ax] - lo[ax];
  if (hist && span > 0) {
    for (int i = 0; i < n; i++) {
      int b = (int)((cen[3 * faces[i] + ax] - lo[ax]) / span * (NB - 1));
      hist[b < 0 ? 0 : (b >= NB ? NB - 1 : b)]++;
    }
    long want = (long)n * left_parts / parts, acc = 0;
    for (int b = 0; b < NB; b++) {
      acc += hist[b];
      if (acc >= want) {
        cut = lo[ax] + (b + 1) * span / (NB - 1);
        break;
      }
    }
  }
  free(hist);
  int i = 0, j = n - 1;
  while (i <= j) {
    if (cen[3 * faces[i] + ax] < cut) i++;
    else {
      int t = faces[i]; faces[i] = faces[j]; faces[j] = t;
      j--;
    }
  }
  if (i == 0 || i == n) i = n / 2; /* all on one side: split by order */
  split_blocks(faces, i, left_parts, cen, block_of, first);
  split_blocks(faces + i, n - i, parts - left_parts, cen, block_of, first + left_parts);
}

/* ---------- entry point ---------- */

#define BLOCK_FLOOR 0.05

EXPORT int mdecim_version(void) { return 3; }

EXPORT int mdecim_run(const float *Vin, int nv, const int *Fin, int nf, int target_faces, const MdecimOpts *opt,
                      const unsigned char *locked, const float *weight, const int *feat, int nfeat, float *outV,
                      int *outF, int *outVsrc, int *outFsrc, int *out_nv, int *out_nf) {
  int rc = 1;
  for (int i = 0; i < 3 * nf; i++)
    if (Fin[i] < 0 || Fin[i] >= nv) return 2;
  double *V = (double *)malloc(sizeof(double) * 3 * (size_t)nv);
  double *Q = (double *)malloc(sizeof(double) * 10 * (size_t)nv);
  uint8_t *border = (uint8_t *)malloc(nv ? nv : 1);
  int *F = (int *)malloc(sizeof(int) * 3 * (size_t)(nf ? nf : 1));
  int *fsrc = (int *)malloc(sizeof(int) * (size_t)(nf ? nf : 1));
  Block *blocks = NULL;
  int nblocks = 0;
  uint8_t *seam = NULL;
  int *block_of = NULL, *order = NULL, *gmap = NULL;
  float *cen = NULL;
  Ctx c;
  memset(&c, 0, sizeof(c));
  if (!V || !Q || !border || !F || !fsrc) goto done;
  for (int i = 0; i < 3 * nv; i++) V[i] = Vin[i];
  memcpy(F, Fin, sizeof(int) * 3 * (size_t)nf);
  for (int f = 0; f < nf; f++) fsrc[f] = f;
  if (make_quadrics(V, nv, F, nf, NULL, opt->boundary_weight, feat, nfeat, Q, border)) goto done;

  int threads = opt->threads;
  if (threads > 64) threads = 64;
  if (threads > nf / 25000) threads = nf / 25000; /* small meshes: one thread is quicker */
  int cur_nf = nf;
  if (threads >= 2 && target_faces < nf) {
    /* blocks go part of the way (the rest is done over the whole mesh, so detail still goes where it is needed) */
    double t = (double)target_faces / nf;
    double r1 = 3.0 * t;
    if (r1 > t + (1.0 - t) * 0.25) r1 = t + (1.0 - t) * 0.25;
    /* never below 5 % in the blocks: a block taken almost to nothing round its frozen seam left long slivers fanning
       from the seam, and the whole-mesh pass after them lost a third of the volume (679k quads -> 281 points) */
    if (r1 < BLOCK_FLOOR) r1 = BLOCK_FLOOR;
    nblocks = threads;
    blocks = (Block *)calloc(nblocks, sizeof(Block));
    seam = (uint8_t *)calloc(nv, 1);
    block_of = (int *)malloc(sizeof(int) * nf);
    order = (int *)malloc(sizeof(int) * nf);
    gmap = (int *)malloc(sizeof(int) * nv);
    cen = (float *)malloc(sizeof(float) * 3 * (size_t)nf);
    if (!blocks || !seam || !block_of || !order || !gmap || !cen) goto done;
    for (int f = 0; f < nf; f++) {
      order[f] = f;
      for (int k = 0; k < 3; k++)
        cen[3 * f + k] = (float)((V[3 * F[3 * f] + k] + V[3 * F[3 * f + 1] + k] + V[3 * F[3 * f + 2] + k]) / 3.0);
    }
    split_blocks(order, nf, nblocks, cen, block_of, 0);
    free(cen);
    cen = NULL;
    /* seam points: used by more than one block */
    for (int i = 0; i < nv; i++) gmap[i] = -1;
    for (int f = 0; f < nf; f++)
      for (int k = 0; k < 3; k++) {
        int v = F[3 * f + k];
        if (gmap[v] < 0) gmap[v] = block_of[f];
        else if (gmap[v] != block_of[f]) seam[v] = 1;
      }
    for (int f = 0; f < nf; f++) blocks[block_of[f]].nf++;
    for (int b = 0; b < nblocks; b++) {
      blocks[b].faces = (int *)malloc(sizeof(int) * (blocks[b].nf ? blocks[b].nf : 1));
      blocks[b].F = (int *)malloc(sizeof(int) * 3 * (blocks[b].nf ? blocks[b].nf : 1));
      blocks[b].verts = (int *)malloc(sizeof(int) * 3 * (blocks[b].nf ? blocks[b].nf : 1));
      if (!blocks[b].faces || !blocks[b].F || !blocks[b].verts) goto done;
      blocks[b].nf = 0;
    }
    for (int f = 0; f < nf; f++) {
      Block *k = &blocks[block_of[f]];
      k->faces[k->nf++] = f;
    }
    /* local numbering, one block after the other (gmap: global -> local of the current block) */
    for (int i = 0; i < nv; i++) gmap[i] = -1;
    for (int b = 0; b < nblocks; b++) {
      Block *k = &blocks[b];
      for (int i = 0; i < k->nf; i++)
        for (int j = 0; j < 3; j++) {
          int g = F[3 * k->faces[i] + j];
          if (gmap[g] < 0) {
            gmap[g] = k->nv;
            k->verts[k->nv++] = g;
          }
          k->F[3 * i + j] = gmap[g];
        }
      for (int i = 0; i < k->nv; i++) gmap[k->verts[i]] = -1;
      k->target = (int)(k->nf * r1);
      k->gV = V; k->gQ = Q; k->gborder = border; k->glocked = locked; k->gseam = seam; k->gweight = weight;
      k->o = *opt;
    }
#ifdef _WIN32
    HANDLE th[64];
    for (int b = 0; b < nblocks; b++) th[b] = CreateThread(NULL, 0, block_thread, &blocks[b], 0, NULL);
    for (int b = 0; b < nblocks; b++)
      if (th[b]) {
        WaitForSingleObject(th[b], INFINITE);
        CloseHandle(th[b]);
      } else {
        block_work(&blocks[b]);
      }
#else
    pthread_t th[64];
    int started[64];
    for (int b = 0; b < nblocks; b++) started[b] = pthread_create(&th[b], NULL, block_thread, &blocks[b]) == 0;
    for (int b = 0; b < nblocks; b++)
      if (started[b]) pthread_join(th[b], NULL);
      else block_work(&blocks[b]);
#endif
    /* back into the whole mesh: moved points and their quadrics (seam points never moved, nor lost a neighbour) */
    cur_nf = 0;
    for (int b = 0; b < nblocks; b++) {
      Block *k = &blocks[b];
      if (k->rc) goto done;
      for (int i = 0; i < k->nv; i++) {
        int g = k->verts[i];
        if (seam[g] || !k->c.alive[i]) continue;
        memcpy(&V[3 * g], &k->c.V[3 * i], sizeof(double) * 3);
        memcpy(&Q[10 * g], &k->c.Q[10 * i], sizeof(double) * 10);
        border[g] = k->c.border[i];
      }
    }
    for (int b = 0; b < nblocks; b++) {
      Block *k = &blocks[b];
      for (int i = 0; i < k->nf; i++) {
        if (k->c.fdead[i]) continue;
        for (int j = 0; j < 3; j++) F[3 * cur_nf + j] = k->verts[k->c.F[3 * i + j]];
        fsrc[cur_nf] = k->faces[i];
        cur_nf++;
      }
    }
  }
  /* the whole mesh (after the blocks: the rest and the seams) */
  if (ctx_init(&c, nv, V, cur_nf, F, Q, border, locked, weight, opt)) goto done;
  if (ctx_decimate(&c, target_faces)) goto done;
  {
    int *remap = c.mark;
    for (int i = 0; i < nv; i++) remap[i] = -1;
    int n_v = 0, n_f = 0;
    for (int f = 0; f < cur_nf; f++) {
      if (c.fdead[f]) continue;
      int *t = &c.F[3 * f];
      for (int k = 0; k < 3; k++) {
        int v = t[k];
        if (remap[v] < 0) {
          remap[v] = n_v;
          outV[3 * n_v] = (float)c.V[3 * v];
          outV[3 * n_v + 1] = (float)c.V[3 * v + 1];
          outV[3 * n_v + 2] = (float)c.V[3 * v + 2];
          if (outVsrc) outVsrc[n_v] = v;
          n_v++;
        }
        outF[3 * n_f + k] = remap[v];
      }
      if (outFsrc) outFsrc[n_f] = fsrc[f];
      n_f++;
    }
    *out_nv = n_v;
    *out_nf = n_f;
  }
  rc = 0;
done:
  ctx_free(&c);
  if (blocks)
    for (int b = 0; b < nblocks; b++) {
      free(blocks[b].faces); free(blocks[b].F); free(blocks[b].verts); free(blocks[b].weight);
      ctx_free(&blocks[b].c);
    }
  free(blocks); free(seam); free(block_of); free(order); free(gmap); free(cen);
  free(V); free(Q); free(border); free(F); free(fsrc);
  return rc;
}
