# CHANGELOG

## 0.13.0 — Station Primitive (Advanced Parametric Primitive, Phase 1: 생성 엔진) (2026-10-13)

- 새 엔진 `station_sweep.py`(순수 기하): 단면 7종(Round/Oval, Capsule, Box, Rounded, Chamfer, Ribbon, Polygon) ×
  지점(Station) 사슬. 지점마다 꺾임 각도·방향·반경(0 = 접힘, 마이터로 두께 유지)·길이·비틀림·Local/World 방향,
  좌/우 폭, 위/아래 높이, 좌/우 두께, 좌/우 모서리, 릿지 높이·폭·위치. 구간 보간 Linear/Smooth/Step.
  릿지 6종(Crease, Raised, Box, Round, Groove, Double). 끝 마감 Flat/Round/Point/Open. 자동 세그먼트(각도·비틀림·보간),
  반경이 단면보다 작으면 올리고 경고.
- 지점은 앞 구간 끝 방향에서 시작: 지점 1을 바꾸면 뒤 사슬이 함께 돌고, 뒤 지점들의 값은 그대로(시나리오 E 테스트).
- Blender: `station_primitive.py` — 객체별 파라미터(저장 후 재편집), 항상 실제 메시로 재생성(GN 아님, Cut/Boolean 바로 가능),
  Shell(라이브 Solidify), 프리셋 6개(Flat Panel, Multi-Bend Armor, Wrap/Tyre Cover, Helmet/Teardrop, Automotive Panel, Duct),
  지점 추가(활성 지점 뒤, 값 복사)/삭제/순서, Apply. Primitive 도구 패널 맨 위(간단 + Asymmetry/Advanced 접기).
- 살아 있는 Station Primitive를 Cut/Split/Boolean 하면 먼저 동결(자른 결과가 다음 재생성에 덮이지 않도록)하고 메시지로 알림.
- 테스트: 21개 파일 1124/1124 (`tests/test_log_bpy501_v0130.txt`), 신규 `test_v0130.py` 50항목. ZIP sha256 `a9dba3e703b9d92e5f0cbd761033fb0f663bfe871f1a857641868192b83133f9`.
- 미구현: 뷰포트 지점 핸들(Phase 4), 헬멧 쉘 전용 옵션·릿지 구간(Phase 2), 랜덤 생성기(Phase 3).

## 0.12.0 — UX 프로토타입 v2.1의 최소 Blender 버전 (2026-10-13)

기준: 0.11.3 + 브라우저 프로토타입 v2.1. Cut/Split 엔진(기하 계산)은 그대로, 입력·도구 전환만 추가.
- **자동 대상 (Auto Target, 새 기본값)** / **선택만 (Selected Only)**: Cut/Split에서 그린 도형이 덮는 메시를 바로 자름
  (선택 무시). 도구를 유지한 채 다음 장갑판을 바로 자를 수 있음. 잘린 메시가 선택됨. 도구 헤더 토글 + **T** 키.
  잠금(선택 불가)·와이어 표시(커터 등) 오브젝트는 제외. 판정: 화면 경계 사전 필터 → 외곽선·내부 샘플 레이캐스트/중심점.
  Selected Only는 기존 동작(선택한 메시만). 빈 곳에서 시작한 도형이 아무것도 덮지 않으면 아무것도 바뀌지 않음.
- **Q = 도구 파이**(8개: Select, Cut, Split, Base, Boolean, Mirror, Primitive, Radial), **Shift+Q = Select ↔ 마지막
  모델링 도구**. 둘 다 MECHA LAB에서만(밖에서는 Q = Blender Quick Favorites).
- **V 비움, N = Blender 사이드바로 복귀.** F = Select/Move, Space = 큰 도구 메뉴, B/C 그대로.
- **하단 툴바**: 뷰포트 하단 가운데 2D 버튼 기즈모(모달 아님), 현재 도구 주황 표시, 크기 S/M/L, 아이콘 아래 이름(선택).
  Preferences에서 끄기 가능.
- 마지막 도구·Select 상태는 WindowManager에 저장(Undo에 안 섞이고 파일에 저장 안 됨).
- 테스트: 20개 파일 1074/1074 (`tests/test_log_bpy501_v0120.txt`), 신규 `test_v0120.py` 27항목. ZIP sha256 `270841f19e16687320f5e91e0567a7e5b6b414dd5407e8228a1140304417c7fe`.
- 프로토타입 v2.1(별도 HTML): Box Hide Apply가 복원 기록을 버리던 버그 수정, 자동 대상/선택만, 메시별 Cap,
  아이콘 이름 표시, 옵션 카드 접기·위치·자동 흐림.

## 0.11.3 — 스탬프 도형 6종, 단축키, Ctrl+Z 도형 유지, Cable→Mesh, Curve Lasso 원래 방식, Mirror 업그레이드 (2026-10-13)

- **기본 스탬프 도형 6종** (Lasso / Stamp 도형 팔레트): 오각형, 사다리꼴, 기울어진 알약 3개(나란히, 각각 분리),
  삼각형, 둥근 홈 박스(원기둥으로 파낸 모양), 다각형 홈 박스. 애드온 안에 포함(`shapes/builtin_shapes.json`,
  `icons/shape_*.png`, 생성기 `tools_dev/make_shapes.py`) — 사용자 폴더에 쓰지 않음, 삭제 불가. 클릭 = 찍기, 드래그 = 크기/회전.
- **단축키** (MECHA LAB에서만): Tool Menu = **V**(Space도 유지), Quick Menu = **N**, Select / Move = **F**.
  MECHA LAB의 Object Mode에서는 N이 사이드바 대신 Quick Menu (다른 Workspace는 Blender 기본 그대로).
