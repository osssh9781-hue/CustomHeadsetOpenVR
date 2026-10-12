# RETURN HANDOFF — Mecha Lab 0.8.0 (Claude Code → ChatGPT)

작성 2026-10-13. 기준 소스: ChatGPT **v0.7.2** (`reference/CHATGPT_v0_7_2/MECHA_LAB_v0_7_2_CURRENT_BASE.zip`).
요청서: `handoff/2026-10-13/`. 0.7.0 시절 인수인계 내용(기하 코어, Workspace 설계)은 git 이력과 아래 요약으로 대체.
**모든 검증은 Linux headless bpy 5.0.1. Windows Blender 5.0.2 GUI 실행 0회.**

## 1. 요약
- P0 입력: Esc→선택 도구, 원거리 더블클릭 자동 폐합(중복점/0길이 엣지 방지), 트리플 클릭과 점 편집 클릭 분리,
  처음부터 곡선인 Curve Lasso(Bezier 핸들), 진짜 연속 Free Draw(+Lasso 드래그), 2D 윤곽 모서리 옵션 분리.
- P1: Base Mesh from Shape 새 도구(Flat/Chamfer/Bevel/Dome, RMB 프로필 팝업, Live, 실패 시 무생성).
- P2: Loft/Sweep(Live, NURBS-like 폴리곤), ZBrush OBJ Bridge(GoZ 아님, 자동 Join 없음).
- 보존: v0.7.1 트리플 클릭·Ortho Lock(로드 시 재시작 추가), v0.7.2 마스크 레이캐스트·열린 브러시·Edge Finish 진단.
- 독립 Curve Tool(`mch.draw_path`, Panel/Curve 패널)은 **손대지 않음**.

