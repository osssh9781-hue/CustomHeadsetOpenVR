Mecha Lab v0.5.8: PNG-to-Vector Cut 프리셋과 썸네일, 메쉬 스탬프 불린 기능 추가. 자세한 안내는 PNG_CUT_GUIDE_KO.md 참조.

# Mecha Lab v0.5.7 — Simplified Edition

## What was removed
- Hard Surface Cleanup (Smart Remesh-inspired automatic face cleanup): completely unregistered and its module removed.
- Alpha Stamp / Paint Boolean / 3-View Sketch: entire alpha feature family removed, not just hidden.

## What remains
- Cut & Remove (rectangle / circle / freehand / polyline / custom polygon / regular N-gon); instant cut, continuous drawing, Alt inversion.
- Boolean Union/Difference/Intersect/Split Both, Smart Fuse, World/Local/Collection Mirror.
- Editable Panel Lines, Curve Profiles, Curve Array, Radial Array/Boolean, Surface Conform, Mesh Profile Library, Sculpt Move, and original one-click Voxel Remesh.

## UI
N > Mecha Lab now lists collapsible CUT, BOOLEAN, SMART FUSE, MIRROR first. Other features are collapsed underneath. Blender panel labels/icons cannot have arbitrary oversized font using the normal API.

## Cautions
- Painting a protection mask is NOT implemented in this package. Do not assume existing mesh masks protect from cut/boolean.
- The Space popup and session-only custom hotkeys are NOT included yet; B/C still register globally in Blender Object Mode.
- Bezier handles for Cut itself have not been added yet (editable Curve/Panel Path tools are separate).
- Smart Fuse is kept, but its successful operation requires two mesh objects selected, overlapping, with the active one as target. Specific failure screenshot needs exact Blender traceback for reproduction.
- Actual Blender 5.0.2 UI and mouse modal testing remains unverified; test on a duplicate .blend first.

## Installation
Blender > Edit > Preferences > Get Extensions > Install from Disk. Disable/uninstall older Mecha Lab versions first.
