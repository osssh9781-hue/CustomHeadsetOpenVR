/* mquad: field-aligned quad remeshing on plain arrays (Instant Meshes: Jakob, Tarini, Panozzo, Sorkine-Hornung 2015),
 * multi-threaded, loaded with ctypes (no Python API).  Built into the same library as mdecim.
 *
 * int mquad_run(int nlevels, const int *nv, const int *nf, const float *V, const int *F, const int *src,
 *               const MquadOpts *opt, MquadOut *out)
 *   The surface sampled at nlevels resolutions, fine (0) to coarse: level k has nv[k] points (V: 3 floats each, the
 *   levels one after another) and nf[k] triangles (F: 3 indices into that level, one level after another).
 *   src (from level 1 on, one level after another): the point of level k - 1 each point of level k came from
 *   (Mecha Lab's decimation keeps one of the two points of every collapse).
 *   out: points (3 floats), faces (4 point indices, the 4th -1 for a triangle), for each face the fine triangle under
 *   its centre and for each point the fine point nearest it (attributes can be copied over).  Free with mquad_free.
 *   Returns 0 on success.
 *
 * 1. orientation field (4-RoSy) then position field (4-PoSy), coarse to fine, Gauss-Seidel by colour with the
 *    paper's extrinsic formulas; hard edges (and open borders) hold the direction, their lattice line and corners
 *    their point
 * 2. extraction: mesh edges whose ends sit on the same lattice point collapse (lowest error first, never across a
 *    unit edge), unit lattice steps become edges, points on an edge between two neighbours drop that edge, faces are
 *    walked round each point (quads first), holes up to 16 sides are filled, triangle pairs that make a good quad join
 * 3. points go back onto the surface (hard-edge points onto the hard edges); all_quads splits every face into quads
 */
#include <math.h>
#include <setjmp.h>
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

#define MAXLEV 8

typedef struct {
  float scale;               /* target edge length */
  float crease_deg;          /* hard edges: faces meeting at more than this (and open borders) */
  float min_chain;           /* hard-edge chains shorter than this are ignored */
  int all_quads;             /* split every face into quads at the end */
  int threads;               /* <= 1: one thread */
  int seed;
  int iters_orient[MAXLEV];  /* Gauss-Seidel sweeps per level (fine first) */
  int iters_pos[MAXLEV];
} MquadOpts;

typedef struct {
  int nv, nf;
  float *V;      /* nv * 3 */
  int *F;        /* nf * 4, -1 = triangle */
  int *fsrc;     /* nf: fine triangle under the face centre */
  int *vsrc;     /* nv: fine point nearest the point */
  int stats[8];  /* collapses, conflicts, points, holes filled, triangle pairs joined, triangles, quads,
                    faces dropped from edges on 3+ faces */
} MquadOut;

/* ---------- memory: everything goes when the run ends (longjmp out on failure) ---------- */

typedef struct {
  void **p;
  int n, cap;
  char *cur;
  size_t left;
  jmp_buf jb;
} Mem;

static void *xmalloc(Mem *m, size_t sz) {
  void *p = malloc(sz ? sz : 1);
  if (!p) longjmp(m->jb, 1);
  if (m->n == m->cap) {
    int nc = m->cap ? m->cap * 2 : 256;
    void **np = (void **)realloc(m->p, sizeof(void *) * nc);
    if (!np) {
      free(p);
      longjmp(m->jb, 1);
    }
    m->p = np;
    m->cap = nc;
  }
  m->p[m->n++] = p;
  return p;
}

static void *xcalloc(Mem *m, size_t n, size_t sz) {
  void *p = xmalloc(m, n * sz);
  memset(p, 0, n * sz);
  return p;
}

static void *aalloc(Mem *m, size_t sz) { /* small blocks from 1 MB chunks */
  sz = (sz + 15) & ~(size_t)15;
  if (sz > 65536) return xmalloc(m, sz);
  if (m->left < sz) {
    m->cur = (char *)xmalloc(m, 1 << 20);
    m->left = 1 << 20;
  }
  void *p = m->cur;
  m->cur += sz;
  m->left -= sz;
  return p;
}

static void mem_free(Mem *m) {
  for (int i = 0; i < m->n; i++) free(m->p[i]);
  free(m->p);
  m->p = NULL;
  m->n = m->cap = 0;
}

typedef struct {
  int *a;
  int n, cap;
} IL;

static void il_push(Mem *m, IL *l, int v) {
  if (l->n == l->cap) {
    int nc = l->cap ? l->cap * 2 : 4;
    int *na = (int *)aalloc(m, sizeof(int) * nc);
    if (l->n) memcpy(na, l->a, sizeof(int) * l->n);
    l->a = na;
    l->cap = nc;
  }
  l->a[l->n++] = v;
}

static int il_has(const IL *l, int v) {
  for (int i = 0; i < l->n; i++)
    if (l->a[i] == v) return 1;
  return 0;
}

static void il_remove(IL *l, int v) {
  for (int i = 0; i < l->n; i++)
    if (l->a[i] == v) {
      l->a[i] = l->a[--l->n];
      return;
    }
}

/* ---------- vectors ---------- */