- **Ctrl+Z가 도형을 예전 것으로 되돌리던 문제**: 도형·스탬프·선택 도구가 Scene 데이터라 Undo에 포함됐음 →
  undo/redo 직전 값을 기억했다가 직후 복원(`tool_state.snapshot_ui_state / restore_ui_state`).
- **Cable: Convert to Object (Mesh)** 버튼 — 같은 이름의 메쉬 오브젝트로 굽고 커브·숨은 단면 커브 정리.
- **Curve Lasso 원래 방식 복구 (ChatGPT v0.7.2 규칙)**: 점은 처음에 직선 모서리, 점 클릭마다 약 → 중 → 강 → 직선 순환,
  파란 핸들 드래그로 둥글기 조절. (0.8.0에서 기본 곡선 스플라인으로 바뀌었던 것을 되돌림.)
- **Mirror 업그레이드 (HardOps 방식)**: Mirror 도구를 고르면 바로 라이브 미러 시작(`mch.mirror_lean`).
  마우스를 복사하고 싶은 쪽으로 기울이면 그 축/방향으로 미러(Bisect: 그 쪽이 반대쪽 복사본으로 바뀜).
  **Enter / Space = 적용(Apply)**, 클릭 = 라이브 유지, Shift+클릭 = 축 추가, X/Y/Z = 축 토글, B = Bisect, Esc/우클릭 = 취소(원상복구).
  패널: "MIRROR: LEAN MOUSE TO SIDE" 버튼, "Copy toward +X/Y/Z", "Start when Mirror is picked". Bisect 기본 ON.
- **충돌(크래시) 대비**: 단축키 편집 행이 KeyMapItem을 모듈 리스트에 붙잡고 다시 그리던 방식(해제된 메모리 접근 위험) →
  매번 새로 찾음. Ortho Lock이 카메라 뷰를 건드리지 않음. Radial Array 자체는 headless에서 충돌 재현 안 됨.
- 테스트: 19개 파일 1046/1046 (`tests/test_log_bpy501_v0113.txt`), 신규 `test_v0113.py` 35항목. ZIP sha256 `deed2943d3d8276a383cdf338455d393e508cf337c6d42e01a1f98c9604e2c37`.

## 0.11.2 — 일반 Cube Cut/Split 오류 추적용 진단 + Edit Mode Cut 수정 (2026-10-13)

사용자 보고: 0.11.1에서도 일반 Cube Cut/Split이 "whole object"로 실패. headless(실제 RegionView3D 원근/직교 포함)에서는
재현되지 않음 → 원인을 사용자 환경에서 바로 확인할 수 있게 함.
- 실패 메시지에 사실 정보 추가: 그린 도형이 오브젝트 정점 몇 개를 덮는지(화면 루프 + 깊이 범위), 도형 픽셀 범위와 뷰 크기,
  PERSP/ORTHO, Alt/반전 상태, **실행 중인 Mecha Lab 버전**. 같은 내용이 시스템 콘솔에 `[Mecha Lab] cut failed:`로 출력.
  - 도형이 정말 오브젝트 전체를 덮으면: "The drawn shape covers the whole of ..."(정상 거부, 이유 명시).
  - Alt 반전인데 겹치지 않으면: "does not intersect"(다중 대상에서는 건너뜀 목록으로).
- Self Test에 **실제 3D View 투영으로 Cut / Alt Cut / Split** 단계 추가(뷰 중심에 임시 큐브, 끝나면 삭제). 13단계.
- Edit Mode에서 Cut/Split 시 `to_mesh(): Mesh is in editmode` 오류 → Object Mode로 나간 뒤 실행.
- 테스트: 1012/1012 (`tests/test_log_bpy501_v0112.txt`). ZIP sha256 `000db2d3d84a0215dcfd1b55fcd296e59267c1e091a2be5d04af7593676c0aa5`.

## 0.11.1 — Cut/Split "whole object" 오류 수정, Alt 모드 전환 롤백, Select / Move (2026-10-13)

기준: 0.11.0. 입력·작업 상태 관리 부분만 v0.9.3 방식으로 복구, 다른 기능은 그대로. 검증은 Linux headless bpy 5.0.1뿐.

- **Alt+뷰포트 클릭 모드 전환 완전 삭제**: 빈 곳 Alt+클릭 → 선택 모드, 오브젝트 Alt+클릭 → 도구 복귀, `ALTWAIT` 단계,
  `alt_pending`/`alt_wait`, `ALT_CLICK_SEC`/`ALT_DRAG_PX`, `_alt_begin_drag`/`_modal_altwait`/`_modal_alt_pending`,
  `mch_last_tool` 저장, `MCH_OT_alt_click_return` 연산자와 Object Mode `Alt+LEFTMOUSE CLICK` 키맵, `alt_click_return` 설정 제거.
- **Cut/Split 입력 v0.9.3 복구**: 누를 때 대상 수집 후 바로 획 시작, `alt_latch`(누를 때 Alt) 또는 그리는 중 Alt = 반전(안쪽
  남기기). 그리는 중 Alt+클릭도 점 추가 + 반전. 직선 2점의 면 선택은 다시 Alt+클릭 = 그쪽 남기기. Ctrl+드래그 중심 그리기 유지.
  (0.10~0.11의 더블클릭 자체 판정, 시작점 닫기, Tab 통과, PNG R 회전, Stabilizer, 다중 대상 보고는 유지.)
