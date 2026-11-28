/* mcut: helpers for Mecha Lab's cut engine, plain arrays, multi-threaded, loaded with ctypes.  Built into the same
 * library as mdecim / mquad / mbake / mcloth.
 *
 * 0.24.363 (user: "왜 라인으로 자르는 건 엄청 느려?"): a line cut's cutter is half of the part (a polygon to the view's
 * box, extruded), so the "only the faces round the cutter" boolean found most of the part round it and the whole
 * part went through the boolean (5 M faces: 40 - 60 s).  The faces away from the cutter's surface only have to be
 * told inside / outside: this does it for millions of points at once.
 *
 *   int mcut_inside(int n, const double *P, int nt, const double *T, unsigned char *out, int threads)
 *     P: n points (3 each); T: nt triangles (9 doubles each) of a CLOSED mesh; out[i] = 1 when point i is inside
 *     (a ray along +X, its crossings counted - odd = inside; the ray is nudged a hair off the axis so it never runs
 *     through an edge).  The triangles are binned on a (y, z) grid: a ray only looks at the cells it runs through.
 *     Returns 0, 1 bad input, 2 out of memory. */
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
  const double *P, *T; unsigned char *out;
  int G; double y0, z0, cy, cz, ny, nz;          /* the (y, z) grid */
  const int *cs, *cl;                            /* cell start (G*G+1), triangle list */
} InJob;

static int ray_tri(const double *o, const double *t) {
  /* ray o + s (1, 0, 0), s > 0, against triangle t (Moller-Trumbore with d = +X) */
  double e1x = t[3] - t[0], e1y = t[4] - t[1], e1z = t[5] - t[2];
  double e2x = t[6] - t[0], e2y = t[7] - t[1], e2z = t[8] - t[2];
  /* p = d x e2 = (0, -e2z, e2y) */
  double px = 0.0, py = -e2z, pz = e2y;
  double det = e1x * px + e1y * py + e1z * pz;
  if (fabs(det) < 1e-300) return 0;
  double inv = 1.0 / det;
  double tx = o[0] - t[0], ty = o[1] - t[1], tz = o[2] - t[2];
  double u = (tx * px + ty * py + tz * pz) * inv;
  if (u < 0.0 || u > 1.0) return 0;
  double qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x;
  double v = (qx) * inv;                          /* d . q with d = +X */
  if (v < 0.0 || u + v > 1.0) return 0;
  double s = (e2x * qx + e2y * qy + e2z * qz) * inv;
  return s > 0.0;
}

static void in_work(InJob *J, int i0, int i1) {
  for (int i = i0; i < i1; i++) {
    double o[3] = { J->P[3 * (size_t)i], J->P[3 * (size_t)i + 1] + 1.234567e-7 * J->cy, J->P[3 * (size_t)i + 2] + 2.345678e-7 * J->cz };
    int gy = (int)floor((o[1] - J->y0) / J->cy), gz = (int)floor((o[2] - J->z0) / J->cz);
    if (gy < 0 || gz < 0 || gy >= J->G || gz >= J->G) { J->out[i] = 0; continue; }
    int c = gy * J->G + gz, hits = 0;
    for (int k = J->cs[c]; k < J->cs[c + 1]; k++) hits += ray_tri(o, J->T + 9 * (size_t)J->cl[k]);
    J->out[i] = (unsigned char)(hits & 1);
  }
}

typedef struct { InJob *J; int i0, i1; } InPart;
#ifdef _WIN32
static DWORD WINAPI in_thread(LPVOID p) { InPart *w = (InPart *)p; in_work(w->J, w->i0, w->i1); return 0; }
#else
static void *in_thread(void *p) { InPart *w = (InPart *)p; in_work(w->J, w->i0, w->i1); return NULL; }
#endif

EXPORT int mcut_version(void) { return 1; }