static inline double dot3(const double *a, const double *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
static inline void cross3(const double *a, const double *b, double *o) {
  o[0] = a[1] * b[2] - a[2] * b[1];
  o[1] = a[2] * b[0] - a[0] * b[2];
  o[2] = a[0] * b[1] - a[1] * b[0];
}
static inline void sub3(const double *a, const double *b, double *o) {
  o[0] = a[0] - b[0];
  o[1] = a[1] - b[1];
  o[2] = a[2] - b[2];
}
static inline double norm3(const double *a) { return sqrt(dot3(a, a)); }
static inline void normalize3(double *a) {
  double l = norm3(a);
  if (l > 1e-30) {
    a[0] /= l;
    a[1] /= l;
    a[2] /= l;
  }
}
static inline void tangent3(double *v, const double *n) { /* v minus its part along n, unit */
  double d = dot3(v, n);
  v[0] -= n[0] * d;
  v[1] -= n[1] * d;
  v[2] -= n[2] * d;
  normalize3(v);
}

static uint64_t rnd(uint64_t *s) {
  uint64_t x = *s;
  x ^= x << 13;
  x ^= x >> 7;
  x ^= x << 17;
  return *s = x;
}

static double angle_deg(const double *v0, const double *v1, const double *v2) { /* the corner at v1 */
  double d0[3], d1[3];
  sub3(v0, v1, d0);
  sub3(v2, v1, d1);
  double l = norm3(d0) * norm3(d1);
  double c = l > 1e-30 ? dot3(d0, d1) / l : 1.0;
  if (c > 1.0) c = 1.0;
  if (c < -1.0) c = -1.0;
  return acos(c) * (180.0 / 3.14159265358979323846);
}

/* ---------- levels ---------- */

typedef struct {
  int64_t key;
  int f;
} EK;

static int ek_cmp(const void *a, const void *b) {
  int64_t x = ((const EK *)a)->key, y = ((const EK *)b)->key;
  return (x > y) - (x < y);
}

typedef struct {
  int nv, nf, ne;
  double *P, *N;
  const int *F;
  int *E;        /* ne * 2 */
  int *ecr;      /* hard edge */
  int nbound;    /* open border edges */
  int *as, *aj;  /* neighbours (CSR) */
  int *cc;       /* hard edges through the point: 1 an end, 2 along a hard edge, 3+ a corner */
  double *cd;    /* hard-edge direction at the point (tangent) */
  int ncol, *cs, *cv; /* points by colour */
  double *Q, *O;
  int *up;       /* nearest point of the next coarser level */
} Level;

static int uf_find(int *par, int x) {
  while (par[x] != x) {
    par[x] = par[par[x]];
    x = par[x];
  }
  return x;
}

static void build_level(Mem *m, Level *L, const float *V, int nv, const int *F, int nf, double cos_cr,
                        double min_chain, uint64_t *rng) {
  L->nv = nv;
  L->nf = nf;
  L->F = F;
  double *P = L->P = (double *)xmalloc(m, sizeof(double) * 3 * nv);
  for (int i = 0; i < 3 * nv; i++) P[i] = V[i];
  double *fn = (double *)xmalloc(m, sizeof(double) * 3 * nf);
  double *N = L->N = (double *)xcalloc(m, 3 * (size_t)nv, sizeof(double));
  for (int f = 0; f < nf; f++) {
    const int *t = &F[3 * f];
    double e1[3], e2[3];
    sub3(&P[3 * t[1]], &P[3 * t[0]], e1);
    sub3(&P[3 * t[2]], &P[3 * t[0]], e2);
    cross3(e1, e2, &fn[3 * f]);
    for (int k = 0; k < 3; k++)
      for (int d = 0; d < 3; d++) N[3 * t[k] + d] += fn[3 * f + d];
  }
  for (int i = 0; i < nv; i++) {
    double *n = &N[3 * i];
    if (norm3(n) < 1e-30) {
      n[0] = n[1] = 0.0;
      n[2] = 1.0;
    }
    normalize3(n);
  }
  /* edges */
  EK *ek = (EK *)xmalloc(m, sizeof(EK) * 3 * (size_t)nf);
  for (int f = 0; f < nf; f++)
    for (int k = 0; k < 3; k++) {
      int a = F[3 * f + k], b = F[3 * f + (k + 1) % 3];
      if (a > b) {
        int s = a;
        a = b;
        b = s;
      }
      ek[3 * f + k].key = (int64_t)a * nv + b;
      ek[3 * f + k].f = f;
    }
  qsort(ek, 3 * (size_t)nf, sizeof(EK), ek_cmp);
  int ne = 0;
  for (int i = 0; i < 3 * nf; i++)
    if (i == 0 || ek[i].key != ek[i - 1].key) ne++;
  L->ne = ne;
  int *E = L->E = (int *)xmalloc(m, sizeof(int) * 2 * ne);
  int *ecr = L->ecr = (int *)xcalloc(m, ne, sizeof(int));
  int e = 0;
  for (int i = 0; i < 3 * nf;) {
    int j = i;
    while (j < 3 * nf && ek[j].key == ek[i].key) j++;
    E[2 * e] = (int)(ek[i].key / nv);
    E[2 * e + 1] = (int)(ek[i].key % nv);
    if (j - i != 2) {
      ecr[e] = 1;
      L->nbound++;
    } else {
      const double *na = &fn[3 * ek[i].f], *nb = &fn[3 * ek[i + 1].f];
      double la = norm3(na), lb = norm3(nb);
      if (la > 1e-30 && lb > 1e-30 && dot3(na, nb) < cos_cr * la * lb) ecr[e] = 1;
    }
    e++;
    i = j;
  }
  /* hard-edge chains shorter than min_chain are not hard edges */
  if (min_chain > 0) {
    int *par = (int *)xmalloc(m, sizeof(int) * nv);
    double *len = (double *)xcalloc(m, nv, sizeof(double));
    for (int i = 0; i < nv; i++) par[i] = i;
    for (e = 0; e < ne; e++)
      if (ecr[e]) {
        int ra = uf_find(par, E[2 * e]), rb = uf_find(par, E[2 * e + 1]);
        if (ra != rb) par[rb] = ra;
      }
    for (e = 0; e < ne; e++)
      if (ecr[e]) {
        double d[3];
        sub3(&P[3 * E[2 * e]], &P[3 * E[2 * e + 1]], d);
        len[uf_find(par, E[2 * e])] += norm3(d);
      }
    for (e = 0; e < ne; e++)
      if (ecr[e] && len[uf_find(par, E[2 * e])] < min_chain) ecr[e] = 0;
  }
  int *cc = L->cc = (int *)xcalloc(m, nv, sizeof(int));
  double *cd = L->cd = (double *)xcalloc(m, 3 * (size_t)nv, sizeof(double));
  for (e = 0; e < ne; e++) {
    if (!ecr[e]) continue;
    double d[3];
    sub3(&P[3 * E[2 * e + 1]], &P[3 * E[2 * e]], d);
    normalize3(d);
    for (int k = 0; k < 2; k++) {
      int v = E[2 * e + k];
      double s = k ? -1.0 : 1.0;
      if (dot3(&cd[3 * v], d) * s < 0) s = -s; /* no sign: agree with what is there */
      for (int c = 0; c < 3; c++) cd[3 * v + c] += d[c] * s;
      cc[v]++;
    }
  }
  for (int i = 0; i < nv; i++)
    if (cc[i]) tangent3(&cd[3 * i], &N[3 * i]);
  /* neighbours */
  int *as = L->as = (int *)xcalloc(m, nv + 1, sizeof(int));
  for (e = 0; e < ne; e++) {
    as[E[2 * e] + 1]++;
    as[E[2 * e + 1] + 1]++;
  }
  for (int i = 0; i < nv; i++) as[i + 1] += as[i];
  int *aj = L->aj = (int *)xmalloc(m, sizeof(int) * 2 * (size_t)ne);
  int *fill = (int *)xmalloc(m, sizeof(int) * nv);
  memcpy(fill, as, sizeof(int) * nv);
  for (e = 0; e < ne; e++) {
    aj[fill[E[2 * e]]++] = E[2 * e + 1];
    aj[fill[E[2 * e + 1]]++] = E[2 * e];
  }
  /* greedy colouring in random order: points of one colour share no edge (updated in parallel) */
  int *perm = (int *)xmalloc(m, sizeof(int) * nv);
  for (int i = 0; i < nv; i++) perm[i] = i;
  for (int i = nv - 1; i > 0; i--) {
    int j = (int)(rnd(rng) % (uint64_t)(i + 1));
    int s = perm[i];
    perm[i] = perm[j];
    perm[j] = s;
  }
  int maxdeg = 0;
  for (int i = 0; i < nv; i++)
    if (as[i + 1] - as[i] > maxdeg) maxdeg = as[i + 1] - as[i];
  int *col = (int *)xmalloc(m, sizeof(int) * nv);
  int *mark = (int *)xcalloc(m, maxdeg + 2, sizeof(int));
  for (int i = 0; i < nv; i++) col[i] = -1;
  int ncol = 0;
  for (int k = 0; k < nv; k++) {
    int v = perm[k];
    for (int a = as[v]; a < as[v + 1]; a++) {
      int c = col[aj[a]];
      if (c >= 0 && c <= maxdeg + 1) mark[c] = k + 1;
    }
    int c = 0;
    while (mark[c] == k + 1) c++;
    col[v] = c;
    if (c + 1 > ncol) ncol = c + 1;
  }
  L->ncol = ncol;
  int *cs = L->cs = (int *)xcalloc(m, ncol + 1, sizeof(int));
  for (int i = 0; i < nv; i++) cs[col[i] + 1]++;
  for (int c = 0; c < ncol; c++) cs[c + 1] += cs[c];
  int *cv = L->cv = (int *)xmalloc(m, sizeof(int) * nv);
  memcpy(fill, cs, sizeof(int) * ncol);
  for (int k = 0; k < nv; k++) {
    int v = perm[k];
    cv[fill[col[v]]++] = v;
  }
  L->Q = (double *)xmalloc(m, sizeof(double) * 3 * nv);
  L->O = (double *)xmalloc(m, sizeof(double) * 3 * nv);
  L->up = NULL;
}

/* nearest point of the coarser level for every point (along the surface: Dijkstra from the points it kept) */
typedef struct {
  double d;
  int v;
} HE;

static void heap_up(HE *h, int i) {
  while (i > 0) {
    int p = (i - 1) / 2;
    if (h[p].d <= h[i].d) break;
    HE t = h[p];
    h[p] = h[i];
    h[i] = t;
    i = p;
  }
}

static void heap_down(HE *h, int n, int i) {
  for (;;) {
    int l = 2 * i + 1, r = l + 1, s = i;
    if (l < n && h[l].d < h[s].d) s = l;
    if (r < n && h[r].d < h[s].d) s = r;
    if (s == i) break;
    HE t = h[s];
    h[s] = h[i];
    h[i] = t;
    i = s;
  }
}

static void prolong_map(Mem *m, Level *L, int ncoarse, const int *src) {
  int nv = L->nv;
  int *up = L->up = (int *)xmalloc(m, sizeof(int) * nv);
  double *dist = (double *)xmalloc(m, sizeof(double) * nv);
  HE *h = (HE *)xmalloc(m, sizeof(HE) * ((size_t)nv + 2 * (size_t)L->ne + ncoarse + 1));
  int hn = 0;
  for (int i = 0; i < nv; i++) {
    up[i] = -1;
    dist[i] = HUGE_VAL;
  }
  for (int j = 0; j < ncoarse; j++) {
    int v = src[j];
    if (v < 0 || v >= nv || up[v] >= 0) continue;
    up[v] = j;
    dist[v] = 0.0;
    h[hn].d = 0.0;
    h[hn].v = v;
    heap_up(h, hn++);
  }
  while (hn) {
    HE top = h[0];
    h[0] = h[--hn];
    heap_down(h, hn, 0);
    if (top.d > dist[top.v]) continue;
    for (int a = L->as[top.v]; a < L->as[top.v + 1]; a++) {
      int u = L->aj[a];
      double d[3];
      sub3(&L->P[3 * u], &L->P[3 * top.v], d);
      double nd = top.d + norm3(d);
      if (nd < dist[u]) {
        dist[u] = nd;
        up[u] = up[top.v];
        h[hn].d = nd;
        h[hn].v = u;
        heap_up(h, hn++);
      }
    }
  }
}

/* ---------- Instant Meshes building blocks (extrinsic, 4-RoSy / 4-PoSy) ---------- */

static void compat_orient(const double *q0, const double *n0, const double *q1, const double *n1, double *a,
                          double *b) {
  double A[2][3], B[2][3];
  memcpy(A[0], q0, sizeof(double) * 3);
  cross3(n0, q0, A[1]);
  memcpy(B[0], q1, sizeof(double) * 3);
  cross3(n1, q1, B[1]);
  double best = -1.0, bs = 1.0;
  int ia = 0, ib = 0;
  for (int i = 0; i < 2; i++)
    for (int j = 0; j < 2; j++) {
      double s = dot3(A[i], B[j]);
      if (fabs(s) > best + 1e-9) {
        best = fabs(s);
        ia = i;
        ib = j;
        bs = s < 0 ? -1.0 : 1.0;
      }
    }
  memcpy(a, A[ia], sizeof(double) * 3);
  for (int d = 0; d < 3; d++) b[d] = B[ib][d] * bs;
}

static void middle_point(const double *p0, const double *n0, const double *p1, const double *n1, double *mid) {
  double n0p0 = dot3(n0, p0), n0p1 = dot3(n0, p1), n1p0 = dot3(n1, p0), n1p1 = dot3(n1, p1), n0n1 = dot3(n0, n1);
  double den = 1.0 / (1.0 - n0n1 * n0n1 + 1e-4);
  double l0 = 2.0 * (n0p1 - n0p0 - n0n1 * (n1p0 - n1p1)) * den;
  double l1 = 2.0 * (n1p0 - n1p1 - n0n1 * (n0p1 - n0p0)) * den;
  for (int d = 0; d < 3; d++) mid[d] = 0.5 * (p0[d] + p1[d]) - 0.25 * (n0[d] * l0 + n1[d] * l1);
}

/* the lattice points of o0 and o1 nearest each other round the middle of the edge; returns the squared gap */
static double compat_pos(const double *p0, const double *n0, const double *q0, const double *o0, const double *p1,
                         const double *n1, const double *q1, const double *o1, double h, double *a, double *b,
                         int *i0, int *i1) {
  double t0[3], t1[3], mid[3], d0[3], d1[3];
  cross3(n0, q0, t0);
  cross3(n1, q1, t1);
  middle_point(p0, n0, p1, n1, mid);
  sub3(mid, o0, d0);
  sub3(mid, o1, d1);
  double inv = 1.0 / h;
  double a0 = floor(dot3(q0, d0) * inv), b0 = floor(dot3(t0, d0) * inv);
  double a1 = floor(dot3(q1, d1) * inv), b1 = floor(dot3(t1, d1) * inv);
  double A[4][3], B[4][3];
  for (int k = 0; k < 4; k++) {
    double ca = a0 + (k & 1), cb = b0 + (k >> 1), da = a1 + (k & 1), db = b1 + (k >> 1);
    for (int d = 0; d < 3; d++) {
      A[k][d] = o0[d] + (q0[d] * ca + t0[d] * cb) * h;
      B[k][d] = o1[d] + (q1[d] * da + t1[d] * db) * h;
    }
  }
  double best = HUGE_VAL;
  int bi = 0, bj = 0;
  for (int i = 0; i < 4; i++)
    for (int j = 0; j < 4; j++) {
      double d[3];
      sub3(A[i], B[j], d);
      double c = dot3(d, d);
      if (c < best) {
        best = c;
        bi = i;
        bj = j;
      }
    }
  if (a) memcpy(a, A[bi], sizeof(double) * 3);
  if (b) memcpy(b, B[bj], sizeof(double) * 3);
  if (i0) {
    i0[0] = (int)a0 + (bi & 1);
    i0[1] = (int)b0 + (bi >> 1);
    i1[0] = (int)a1 + (bj & 1);
    i1[1] = (int)b1 + (bj >> 1);
  }
  return best;
}

static void round4(double *o, const double *q, const double *n, const double *p, double h) {
  double t[3], d[3];
  cross3(n, q, t);
  sub3(p, o, d);
  double a = floor(dot3(q, d) / h + 0.5) * h, b = floor(dot3(t, d) / h + 0.5) * h;
  for (int k = 0; k < 3; k++) o[k] += q[k] * a + t[k] * b;
}

static void orient_point(Level *L, int i) {
  const double *n = &L->N[3 * i];
  double s[3], a[3], b[3];
  memcpy(s, &L->Q[3 * i], sizeof(s));
  double ws = 0.0;
  for (int k = L->as[i]; k < L->as[i + 1]; k++) {
    int j = L->aj[k];
    compat_orient(s, n, &L->Q[3 * j], &L->N[3 * j], a, b);
    for (int d = 0; d < 3; d++) s[d] = a[d] * ws + b[d];
    tangent3(s, n);
    ws += 1.0;
  }
  if ((L->cc[i] == 1 || L->cc[i] == 2) && norm3(&L->cd[3 * i]) > 0.5) { /* along the hard edge */
    compat_orient(s, n, &L->cd[3 * i], n, a, b);
    memcpy(s, b, sizeof(s));
    tangent3(s, n);
  }
  if (norm3(s) > 0.5) memcpy(&L->Q[3 * i], s, sizeof(s));
}

static void pos_point(Level *L, int i, double h) {
  const double *n = &L->N[3 * i], *p = &L->P[3 * i], *q = &L->Q[3 * i];
  double s[3], a[3], b[3];
  memcpy(s, &L->O[3 * i], sizeof(s));
  double ws = 0.0;
  for (int k = L->as[i]; k < L->as[i + 1]; k++) {
    int j = L->aj[k];
    compat_pos(p, n, q, s, &L->P[3 * j], &L->N[3 * j], &L->Q[3 * j], &L->O[3 * j], h, a, b, NULL, NULL);
    for (int d = 0; d < 3; d++) s[d] = (a[d] * ws + b[d]) / (ws + 1.0);
    ws += 1.0;
    double off = n[0] * (s[0] - p[0]) + n[1] * (s[1] - p[1]) + n[2] * (s[2] - p[2]);
    for (int d = 0; d < 3; d++) s[d] -= n[d] * off;
  }
  int c = L->cc[i];
  if (c == 1 || c == 2) { /* a lattice line on the hard edge */
    const double *cd = &L->cd[3 * i];
    double d[3];
    sub3(p, s, d);
    double t = dot3(cd, d);
    for (int k = 0; k < 3; k++) s[k] += d[k] - cd[k] * t;
  }
  round4(s, q, n, p, h);
  if (c > 2) memcpy(s, p, sizeof(s)); /* corners: a lattice point right there */
  memcpy(&L->O[3 * i], s, sizeof(s));
}

/* ---------- threads: one colour's points in parallel ---------- */

typedef struct {
  Level *L;
  double h;
  const int *v;
  int b, e, what;
} Part;

static void run_part(Part *p) {
  for (int k = p->b; k < p->e; k++) {
    if (p->what == 0)
      orient_point(p->L, p->v[k]);
    else
      pos_point(p->L, p->v[k], p->h);
  }
}

#ifdef _WIN32
static DWORD WINAPI part_thread(LPVOID p) {
  run_part((Part *)p);
  return 0;
}
#else
static void *part_thread(void *p) {
  run_part((Part *)p);
  return NULL;
}
#endif

static void sweep(Level *L, int what, double h, int threads) {
  for (int c = 0; c < L->ncol; c++) {
    const int *v = &L->cv[L->cs[c]];
    int n = L->cs[c + 1] - L->cs[c];
    int t = threads;
    if (t > 64) t = 64;
    if (t > n / 2048) t = n / 2048;
    Part parts[64];
    if (t < 2) {
      Part p = {L, h, v, 0, n, what};
      run_part(&p);
      continue;
    }
    for (int k = 0; k < t; k++) {
      parts[k].L = L;
      parts[k].h = h;
      parts[k].v = v;
      parts[k].b = (int)((int64_t)n * k / t);
      parts[k].e = (int)((int64_t)n * (k + 1) / t);
      parts[k].what = what;
    }
#ifdef _WIN32
    HANDLE th[64];
    for (int k = 1; k < t; k++) th[k] = CreateThread(NULL, 0, part_thread, &parts[k], 0, NULL);
    run_part(&parts[0]);
    for (int k = 1; k < t; k++) {
      if (th[k]) {
        WaitForSingleObject(th[k], INFINITE);
        CloseHandle(th[k]);
      } else {
        run_part(&parts[k]);
      }
    }
#else
    pthread_t th[64];
    int ok[64];
    for (int k = 1; k < t; k++) ok[k] = pthread_create(&th[k], NULL, part_thread, &parts[k]) == 0;
    run_part(&parts[0]);
    for (int k = 1; k < t; k++) {
      if (ok[k])
        pthread_join(th[k], NULL);
      else
        run_part(&parts[k]);
    }
#endif
  }
}

/* ---------- closest points on the fine surface (spatial hash) ---------- */

typedef struct {
  double cell, lo[3];
  unsigned mask;
  int *bs, *items;
  int nprim, kind; /* 0 triangles, 1 segments */
  const int *idx;  /* 3 or 2 point indices per primitive */
  const double *P;
  int *stamp, st;
} Hash;

static inline unsigned hcell(int x, int y, int z, unsigned mask) {
  return ((unsigned)x * 73856093u ^ (unsigned)y * 19349663u ^ (unsigned)z * 83492791u) & mask;
}

static void prim_box(const Hash *H, int p, int *c0, int *c1) {
  int np = H->kind ? 2 : 3;
  double mn[3] = {HUGE_VAL, HUGE_VAL, HUGE_VAL}, mx[3] = {-HUGE_VAL, -HUGE_VAL, -HUGE_VAL};
  for (int k = 0; k < np; k++) {
    const double *v = &H->P[3 * H->idx[np * p + k]];
    for (int d = 0; d < 3; d++) {
      if (v[d] < mn[d]) mn[d] = v[d];
      if (v[d] > mx[d]) mx[d] = v[d];
    }
  }
  for (int d = 0; d < 3; d++) {
    c0[d] = (int)floor((mn[d] - H->lo[d]) / H->cell);
    c1[d] = (int)floor((mx[d] - H->lo[d]) / H->cell);
    if (c1[d] - c0[d] > 64) c1[d] = c0[d] + 64; /* (a huge primitive: it is still found by the fallback) */
  }
}

static void hash_build(Mem *m, Hash *H, const double *P, int np_pts, const int *idx, int nprim, int kind, double cell) {
  memset(H, 0, sizeof(*H));
  H->P = P;
  H->idx = idx;
  H->nprim = nprim;
  H->kind = kind;
  H->cell = cell;
  H->lo[0] = H->lo[1] = H->lo[2] = HUGE_VAL;
  for (int i = 0; i < np_pts; i++)
    for (int d = 0; d < 3; d++)
      if (P[3 * i + d] < H->lo[d]) H->lo[d] = P[3 * i + d];
  if (np_pts == 0) H->lo[0] = H->lo[1] = H->lo[2] = 0.0;
  unsigned nb = 1024;
  while (nb < (unsigned)nprim * 2u && nb < (1u << 26)) nb <<= 1;
  H->mask = nb - 1;
  H->bs = (int *)xcalloc(m, nb + 1, sizeof(int));
  int c0[3], c1[3];
  for (int p = 0; p < nprim; p++) {
    prim_box(H, p, c0, c1);
    for (int x = c0[0]; x <= c1[0]; x++)
      for (int y = c0[1]; y <= c1[1]; y++)
        for (int z = c0[2]; z <= c1[2]; z++) H->bs[hcell(x, y, z, H->mask) + 1]++;
  }
  for (unsigned b = 0; b < nb; b++) H->bs[b + 1] += H->bs[b];
  H->items = (int *)xmalloc(m, sizeof(int) * ((size_t)H->bs[nb] + 1));
  int *fill = (int *)xmalloc(m, sizeof(int) * nb);
  memcpy(fill, H->bs, sizeof(int) * nb);
  for (int p = 0; p < nprim; p++) {
    prim_box(H, p, c0, c1);
    for (int x = c0[0]; x <= c1[0]; x++)
      for (int y = c0[1]; y <= c1[1]; y++)
        for (int z = c0[2]; z <= c1[2]; z++) {
          unsigned b = hcell(x, y, z, H->mask);
          int k;
          for (k = H->bs[b]; k < fill[b]; k++) /* a primitive once per bucket */
            if (H->items[k] == p) break;
          if (k == fill[b]) H->items[fill[b]++] = p;
        }
  }
  /* buckets may now have unused tail slots: mark them */
  for (unsigned b = 0; b < nb; b++)
    for (int k = fill[b]; k < H->bs[b + 1]; k++) H->items[k] = -1;
  H->stamp = (int *)xcalloc(m, nprim + 1, sizeof(int));
  H->st = 0;
}

static double closest_tri(const double *p, const double *a, const double *b, const double *c, double *q) {
  double ab[3], ac[3], ap[3], bp[3], cp[3];
  sub3(b, a, ab);
  sub3(c, a, ac);
  sub3(p, a, ap);
  double d1 = dot3(ab, ap), d2 = dot3(ac, ap);
  if (d1 <= 0 && d2 <= 0) {
    memcpy(q, a, sizeof(double) * 3);
  } else {
    sub3(p, b, bp);
    double d3 = dot3(ab, bp), d4 = dot3(ac, bp);
    if (d3 >= 0 && d4 <= d3) {
      memcpy(q, b, sizeof(double) * 3);
    } else {
      double vc = d1 * d4 - d3 * d2;
      if (vc <= 0 && d1 >= 0 && d3 <= 0) {
        double v = d1 / (d1 - d3);
        for (int k = 0; k < 3; k++) q[k] = a[k] + ab[k] * v;
      } else {
        sub3(p, c, cp);
        double d5 = dot3(ab, cp), d6 = dot3(ac, cp);
        if (d6 >= 0 && d5 <= d6) {
          memcpy(q, c, sizeof(double) * 3);
        } else {
          double vb = d5 * d2 - d1 * d6;
          if (vb <= 0 && d2 >= 0 && d6 <= 0) {
            double w = d2 / (d2 - d6);
            for (int k = 0; k < 3; k++) q[k] = a[k] + ac[k] * w;
          } else {
            double va = d3 * d6 - d5 * d4;
            if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0) {
              double w = (d4 - d3) / ((d4 - d3) + (d5 - d6));
              for (int k = 0; k < 3; k++) q[k] = b[k] + (c[k] - b[k]) * w;
            } else {
              double den = va + vb + vc;
              double v = den != 0 ? vb / den : 0.0, w = den != 0 ? vc / den : 0.0;
              for (int k = 0; k < 3; k++) q[k] = a[k] + ab[k] * v + ac[k] * w;
            }
          }
        }
      }
    }
  }
  double d[3];
  sub3(p, q, d);
  return dot3(d, d);
}