- **"The result would delete the whole object" 수정**:
  - 원인(재현됨): Live Primitive(MCH_Box 등 Geometry Nodes)는 기본 메쉬가 비어 있어 Boolean 결과가 항상 빈 메쉬.
    → `core_geometry.ensure_real_mesh`가 Cut / Split / Boolean 전에 평가된 형상을 실제 메쉬로 굽힘(재질 유지, 보고에 표시).
  - 빈 결과일 때 다음 솔버(Manifold → Exact)로 재시도.
  - 그래도 실패하면 메시지에 대상 이름, 연산(Cut / Keep inside / Union), 시도한 솔버를 표시.
  - 일반 Cube에서의 같은 오류는 headless에서 재현되지 않았습니다(Alt 상태가 남는 경로를 제거한 것이 대응).
- **Select / Move** (`mch.select_move`): Mecha Lab 메뉴(왼쪽 도구 목록·Space·V 팝업·사이드바) 맨 위. Object Mode로 전환 후
  `builtin.move` 툴(Blender 선택 + 이동 기즈모, 다중 선택) + 기즈모 표시. 실행 중인 Cut/Split 모달은 툴 변경을 감지해 취소,
  다시 들어가면 새 획. 단축키: Object Mode `W`(`mch.select_move_key`, MECHA LAB Workspace에서만), Preferences와
  Workspace & Hotkeys 패널의 **키 편집 행**에서 바꿀 수 있음(Quick Menu / Tool Menu / B·C 단축키도 함께).
- 시작 시 활성화에서 `bpy.data` 제한 오류(`_RestrictData`)가 나던 Ortho 검사를 타이머로 미룸.
- 테스트: 18개 파일 1007/1007 (`tests/test_log_bpy501_v0111.txt`). `test_v0100_regression.py` 108항목(0.11.1 블록 신규).

## 0.11.0 — Mechanical Modeling Toolkit (Face Extract / Armor Sculpt / Molding / Cable / Hollow / Mesh Along Curve) (2026-10-13)

기준: 0.10.0. 기존 기능 제거 없음. 검증은 Linux headless bpy 5.0.1뿐(Windows Blender 5.0.2 GUI 미실행, Blender 5.3도 미실행).

- **Base Mesh**: 다른 상단 탭(Workspace)으로 나가면 이번 세션에 만든 미확정 Base Mesh를 자동 Apply(0.5초 간격 가벼운 타이머,
  미확정 도형이 있을 때만 동작).
- **Face Extract (Basic)** — 새 도구. Edit Mode에서 선택한 면(여러 오브젝트·여러 섬 각각)을 별도 파츠로 추출, 원본 불변.
  Bevel Modifier 조합이 아니라 **자체 단면 생성기**(`panel_gen.py`): Extract Height / Thickness(0=솔리드, >0=Solidify 쉘) /
  Surface Offset / Resolution, Bevel Width·Segments·Profile·Angle(윗면 엣지 라운드 + 외곽선 코너가 Bevel Angle보다 날카로운
  측면 세로 엣지만), Chamfer Width·Angle·Depth(세 값 중 두 개를 고르는 모드, 나머지는 계산 표시)·Direction Inward/Outward,
  Outer Edge(바닥 엣지) Bevel Width / Chamfer Width / Angle. 모든 값 실시간, 파츠를 다시 선택해도 유지.
- **Armor Sculpt** — 같은 생성기의 고급 모드. 평균 노멀 + 주축으로 로컬 N/E/S/W(회전·스케일·오프셋·미러). 방향별 Thickness /
  Slope / Roundness / Chamfer Width·Angle / Bevel Width·Segments를 부드러운 분할(cos²)로 연결. 중앙 라인 6종(Straight, Cross,
  Y, X, S, Z) + Rotation / Scale X·Y / Offset / Width / Height / Strength / Sharpness / Roundness / Angle / Invert / Symmetry,
  방향별 Length·Width, Y·X 가지 각도, S 곡률. Ridge Profile 6종(Sharp, Flat, Round, Box, Groove, Split), Surface Transition
  (Width, Smoothness, Surface Tension). 실제 메시 높이를 바꾸는 높이장, 결과는 항상 닫힌 솔리드.
- **Edge Molding** — 선택 면 외곽 / 선택 엣지 / 추출 파츠 경계 / Armor 중앙선에서 별도 오브젝트. Width, Height, Surface Offset,
  Slope Angle, Chamfer Width·Angle, Bevel Width·Segments, Profile Resolution, Smooth Boundary(기본 0 = 원래 엣지 그대로),
  Round / Square / Flat / Chamfer / Custom, 배치 Centered / Inside / Outside. 표면 노멀 기준으로 세워 휘어진 표면에서도 똑바름.
- **Hollow / Shell** — 여러 메쉬 동시. Wall Thickness, Inward/Outward/Center, Even, Rim Fill, Rim Thickness(정점별 Solidify 두께),
  Rim Bevel + Segments, 선택 면 = 개구부(GN), 자기교차/두께 초과 검사, Apply / Reset.
- **Mesh Along Curve** — Curve Deform(±X/Y/Z, Start Offset, Rotation, Scale, Stretch), Curve Array(Rigid = GN 인스턴스 / Deform =
  Array+Curve, Count / Spacing / Fit Curve, Start·End Offset, Global Scale, Rotation Offset, Follow Tangent, Align Axis, Reverse,
  Apply / Reset). 커브 배치 Free / World X / Y / Z(기준 중심선만 축에 고정, 제어점은 자유, 생성 후 변경 가능).
- **Cable Generator** — 두 메쉬 표면 클릭(서로 다른 오브젝트 가능, 노멀 방향으로 출발), Control Points 추가/삭제, Handle Angle /
  Length, Sag, Curvature, Midpoint Offset, Twist, Thickness / Start / End / Taper, Curve·Profile Resolution, Round / Square /
  Ribbon / Oval / Custom. Edge to Cable(엣지 유지, 체인별 또는 한 오브젝트, Smoothing).
