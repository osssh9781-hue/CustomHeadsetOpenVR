# Claude Code project instructions — Mecha Lab

You are working on a **Blender 5.0.2 for Windows** modeling add-on. The user needs a 3DCoat/ZBrush-inspired dedicated `MECHA LAB` **workspace tab**, robust Cut / Split, shared shapes, and responsive non-blocking UI.

## Authority/precedence
1. `docs/00_LATEST_USER_DECISIONS_KO.md` — most recent, authoritative user decisions
2. `docs/01_WORKSPACE_UIUX_KO.md` — UI/UX architecture and workspace acceptance criteria
3. `docs/02_ALL_FEATURES_KO.md` — full functional requirements
4. `docs/03_BUGS_AND_REALITY_KO.md` and `docs/05_TEST_ACCEPTANCE_KO.md` — bugs and validation
5. Existing implementation — do not treat current code as proof that a feature works
6. `legacy/` — historical context only; may contradict newer decisions

## Source-of-truth code
`source/RELEASE_v0_5_9/mecha_lab/` is the **last released** source and must be preserved. WIP v0.6.0 is experimental and *not* validated. Create a separate working copy, do not overwrite the release. Original ZIP is in `archives/`.

## Non-negotiables
- Preserve Blender objects, mesh users, modifiers, materials, collection links, original scene data; require explicit destructive confirmation when necessary. All cut/boolean operations must have meaningful Undo/Redo and rollback on errors.
- A Python `register()` pass or headless `bpy` check is NOT proof that UI / keyboard / mouse modal operators work. Distinguish tested, untested, and known failing functions.
- Blender 5.0.2 GUI **first**; 5.2 and 4.5 headless smoke tests as secondary. Don't invent tests, timings, or compatibility.
- Do NOT resurrect removed voxel Alpha Boolean / Sketch Box / Organic/Hard Surface Smart Remesh modules. PNG-to-vector custom *Cut shape preset* stays in scope; do not confuse it with former voxel Alpha Boolean.
- `Cut` and `Split` are **separate tools**. The shared shape palette has Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Brush Stroke plus thumbnail cut presets. Random Polygon is not an independent item.
- `Space` tool palette is useful but dedicated workspace and left toolbar must work without it. Dedicated workspace must not permanently hijack unrelated Blender workspaces or shortcuts.
- If a feature cannot be safely completed, report it, isolate it, provide a fallback, and keep known working functionality intact. No unsupported "fully implemented" claims.

## Deliverables
1. A runnable add-on ZIP plus a reproducible creation/activation path for the `MECHA LAB` workspace; ideally optional workspace template `.blend` if feasible.
2. Regression tests and real GUI checklist, logs, timings and geometric validity tests.
3. Explicit list of done / partial / unimplemented and serious known limitations.
4. Separate changelog and return-handoff for ChatGPT review.

First read `START_HERE_KO.md`, `docs/00_LATEST_USER_DECISIONS_KO.md`, `docs/01_WORKSPACE_UIUX_KO.md`, and `docs/03_BUGS_AND_REALITY_KO.md` before editing code.