static double closest_seg(const double *p, const double *a, const double *b, double *q) {
  double ab[3], ap[3];
  sub3(b, a, ab);
  sub3(p, a, ap);
  double l = dot3(ab, ab);
  double t = l > 0 ? dot3(ap, ab) / l : 0.0;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  for (int k = 0; k < 3; k++) q[k] = a[k] + ab[k] * t;
  double d[3];
  sub3(p, q, d);
  return dot3(d, d);
}

static double prim_closest(const Hash *H, int p, const double *x, double *q) {
  if (H->kind)
    return closest_seg(x, &H->P[3 * H->idx[2 * p]], &H->P[3 * H->idx[2 * p + 1]], q);
  return closest_tri(x, &H->P[3 * H->idx[3 * p]], &H->P[3 * H->idx[3 * p + 1]], &H->P[3 * H->idx[3 * p + 2]], q);
}

/* the closest point on any primitive (q) and that primitive; -1 when there are none */
static int hash_nearest(Hash *H, const double *x, double *q) {
  if (H->nprim == 0) return -1;
  if (++H->st == 0x7fffffff) {
    memset(H->stamp, 0, sizeof(int) * (H->nprim + 1));
    H->st = 1;
  }
  int c[3];
  for (int d = 0; d < 3; d++) c[d] = (int)floor((x[d] - H->lo[d]) / H->cell);
  double best = HUGE_VAL, t[3];
  int bp = -1;
  for (int r = 0; r <= 6; r++) {
    for (int dx = -r; dx <= r; dx++)
      for (int dy = -r; dy <= r; dy++)
        for (int dz = -r; dz <= r; dz++) {
          int ax = abs(dx), ay = abs(dy), az = abs(dz);
          int mx = ax > ay ? ax : ay;
          if (az > mx) mx = az;
          if (mx != r) continue;
          unsigned b = hcell(c[0] + dx, c[1] + dy, c[2] + dz, H->mask);
          for (int k = H->bs[b]; k < H->bs[b + 1]; k++) {
            int p = H->items[k];
            if (p < 0 || H->stamp[p] == H->st) continue;
            H->stamp[p] = H->st;
            double d = prim_closest(H, p, x, t);
            if (d < best) {
              best = d;
              bp = p;
              memcpy(q, t, sizeof(t));
            }
          }
        }
    if (bp >= 0 && sqrt(best) <= r * H->cell) return bp;
  }
  for (int p = 0; p < H->nprim; p++) { /* far from everything: look at all of them */
    double d = prim_closest(H, p, x, t);
    if (d < best) {
      best = d;
      bp = p;
      memcpy(q, t, sizeof(t));
    }
  }
  return bp;
}