## 2. 파일 맵 (`addon/mecha_lab/`)
| 파일 | 역할 / 이번 변경 |
|---|---|
| `cut_engine.py` | 공통 획 상태기계 `StrokeLogic`(모드 CUT/SPLIT/MASK/**BASE**), `GateLogic`(RMB, popup=SHAPE/PROFILE), `MCH_OT_exit_tool`(Esc). 순수 함수: `curve_lasso_spline`, `curve_tangents`, `curve_handles`, `round_corners`, `smooth_open`, `clean_clicks`. v0.7.2의 `triple_click_to_select` 유지 + `triple_reset`(편집 클릭) |
| `base_mesh.py` | **신규.** `perform_base`(화면 윤곽→뷰 평면→솔리드), `build_bmesh`(프리즘/Dome), `_triangulate`(CDT + 교차 parity 영역 분류), `Object/Scene.mch_base`, `mch.set_profile`, `mch.base_freeze` |
| `loft_surface.py` | **신규.** `Object/Scene.mch_loft`, `loft_rows`/`sweep_rows`, `build_mesh_from_rows`, depsgraph 핸들러 `_on_depsgraph`(Live), 연산자 create/sweep/rebuild/move/apply |
| `zbrush_bridge.py` | **신규.** `send_objects`, `import_back`, 매니페스트 JSON, `Scene.mch_zbrush`, `detect_goz`(정보용) |
| `tool_state.py` | 도구 BASE(15)/LOFT(16)/ZBRUSH(17) 추가, Shape 설명, 브러시 속성(curve_smoothness, outline_*, stroke_smooth) |
| `workspace_ui.py` | `mecha.base_mesh` WorkSpaceTool, 도구 키맵에 ESC, RMB 게이트 popup 속성, `MCH_PT_profile_popup`, Ortho Lock load_post |
| `ui_tool_settings.py` | Shape 옵션 개편, `draw_base`, `draw_loft`, `draw_zbrush` |
| `core_geometry.py` | 변경 없음(0.7.0 코어: frustum 커터, 검증 Boolean, apply_single_modifier, Edge Finish) |

## 3. 핵심 설계
### 3.1 입력 상태기계 (cut_engine.StrokeLogic)
- 단계 POINTS(Lasso/Curve Lasso) / DRAG(Rect, Circle, Ellipse, Free Draw, Custom) / SIDE(열린 선의 지울 쪽 선택).
- 종료: FINISHED 1회 = 작업 1개 = Undo 1단계. CANCELLED = 변화 없음. `_leave_tool` = 정리 + `exit_tool`(select_box).
- Esc(획 중) → `_leave_tool`. Esc(대기) → 도구 키맵 `mch.exit_tool`. 팝업 대기 게이트 중 Esc → exit.
- DOUBLE_CLICK(POINTS) → `_confirm` → `_clean_points`(4px 중복·시작점 겹침 제거) → 닫힌 윤곽 실행. 점 추가 없음.
- 트리플: PRESS/DOUBLE_CLICK마다 `triple_click_to_select`(v0.7.2, 0.72초/12px, 25ms 중복 필터). 단 POINTS 단계에서 기존 점
  (마지막 점·닫기용 첫 점 제외) 또는 핸들을 누른 PRESS는 `triple_reset` 후 미집계. invoke 첫 PRESS도 집계 → "점 클릭 →
  더블 확정 → 같은 자리 3번째 클릭"이 선택 복귀.
- Curve Lasso: `pts`, `sharp[i]`, `overrides[i]`(핸들 드래그 탄젠트). 탄젠트 기본 = (P[i+1]-P[i-1])/2 × smoothness.
  구간 = 3차 Bezier(P, P+T/3, Q-T'/3, Q), 구간당 `curve_resolution` 샘플.
- Free Draw: DRAG 중 MOUSEMOVE/INBETWEEN_MOUSEMOVE마다 `stroke_spacing` 이상이면 샘플 추가. 실행 시 smooth→simplify→
  (닫힌 경우) trim_closing_overlap. Mask는 `apply_mask_stroke`(열린 경로).
- 테스트 훅: `make_projector`, `add_draw_handler`, `open_popup`, `exit_tool`, `_now` (tests/test_stroke_events.py).

### 3.2 Base Mesh
- 평면: 윤곽 중심의 시선이 씬 메쉬에 맞으면 그 점, 아니면 3D 커서를 지나는 시선 수직 평면. 오브젝트 로컬 XY = 평면,
  +Z = 뷰어 쪽. 그 뷰에서 실루엣이 그린 윤곽과 일치(테스트 <0.01px).
- 프리즘: 구멍 없으면 n-gon 캡, 있으면 CDT 삼각형 캡. Chamfer/Bevel = 윗면 림 엣지만 `bmesh.ops.bevel`(폭 ≤ 0.95·Height).
- Dome: 경계를 `extent/resolution` 간격으로 조밀화, 엇갈린 내부 격자(경계에서 0.45·간격 이상), 거리장 d(numpy),
  z = edge + H·(1-(1-t)^q)^(1/q), t=d/R, q=1+3·roundness. 윗면 = CDT(경계+내부), 아랫면 = CDT(경계), 벽 = edge height.
  Edge Height 최소 1%·Height(0이면 경계 전용 삼각형이 바닥과 겹쳐 닫힌 솔리드 불가).
- `_triangulate`: CDT 출력 삼각형을 **제약(윤곽) 엣지로 나뉜 영역**으로 묶고, 볼록 껍질 밖 가상 영역에서 제약 엣지를
  건널 때마다 parity를 뒤집어 홀수 영역만 유지. (중심점 판정은 경사 뷰의 sliver에서 실패했음.)
- 검증: manifold, 법선 재계산, 부피>0. 실패 시 CutError → 오브젝트 미생성.
- Live: `mch_base.outline`(JSON, 로컬 2D 그룹) + 설정. update 콜백이 `rebuild` → 실패 시 `last_error` 표시, 메쉬 유지.

### 3.3 Loft/Sweep
- 커브 첫 스플라인을 world 폴리라인으로(BEZIER는 `interpolate_bezier`, POLY 그대로, NURBS는 evaluated to_mesh),
  호 길이 재샘플. 열린 커브: 양끝 거리로 뒤집기. 닫힌 커브: 시작점 회전+방향 최소 오차 탐색, `twist`로 추가 회전.
- 단면 사이: Catmull-Rom과 선형을 `smoothness`로 혼합. `close_loft`는 마지막→첫 섹션 연결.
- 메쉬: 행×열 쿼드, Cap(닫힌 단면, 열린 loft), Flip, Thickness = Solidify 모디파이어(Live), Apply = 데이터 적용.
- Live: `depsgraph_update_post`에서 바뀐 커브 오브젝트/데이터를 참조하는 Live 오브젝트만 재생성(`_building` 재귀 가드).
- Sweep: 경로 평행 이동 프레임, 단면은 단면 오브젝트 로컬 XY.

### 3.4 ZBrush Bridge
- Send: 객체마다 선택을 그것 하나로 바꿔 `wm.obj_export`(world 좌표, axis/scale 설정) → 매니페스트에 export matrix.
- Import Back: 파일 mtime > 기록값인 것만 `wm.obj_import`, 여러 그룹이면 bmesh로 하나로, export matrix 역변환,
  원래 오브젝트(ID → 이름) 메쉬 교체(공유 메쉬면 이 오브젝트만), 이전 메쉬 `_preZBrush`(fake user). 없으면 새 오브젝트.

## 4. 기능 상태
`test_report.md`의 "기능별 상태" 표 참고 (완료/실행 검증 · 구현됐으나 GUI 미검증 · 부분 구현 · 미구현).

## 5. 다음 작업 제안
**P0 (사용자 GUI 결과부터)**: `GUI_TEST_CHECKLIST_KO.md` 결과/콘솔 로그로 이벤트 타이밍(더블·트리플 시간창), Esc 키맵 우선순위,
팝업, 왼쪽 목록 표시, Workspace 생성 확인 후 조정.
**P1**: Base Mesh Surface Follow/Project(곡면 위 장갑판: 윤곽을 표면에 레이캐스트해 높이장을 표면 법선 방향으로),
Curve Lasso 좌우 독립 핸들/첫 점 편집, Live Cut Edge Finish.
**P2**: Loft의 열린/닫힌 혼합(닫힌 쪽을 펼치기), 섹션별 샘플 매칭 옵션, GoZ(실제 ZBrush 설치에서 검증 가능할 때만),
Mask Protect / Pose / FBX 커터.

## 6. 규칙
- `core_geometry`·`base_mesh`·`loft_surface`의 기하 코드에 `bpy.ops` 금지(헤드리스 테스트·안전성).
- 상태기계 변경 시 `tests/test_stroke_events.py` 먼저 갱신. 새 패널은 `tests/test_ui_draw.py`에 추가(아이콘 enum 검사 포함).
- 독립 Curve Tool 수정 금지(요청 범위 밖). ZBrush 전송 전 자동 Join 금지. Startup/설정 무단 변경 금지.
- "구현됨"과 "GUI 검증됨"을 구분해 보고.
