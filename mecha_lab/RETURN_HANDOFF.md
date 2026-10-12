# RETURN HANDOFF — Mecha Lab 0.7.0 (Claude Code → ChatGPT)

작성: 2026-10-12. 대상: 다음 작업자(ChatGPT). 이 문서만 읽고 이어서 작업할 수 있게 썼습니다.
**검증 수준을 혼동하지 마세요:** 모든 자동 테스트는 Linux headless `bpy 5.0.1`입니다. Windows/Blender 5.0.2 GUI 실행 0회.

## 1. 한 줄 요약
v0.5.9를 기준으로 UI를 `MECHA LAB` Workspace(왼쪽 도구 목록 / 툴헤더 공통 Shape 팔레트 / 오른쪽 단일 도구 설정)로
재구성하고, Cut 입력을 **네이티브 WorkSpaceTool + 한 획짜리 모달**로 다시 써서 Ctrl+Z·메뉴 클릭·RMB 문제를 구조적으로
제거했고, Boolean 적용 경로 전체를 **데이터 수준 적용 + 검증 + 롤백**으로 교체했습니다(Alt+D, PNG 비매니폴드, Smart Fuse 크래시 해결).

## 2. 저장소 구조 (`mecha_lab/`)
```
addon/mecha_lab/          ← 개발 소스 (ZIP 루트와 동일)
  __init__.py             v0.5.9 연산자(Boolean/Slice/Fuse/Path/Library/Remesh...) + 등록 순서
  tool_state.py           도구/Shape 레지스트리, Scene.mch_brush, Scene.mch_cut, effective_tool()
  core_geometry.py        UI 없는 기하 코어 (bpy.ops 사용 안 함, headless 테스트 가능)
  cut_engine.py           Shape 생성 + perform_closed/line/mask + StrokeLogic(모달) + GateLogic(RMB)
  workspace_ui.py         WorkSpaceTool 3종, Workspace 생성, 패널/팝업/팔레트, 게이트 단축키, AddonPreferences
  ui_tool_settings.py     오른쪽 Sidebar의 도구별 draw 함수(DRAWERS)
  cut_presets.py          PNG→벡터 Custom Shape (import/load/preview)
  cut_tools.py            호환 alias(mch.draw_delete_cut), Apply Live Cut
  mask_tools.py           면 마스크(apply_mask_loops), Extract & Raise
  mirror_tools.py / radial_array.py / surface_conform.py   v0.5.9 그대로 + poll/적용 경로만 수정
  icons/*.png             tools_dev/make_icons.py로 생성한 원본 아이콘
reference/RELEASE_v0_5_9/ ← 배포본 원본 (수정 금지) + ORIGINAL_v0_5_9.zip
handoff/                  ← ChatGPT가 준 원래 지시 문서(docs, legacy)
tests/                    ← headless 테스트, run_all.py, test_log_bpy501.txt
tools_dev/                ← make_icons.py, build_zip.py
dist/mecha_lab-0.7.0.zip  ← 설치 파일
README_KO.md CHANGELOG.md KNOWN_LIMITATIONS.md test_report.md GUI_TEST_CHECKLIST_KO.md
```
빌드: `python tools_dev/build_zip.py` · 테스트: `pip install bpy==5.0.*`(Python 3.11) 후 `python tests/run_all.py`.

## 3. 핵심 설계 결정과 이유

### 3.1 Cut 입력: 장기 모달 → 네이티브 도구 + 한 획 모달
- v0.5.9 `mch.draw_delete_cut`은 하나의 모달이 여러 컷을 처리 → (a) 모달이 Ctrl+Z를 먹음, (b) Undo 1단계에 여러 컷,
  (c) 사이드바/메뉴 클릭 시 Esc 필요. v0.6.0 초안은 "컷 후 FINISHED → 타이머로 모달 재시작"이었는데 타이머/컨텍스트
  경쟁 위험이 커서 **채택하지 않음**.