/* ---------- result mesh ---------- */

typedef struct {
  int v[4]; /* v[3] = -1: triangle */
} Face;

typedef struct {
  Face *f;
  int n, cap;
} Faces;

static void faces_add(Mem *m, Faces *F, int a, int b, int c, int d) {
  if (a == b || a == c || b == c || (d >= 0 && (d == a || d == b || d == c))) return; /* degenerate */
  if (F->n == F->cap) {
    int nc = F->cap ? F->cap * 2 : 1024;
    Face *nf = (Face *)xmalloc(m, sizeof(Face) * nc);
    if (F->n) memcpy(nf, F->f, sizeof(Face) * F->n);
    F->f = nf;
    F->cap = nc;
  }
  Face *f = &F->f[F->n++];
  f->v[0] = a;
  f->v[1] = b;
  f->v[2] = c;
  f->v[3] = d;
}

static int fsize(const Face *f) { return f->v[3] < 0 ? 3 : 4; }

/* ---------- extraction ---------- */

typedef struct {
  double err;
  int a, b;
} Col;

static int col_cmp(const void *x, const void *y) {
  double a = ((const Col *)x)->err, b = ((const Col *)y)->err;
  return (a > b) - (a < b);
}

typedef struct {
  double h;
  int i, j, k;
} Cand;

