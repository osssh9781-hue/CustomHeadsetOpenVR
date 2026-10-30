"""0.24.93 Paint Lab: the pure maths (photo adjust, brightness mask, edge mask) - the workspace / brushes / masks
on a mesh follow below once the tab exists."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import paint_lab_core as pc

mecha_lab.register()
fresh()
C = bpy.context

# -- photo adjust (pure) -------------------------------------------------------------------------------------
rng = np.random.default_rng(1)
im = rng.random((64, 48, 4), np.float32)
check('adjust with nothing set is the identity (alpha kept)', np.array_equal(pc.adjust(im), im))
red = np.array([[[1.0, 0.0, 0.0, 1.0]]], np.float32)
h120 = pc.adjust(red, hue=120)[0, 0, :3]
check('Hue +120 turns red toward green (HSV direction)', h120[1] > 0.6 and h120[0] < 0.1 and h120[2] < 0.1, tuple(h120.round(3)))
check('Saturation 0 = the luminance grey (0.299 for red)', np.allclose(pc.adjust(red, saturation=0)[0, 0, :3], 0.299, atol=1e-3))
grey = np.array([[[0.6, 0.6, 0.6, 1.0]]], np.float32)
check('Contrast about mid grey: 0.6 -> 0.7 at x2, brightness +0.1 adds', abs(pc.adjust(grey, contrast=2)[0, 0, 0] - 0.7) < 1e-5
      and abs(pc.adjust(grey, brightness=0.1)[0, 0, 0] - 0.7) < 1e-5)
check('Clipped to 0..1, flips reverse the axes', pc.adjust(grey, brightness=5)[0, 0, 0] == 1.0
      and np.array_equal(pc.adjust(im, flip_x=True), im[:, ::-1]) and np.array_equal(pc.adjust(im, flip_y=True), im[::-1]))

# -- the masks (pure) ----------------------------------------------------------------------------------------
cols = np.array([[0, 0, 0, 1], [0.5, 0.5, 0.5, 1], [1, 1, 1, 1], [1, 0, 0, 1]])
check('value_mask: brightness 0..1 straight (red = 0.299), a black / white range, invert',
      np.allclose(pc.value_mask(cols), [0, 0.5, 1, 0.299], atol=1e-3) and np.allclose(pc.value_mask(cols, 0.25, 0.75), [0, 0.5, 1, 0.098], atol=1e-3)
      and np.allclose(pc.value_mask(cols, invert=True), [1, 0.5, 0, 0.701], atol=1e-3))
co = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
vi = np.array([i for f in faces for i in f]); start = np.arange(0, 24, 4); tot = np.full(6, 4)
check('edge_angles: every cube corner sits on 90-degree folds', np.allclose(pc.edge_angles(co, vi, start, tot, 8), 90.0))
g = np.array([[x, y, 0] for y in range(3) for x in range(3)], float)
gf = [(y * 3 + x, y * 3 + x + 1, (y + 1) * 3 + x + 1, (y + 1) * 3 + x) for y in range(2) for x in range(2)]
gvi = np.array([i for f in gf for i in f]); gs = np.arange(0, 16, 4); gt = np.full(4, 4)
check('... and a flat grid has none; edge_mask 1 on the cube, 0 on the grid, grow spreads one ring',
      pc.edge_angles(g, gvi, gs, gt, 9).max() == 0 and np.all(pc.edge_mask(co, vi, start, tot, 8) == 1)
      and np.all(pc.edge_mask(g, gvi, gs, gt, 9) == 0)
      and np.array_equal(pc.grow_mask(np.array([1, 0, 0, 0, 0, 0, 0, 0, 0.]), gvi, gs, gt, 9, 1), [1, 1, 0, 1, 0, 0, 0, 0, 0]))
check('corner_to_point averages corner colours onto points', np.allclose(pc.corner_to_point(np.ones((24, 4)) * 0.5, vi, 8), 0.5))
summary()