- 0.7.0: `mecha.cut` / `mecha.split` / `mecha.mask` WorkSpaceTool. 도구 키맵: LMB(any) → `mch.cut_stroke(mode)`,
  RMB → `mch.rmb_gate`, SPACE → `mch.space_tools`. `mch.cut_stroke`는 한 획 동안만 모달이고 성공 시 FINISHED(Undo 1단계),
  실패/취소 시 CANCELLED(Undo 없음). 획 사이에는 모달이 없으므로 Blender 기본 Undo/UI가 그대로 동작.
- 모달 로직은 `cut_engine.StrokeLogic`(순수 Python 믹스인)에 있고, `MCH_OT_cut_stroke(StrokeLogic, Operator)`는 RNA만 추가.
  테스트는 같은 클래스에 가짜 이벤트를 넣습니다(`tests/test_stroke_events.py`). 훅: `make_projector`, `add_draw_handler`,
  `open_popup`, `exit_tool`, `_now`.

### 3.2 상태 머신
```
(도구 활성, 모달 없음) --LMB--> invoke: 대상 결정(활성 메쉬 / 커서 아래 메쉬, 없으면 PASS_THROUGH)
   Lasso/Curve Lasso: POINTS --Enter/더블/첫점--> 실행 | 2점 또는 F(open) --> SIDE --클릭--> 실행
   Rect/Circle/Ellipse/Stroke/Custom: DRAG --release--> 실행 (작은 클릭 = 취소, Custom 클릭 = 고정 크기 스탬프)
   공통: Esc/Ctrl+Z(점 0개) → CANCELLED, Shape 변경/네이티브 도구 변경/대상 삭제 → CANCELLED,
         뷰포트 밖 이벤트 → PASS_THROUGH(획 유지), 내비게이션 → PASS_THROUGH, 나머지 키는 삼킴,
         RMB: 첫 PRESS 기록 + 타이머, 더블클릭 간격 내 두 번째 PRESS/DOUBLE_CLICK → exit_tool, 간격 경과 → 팝업(획 유지),
         Space → 획 취소 + 도구 팝업.  Undo 중 RNA 무효 → ReferenceError를 조용히 CANCELLED 처리.
```

### 3.3 기하 파이프라인 (`core_geometry`)
1. `prepare_loops`: 중복/스파이크 제거, 그리드 가속 교차 검사(`find_intersections`), 포함 깊이로 외곽/구멍 그룹.
2. `depth_planes`: 시선 방향에 수직인 near/far 평면(Through: 대상 bbox 투영 + 패딩, Surface: 히트점 기준 깊이).
   원근에서 near가 눈 뒤면 눈 바로 앞으로 이동.
3. `build_cutter_mesh`: 각 2D 점의 ray를 두 평면과 교차 → frustum prism. 캡은 `tessellate_polygon`(구멍 지원),
   벽은 캡 정점 공유 → 구성상 닫힘. remove_doubles → manifold 검사 → 법선 재계산 → 부피 검사.
   모든 면에 BOOLEAN 면 속성 `mch_cutter_face=True`.
4. `boolean_result`: 대상의 다른 모디파이어를 잠시 끄고 임시 Boolean만으로 평가 → `new_from_object`.
   검증: 빈 결과(전체 삭제) 거부, cutter 면이 없고 정점/면 수가 같으면 "교차 없음", 원본이 manifold인데 결과가 아니면 다음 solver.
   Solver AUTO = (Manifold, Exact); 대상이 열린 메쉬면 Exact만.
5. `finish_new_edges`: 결과에서 cutter 면 ↔ 원래 면 경계 엣지만 `bmesh.ops.bevel`(Chamfer = segments 1). 폭은 오브젝트 스케일로 나눔.
6. `commit_mesh`: bmesh로 대상 메쉬 데이터에 덮어씀(데이터 블록 identity 유지). users>1이면 정책(SINGLE: copy 후 기록 / ALL: 공유 데이터 기록).
   속성 `mch_cutter_face` 제거. 셰이프 키/라이브러리/비활성 메쉬는 `check_target`에서 거부.
7. `apply_single_modifier`: `bpy.ops.object.modifier_apply` 대체(같은 의미: 그 모디파이어만 베이스 메쉬에 적용).
   `__init__.safe_apply`, Mirror/Radial/Live Cut 적용이 모두 이것을 사용.