static int cand_cmp(const void *x, const void *y) {
  double a = ((const Cand *)x)->h, b = ((const Cand *)y)->h;
  return (a > b) - (a < b);
}

typedef struct {
  /* clusters (result points) */
  int nc, cap;
  double *pos, *nrm;
  int *kind; /* 0 surface, 1 hard edge, 2 corner */
  IL *adj;
  /* walk */
  int **used;
  Faces faces;
  int holes;
} Graph;

static int walk(Graph *G, int cur, int ci, int size, int *rc, int *rk) {
  int init = cur, n = 0;
  for (;;) {
    if (G->used[cur][ci] || (size && n + 1 > size)) return 0;
    rc[n] = cur;
    rk[n] = ci;
    n++;
    int nxt = G->adj[cur].a[ci];
    IL *l = &G->adj[nxt];
    int k = -1;
    for (int t = 0; t < l->n; t++)
      if (l->a[t] == cur) {
        k = t;
        break;
      }
    if (k < 0 || l->n == 1) return 0;
    cur = nxt;
    ci = (k + 1) % l->n;
    if (cur == init) {
      if (size && n != size) return 0;
      return n;
    }
    if (n >= 64) return 0;
  }
}

static double quad_score(const double *pos, const int *q) { /* corners off 90 degrees */
  double s = 0.0;
  for (int k = 0; k < 4; k++)
    s += fabs(angle_deg(&pos[3 * q[(k + 3) % 4]], &pos[3 * q[k]], &pos[3 * q[(k + 1) % 4]]) - 90.0);
  return s;
}

static void fill_loop(Mem *m, Faces *FS, const double *P, int *vs, int n) {
  while (n > 2) {
    if (n == 3) {
      faces_add(m, FS, vs[0], vs[1], vs[2], -1);
      return;
    }
    if (n == 4) {
      faces_add(m, FS, vs[0], vs[1], vs[2], vs[3]);
      return;
    }
    if (n == 5) { /* a quad and a triangle: the best-shaped pair */
      double best = HUGE_VAL;
      int bi = 0;
      for (int st = 0; st < 5; st++) {
        int q[4] = {vs[st], vs[(st + 1) % 5], vs[(st + 2) % 5], vs[(st + 3) % 5]};
        int t[3] = {vs[(st + 3) % 5], vs[(st + 4) % 5], vs[st]};
        double s = quad_score(P, q);
        for (int k = 0; k < 3; k++)
          s += fabs(angle_deg(&P[3 * t[(k + 2) % 3]], &P[3 * t[k]], &P[3 * t[(k + 1) % 3]]) - 60.0);
        if (s < best) {
          best = s;
          bi = st;
        }
      }
      faces_add(m, FS, vs[bi], vs[(bi + 1) % 5], vs[(bi + 2) % 5], vs[(bi + 3) % 5]);
      faces_add(m, FS, vs[(bi + 3) % 5], vs[(bi + 4) % 5], vs[bi], -1);
      return;
    }
    /* more: cut off the best-shaped quad (Instant Meshes' score: the corners after its first point) */
    double best = HUGE_VAL;
    int bi = 0;
    for (int st = 0; st < n; st++) {
      double s = 0.0;
      for (int k = 0; k < 4; k++)
        s += fabs(angle_deg(&P[3 * vs[(st + k) % n]], &P[3 * vs[(st + k + 1) % n]], &P[3 * vs[(st + k + 2) % n]]) -
                  90.0);
      if (s < best) {
        best = s;
        bi = st;
      }
    }
    faces_add(m, FS, vs[bi], vs[(bi + 1) % n], vs[(bi + 2) % n], vs[(bi + 3) % n]);
    int d1 = (bi + 1) % n, d2 = (bi + 2) % n, w = 0;
    for (int k = 0; k < n; k++)
      if (k != d1 && k != d2) vs[w++] = vs[k];
    n = w;
  }
}