EXPORT int mcut_inside(int n, const double *P, int nt, const double *T, unsigned char *out, int threads) {
  if (n < 0 || nt < 0 || !P || !T || !out) return 1;
  if (!nt) { memset(out, 0, (size_t)n); return 0; }
  double y0 = 1e300, y1 = -1e300, z0 = 1e300, z1 = -1e300;
  for (int k = 0; k < nt; k++) for (int c = 0; c < 3; c++) {
    double y = T[9 * (size_t)k + 3 * c + 1], z = T[9 * (size_t)k + 3 * c + 2];
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
    if (z < z0) z0 = z;
    if (z > z1) z1 = z;
  }
  double pad = 1e-9 * (fabs(y1 - y0) + fabs(z1 - z0) + 1e-12);
  y0 -= pad; z0 -= pad; y1 += pad; z1 += pad;
  int G = (int)sqrt((double)nt) * 2 + 1; if (G > 512) G = 512;
  double cy = (y1 - y0) / G, cz = (z1 - z0) / G;
  if (cy <= 0) cy = 1e-12;
  if (cz <= 0) cz = 1e-12;
  int *cs = (int *)calloc((size_t)G * G + 1, sizeof(int));
  if (!cs) return 2;
  int *cnt = (int *)calloc((size_t)G * G, sizeof(int));
  if (!cnt) { free(cs); return 2; }
  for (int k = 0; k < nt; k++) {
    const double *t = T + 9 * (size_t)k;
    double a = fmin(t[1], fmin(t[4], t[7])), b = fmax(t[1], fmax(t[4], t[7]));
    double c = fmin(t[2], fmin(t[5], t[8])), d = fmax(t[2], fmax(t[5], t[8]));
    int ya = (int)floor((a - y0) / cy), yb = (int)floor((b - y0) / cy), za = (int)floor((c - z0) / cz), zb = (int)floor((d - z0) / cz);
    if (ya < 0) ya = 0;
    if (za < 0) za = 0;
    if (yb >= G) yb = G - 1;
    if (zb >= G) zb = G - 1;
    for (int y = ya; y <= yb; y++) for (int z = za; z <= zb; z++) cnt[y * G + z]++;
  }
  for (int c = 0; c < G * G; c++) cs[c + 1] = cs[c] + cnt[c];
  int *cl = (int *)malloc(sizeof(int) * (size_t)(cs[G * G] ? cs[G * G] : 1));
  if (!cl) { free(cs); free(cnt); return 2; }
  memset(cnt, 0, sizeof(int) * (size_t)G * G);
  for (int k = 0; k < nt; k++) {
    const double *t = T + 9 * (size_t)k;
    double a = fmin(t[1], fmin(t[4], t[7])), b = fmax(t[1], fmax(t[4], t[7]));
    double c = fmin(t[2], fmin(t[5], t[8])), d = fmax(t[2], fmax(t[5], t[8]));
    int ya = (int)floor((a - y0) / cy), yb = (int)floor((b - y0) / cy), za = (int)floor((c - z0) / cz), zb = (int)floor((d - z0) / cz);
    if (ya < 0) ya = 0;
    if (za < 0) za = 0;
    if (yb >= G) yb = G - 1;
    if (zb >= G) zb = G - 1;
    for (int y = ya; y <= yb; y++) for (int z = za; z <= zb; z++) { int cc = y * G + z; cl[cs[cc] + cnt[cc]++] = k; }
  }
  free(cnt);
  InJob J = { P, T, out, G, y0, z0, cy, cz, 0, 0, cs, cl };
  int nth = threads < 1 ? 1 : (threads > 64 ? 64 : threads);
  if (n < 65536) nth = 1;
  InPart w[64];
  for (int k = 0; k < nth; k++) { w[k].J = &J; w[k].i0 = (int)((long long)n * k / nth); w[k].i1 = (int)((long long)n * (k + 1) / nth); }
#ifdef _WIN32
  HANDLE th[64];
  for (int k = 1; k < nth; k++) th[k] = CreateThread(NULL, 0, in_thread, &w[k], 0, NULL);
  in_work(&J, w[0].i0, w[0].i1);
  for (int k = 1; k < nth; k++) if (th[k]) { WaitForSingleObject(th[k], INFINITE); CloseHandle(th[k]); } else in_work(&J, w[k].i0, w[k].i1);
#else
  pthread_t th[64]; int ok[64];
  for (int k = 1; k < nth; k++) ok[k] = pthread_create(&th[k], NULL, in_thread, &w[k]) == 0;
  in_work(&J, w[0].i0, w[0].i1);
  for (int k = 1; k < nth; k++) { if (ok[k]) pthread_join(th[k], NULL); else in_work(&J, w[k].i0, w[k].i1); }
#endif
  free(cs); free(cl);
  return 0;
}