8. `plane_split_mesh`: 2점 직선 컷(bisect + holes_fill, 캡 면에 cutter 속성).

### 3.4 UI
- Workspace: `mch.workspace_open` → 태그(`ws['mch_workspace']=True`) 또는 이름 "MECHA LAB"로 찾기 → 없으면
  `workspace.duplicate()` → 이름/태그/object_mode → 화면 데이터 설정(`configure_screen`: toolbar/tool header/sidebar 표시,
  sidebar 카테고리) → `window.workspace = ws` → `bpy.app.timers`로 전환 후 `screen.area_split(VERTICAL, 0.12)` +
  왼쪽 영역을 PROPERTIES/TOOL로 + 기본 도구 `mecha.cut`. **전부 GUI 미검증.**
- 왼쪽 목록 `MCH_PT_tool_list`: `VIEW_3D/UI/category='Tool'` + poll(space_data.type == 'PROPERTIES' and MECHA ws).
  Blender의 Properties Tool 탭이 View3D "Tool" 카테고리 패널을 재사용한다는 점에 의존(미검증). 실패 대비: Sidebar `MCH_PT_tools`(접힘),
  Space 팝업, T툴바.
- 팔레트: `VIEW3D_HT_tool_header.prepend(draw_shape_palette)`, MECHA ws + Object Mode에서만 그림.
- 오른쪽: `MCH_PT_main`(idname 유지 → mirror/radial/surface 서브패널 bl_parent_id 호환). `ui_tool_settings.DRAWERS[tool]`.
- 도구 상태: `effective_tool()` = 네이티브 도구가 mecha.*이면 그것, 아니면 `scene.mch_settings.mch_active_tool`.
  `activate_mecha_tool()`이 둘을 동기화(그리기 도구는 tool_set_by_id, 그 외 도구는 select_box로).
- 단축키: addon keyconfig에 `3D View: SPACE → mch.space_tools`, `Object Mode: B/C → mch.hotkey`. 둘 다 poll에서
  (MECHA ws + 환경설정)을 확인 → poll 실패 시 이벤트가 Blender 기본 키로 넘어감. 이 동작(poll 실패 = pass-through)은
  Blender의 wm_operator_invoke 동작에 근거하며 GUI 미검증.

### 3.5 PNG (`cut_presets`)
`_load_pixels`(512px 축소, alpha/luminance) → `clean_mask`(작은 섬/핀홀 제거, 2×2 saddle 채움 반복) → `trace_mask`
(픽셀 엣지, 직선 정점 제거) → Chaikin + RDP 후 `find_intersections`로 검증, 실패 시 허용오차 절반씩, 최종 원본 윤곽 →
[-0.5, 0.5] 정규화 → JSON schema 2. `load_loops`는 schema 1을 검증하고 깨졌으면 저장된 PNG로 재벡터화.

## 4. 기능 상태 매트릭스
| 기능 | 상태 | 근거 |
|---|---|---|
| Workspace 생성/전환/복구, Startup opt-in | 구현, **GUI 미검증** | 데이터 수준 테스트만 |
| 왼쪽 도구 목록 / Space 팝업 / Sidebar fallback | 구현, GUI 미검증 | draw 검증 테스트 |
| Tool Header Shape 팔레트 | 구현, GUI 미검증 | draw 검증 테스트 |
| 오른쪽 단일 도구 설정 | 구현 | draw 검증 테스트(14 도구) |
| Cut / Split 분리, 7 Shape | 구현 | 기하 + 이벤트 시뮬레이션 |
| 컷당 Undo 1단계, Ctrl+Z/Esc/RMB/Space 규칙 | 구현 | 이벤트 시뮬레이션(실제 GUI 미검증) |
| Curve Lasso 라운드/드래그 | 부분(대칭 핸들) | 이벤트 시뮬레이션 |
| Edge Finish(새 엣지만) | 구현(Apply 모드) | 기하 테스트, Live 모드 미적용 |
| Alt+D 공유 메쉬 정책 | 구현(모든 적용 경로) | 기하 + 회귀 |
| PNG Custom Shape | 구현 | 9 마스크 × 2 깊이 |
| Live 커터 + Apply Live Cut | 구현(단순 메쉬 커터) | 기하 테스트 |
| Smart Fuse | 부분: 크래시 2건 수정, seam 검증, 겹친 닫힌 메쉬만 | 기하 테스트 |
| Mask | 부분: 공통 Shape 면 마스크, Alt 지우기, Extract | Protect/정확윤곽/Weight 미구현 |
| Pose | 미구현(패널에 명시) | — |
| FBX/Asset 커터, 사용자 키 UI, Radial 방향 수정, Panel 도구의 Shape 공유 | 미구현 | — |

