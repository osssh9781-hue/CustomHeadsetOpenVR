/* mcloth: the constraint passes of Mecha Lab's position-based cloth (cloth_pbd.Cloth), plain arrays, multi-threaded,
 * loaded with ctypes.  Built into the same library as mdecim / mquad / mbake.
 *
 * 0.24.358 (user: "클로스가 좀 느린데 ... 마블러스는 좀 더 빠른 편이잖아", "c 엔진으로 옮겨 줘"): a 10k-point drape spent
 * 80 % of its time in the numpy Jacobi pass (cloth_pbd.Cloth._project).  The same pass here, the same rule and the
 * same order of sums (so the cloth folds the same way):
 *
 *   for every pair (a, b):  d = co[b] - co[a],  L = |d|,  c = clamp((L - rest) / L * k, -0.5, 0.5)
 *                           (and |c| <= maxmove / L when maxmove > 0)
 *                           da =  d * c * wa / (wa + wb),  db = -d * c * wb / (wa + wb)      (w = 1 / mass)
 *   every point:  co += (sum of its da + sum of its db) / max(1, number of its pairs)
 *
 * A "plan" is made once per pair list: for every point the pairs it is the first / second point of, in pair order
 * (the gather is then per point - no two threads write the same point, and every sum runs in the pair order numpy's
 * bincount uses).
 *
 *   void *mcloth_plan(int n, int m, const long long *pairs)          (pairs: m x 2 point indices)
 *   void  mcloth_plan_free(void *plan)
 *   int   mcloth_project(void *plan, double *co, const double *w, const double *rest, double strength, double sor,
 *                        double maxmove, int threads)                                (co: n x 3, changed in place; w: n; rest: m)
 *   int   mcloth_smooth(void *plan, double *co, double amount, int threads)
 *                        (the plan of the edges: every point toward the mean of its edge neighbours by amount) */
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

typedef struct {
  int n, m;
  int *pa, *pb;                 /* m: the pair's points */
  int *sa, *la;                 /* n + 1 / m: the pairs a point is the FIRST point of (CSR, in pair order) */
  int *sb, *lb;                 /* ... the SECOND point of */
  int *posa, *posb;             /* m: where the pair's da / db go in the per-point (CSR) order */
  double *dd;                   /* 2m x 3 scratch: the da's in the first points' order, then the db's in the second's */
  double *tmp;                  /* n x 3 scratch (smooth) */
} Plan;

typedef void (*CWorkFn)(void *ctx, int i0, int i1);

/* 0.24.358 a small pool of worker threads made once and kept (a thread made per call cost more than a pass of a 10k-
 * point cloth saves): the caller does the first share, the workers the rest; a generation counter wakes them. */
#define POOL_MAX 32
typedef struct {
  int nthreads, gen, busy, quit;
  CWorkFn f; void *ctx; int n, parts;
#ifdef _WIN32
  CRITICAL_SECTION mu; CONDITION_VARIABLE go, done; HANDLE th[POOL_MAX];
#else
  pthread_mutex_t mu; pthread_cond_t go, done; pthread_t th[POOL_MAX];
#endif
  int idx[POOL_MAX];
} Pool;
static Pool POOL;
static int pool_ready = 0;

static void pool_run_part(int k) {
  int i0 = (int)((long long)POOL.n * k / POOL.parts), i1 = (int)((long long)POOL.n * (k + 1) / POOL.parts);
  if (i1 > i0) POOL.f(POOL.ctx, i0, i1);
}