static void extract(Mem *m, Level *L, double h, Graph *G, int *st) {
  int nv = L->nv, ne = L->ne;
  const double *P = L->P, *N = L->N, *Q = L->Q, *O = L->O;
  IL *adj = (IL *)xcalloc(m, nv, sizeof(IL));
  Col *col = (Col *)xmalloc(m, sizeof(Col) * (ne + 1));
  int ncol = 0;
  for (int e = 0; e < ne; e++) {
    int i = L->E[2 * e], j = L->E[2 * e + 1];
    double qa[3], qb[3];
    int s0[2], s1[2];
    compat_orient(&Q[3 * i], &N[3 * i], &Q[3 * j], &N[3 * j], qa, qb);
    double err = compat_pos(&P[3 * i], &N[3 * i], qa, &O[3 * i], &P[3 * j], &N[3 * j], qb, &O[3 * j], h, NULL, NULL,
                            s0, s1);
    int da = abs(s0[0] - s1[0]), db = abs(s0[1] - s1[1]);
    if (da > 1 || db > 1 || (da == 1 && db == 1)) continue; /* farther, or a diagonal */
    if (da + db == 0) {
      col[ncol].err = err;
      col[ncol].a = i;
      col[ncol].b = j;
      ncol++;
    } else {
      il_push(m, &adj[i], j);
      il_push(m, &adj[j], i);
    }
  }
  qsort(col, ncol, sizeof(Col), col_cmp);
  int *par = (int *)xmalloc(m, sizeof(int) * nv);
  int *nco = (int *)xcalloc(m, nv, sizeof(int));
  int *mark = (int *)xcalloc(m, nv, sizeof(int));
  int stamp = 0;
  for (int i = 0; i < nv; i++) par[i] = i;
  int conflicts = 0, done = 0;
  for (int c = 0; c < ncol; c++) {
    int ra = uf_find(par, col[c].a), rb = uf_find(par, col[c].b);
    if (ra == rb) continue;
    int clash = 0;
    for (int k = 0; k < adj[ra].n && !clash; k++)
      if (uf_find(par, adj[ra].a[k]) == rb) clash = 1;
    if (clash) { /* already one lattice step apart: both stay */
      conflicts++;
      continue;
    }
    par[rb] = ra;
    stamp++;
    IL merged = {NULL, 0, 0};
    for (int s = 0; s < 2; s++) {
      IL *l = &adj[s ? rb : ra];
      for (int k = 0; k < l->n; k++) {
        int r = uf_find(par, l->a[k]);
        if (r == ra || mark[r] == stamp) continue;
        mark[r] = stamp;
        il_push(m, &merged, r);
      }
    }
    adj[ra] = merged;
    adj[rb].n = 0;
    nco[ra] += nco[rb] + 1;
    done++;
  }
  st[0] = done;
  st[1] = conflicts;
  /* clusters: roots with enough members (lone stray points go) */
  int nroot = 0;
  double tot = 0.0;
  for (int i = 0; i < nv; i++)
    if (uf_find(par, i) == i) {
      nroot++;
      tot += nco[i];
    }
  double cut = nroot ? tot / nroot / 10.0 : 0.0;
  int *cid = (int *)xmalloc(m, sizeof(int) * nv);
  int nc = 0;
  for (int i = 0; i < nv; i++) cid[i] = (uf_find(par, i) == i && nco[i] > cut) ? nc++ : -1;
  G->nc = nc;
  G->pos = (double *)xcalloc(m, 3 * (size_t)nc + 3, sizeof(double));
  G->nrm = (double *)xcalloc(m, 3 * (size_t)nc + 3, sizeof(double));
  G->kind = (int *)xcalloc(m, nc + 1, sizeof(int));
  double *ws = (double *)xcalloc(m, nc + 1, sizeof(double));
  double *ps = (double *)xcalloc(m, 3 * (size_t)nc + 3, sizeof(double));
  int *cnt = (int *)xcalloc(m, nc + 1, sizeof(int));
  for (int i = 0; i < nv; i++) {
    int c = cid[uf_find(par, i)];
    if (c < 0) continue;
    double d[3];
    sub3(&O[3 * i], &P[3 * i], d);
    double w = exp(-dot3(d, d) / (h * h) * 9.0);
    for (int k = 0; k < 3; k++) {
      G->pos[3 * c + k] += O[3 * i + k] * w;
      G->nrm[3 * c + k] += N[3 * i + k] * w;
      ps[3 * c + k] += O[3 * i + k];
    }
    ws[c] += w;
    cnt[c]++;
    int kd = L->cc[i] > 2 ? 2 : (L->cc[i] > 0 ? 1 : 0);
    if (kd > G->kind[c]) G->kind[c] = kd;
  }
  for (int c = 0; c < nc; c++) {
    for (int k = 0; k < 3; k++)
      G->pos[3 * c + k] = ws[c] > 1e-300 ? G->pos[3 * c + k] / ws[c] : ps[3 * c + k] / (cnt[c] ? cnt[c] : 1);
    if (norm3(&G->nrm[3 * c]) < 1e-30) G->nrm[3 * c + 2] = 1.0;
    normalize3(&G->nrm[3 * c]);
  }
  /* edges between clusters */
  G->adj = (IL *)xcalloc(m, nc + 1, sizeof(IL));
  for (int i = 0; i < nv; i++) {
    if (uf_find(par, i) != i || cid[i] < 0) continue;
    int a = cid[i];
    for (int k = 0; k < adj[i].n; k++) {
      int b = cid[uf_find(par, adj[i].a[k])];
      if (b < 0 || b == a || il_has(&G->adj[a], b)) continue;
      il_push(m, &G->adj[a], b);
      il_push(m, &G->adj[b], a);
    }
  }
  st[2] = nc;
  /* a point on the edge between two of its neighbours: that edge goes */
  for (int round = 0; round < 5; round++) {
    int ncand = 0, cap = 1024;
    Cand *cand = (Cand *)xmalloc(m, sizeof(Cand) * cap);
    for (int i = 0; i < nc; i++) {
      const double *pi = &G->pos[3 * i];
      for (int x = 0; x < G->adj[i].n; x++) {
        int j = G->adj[i].a[x];
        const double *pj = &G->pos[3 * j];
        for (int y = 0; y < G->adj[j].n; y++) {
          int k = G->adj[j].a[y];
          if (k == i || j > k || !il_has(&G->adj[i], k)) continue;
          const double *pk = &G->pos[3 * k];
          double d[3];
          sub3(pj, pk, d);
          double a = norm3(d);
          sub3(pi, pj, d);
          double b = norm3(d);
          sub3(pi, pk, d);
          double c = norm3(d);
          if (a <= (b > c ? b : c)) continue;
          double s = 0.5 * (a + b + c), ar = s * (s - a) * (s - b) * (s - c);
          double ht = 2.0 * sqrt(ar > 0 ? ar : 0.0) / (a > 1e-30 ? a : 1e-30);
          if (ht >= 0.3 * h) continue;
          if (ncand == cap) {
            Cand *nn = (Cand *)xmalloc(m, sizeof(Cand) * cap * 2);
            memcpy(nn, cand, sizeof(Cand) * cap);
            cand = nn;
            cap *= 2;
          }
          cand[ncand].h = ht;
          cand[ncand].i = i;
          cand[ncand].j = j;
          cand[ncand].k = k;
          ncand++;
        }
      }
    }
    if (!ncand) break;
    qsort(cand, ncand, sizeof(Cand), cand_cmp);
    int changed = 0;
    for (int c = 0; c < ncand; c++) {
      int i = cand[c].i, j = cand[c].j, k = cand[c].k;
      if (il_has(&G->adj[j], k) && il_has(&G->adj[i], j) && il_has(&G->adj[i], k)) {
        il_remove(&G->adj[j], k);
        il_remove(&G->adj[k], j);
        changed = 1;
      }
    }
    if (!changed) break;
  }
  /* neighbours clockwise round each point */
  for (int c = 0; c < nc; c++) {
    IL *l = &G->adj[c];
    if (l->n < 2) continue;
    const double *n = &G->nrm[3 * c];
    double ax[3] = {1, 0, 0}, s[3], t[3];
    if (fabs(n[0]) > 0.9) {
      ax[0] = 0;
      ax[1] = 1;
    }
    cross3(n, ax, s);
    normalize3(s);
    cross3(n, s, t);
    double ang[256];
    int cnt2 = l->n < 256 ? l->n : 256;
    for (int k = 0; k < cnt2; k++) {
      double d[3];
      sub3(&G->pos[3 * l->a[k]], &G->pos[3 * c], d);
      ang[k] = atan2(dot3(d, t), dot3(d, s));
    }
    for (int a = 1; a < cnt2; a++) { /* insertion sort, descending angle */
      double ka = ang[a];
      int kv = l->a[a], b = a - 1;
      while (b >= 0 && ang[b] < ka) {
        ang[b + 1] = ang[b];
        l->a[b + 1] = l->a[b];
        b--;
      }
      ang[b + 1] = ka;
      l->a[b + 1] = kv;
    }
  }
  /* faces: quads first, then triangles, then bigger loops (split), then holes */
  G->used = (int **)xmalloc(m, sizeof(int *) * (nc + 1));
  for (int c = 0; c < nc; c++) G->used[c] = (int *)xcalloc(m, G->adj[c].n + 1, sizeof(int));
  int rc[80], rk[80], vs[80];
  const int sizes[7] = {4, 3, 5, 6, 7, 8, 0};
  G->holes = 0;
  for (int s = 0; s < 7; s++) {
    for (int c = 0; c < nc; c++)
      for (int k = 0; k < G->adj[c].n; k++) {
        int n = walk(G, c, k, sizes[s], rc, rk);
        if (!n || n > 16) continue;
        for (int t = 0; t < n; t++) {
          G->used[rc[t]][rk[t]] = 1;
          vs[t] = rc[t];
        }
        if (!sizes[s]) G->holes++;
        fill_loop(m, &G->faces, G->pos, vs, n);
      }
  }
}

/* neighbouring triangles whose union is a good quad become that quad (best first) */
typedef struct {
  int64_t key;
  int f, s;
} FE;

static int fe_cmp(const void *a, const void *b) {
  int64_t x = ((const FE *)a)->key, y = ((const FE *)b)->key;
  return (x > y) - (x < y);
}

typedef struct {
  double dev;
  int f1, f2, q[4];
} JC;

static int jc_cmp(const void *a, const void *b) {
  double x = ((const JC *)a)->dev, y = ((const JC *)b)->dev;
  return (x > y) - (x < y);
}

static int join_tris(Mem *m, Faces *F, const double *pos, int npts) {
  int nt = 0;
  for (int f = 0; f < F->n; f++) nt += fsize(&F->f[f]) == 3;
  if (nt < 2) return 0;
  FE *fe = (FE *)xmalloc(m, sizeof(FE) * 3 * (size_t)nt);
  int n = 0;
  for (int f = 0; f < F->n; f++) {
    if (fsize(&F->f[f]) != 3) continue;
    for (int s = 0; s < 3; s++) {
      int a = F->f[f].v[s], b = F->f[f].v[(s + 1) % 3];
      fe[n].key = a < b ? (int64_t)a * npts + b : (int64_t)b * npts + a;
      fe[n].f = f;
      fe[n].s = s;
      n++;
    }
  }
  qsort(fe, n, sizeof(FE), fe_cmp);
  JC *jc = (JC *)xmalloc(m, sizeof(JC) * (n / 2 + 1));
  int nj = 0;
  double cb = cos(35.0 * 3.14159265358979323846 / 180.0);
  for (int i = 0; i + 1 < n; i++) {
    if (fe[i].key != fe[i + 1].key || (i + 2 < n && fe[i + 2].key == fe[i].key) ||
        (i > 0 && fe[i - 1].key == fe[i].key))
      continue;
    const Face *f1 = &F->f[fe[i].f], *f2 = &F->f[fe[i + 1].f];
    int s = fe[i].s;
    int x0 = f1->v[s], x1 = f1->v[(s + 1) % 3], x2 = f1->v[(s + 2) % 3], y = -1;
    for (int k = 0; k < 3; k++)
      if (f2->v[k] != x0 && f2->v[k] != x1) y = f2->v[k];
    if (y < 0 || y == x2) continue;
    double e1[3], e2[3], n1[3], n2[3];
    sub3(&pos[3 * x1], &pos[3 * x0], e1);
    sub3(&pos[3 * x2], &pos[3 * x0], e2);
    cross3(e1, e2, n1);
    sub3(&pos[3 * x0], &pos[3 * x1], e1);
    sub3(&pos[3 * y], &pos[3 * x1], e2);
    cross3(e1, e2, n2);
    if (dot3(n1, n2) < cb * norm3(n1) * norm3(n2)) continue;
    int q[4] = {x0, y, x1, x2};
    double dev = 0.0;
    for (int k = 0; k < 4; k++) {
      double a = fabs(angle_deg(&pos[3 * q[(k + 3) % 4]], &pos[3 * q[k]], &pos[3 * q[(k + 1) % 4]]) - 90.0);
      if (a > dev) dev = a;
    }
    if (dev >= 40.0) continue;
    jc[nj].dev = dev;
    jc[nj].f1 = fe[i].f;
    jc[nj].f2 = fe[i + 1].f;
    memcpy(jc[nj].q, q, sizeof(q));
    nj++;
  }
  qsort(jc, nj, sizeof(JC), jc_cmp);
  unsigned char *gone = (unsigned char *)xcalloc(m, F->n, 1);
  int joined = 0;
  for (int k = 0; k < nj; k++) {
    if (gone[jc[k].f1] || gone[jc[k].f2]) continue;
    gone[jc[k].f1] = gone[jc[k].f2] = 1;
    memcpy(F->f[jc[k].f1].v, jc[k].q, sizeof(int) * 4);
    gone[jc[k].f1] = 2; /* replaced, keep */
    joined++;
  }
  int w = 0;
  for (int f = 0; f < F->n; f++)
    if (gone[f] != 1) F->f[w++] = F->f[f];
  F->n = w;
  return joined;
}

