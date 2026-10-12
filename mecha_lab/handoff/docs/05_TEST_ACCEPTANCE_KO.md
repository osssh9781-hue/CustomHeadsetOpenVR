# Mecha Lab 테스트 / 수용 기준

## 반드시 구분
1. **정적 검사**(compile, import, register) 2. **headless bpy 기하** 3. **실제 Blender GUI 이벤트** 4. **사용자 5.0.2 환경**. 첫 두 단계가 셋·넷을 보증하지 않습니다. 기능별 검증 레벨과 에러를 표시하세요.

## GUI 수용 시나리오 (Blender 5.0.2, Windows)
- [ ] 설치/활성화 후 기존 workspace와 keymap 변화 없이 `MECHA LAB` Workspace 생성 가능.
- [ ] 상단 탭 전환해도 기존 Layout/Modeling/Sculpting 보존. Workspace 안에서만 커스텀 hotkeys 작동. 비활성화/제거 시 Blender 기본 상태로 복귀.
- [ ] 왼쪽 large tool icons+names (Cut/Split/Boolean/Smart Fuse/Mirror first), 위쪽 왼쪽 6 shape brushes, 오른쪽 선택한 tool settings만 표시.
- [ ] Space 큰 tool picker 메뉴 열림(실패 시 왼쪽 도구로 동일 기능 가능). Space 단축키가 Cut modal 중 confirm과 충돌하지 않음.
- [ ] Cut 중 RMB single shared shape preset popup. RMB double exits; single popup가 먼저 실행돼 double을 가로막지 않음. 해당 타이밍 사용자 확인.
- [ ] Shape 전환/오른쪽 Width/Depth·Bevel/Chamfer 변경/다른 Editor 클릭 후에도 ESC 없이 정상 조작.
- [ ] Enter/LMB double 한 획 확정 후 Cut 상태 유지, double 입력으로 마지막 점 두 번 찍히지 않음; ESC current stroke만 취소.
- [ ] Ctrl+Z 독립 Cut 1개만 undo, Ctrl+Shift+Z redo. 그리는 중 point undo와 최종 cut undo 일관됨.
- [ ] Mask Brush Stroke가 실제 누적·Alt 차감·저장 후 재열기에도 지속. Extract/Cut/Split/Protect와 결과 연결 별도 검증.

## 기하 검사 대상
- Cube, low-poly cylinder, UV sphere, curved helmet shell, bevelled mechanical plate, open mesh shell, thin slits, concave stamp (cross), ring hole, multi-island PNG, vent grid (20+ holes), self-overlap input and overlapping radial cutters.
- Multi-user mesh (`Alt+D`), nonuniform object scale, applied vs unapplied transforms, existing modifier stacks, mirror/array with shared datablocks, collection instances.
- Compare evaluated and applied results; area/volume, manifold edges, flipped normals, disconnected pieces, unexpected hidden/removed objects, render/viewport shading.
- Smart Fuse overlapping/merely touching/disconnected/non-manifold objects; unsupported cases should fail safely with explanation.
- PNG threshold/anti-alias, high/low resolution vectorization, Save/Reload original presets; external library path migration.
- 1k/10k/100k/1M polygons where feasible: time/memory and interactive viewport latency; shape drawing GPU overlay fast even if Boolean expensive.

## 배포 기준
- Fatal/known P0 crashes/data-loss/undo lock must be resolved before recommended install.
- `.zip` correct Blender extension structure, readme install/enable/uninstall/restore workspace instructions.
- `test_report.md` records exact Blender build, OS, test commands, pass/fail, timings; manual GUI items not run marked Not Tested.
- `CHANGELOG.md`, `KNOWN_LIMITATIONS.md`, `RETURN_HANDOFF.md` included; original v0.5.9 code untouched.