- 정리용 컬렉션 `Mechanical Parts / Extracted Armor, Edge Moldings, Cable Objects, Curve Arrays`.
- 그리던 도중 **Tab** = 획 폐기 후 Blender로 전달(Edit Mode 전환). 새 도구는 모달이 아니라 패널 + 오브젝트별 설정이라
  Edit/Object 전환과 무관하게 유지.
- 자가 진단(Self Test)에 Face Extract / Armor / Molding / Hollow / Cable 추가(12항목).
- 테스트: 18개 파일 995/995 (`tests/test_log_bpy501_v0110.txt`), 신규 `test_mechanical_toolkit.py` 99항목.

## 0.10.0 — 안정화 + 입력 UX 통일 + Deform 포인트 조작 + Free Draw Stabilizer (2026-10-13)

기준: **ChatGPT v0.9.3** (= Claude 0.9.0 + ChatGPT Deform v0.9.1 + Primitive v0.9.2/0.9.3). 무수정 원본은
`reference/CHATGPT_v0_9_3/`. 검증은 Linux headless bpy 5.0.1뿐이며 **Windows 11 / Blender 5.0.2 GUI는 실행하지 못함**.

### 사용자 보고 고장(P0) — 원인 분석과 조치
| ID | 조치 | 비고 |
|---|---|---|
| B09 등록 오류 `MCH_PG_Brush already registered` | `addon_safety.py`: 등록 전 이전 실행/다른 사본의 잔여 클래스·`mch_*` 속성·핸들러·헤더 함수·`mch.*` 키맵·`mecha.*` 툴을 정리, 등록 중 예외 시 **완전 롤백**, 해제는 단계별로 계속 진행(중간 실패해도 나머지 해제) | 해제가 중간에 멈추면 다음 활성화가 이 오류로 실패하고, 그 뒤에 등록되는 Mirror/Radial/Surface 패널·키맵·툴이 통째로 빠짐 → B01 등 "여러 기능 먹통"의 유력한 공통 원인. 다른 Mecha Lab 사본이 켜져 있으면 패널 상단에 경고 |
| B01 Mirror / B02 Loft / B03 Smart Fuse | 코드는 0.9.0과 동일했고 headless에서는 모두 통과 → GUI 전용 경로를 보강: 왼쪽 도구 목록(Properties 편집기)에서 도구를 바꿀 때 `tool_set_by_id`를 **3D View 컨텍스트로 실행**, 툴바가 바뀌지 않아도 선택한 도구 패널이 표시되고 Cut이 LMB를 가로채지 않음. Mirror Apply/Remove 다중 선택. Smart Fuse: 다른 오브젝트의 미확정 미리보기가 패널을 가로채지 않음, Undo 등으로 남은 `active` 플래그 자동 복구, 확정/취소 후 고아 노드 그룹 정리 | **재현 불가 → 추정 원인 기반 수정.** 새 `Run Mecha Lab Self Test` 버튼(Workspace & Hotkeys 패널)이 사용자 Blender에서 임시 씬으로 Mirror/Loft/Fuse×3/Boolean/Cut/Base Mesh/Deform을 실행하고 결과를 클립보드에 복사 |
| B04 Lasso 더블클릭 | Blender가 두 번째 클릭을 `DOUBLE_CLICK` 대신 `PRESS`로 보내는 환경에서도 닫히도록 **자체 더블클릭 판정**(시간+거리). 시작점 닫기 반경 14px × UI Scale. 3회 클릭 토글 제거(충돌 원인) | Curve Lasso 점 편집 클릭과 충돌하지 않음(편집 클릭 뒤의 더블클릭은 닫지 않음) |
| B05 Mesh Curve 직선/점만 | 기존 점 **더블클릭이 두 번 토글되어 Smooth→Straight로 되돌아가던 버그** 수정(첫 PRESS + DOUBLE_CLICK, 또는 PRESS 두 번). 이제 한 번의 더블클릭 = 한 번 전환 | |
| B06 PNG R 회전 | 드로잉 중 `R`/`Shift+R` 15° 회전, 대기 상태에서도 `R`(PNG 모양일 때만, 아니면 Blender R), 커서에 스탬프 윤곽 미리보기(WorkSpaceTool draw_cursor) | 미리보기 = 실제 커터 윤곽(테스트) |
| B07 Split Gap 확정 | 시작점 클릭 / 아무 곳 더블클릭 / Enter 모두 확정, 열린 선(F)도 시작점 클릭으로 확정 | |
| B08 Mask | 도구 목록·Space·V·툴바·단축키에서 **숨김**. 코드·연산자·저장된 마스크 속성/Vertex Group은 그대로 | 이전 파일에서 Mask가 활성이면 Cut으로 표시 |
| B10 Bevel 폭 | Cut Edge Finish / Split Side A·B 폭 슬라이더 상한 0.5→2.0(숫자 입력 무제한), `Clamp Overlap` 옵션, 짧은 이웃 엣지 때문에 폭이 제한되면 결과 메시지에 "limited to about …" 표시 | |

### 입력 UX (docs/02)
- **Alt+짧은 좌클릭**(놓을 때 이동량/시간으로 판정): 드로잉 도구 → 선택 모드(그리던 획 폐기, 완료 작업 유지). 선택 모드에서
  오브젝트 위 Alt+클릭 → 마지막 Mecha 도구로 복귀(빈 곳이면 Blender 기본). **Alt+드래그**: Cut = 안쪽 남기기, Base Mesh = Boolean
  커터. 직선 Cut의 면 선택 단계에서 "남길 쪽"은 Alt 대신 **Ctrl+클릭**.