/* edges on more than two faces lose the worst-shaped extra faces; holes up to 16 sides are filled (any hole when
   the surface is closed, else only holes that are not all on hard edges / borders) */
static double face_bad(const double *pos, const Face *f) {
  if (fsize(f) == 4) return quad_score(pos, f->v);
  double s = 0.0;
  for (int k = 0; k < 3; k++)
    s += fabs(angle_deg(&pos[3 * f->v[(k + 2) % 3]], &pos[3 * f->v[k]], &pos[3 * f->v[(k + 1) % 3]]) - 60.0);
  return s + 60.0; /* a triangle goes before an equally bad quad */
}

static FE *face_edges(Mem *m, const Faces *F, int npts, int *n_out) {
  FE *fe = (FE *)xmalloc(m, sizeof(FE) * (4 * (size_t)F->n + 1));
  int n = 0;
  for (int f = 0; f < F->n; f++) {
    int s = fsize(&F->f[f]);
    for (int k = 0; k < s; k++) {
      int a = F->f[f].v[k], b = F->f[f].v[(k + 1) % s];
      fe[n].key = a < b ? (int64_t)a * npts + b : (int64_t)b * npts + a;
      fe[n].f = f;
      fe[n].s = k;
      n++;
    }
  }
  qsort(fe, n, sizeof(FE), fe_cmp);
  *n_out = n;
  return fe;
}

static void cleanup(Mem *m, Faces *F, const double *pos, const int *kind, int npts, int closed, int *st) {
  int removed = 0, filled = 0;
  for (int pass = 0; pass < 3; pass++) {
    int n;
    FE *fe = face_edges(m, F, npts, &n);
    unsigned char *gone = (unsigned char *)xcalloc(m, F->n + 1, 1);
    int any = 0;
    for (int i = 0; i < n;) {
      int j = i;
      while (j < n && fe[j].key == fe[i].key) j++;
      while (j - i > 2) {
        int live = 0, worst = -1;
        double wb = -1.0;
        for (int t = i; t < j; t++) {
          if (gone[fe[t].f]) continue;
          live++;
          double b = face_bad(pos, &F->f[fe[t].f]);
          if (b > wb) {
            wb = b;
            worst = fe[t].f;
          }
        }
        if (live <= 2 || worst < 0) break;
        gone[worst] = 1;
        removed++;
        any = 1;
      }
      i = j;
    }
    if (!any) break;
    int w = 0;
    for (int f = 0; f < F->n; f++)
      if (!gone[f]) F->f[w++] = F->f[f];
    F->n = w;
  }
  /* holes: a face side a->b with no neighbour means the hole runs b->a */
  int n;
  FE *fe = face_edges(m, F, npts, &n);
  int *nxt = (int *)xmalloc(m, sizeof(int) * (npts + 1));
  int *cnt = (int *)xcalloc(m, npts + 1, sizeof(int));
  for (int i = 0; i < npts; i++) nxt[i] = -1;
  for (int i = 0; i < n;) {
    int j = i;
    while (j < n && fe[j].key == fe[i].key) j++;
    if (j - i == 1) {
      const Face *f = &F->f[fe[i].f];
      int s = fsize(f), a = f->v[fe[i].s], b = f->v[(fe[i].s + 1) % s];
      nxt[b] = a;
      cnt[b]++;
    }
    i = j;
  }
  unsigned char *seen = (unsigned char *)xcalloc(m, npts + 1, 1);
  int vs[20];
  for (int v0 = 0; v0 < npts; v0++) {
    if (nxt[v0] < 0 || seen[v0]) continue;
    int len = 0, v = v0, ok = 1, soft = 0;
    while (!seen[v]) {
      seen[v] = 1;
      if (cnt[v] != 1 || nxt[v] < 0 || len >= 16) ok = 0;
      if (len < 20) vs[len] = v;
      len++;
      if (kind[v] == 0) soft = 1;
      v = nxt[v];
      if (v < 0) {
        ok = 0;
        break;
      }
    }
    if (!ok || v != v0 || len < 3 || len > 16 || (!closed && !soft)) continue;
    fill_loop(m, F, pos, vs, len);
    filled++;
  }
  st[0] = removed;
  st[1] = filled;
}

/* ---------- run ---------- */

/* hard-edge points onto the nearest hard edge (when one is that close), the rest onto the surface */
static void snap_points(Hash *tri, Hash *seg, double *pos, const int *kind, int from, int to, double reach) {
  double q[3], d[3];
  for (int c = from; c < to; c++) {
    if (kind[c] == 2) continue;
    if (kind[c] == 1 && seg->nprim > 0 && hash_nearest(seg, &pos[3 * c], q) >= 0) {
      sub3(q, &pos[3 * c], d);
      if (dot3(d, d) <= reach * reach) {
        memcpy(&pos[3 * c], q, sizeof(q));
        continue;
      }
    }
    if (hash_nearest(tri, &pos[3 * c], q) >= 0) memcpy(&pos[3 * c], q, sizeof(q));
  }
}

EXPORT int mquad_version(void) { return 1; }

EXPORT void mquad_free(MquadOut *out) {
  if (!out) return;
  free(out->V);
  free(out->F);
  free(out->fsrc);
  free(out->vsrc);
  out->V = NULL;
  out->F = out->fsrc = out->vsrc = NULL;
  out->nv = out->nf = 0;
}