#ifdef _WIN32
static DWORD WINAPI pool_main(LPVOID p) {
#else
static void *pool_main(void *p) {
#endif
  int k = *(int *)p, seen = 0;
  for (;;) {
#ifdef _WIN32
    EnterCriticalSection(&POOL.mu);
    while (POOL.gen == seen && !POOL.quit) SleepConditionVariableCS(&POOL.go, &POOL.mu, INFINITE);
    seen = POOL.gen; int q = POOL.quit; int mine = k < POOL.parts;
    LeaveCriticalSection(&POOL.mu);
    if (q) return 0;
    if (mine) pool_run_part(k);
    EnterCriticalSection(&POOL.mu);
    if (--POOL.busy == 0) WakeAllConditionVariable(&POOL.done);
    LeaveCriticalSection(&POOL.mu);
#else
    pthread_mutex_lock(&POOL.mu);
    while (POOL.gen == seen && !POOL.quit) pthread_cond_wait(&POOL.go, &POOL.mu);
    seen = POOL.gen; int q = POOL.quit; int mine = k < POOL.parts;
    pthread_mutex_unlock(&POOL.mu);
    if (q) return NULL;
    if (mine) pool_run_part(k);
    pthread_mutex_lock(&POOL.mu);
    if (--POOL.busy == 0) pthread_cond_broadcast(&POOL.done);
    pthread_mutex_unlock(&POOL.mu);
#endif
  }
}

static int pool_start(int want) {
  if (pool_ready) return POOL.nthreads;
  memset(&POOL, 0, sizeof(POOL));
  int nt = want - 1; if (nt > POOL_MAX) nt = POOL_MAX; if (nt < 0) nt = 0;
#ifdef _WIN32
  InitializeCriticalSection(&POOL.mu); InitializeConditionVariable(&POOL.go); InitializeConditionVariable(&POOL.done);
  for (int k = 0; k < nt; k++) { POOL.idx[k] = k + 1; POOL.th[k] = CreateThread(NULL, 0, pool_main, &POOL.idx[k], 0, NULL); if (!POOL.th[k]) { nt = k; break; } }
#else
  pthread_mutex_init(&POOL.mu, NULL); pthread_cond_init(&POOL.go, NULL); pthread_cond_init(&POOL.done, NULL);
  for (int k = 0; k < nt; k++) { POOL.idx[k] = k + 1; if (pthread_create(&POOL.th[k], NULL, pool_main, &POOL.idx[k]) != 0) { nt = k; break; } }
#endif
  POOL.nthreads = nt;
  pool_ready = 1;
  return nt;
}

static int cpool_lock_free = 1;                      /* (one caller at a time: Blender's Python runs one at a time) */

static void cparallel(CWorkFn f, void *ctx, int n, int threads) {
  int want = threads < 1 ? 1 : (threads > POOL_MAX + 1 ? POOL_MAX + 1 : threads);
  if (n < 8192 || want < 2 || !cpool_lock_free) { f(ctx, 0, n); return; }
  int nw = pool_start(want);
  if (nw < 1) { f(ctx, 0, n); return; }
  int parts = nw + 1; if (parts > want) parts = want;
  cpool_lock_free = 0;
#ifdef _WIN32
  EnterCriticalSection(&POOL.mu);
#else
  pthread_mutex_lock(&POOL.mu);
#endif
  POOL.f = f; POOL.ctx = ctx; POOL.n = n; POOL.parts = parts; POOL.busy = nw; POOL.gen++;
#ifdef _WIN32
  WakeAllConditionVariable(&POOL.go);
  LeaveCriticalSection(&POOL.mu);
#else
  pthread_cond_broadcast(&POOL.go);
  pthread_mutex_unlock(&POOL.mu);
#endif
  int i1 = (int)((long long)n / parts);                /* (the caller's share: part 0) */
  if (i1 > 0) f(ctx, 0, i1);
#ifdef _WIN32
  EnterCriticalSection(&POOL.mu);
  while (POOL.busy > 0) SleepConditionVariableCS(&POOL.done, &POOL.mu, INFINITE);
  LeaveCriticalSection(&POOL.mu);
#else
  pthread_mutex_lock(&POOL.mu);
  while (POOL.busy > 0) pthread_cond_wait(&POOL.done, &POOL.mu);
  pthread_mutex_unlock(&POOL.mu);
#endif
  cpool_lock_free = 1;
}

EXPORT int mcloth_version(void) { return 3; }

EXPORT void mcloth_plan_free(void *plan) {
  Plan *P = (Plan *)plan;
  if (!P) return;
  free(P->pa); free(P->pb); free(P->sa); free(P->la); free(P->sb); free(P->lb); free(P->dd); free(P->tmp);
  free(P->posa); free(P->posb);
  free(P);
}

EXPORT void *mcloth_plan(int n, int m, const long long *pairs) {
  if (n < 0 || m < 0) return NULL;
  Plan *P = (Plan *)calloc(1, sizeof(Plan));
  if (!P) return NULL;
  P->n = n; P->m = m;
  P->pa = (int *)malloc(sizeof(int) * (m ? m : 1)); P->pb = (int *)malloc(sizeof(int) * (m ? m : 1));
  P->sa = (int *)calloc(n + 1, sizeof(int)); P->sb = (int *)calloc(n + 1, sizeof(int));
  P->la = (int *)malloc(sizeof(int) * (m ? m : 1)); P->lb = (int *)malloc(sizeof(int) * (m ? m : 1));
  P->dd = (double *)malloc(sizeof(double) * 6 * (m ? m : 1));
  P->posa = (int *)malloc(sizeof(int) * (m ? m : 1)); P->posb = (int *)malloc(sizeof(int) * (m ? m : 1));
  P->tmp = (double *)malloc(sizeof(double) * 3 * (n ? n : 1));
  if (!P->pa || !P->pb || !P->sa || !P->sb || !P->la || !P->lb || !P->dd || !P->tmp || !P->posa || !P->posb) {
    mcloth_plan_free(P); return NULL;
  }
  for (int i = 0; i < m; i++) {
    long long a = pairs[2 * i], b = pairs[2 * i + 1];
    if (a < 0 || b < 0 || a >= n || b >= n) { mcloth_plan_free(P); return NULL; }
    P->pa[i] = (int)a; P->pb[i] = (int)b;
    P->sa[a + 1]++; P->sb[b + 1]++;
  }
  for (int p = 0; p < n; p++) { P->sa[p + 1] += P->sa[p]; P->sb[p + 1] += P->sb[p]; }
  int *fa = (int *)malloc(sizeof(int) * (n ? n : 1)), *fb = (int *)malloc(sizeof(int) * (n ? n : 1));
  if (!fa || !fb) { free(fa); free(fb); mcloth_plan_free(P); return NULL; }
  memcpy(fa, P->sa, sizeof(int) * n); memcpy(fb, P->sb, sizeof(int) * n);
  for (int i = 0; i < m; i++) {                                                              /* (pair order kept) */
    P->posa[i] = fa[P->pa[i]]; P->la[fa[P->pa[i]]++] = i;
    P->posb[i] = fb[P->pb[i]]; P->lb[fb[P->pb[i]]++] = i;
  }
  free(fa); free(fb);
  return P;
}

typedef struct { Plan *P; double *co; const double *w; const double *rest; double k, sor, maxmove, amount; } Job;

static void pair_work(void *ctx, int i0, int i1) {
  Job *J = (Job *)ctx; Plan *P = J->P;
  const double *co = J->co;
  for (int i = i0; i < i1; i++) {
    int a = P->pa[i], b = P->pb[i];
    double dx = co[3 * b] - co[3 * a], dy = co[3 * b + 1] - co[3 * a + 1], dz = co[3 * b + 2] - co[3 * a + 2];
    double L = sqrt(dx * dx + dy * dy + dz * dz);
    if (L < 1e-12) L = 1e-12;
    double c = (L - J->rest[i]) / L * J->k * J->sor;           /* (numpy: (L - rest) / L * strength * sor) */
    if (c < -0.5) c = -0.5; else if (c > 0.5) c = 0.5;
    if (J->maxmove > 0.0) { double lim = J->maxmove / L; if (c < -lim) c = -lim; else if (c > lim) c = lim; }
    double wa = J->w ? J->w[a] : 1.0, wb = J->w ? J->w[b] : 1.0, ws = wa + wb;
    double fa = c * wa / ws, fb = c * wb / ws;
    double *oa = P->dd + 3 * (size_t)P->posa[i], *ob = P->dd + 3 * ((size_t)P->m + P->posb[i]);
    oa[0] = dx * fa; oa[1] = dy * fa; oa[2] = dz * fa;
    ob[0] = -dx * fb; ob[1] = -dy * fb; ob[2] = -dz * fb;
  }
}

static void point_work(void *ctx, int p0, int p1) {
  Job *J = (Job *)ctx; Plan *P = J->P;
  for (int p = p0; p < p1; p++) {
    int ka = P->sa[p], ea = P->sa[p + 1], kb = P->sb[p], eb = P->sb[p + 1];
    int deg = (ea - ka) + (eb - kb);
    if (!deg) continue;
    double ax = 0, ay = 0, az = 0, bx = 0, by = 0, bz = 0;
    const double *oa = P->dd + 3 * (size_t)ka, *ob = P->dd + 3 * ((size_t)P->m + kb);      /* (contiguous) */
    for (int t = ka; t < ea; t++, oa += 3) { ax += oa[0]; ay += oa[1]; az += oa[2]; }
    for (int t = kb; t < eb; t++, ob += 3) { bx += ob[0]; by += ob[1]; bz += ob[2]; }
    J->co[3 * p] += (ax + bx) / deg; J->co[3 * p + 1] += (ay + by) / deg; J->co[3 * p + 2] += (az + bz) / deg;
  }
}

EXPORT int mcloth_project(void *plan, double *co, const double *w, const double *rest, double k, double sor,
                          double maxmove, int threads) {
  Plan *P = (Plan *)plan;
  if (!P || !co || !rest) return 1;
  if (!P->m) return 0;
  Job J = { P, co, w, rest, k, sor, maxmove, 0.0 };
  cparallel(pair_work, &J, P->m, threads);       /* (every correction from the points as they were: Jacobi) */
  cparallel(point_work, &J, P->n, threads);
  return 0;
}

static void smooth_work(void *ctx, int p0, int p1) {
  Job *J = (Job *)ctx; Plan *P = J->P;
  const double *src = P->tmp;
  for (int p = p0; p < p1; p++) {
    int ka = P->sa[p], ea = P->sa[p + 1], kb = P->sb[p], eb = P->sb[p + 1];
    int deg = (ea - ka) + (eb - kb);
    double ax = 0, ay = 0, az = 0, bx = 0, by = 0, bz = 0;
    for (int t = ka; t < ea; t++) { int q = P->pb[P->la[t]]; ax += src[3 * q]; ay += src[3 * q + 1]; az += src[3 * q + 2]; }
    for (int t = kb; t < eb; t++) { int q = P->pa[P->lb[t]]; bx += src[3 * q]; by += src[3 * q + 1]; bz += src[3 * q + 2]; }
    double dv = deg > 0 ? (double)deg : 1.0;
    double mx = (ax + bx) / dv, my = (ay + by) / dv, mz = (az + bz) / dv;
    J->co[3 * p] += (mx - src[3 * p]) * J->amount;
    J->co[3 * p + 1] += (my - src[3 * p + 1]) * J->amount;
    J->co[3 * p + 2] += (mz - src[3 * p + 2]) * J->amount;
  }
}

EXPORT int mcloth_smooth(void *plan, double *co, double amount, int threads) {
  Plan *P = (Plan *)plan;
  if (!P || !co) return 1;
  memcpy(P->tmp, co, sizeof(double) * 3 * (size_t)P->n);
  Job J = { P, co, NULL, NULL, 0.0, 1.0, 0.0, amount };
  cparallel(smooth_work, &J, P->n, threads);
  return 0;
}

/* GridCollider.push (cloth_pbd.py) - the same look-up, in the same float types as the numpy one (the weights and the
 * distance in float32, the push in float64), so the points end where they did:
 *   f = (co - origin) / cell - 0.5,  i0 = floor(f),  t = (float)(f - i0),  inside = 0 <= i0 and i0 + 1 < dims
 *   d = sum over the 8 corners of w * sdf (FAR outside),  a point with d < margin moves along the trilinear gradient
 *   (normalised) by margin - d.  touch[i] = d < margin * touch_at.  Returns how many were moved. */
typedef struct {
  double *co; const double *origin; double cell; const long long *dims, *strides; const float *sdf, *grad;
  float margin, touch; unsigned char *touch_out; int moved;
} PushJob;

static int push_range(PushJob *J, int i0_, int i1_) {
  int moved = 0;
  for (int i = i0_; i < i1_; i++) {
    double *p = J->co + 3 * (size_t)i;
    long long ii[3]; float t[3]; int inside = 1; long long base = 0;
    for (int k = 0; k < 3; k++) {
      double f = (p[k] - J->origin[k]) / J->cell - 0.5;
      double fl = floor(f);
      ii[k] = (long long)fl;
      t[k] = (float)(f - (double)ii[k]);
      if (ii[k] < 0 || ii[k] + 1 >= J->dims[k]) inside = 0;
      long long c = ii[k] < 0 ? 0 : (ii[k] > J->dims[k] - 2 ? J->dims[k] - 2 : ii[k]);
      base += c * J->strides[k];
    }
    float d = 0.0f, gx = 0.0f, gy = 0.0f, gz = 0.0f;
    float w8[8]; long long id8[8]; int c8 = 0;
    for (int dx = 0; dx < 2; dx++) {
      float wx = dx ? t[0] : 1.0f - t[0];
      for (int dy = 0; dy < 2; dy++) {
        float wy = wx * (dy ? t[1] : 1.0f - t[1]);
        for (int dz = 0; dz < 2; dz++) {
          float w = wy * (dz ? t[2] : 1.0f - t[2]);
          long long idx = base + dx * J->strides[0] + dy * J->strides[1] + dz;
          d += w * J->sdf[idx];
          w8[c8] = w; id8[c8] = idx; c8++;
        }
      }
    }
    if (!inside) d = 1e9f;
    if (J->touch_out) J->touch_out[i] = d < J->touch;
    if (d < J->margin) {
      for (int c = 0; c < 8; c++) {
        const float *g = J->grad + 3 * id8[c];
        gx += w8[c] * g[0]; gy += w8[c] * g[1]; gz += w8[c] * g[2];
      }
      double Gx = gx, Gy = gy, Gz = gz;
      double ln = sqrt(Gx * Gx + Gy * Gy + Gz * Gz);
      if (ln < 1e-9) ln = 1.0;
      float md = J->margin - d;
      p[0] += Gx / ln * (double)md; p[1] += Gy / ln * (double)md; p[2] += Gz / ln * (double)md;
      moved++;
    }
  }
  return moved;
}

static void push_work(void *ctx, int i0, int i1) { push_range((PushJob *)ctx, i0, i1); }

EXPORT int mcloth_push(int n, double *co, const double *origin, double cell, const long long *dims,
                       const long long *strides, const float *sdf, const float *grad, double margin, double touch_at,
                       unsigned char *touch, int threads) {
  if (!co || !sdf || !grad || cell <= 0.0) return -1;
  PushJob J = { co, origin, cell, dims, strides, sdf, grad, (float)margin, (float)(margin * touch_at), touch, 0 };
  if (n < 8192 || threads <= 1) return push_range(&J, 0, n);
  cparallel(push_work, &J, n, threads);
  return 0;
}

/* ring_pairs (cloth_pbd.py): point pairs exactly r edges apart (r = 1..R), a BFS from every point over the edge graph
 * - the same order as the Python one (neighbours in edge order, BFS frontier order, (u, w) with w > u), so the wide
 * bending constraints come out the same.  With out == NULL only counts[r] (r = 0..R) are filled; then call again
 * with out (2 x total) and offs[r] = where ring r starts (in pairs).  Returns 0, 2 out of memory. */
EXPORT int mcloth_ring_pairs(int n, int m, const long long *edges, int R, long long *counts, long long *out,
                             const long long *offs) {
  if (n <= 0 || R < 1) return 0;
  int *deg = (int *)calloc(n + 1, sizeof(int));
  if (!deg) return 2;
  for (int i = 0; i < m; i++) { deg[edges[2 * i] + 1]++; deg[edges[2 * i + 1] + 1]++; }
  for (int p = 0; p < n; p++) deg[p + 1] += deg[p];
  int *nb = (int *)malloc(sizeof(int) * (2 * (size_t)m + 1)), *fill = (int *)malloc(sizeof(int) * (n + 1));
  int *stamp = (int *)calloc(n, sizeof(int)), *fr = (int *)malloc(sizeof(int) * (n + 1)), *nx = (int *)malloc(sizeof(int) * (n + 1));
  long long *pos = (long long *)calloc(R + 1, sizeof(long long));
  if (!nb || !fill || !stamp || !fr || !nx || !pos) { free(deg); free(nb); free(fill); free(stamp); free(fr); free(nx); free(pos); return 2; }
  memcpy(fill, deg, sizeof(int) * n);
  for (int i = 0; i < m; i++) {                        /* (python: nb[a].append(b); nb[b].append(a), in edge order) */
    int a = (int)edges[2 * i], b = (int)edges[2 * i + 1];
    nb[fill[a]++] = b; nb[fill[b]++] = a;
  }
  if (!out) for (int r = 0; r <= R; r++) counts[r] = 0;
  for (int u = 0; u < n; u++) {
    int mark = u + 1;
    stamp[u] = mark;
    int nf = 1; fr[0] = u;
    for (int r = 1; r <= R; r++) {
      int nn = 0;
      for (int k = 0; k < nf; k++) {
        int v = fr[k];
        for (int t = deg[v]; t < deg[v + 1]; t++) {
          int w = nb[t];
          if (stamp[w] != mark) { stamp[w] = mark; nx[nn++] = w; }
        }
      }
      for (int k = 0; k < nn; k++) if (nx[k] > u) {
        if (!out) counts[r]++;
        else { long long q = offs[r] + pos[r]++; out[2 * q] = u; out[2 * q + 1] = nx[k]; }
      }
      int *tmp = fr; fr = nx; nx = tmp; nf = nn;
      if (!nf) break;
    }
  }
  free(deg); free(nb); free(fill); free(stamp); free(fr); free(nx); free(pos);
  return 0;
}

/* GridCollider.__init__ (cloth_pbd.py): every collider point splats its tangent plane into the cells within ``band``
 * of it; a cell keeps its nearest point (the LAST of equally near ones, as the numpy chunks do).  best (total doubles,
 * +inf), sdf (total floats, FAR) and grad (3 x total floats, 0) are filled in.  Returns 0. */
EXPORT int mcloth_splat(int np_, const double *P, const double *N, const double *lo, double cell, const long long *dims,
                        const long long *strides, int band, double *best, float *sdf, float *grad) {
  for (int i = 0; i < np_; i++) {
    const double *p = P + 3 * (size_t)i, *nr = N + 3 * (size_t)i;
    long long ijk[3];
    for (int k = 0; k < 3; k++) ijk[k] = (long long)floor((p[k] - lo[k]) / cell);
    for (int ox = -band; ox <= band; ox++) {
      long long cx = ijk[0] + ox; if (cx < 0 || cx >= dims[0]) continue;
      for (int oy = -band; oy <= band; oy++) {
        long long cy = ijk[1] + oy; if (cy < 0 || cy >= dims[1]) continue;
        for (int oz = -band; oz <= band; oz++) {
          long long cz = ijk[2] + oz; if (cz < 0 || cz >= dims[2]) continue;
          long long f = cx * strides[0] + cy * strides[1] + cz * strides[2];
          double ex = lo[0] + ((double)cx + 0.5) * cell, ey = lo[1] + ((double)cy + 0.5) * cell, ez = lo[2] + ((double)cz + 0.5) * cell;
          double dx = ex - p[0], dy = ey - p[1], dz = ez - p[2];
          double d2 = dx * dx + dy * dy + dz * dz;
          if (d2 <= best[f]) {
            best[f] = d2;
            sdf[f] = (float)(dx * nr[0] + dy * nr[1] + dz * nr[2]);
            grad[3 * f] = (float)nr[0]; grad[3 * f + 1] = (float)nr[1]; grad[3 * f + 2] = (float)nr[2];
          }
        }
      }
    }
  }
  return 0;
}