- 3회 클릭 → 선택 모드 기능 **제거**. Alt+MMB는 추가하지 않음.
- `V` 빠른 메뉴(Cut/Boolean/Base Mesh/SubD Plane/Split/Radial, 마우스 위치), `Shift+A > Mecha Lab`(Primitive 5종, SubD Plane,
  Base Mesh 도구, Lattice/Bend). MECHA LAB Workspace에서만, Preferences에서 끌 수 있음.

### 기능 (docs/03)
- **Boolean: 노란색 활성 = 커터, 나머지 선택 = 대상**(여러 대상 각각). 패널에 CUTTER/TARGETS 표시. 실패한 대상은 그대로 두고
  메시지에 표시, 대상이 하나라도 실패하면 커터는 삭제하지 않음. Slice도 같은 규칙.
- Cut/Split: 기본 Targets = Selected, 같은 도형으로 모든 선택 메쉬 처리, 겹치지 않는/실패한 대상은 변경 없이 메시지에 표시(1 Undo).
- **Base Mesh Bevel Sides**: Top Only / Bottom Only / Both Sides / None, Both는 위/아래 폭·세그먼트 별도(기본 연결). 이전
  `Bevel Bottom Too`는 로드 시 Both로 이전. Dome은 Bevel Sides 미사용(UI에 표시). **Alt+드래그**: 그린 입체를 Top↔Bottom
  반전(Both는 위/아래 값 교환)해 표면 안쪽으로 뒤집은 커터로 Boolean Difference(포켓 입구에 반전된 베벨). **도구를 떠날 때**
  (Alt+클릭/Esc/다른 도구) 이번 세션에 이 도구가 만든 Live Base Mesh만 Apply(Freeze), Undo 1단계.
- **Deform(Lattice Cage / Bend Curve) 포인트 직접 조작**: 점 클릭 → Move/Rotate/Scale 기즈모(Mecha 스타일) 또는 Blender 기즈모 +
  Proportional Editing(Mecha 설정과 실시간 동기화). 선택 점이 피벗, Falloff Radius/Smoothness(연속값), 단일 점 회전·스케일도
  주변을 변형, 다중 선택, Pivot(선택 중심/각 점/3D 커서), Lattice Resolution X/Y/Z(편집 중에도, 변형 유지), Bend 점의 접선 회전 =
  국소 Twist(tilt), 스케일 = 두께(radius), 점 개수 재샘플. Apply 전까지 비파괴, 언제든 재편집. v0.9.1 연산자 ID·태그·모디파이어
  이름·스택 베이크 Apply 유지, Twist/Taper 슬라이더는 점별 편집 위에 더해지는 램프로 변경.
- **Free Draw Stabilizer(Lazy Mouse)**: ON/OFF(기본 OFF), Smoothing Strength 0–100%(시간 기반 지수 추종, 이벤트 빈도 무관),
  Lazy Radius 0–80px(원 안에서는 선이 멈춤), Stroke Spacing(기존 Sample Spacing 재사용). 드로잉 중 타이머로 계속 따라오고, 놓을 때
  간격 단위로 부드럽게 따라와 끝남(긴 직선 점프·이중 점 없음). 지연 원/줄 가이드 표시 옵션. OFF/0%/0px는 기존 코드 경로 그대로.
  Cut/Split/Base Mesh 공통, Lasso·Curve Lasso·도형·PNG·Curve Tool은 변경 없음.

### 테스트
- 17개 파일 875/875 통과(`tests/test_log_bpy501_v0100.txt`). 신규: `test_v0100_regression.py`(92), `test_deform.py`(109),
  `test_registration_recovery.py`(38), `test_self_test.py`(4). `test_zip_install.py`는 비활성/재활성 3회.
- 기존 테스트 중 새 사양으로 바뀐 것: Boolean 선택 규칙(활성=커터), Alt는 드래그해야 반전, 3회 클릭 제거.

## 0.9.0 — Mesh Curve 수정, SubD Plane, Radial 회전, Gap Split, 양쪽 독립 베벨 (2026-10-13)

기준: 0.8.0. 기존 기능은 제거·대체 없이 확장. 검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 Mesh Curve (Panel / Curve 도구 → 이름 "Mesh Curve", Curve Lasso와 무관)
- **직선처럼만 생기던 원인 3가지 수정**: (1) 모든 점이 VECTOR 핸들로 생성(Free Draw 포함), (2) Edit Mode 점 더블클릭 →
  Smooth 키맵이 v0.5.9부터 `active = False`로 등록돼 한 번도 동작하지 않음, (3) Straight/Smooth 버튼이 Edit Mode 전용이라
  Object Mode에서 비활성.
- 직선(VECTOR) 그리기는 기본값 그대로. 그리는 중 기존 점 클릭/더블클릭 = Straight ↔ Smooth, `S` = 새 점 종류, Backspace가
  점 종류를 보존. Free Draw 점은 AUTO(부드러움). Edit Mode 더블클릭 키맵 활성화(Mecha 경로가 아니면 통과).
- 새 Live 설정(Object.mch_live): Curve Resolution(경로 resolution_u), Profile Segments(원형 단면), Rotation X/Y/Z(스윕: 단면 회전,
  Curve Array: 복제본 회전), Twist(시작→끝 누적 비틀림, Set Curve Tilt). `All Smooth / All Straight`(Object Mode).
- 0.9 이전에 만든 Live 오브젝트는 처음 값을 바꿀 때 노드 그룹을 한 번 재생성.