EXPORT int mquad_run(int nlevels, const int *nv, const int *nf, const float *V, const int *F, const int *src,
                     const MquadOpts *opt, MquadOut *out) {
  if (nlevels < 1 || nlevels > MAXLEV || !opt || !out || opt->scale <= 0) return 1;
  memset(out, 0, sizeof(*out));
  Mem mem;
  memset(&mem, 0, sizeof(mem));
  if (setjmp(mem.jb)) {
    mem_free(&mem);
    mquad_free(out);
    return 2; /* out of memory */
  }
  double h = opt->scale;
  uint64_t rng = 0x9E3779B97F4A7C15ull ^ (uint64_t)(opt->seed + 1) * 0xBF58476D1CE4E5B9ull;
  double cos_cr = cos(opt->crease_deg * 3.14159265358979323846 / 180.0);
  Level *lv = (Level *)xcalloc(&mem, nlevels, sizeof(Level));
  size_t vo = 0, fo = 0, so = 0;
  for (int k = 0; k < nlevels; k++) {
    if (nv[k] < 3 || nf[k] < 1) {
      mem_free(&mem);
      return 3;
    }
    build_level(&mem, &lv[k], V + 3 * vo, nv[k], F + 3 * fo, nf[k], cos_cr, opt->min_chain, &rng);
    vo += nv[k];
    fo += nf[k];
  }
  for (int k = 0; k + 1 < nlevels; k++) {
    prolong_map(&mem, &lv[k], nv[k + 1], src + so);
    so += nv[k + 1];
  }
  int threads = opt->threads > 1 ? opt->threads : 1;
  /* orientation, coarse to fine */
  for (int k = nlevels - 1; k >= 0; k--) {
    Level *L = &lv[k];
    for (int i = 0; i < L->nv; i++) {
      double *q = &L->Q[3 * i];
      int u = (k + 1 < nlevels && L->up) ? L->up[i] : -1;
      if (u >= 0) {
        memcpy(q, &lv[k + 1].Q[3 * u], sizeof(double) * 3);
      } else {
        for (int d = 0; d < 3; d++) q[d] = (double)(rnd(&rng) % 2000001) / 1000000.0 - 1.0;
      }
      tangent3(q, &L->N[3 * i]);
      if (norm3(q) < 0.5) { /* (parallel to the normal) */
        double ax[3] = {1, 0, 0};
        if (fabs(L->N[3 * i]) > 0.9) {
          ax[0] = 0;
          ax[1] = 1;
        }
        cross3(&L->N[3 * i], ax, q);
        normalize3(q);
      }
    }
    for (int it = 0; it < opt->iters_orient[k]; it++) sweep(L, 0, h, threads);
  }
  /* position, coarse to fine */
  for (int k = nlevels - 1; k >= 0; k--) {
    Level *L = &lv[k];
    for (int i = 0; i < L->nv; i++) {
      double *o = &L->O[3 * i];
      const double *p = &L->P[3 * i], *n = &L->N[3 * i];
      int u = (k + 1 < nlevels && L->up) ? L->up[i] : -1;
      if (u >= 0) {
        memcpy(o, &lv[k + 1].O[3 * u], sizeof(double) * 3);
        double off = n[0] * (o[0] - p[0]) + n[1] * (o[1] - p[1]) + n[2] * (o[2] - p[2]);
        for (int d = 0; d < 3; d++) o[d] -= n[d] * off;
      } else {
        memcpy(o, p, sizeof(double) * 3);
      }
    }
    for (int it = 0; it < opt->iters_pos[k]; it++) sweep(L, 1, h, threads);
  }
  /* extraction on the fine level */
  Level *L0 = &lv[0];
  Graph G;
  memset(&G, 0, sizeof(G));
  extract(&mem, L0, h, &G, out->stats);
  out->stats[3] = G.holes;
  /* back onto the surface */
  Hash tri, seg;
  hash_build(&mem, &tri, L0->P, L0->nv, L0->F, L0->nf, 0, h);
  int nseg = 0;
  for (int e = 0; e < L0->ne; e++) nseg += L0->ecr[e];
  int *segi = (int *)xmalloc(&mem, sizeof(int) * 2 * (nseg + 1));
  nseg = 0;
  for (int e = 0; e < L0->ne; e++)
    if (L0->ecr[e]) {
      segi[2 * nseg] = L0->E[2 * e];
      segi[2 * nseg + 1] = L0->E[2 * e + 1];
      nseg++;
    }
  hash_build(&mem, &seg, L0->P, L0->nv, segi, nseg, 1, h);
  snap_points(&tri, &seg, G.pos, G.kind, 0, G.nc, h);
  int cst[2];
  cleanup(&mem, &G.faces, G.pos, G.kind, G.nc, L0->nbound == 0, cst);
  out->stats[3] += cst[1];
  out->stats[7] = cst[0];
  out->stats[4] = join_tris(&mem, &G.faces, G.pos, G.nc);
  double *pos = G.pos;
  int *kind = G.kind;
  int npts = G.nc;
  Faces *FF = &G.faces;
  Faces split;
  memset(&split, 0, sizeof(split));
  if (opt->all_quads && FF->n) {
    /* every face into quads: edge midpoints (on hard edges when the edge is sharp) + face centres */
    FE *fe = (FE *)xmalloc(&mem, sizeof(FE) * 4 * (size_t)FF->n);
    int n = 0;
    double *fn = (double *)xcalloc(&mem, 3 * (size_t)FF->n, sizeof(double));
    for (int f = 0; f < FF->n; f++) {
      int s = fsize(&FF->f[f]);
      for (int k = 0; k < s; k++) {
        int a = FF->f[f].v[k], b = FF->f[f].v[(k + 1) % s];
        double c[3];
        cross3(&pos[3 * a], &pos[3 * b], c);
        for (int d = 0; d < 3; d++) fn[3 * f + d] += c[d];
        fe[n].key = a < b ? (int64_t)a * npts + b : (int64_t)b * npts + a;
        fe[n].f = f;
        fe[n].s = k;
        n++;
      }
      normalize3(&fn[3 * f]);
    }
    qsort(fe, n, sizeof(FE), fe_cmp);
    int nedge = 0;
    for (int i = 0; i < n; i++)
      if (i == 0 || fe[i].key != fe[i - 1].key) nedge++;
    int total = npts + nedge + FF->n;
    double *np2 = (double *)xmalloc(&mem, sizeof(double) * 3 * (size_t)total);
    int *nk = (int *)xmalloc(&mem, sizeof(int) * total);
    memcpy(np2, pos, sizeof(double) * 3 * npts);
    memcpy(nk, kind, sizeof(int) * npts);
    int *emid = (int *)xmalloc(&mem, sizeof(int) * 4 * (size_t)FF->n); /* per face side: its midpoint */
    int w = npts;
    for (int i = 0; i < n;) {
      int j = i;
      while (j < n && fe[j].key == fe[i].key) j++;
      int a = (int)(fe[i].key / npts), b = (int)(fe[i].key % npts);
      int sharp = (j - i) != 2 || dot3(&fn[3 * fe[i].f], &fn[3 * fe[i + 1].f]) < cos_cr;
      for (int d = 0; d < 3; d++) np2[3 * w + d] = 0.5 * (pos[3 * a + d] + pos[3 * b + d]);
      nk[w] = sharp ? 1 : 0;
      for (int t = i; t < j; t++) emid[4 * fe[t].f + fe[t].s] = w;
      w++;
      i = j;
    }
    for (int f = 0; f < FF->n; f++) {
      int s = fsize(&FF->f[f]);
      int c = w++;
      for (int d = 0; d < 3; d++) {
        np2[3 * c + d] = 0.0;
        for (int k = 0; k < s; k++) np2[3 * c + d] += pos[3 * FF->f[f].v[k] + d] / s;
      }
      nk[c] = 0;
      for (int k = 0; k < s; k++)
        faces_add(&mem, &split, FF->f[f].v[k], emid[4 * f + k], c, emid[4 * f + (k + s - 1) % s]);
    }
    snap_points(&tri, &seg, np2, nk, npts, total, 0.5 * h);
    pos = np2;
    kind = nk;
    npts = total;
    FF = &split;
  }
  /* points no face uses go */
  int *remap = (int *)xmalloc(&mem, sizeof(int) * (npts + 1));
  for (int i = 0; i < npts; i++) remap[i] = -1;
  for (int f = 0; f < FF->n; f++)
    for (int k = 0; k < fsize(&FF->f[f]); k++) remap[FF->f[f].v[k]] = 0;
  int nout = 0;
  for (int i = 0; i < npts; i++)
    if (remap[i] == 0) remap[i] = nout++;
  out->V = (float *)malloc(sizeof(float) * 3 * (nout + 1));
  out->vsrc = (int *)malloc(sizeof(int) * (nout + 1));
  out->F = (int *)malloc(sizeof(int) * 4 * (FF->n + 1));
  out->fsrc = (int *)malloc(sizeof(int) * (FF->n + 1));
  if (!out->V || !out->vsrc || !out->F || !out->fsrc) longjmp(mem.jb, 1);
  double q[3];
  for (int i = 0; i < npts; i++) {
    int r = remap[i];
    if (r < 0) continue;
    for (int d = 0; d < 3; d++) out->V[3 * r + d] = (float)pos[3 * i + d];
    int t = hash_nearest(&tri, &pos[3 * i], q), best = 0;
    double bd = HUGE_VAL;
    for (int k = 0; t >= 0 && k < 3; k++) { /* the triangle's nearest corner */
      double d[3];
      sub3(&L0->P[3 * L0->F[3 * t + k]], &pos[3 * i], d);
      if (dot3(d, d) < bd) {
        bd = dot3(d, d);
        best = L0->F[3 * t + k];
      }
    }
    out->vsrc[r] = best;
  }
  int ntri = 0, nquad = 0;
  for (int f = 0; f < FF->n; f++) {
    const Face *fc = &FF->f[f];
    int s = fsize(fc);
    double c[3] = {0, 0, 0};
    for (int k = 0; k < 4; k++) {
      out->F[4 * f + k] = k < s ? remap[fc->v[k]] : -1;
      if (k < s)
        for (int d = 0; d < 3; d++) c[d] += pos[3 * fc->v[k] + d] / s;
    }
    int t = hash_nearest(&tri, c, q);
    out->fsrc[f] = t >= 0 ? t : 0;
    if (s == 3)
      ntri++;
    else
      nquad++;
  }
  out->nv = nout;
  out->nf = FF->n;
  out->stats[5] = ntri;
  out->stats[6] = nquad;
  mem_free(&mem);
  return 0;
}