## 5. 이번에 발견·확정한 v0.5.9 버그
1. Smart Fuse 라이브 패널 아이콘 `MOD_NODES` 없음(5.0) → 패널 draw TypeError (스크린샷 03 traceback 형태와 일치).
2. Smart Fuse 생성 실패 시 정리 코드가 삭제된 노드 그룹 접근 → ReferenceError.
3. `bpy.ops.object.modifier_apply`의 multi-user 오류: Mirror Apply 등 Cut 이외 경로에 남아 있었음(스크린샷 02).
4. PNG 대각 접촉 픽셀 → 윤곽 정점 공유 → 커터 비매니폴드.
5. 2D prism 커터가 정사영 가정 → 원근 뷰에서 컷이 그린 모양과 어긋남.
6. 열린 직선 컷 측면 판정 상자가 클릭 위치를 포함하지 않으면 반대쪽 삭제(0.7.0 개발 중 테스트로 발견, 수정).

## 6. 다음 작업 우선순위
**P0 — 사용자 GUI 결과 반영 (가장 먼저)**
- `GUI_TEST_CHECKLIST_KO.md` 결과와 System Console 로그를 받아 Workspace 생성(타이머/area_split), 왼쪽 목록 표시,
  팔레트, RMB/더블클릭 타이밍, 키맵 우선순위를 수정. 왼쪽 목록이 Properties Tool 탭에 안 뜨면 대안:
  (a) 별도 `PROPERTIES` 컨텍스트가 아닌 3D View Sidebar를 왼쪽으로 뒤집은 두 번째 뷰, (b) Toolbar 영역 패널.
- 실제로 Workspace를 만든 뒤 `.blend` 템플릿을 저장해 `workspace.append_activate`로 만드는 방식도 검토 가능(GUI 필요).

**P1**
- Live 모드 Edge Finish(확정 시 적용), Live 커터를 v0.5.9처럼 편집 가능한 Bezier 경로로.
- Curve Lasso 좌우 독립 핸들, 첫 점 라운드, 곡선 해상도 UI.
- Brush Stroke 폭 있는 띠 커터(선택 옵션).
- Panel/Curve 도구도 공통 Shape 팔레트 사용.

**P2**
- Mask Protect: `mch_mask` 면 속성을 Boolean 전후에 이용(예: 마스크 면은 결과에서 원래 면으로 복원하거나 커터에서 제외),
  정확 윤곽 마스크, Mask→Cut/Split, Weight 연동. Pose Rigid/Soft. Smart Fuse 복잡 교차 품질.
- Radial Array 개별 방향, FBX/Asset Browser 커터.

## 7. 지켜야 할 규칙 (회귀 방지)
- `core_geometry`에서 `bpy.ops`를 쓰지 마세요(headless 테스트와 Alt+D 안전성이 깨짐).
- 새 적용 경로는 반드시 `apply_single_modifier` 또는 `commit_mesh`를 사용.
- 아이콘 이름은 `tests/test_register.py`가 5.0 enum으로 검사합니다. 새 패널은 `tests/test_ui_draw.py`에 추가.
- 모달 로직 변경 시 `tests/test_stroke_events.py`를 먼저 갱신.
- `reference/RELEASE_v0_5_9`는 수정 금지. 사용자 Startup/설정은 명시적 확인 없이 쓰지 않기(`mch.workspace_save_startup`만, 확인 창).
- "구현됨"과 "GUI 검증됨"을 구분해 보고.