### P0 SubD Plane (새 도구)
- `Create SubD Plane`: 3D 커서에 Plane + `Simple SubD → Catmull-Clark SubD → Solidify`. 두 SubD를 **동시에** 쓰고 레벨 슬라이더
  각각(0~5). Thickness / Offset / Even Thickness / Use Creases, Edit Mode 선택 엣지 Crease, `Apply All`(스택 순서대로 데이터 적용),
  `Add SubD Stack to Selected`. 모든 모디파이어 Edit Mode 표시.

### P1 Radial Array
- Ring Rotation X/Y/Z(배열 전체 회전), Copy Rotation X/Y/Z(복제본 로컬 회전), Start Angle(이름 정리), Rotate Each Copy **기본 OFF**
  (씬 기본값과 오브젝트 모두). 원본 방향은 메쉬에 그대로, 배열 회전은 별도 노드. 이전 배열은 처음 수정 시 노드 그룹 재생성.
- 기울어짐 점검: 복제본 회전은 Rotate Each Copy가 켜져 있을 때만 Z축으로 일어나며, 기본값이 ON이던 것이 "원하지 않는 회전"의
  주원인이었음. OFF에서는 모든 복제본이 원본 축을 유지함을 테스트로 확인.

### P1 Gap Split
- Split Mode: Normal(기존) / Gap. Gap Width(모델 단위)만큼 띠를 제거: 닫힌 도형은 윤곽을 ±Gap/2 오프셋한 두 커터로
  (안쪽 = 조각, 바깥쪽 = 남는 원본), 2점 직선은 ±Gap/2 두 평면, 폴리라인/곡선도 지원. 중심선 유지, Cap 옵션, 각각 별도 오브젝트.
  Gap이 도형에 비해 너무 크면 메시지와 함께 거부, Auto Apply OFF에서는 안내 후 거부.

### P2 Split 양쪽 독립 마감
- Side A(남는 원본) / Side B(`_Split`) 각각 None/Chamfer/Bevel, Width, Segments, `Swap Sides`. Normal/Gap/직선 모두,
  새 절단 경계만 처리(원래 모서리 불변 테스트). Split은 이제 이 설정을 쓰고, Cut의 Edge Finish는 Cut 전용.

### P2 2D Corner 점검
- 0.8.0의 Sharp/Chamfer/Round, Corner Width(px, 이름 정리), Corner Segments, Lasso 그리는 중·Rectangle 드래그 중 미리보기가
  실제 상태기계에서 동작함을 테스트로 확인. 새 기능 추가 없음.

## 0.8.0 — 입력 P0 수정, Base Mesh, Loft/Surface, ZBrush Bridge (2026-10-13)

기준: ChatGPT **v0.7.2** (`reference/CHATGPT_v0_7_2/`). v0.7.1(트리플 클릭, Ortho Lock)과 v0.7.2(마스크 레이캐스트,
열린 Mask Brush Stroke, Edge Finish 엣지 수 진단)는 유지. 독립 Curve Tool(Panel/Curve, `mch.draw_path`)은 수정하지 않음.
검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 입력 / UI
- **Esc → 선택 도구 복귀**: 획 중이든 대기 중이든 Esc는 미완성 획만 버리고 `builtin.select_box`로 전환. 적용된 컷 유지.
  (대기 중 Esc는 도구 키맵의 `mch.exit_tool`, 팝업 대기 중 Esc도 동일.)
- **더블클릭 자동 폐합**: Lasso/Curve Lasso는 시작점 근처가 아니어도 더블클릭 위치에서 마지막 점→시작점으로 닫고 적용.
  DOUBLE_CLICK은 점을 추가하지 않고, 같은 마우스다운에 PRESS+DOUBLE_CLICK이 함께 와도 4px 이내 중복 점은 버림,
  시작점 위의 마지막 점도 제거 → 길이 0 엣지 없음.
- **트리플 클릭 상태기계 정리**: v0.7.1 카운터 유지, 단 Curve Lasso 점 토글/드래그·핸들 클릭(편집 클릭)은 세지 않음.
  v0.7.2에서 같은 점을 세 번 누르면 도구가 꺼지던 충돌을 테스트로 재현 → 수정.
- **Curve Lasso 재설계**: 처음부터 부드러운 닫힌 스플라인(Catmull-Rom 탄젠트 → 3차 Bezier 구간). 점 클릭 = 각/부드러움 토글,
  점·Bezier 핸들 드래그(정렬된 대칭 핸들), `Curve Samples`, `Curve Smoothness`. 이전의 "각진 라쏘 + 꼭짓점 라운드 단계" 제거.
- **Free Draw**: Shape 이름을 Brush Stroke → Free Draw로. PRESS→MOUSEMOVE 연속 샘플→RELEASE, 간격/스무딩/단순화.
  Cut/Split/Base Mesh는 닫힌 외곽선, Mask는 열린 브러시(v0.7.2). Lasso에서도 LMB를 누른 채 끌면 연속으로 그려짐.
- **Outline Corners**: Lasso/Rectangle의 2D 모서리 Round/Chamfer(px) — 3D Edge Finish와 분리된 설정.
- 우클릭: Cut/Split/Mask = Shape/PNG 팝업, **Base Mesh = 단면 프로필 팝업**, 더블 = 종료.

### P1 Base Mesh from Shape (새 도구 `mecha.base_mesh`)
- 공통 Shape(Lasso/Curve Lasso/Rect/Circle/Ellipse/Free Draw/PNG)로 그린 윤곽을 뷰 평면에 투영해 **새 닫힌 솔리드** 생성.
  표면 위(윤곽 아래 메쉬가 있으면) 또는 3D 커서 평면. 원본 메쉬 무변경.
- 프로필: Flat, Chamfer(윗면 경계 1세그먼트), Bevel(윗면 경계 N세그먼트), **Rounded/Dome**(경계까지 거리 기반 높이장,
  densified 경계 + 내부 격자의 Constrained Delaunay → 오목 윤곽에서도 면 뒤집힘 없음). Roundness/Height/Edge Height/
  Resolution/Border Width/Segments/Offset/Bevel Bottom.
- 구멍(PNG 링)·여러 섬 지원. 자기교차·너무 작은 윤곽은 메시지와 함께 거부(오브젝트 생성 안 함).
- **Live**: 윤곽과 설정이 오브젝트에 저장되어 값 변경 시 재생성, RMB 프로필 선택도 선택된 Live 오브젝트에 반영. Freeze.
- 경사 뷰에서 거의 일직선인 경계 점 사이 sliver 삼각형이 잘못 분류되던 문제를 테스트로 찾아 **교차 parity 분류**로 해결.

### P2 Loft / Surface (부분)
- Loft: 2+ 커브, 호 길이 재샘플, 방향/시작점 자동 정렬, Catmull-Rom 단면 보간(Smoothness), Cap Ends, Thickness(Solidify),
  Flip, Twist, Close Loft, 섹션 순서 이동/개별 Reverse. Sweep: 단면+경로(평행 이동 프레임, 스케일, 비틀림).
- 커브 수정 시 depsgraph 핸들러로 **Live 갱신**, Apply로 확정. CAD NURBS 패치가 아닌 보간 폴리곤 표면.

### P2 ZBrush Bridge (부분)
- OBJ 파일 기반 Send / Import Back. 오브젝트마다 개별 파일(자동 Join 없음), ID(`mch_zb_id`)와 매니페스트(파일, 시각,
  내보낼 때의 world matrix), 바뀐 파일만 다시 가져와 원래 오브젝트 로컬 좌표로 변환해 메쉬 교체, 이전 메쉬 백업,
  이름 변경/삭제/파일 누락/공유 메쉬 처리, 축·스케일 설정, ZBrush 실행 파일 선택 실행. **GoZ 프로토콜은 구현하지 않음**
  (설치 경로가 있으면 정보로만 표시).

### 기타
- Ortho Lock(v0.7.1): 잠금 상태로 저장한 파일을 다시 열면 타이머가 자동 재시작(v0.7.2는 버튼을 다시 눌러야 했음).
- 새 아이콘 7개(Base Mesh, Loft, ZBrush, 프로필 4종). 매니페스트 0.8.0.

## 0.7.2 / 0.7.1 (ChatGPT)
`addon/mecha_lab/CHANGELOG_v0_7_1_KO.md`, `CHANGELOG_v0_7_2_KO.md` 참고.

## 0.7.0 — MECHA LAB Workspace MVP (2026-10-12)

기준: 배포본 v0.5.9 (`reference/RELEASE_v0_5_9`, 원본 그대로 보존). 미검증 초안 v0.6.0은 참고만 했고 코드를 가져오지
않았습니다(타이머로 Cut 모달을 재시작하는 방식은 경쟁 상태 위험 때문에 채택하지 않음). 검증 수준은 `test_report.md` 참고.

### UI / UX (P0)
- **`MECHA LAB` Workspace**: 버튼·탭 메뉴·F3에서 생성/전환. 현재 탭을 복제해 만들며 다른 탭·Startup File은 변경하지 않음.
  `Repair Layout`, 확인 창이 있는 opt-in `Save as Startup` 제공.
- **왼쪽 큰 아이콘+이름 도구 목록** (Properties 영역 Tool 탭에 표시). 순서: Cut, Split, Boolean, Smart Fuse, Mirror, Mask,
  Curve Array, Radial Array, Panel/Curve, Pose(미구현 표시), Surface Conform, Assets, Remesh, Live Result.
- **공통 Shape 팔레트** (뷰포트 Tool Header, 왼쪽 위): Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Brush Stroke,
  PNG 썸네일 + Custom + Import. 네이티브 버튼이라 GPU hit-test 없음. Shape를 쓰지 않는 도구에서는 비활성 + 안내.
- **오른쪽 Sidebar = 현재 도구 1개의 설정만** (`MCH_PT_main`). 긴 N패널 제거. Sidebar에 접힌 `Tools (fallback list)`.
- **Space** = 큰 아이콘 도구 팝업 (MECHA LAB 탭에서만; 다른 탭은 Blender 기본 Space).
- **Cut과 Split을 별개 도구로 분리.** 별도 Random Polygon / N-gon 항목 제거(Lasso가 그 역할).
- 원본 아이콘 21개(도구 14 + 도형 7) 생성 스크립트 `tools_dev/make_icons.py`.

### Cut 입력 시스템 (P0 버그 수정)
- Cut/Split/Mask를 **네이티브 WorkSpaceTool**로 재구현. LMB 한 번 = 한 획 동안만 모달(`mch.cut_stroke`),
  끝나면 FINISHED → **컷마다 독립 Undo 단계**. 획 사이에는 모달이 없어 `Ctrl+Z`/메뉴/다른 에디터가 정상 동작.
  (v0.5.9: 하나의 장기 모달이 모든 키를 가로채 Ctrl+Z 불가, 메뉴 클릭 전 Esc 필요.)
- 획 도중: 뷰포트 밖 이벤트는 pass-through(팔레트·사이드바·메뉴 클릭 시 Esc 불필요), Shape/도구 변경 시 미완성 획만 폐기,
  `Ctrl+Z`/`Backspace` = 마지막 점, `Ctrl+Shift+Z` = 점 복구, `Esc` = 획만 취소, 더블클릭 확정 시 점 중복 없음.
- **RMB 1번 = Shape 팝업, RMB 더블 = 도구 종료**: 더블클릭 간격(사용자 설정)만큼 기다린 뒤 팝업을 열어 두 번째 클릭을
  삼키지 않음. 대기 중이 아닐 때는 작은 게이트 연산자(`mch.rmb_gate`)가 같은 규칙 처리.
- `Space`는 컷 확정에 쓰지 않음(도구 메뉴). 확정은 Enter / 더블클릭.
- Curve Lasso: 점 재클릭으로 4단계 라운드 순환, 점·핸들 드래그, 핸들 표시.
- 원근(perspective) 뷰에서도 그린 실루엣과 일치하는 **frustum 커터** (v0.5.9는 정사영 가정 prism).
- 2점 직선 컷의 평면도 원근 정확(두 시선 ray를 포함하는 평면).

### 기하 안정성
- 새 `core_geometry`: 커터를 캡(구멍 포함 삼각분할)+벽이 정점을 공유하는 **닫힌 메쉬로 직접 생성**하고 manifold 검사.
- Boolean은 **베이스 메쉬에 대해서만** 평가(기존 모디파이어는 평가 중 잠시 숨김 → 그대로 유지), 결과 검증
  (전체 삭제 / 교차 없음 / 비매니폴드) 후에만 기록. 실패 시 원본 무변경 + 메시지, Undo 단계도 생기지 않음.
- Solver Auto: 닫힌 메쉬는 Manifold → Exact 폴백, 열린 메쉬는 Exact.
- **공유 메쉬(Alt+D) 지원**: 모든 적용 경로(`Cut`, `Boolean`, `Slice`, `Smart Fuse confirm`, `Remesh`, `Live result`,
  `Mirror apply`, `Radial bake/Boolean`, `Apply Live Cut`)를 `bpy.ops.object.modifier_apply` 대신 데이터 수준 적용으로 교체.
  v0.5.9 오류 "Modifiers cannot be applied to multi-user data"를 headless에서 재현 → 0.7.0에서 해결 확인.
  정책: 이 오브젝트만(기본) / 모든 링크 복제본.
- **Edge Finish (Bevel/Chamfer) — 새 절단 엣지만**: 커터 면에 `mch_cutter_face` 속성을 달아 Boolean 후
  커터 면/원래 면 경계만 bevel. 원래 실루엣 모서리는 테스트로 불변 확인. Lasso 모서리 라운드와 완전히 별개 설정.
- Split: 안쪽은 `<이름>_Split` 새 오브젝트, Cap ON/OFF.
- Depth `From Surface`(고정 깊이 포켓) 추가.

### PNG Custom Cut Shape (P1)
- v0.5.9 비매니폴드 원인 재현: **모서리만 맞닿은 픽셀**(대각선 접촉) → 윤곽선이 한 정점을 공유하는 bow-tie →
  커터가 닫히지 않음. 새 파이프라인은 마스크 정리(점 노이즈/핀홀 제거) + 2×2 saddle 해소 + 단순화 결과의
  자기/상호 교차 검증(실패 시 단순화를 줄여 재시도, 최종적으로 원본 픽셀 윤곽) + 포함 깊이 기반 외곽/구멍/섬 구분.
- PNG 도형이 공통 Shape 팔레트의 일부가 됨(Cut/Split/Mask에서 같은 커터 엔진 사용). 클릭 스탬프 / 드래그 크기.
- Smooth Steps, Remove Specks 옵션, 프리셋 schema 2. v0.5.9 프리셋 자동 업그레이드.

### Smart Fuse (P2, 부분)
- **v0.5.9 Smart Fuse 패널의 크래시 원인 확인**: Live Preview 패널이 Blender 5.0에 없는 아이콘 `MOD_NODES`를 사용 →
  패널을 그릴 때마다 TypeError(스크린샷의 잘린 traceback이 아이콘 enum 목록을 출력하는 형태와 일치). `GEOMETRY_NODES`로 수정.
  모든 소스의 아이콘 이름을 5.0 enum과 대조하는 테스트 추가.
- **두 번째 크래시**: 생성 실패 시 정리 코드가 이미 삭제된 노드 그룹에 접근(ReferenceError). 수정.
- 생성 직후 교차 seam 존재 여부 검사: 떨어져 있거나 면만 맞닿은 메쉬는 설명과 함께 거부하고 원래 상태로 복구.
- 셰이프 키가 있는 메쉬는 거부.

### 호환성
- 이전 연산자 ID 유지: `mch.draw_delete_cut`(→ Cut/Split 도구 활성화), `mch.draw_mask`, `mch.stamp_png_cut`,
  `mch.select_tool`, `mch.cut_finalize`(데이터 안전 적용으로 재작성), `MCH_MT_tool_menu`.
- 저장된 .blend의 선택 도구 enum 번호 유지.
- `mch_enabled`(v0.5.9 세션 토글)는 남겨두었지만 사용하지 않음 — 단축키는 Workspace 범위로 대체.
- manifest `blender_version_min` 4.3 → **4.5** (Manifold solver 필요).

### 제거
- v0.5.9 장기 모달 `MCH_OT_draw_delete_cut` 본체, 긴 N패널(`MCH_PT_cut/boolean/fuse/...`), MECHA LAB MODE 토글 UI.
- 오래된 애드온 내부 문서 `README_v0_5_9_KO.md`, `PNG_CUT_GUIDE_KO.md` (원본은 reference에 보존).
