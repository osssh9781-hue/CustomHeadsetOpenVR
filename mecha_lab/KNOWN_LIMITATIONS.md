# KNOWN LIMITATIONS — Mecha Lab 0.11.3

## 00000. 0.11.3
- Radial Array 충돌: headless에서 재현 안 됨(속성 40회 변경, Boolean 연결·미리보기·적용). 원인 후보(단축키 편집 행의 오래된
  KeyMapItem 참조)를 고쳤지만 확정 아님 → `C:\Users\<이름>\AppData\Local\Temp\blender.crash.txt` 내용 필요.
- MECHA LAB Workspace의 Object Mode에서 N = Quick Menu → 사이드바는 View 메뉴 > Sidebar 또는 단축키 편집 행에서 N을 다른 키로.
- Lean Mirror: 도구 목록(왼쪽 편집기)에서 고르면 마우스가 뷰포트 밖에 있어 첫 이동 때 축이 바로 바뀔 수 있음. 실제 GUI 미검증.
- "기울어진 알약 3개"는 서로 떨어진 3개(환풍구 모양)로 만듦. 서로 붙은 모양이 필요하면 알려 주세요.

## 0000. 0.11.2
- 일반 Cube "whole object" 오류는 여전히 headless에서 재현되지 않음(가짜 투영, 실제 RegionView3D 원근/직교, 모달 경로, Edit Mode 모두
  시도). 0.11.2의 오류 메시지 대괄호 부분과 Self Test의 "real 3D View projection" 줄이 원인 판단에 필요.

## 000. 0.11.1 (먼저 읽기)
- **일반 Cube에서 "would delete the whole object" 오류는 headless에서 재현되지 않았습니다.** MCH_Box(Live Primitive)는 재현·수정.
  Cube에서 아직 나오면 오류 메시지 끝의 `[대상: 연산, solvers tried: ...]` 부분과 **Run Mecha Lab Self Test** 결과를 보내 주세요.
  연산이 "Keep inside"로 나오면 Alt가 눌린 것으로 판정된 것입니다.
- Live Primitive를 Cut/Split/Boolean하면 Live 상태가 해제되고 일반 메쉬가 됩니다(Primitive 슬라이더로 다시 편집 불가).
- Select / Move 단축키 W는 MECHA LAB Workspace의 Object Mode에서만 동작(다른 Workspace의 W = Blender 기본 선택 순환 그대로).
  실제 GUI에서 W 입력·기즈모 표시·모달 취소는 **미검증**(headless는 툴 변경 시 모달 취소 로직만 확인).
- 0.10.0 항목 중 "Alt+짧은 클릭", "직선 Cut Ctrl+클릭"은 0.11.1에서 없어졌습니다(아래 0절은 기록용).

## 00. 0.11.0 Mechanical Toolkit 한계 (먼저 읽기)
- **Windows / Blender 5.0.2·5.3 GUI 미검증.** 기하·로직은 headless 테스트(99항목)로 확인.
- Face Extract / Armor: 파츠는 선택 영역 사본으로 만듦(원본이 나중에 바뀌어도 파츠는 그대로). Armor의 능선 선명도는
  **Resolution**(선택 면 세분) 에 좌우됨 — 능선이 메시 엣지와 정렬되는 것은 아님. 선택 3,000면·Resolution 1에서 슬라이더 1회
  약 0.35초(이 컨테이너 CPU), 큰 선택은 Resolution 0 권장.
- Armor 방향별 값은 경계 정점의 방향 각도로 섞임(N/E/S/W cos² 분할). Bevel Segments는 방향마다 다르게 줄 수 있지만 한 파츠의
  링 수는 최댓값으로 통일(적은 방향은 같은 선 위에 점이 놓여 보이는 모양은 동일). 날카로운 방향(폭 0)은 아주 작은 챔퍼(크기의
  0.2%)를 가짐.
- Armor는 챔퍼 방향 Inward만(Outward는 Basic). Split 능선은 실제 분리가 아니라 깊고 좁은 V홈.
- 엣지 폭이 파츠 높이/크기보다 크면 자동 축소되고 패널에 메모가 뜸. 선택이 한 점에서만 맞닿는 경우 거부.
- Bevel Angle은 Basic의 측면 세로 엣지(Bevel 모디파이어, 가중치)에만. Armor 측면 엣지는 방향별 Bevel로.
- Edge Molding: 코너는 마이터(최대 1/0.3배). 매우 날카로운 코너는 겹칠 수 있음. Armor 중앙선 몰딩은 파츠 윗면에 레이캐스트.
- Hollow: Rim Thickness / 개구부는 원본 오브젝트에 Vertex Group·면 속성(`mch_opening`)을 추가함(형상은 불변, Reset 시 제거).
  자기교차 검사는 겹치는 삼각형 + 안쪽 공간보다 두꺼운 정점 수(대략적).
- Mesh Along Curve: Curve Deform은 슬라이더가 메쉬 오브젝트 위치를 커브 기준으로 설정(메쉬를 직접 옮기면 다음 슬라이더 변경 시
  되돌아감). Curve Array Rigid는 편집 중 인스턴스, Apply 때 실제 메쉬로 변환.
- Cable: 경로 슬라이더를 바꾸면 Edit Mode에서 직접 옮긴 점은 다시 계산됨(두께·단면 슬라이더는 경로를 건드리지 않음).
  처짐은 월드 -Z 방향.
- Undo/Redo는 각 연산자(REGISTER/UNDO)와 슬라이더 변경 단위 — headless에서는 Undo 스택을 실행할 수 없어 GUI 확인 필요.
- 미구현: Custom Guide Mode(표면에 직접 능선 그리기), 메쉬 프로파일(커브만) 케이블, 몰딩/케이블 공유 일괄 편집 UI.


## 0. 0.10.0에서 먼저 알아야 할 것
- **사용자 보고 B01 Mirror / B02 Loft / B03 Smart Fuse는 headless에서 재현되지 않았습니다.** 0.10.0의 수정은 GUI에서만 생길 수
  있는 원인(등록 중단 B09, 도구 목록에서의 툴 전환 실패, 미확정 Fuse 미리보기의 패널 점유, Undo 후 남은 상태)을 고친 것이며
  실제 원인과 같다고 단정할 수 없습니다. 아직 문제가 있으면 **Workspace & Hotkeys > Run Mecha Lab Self Test** 결과(클립보드에
  복사됨)와 Blender 시스템 콘솔 로그를 보내 주세요.
- Alt+짧은 클릭 판정: 0.5초 이내, 5px×UI Scale 이내 이동. Object Mode의 Alt+클릭 복귀는 Blender의 `CLICK` 이벤트 사용
  (Blender 기본 Alt+클릭 = 오브젝트 목록 선택은, 오브젝트가 없는 곳에서는 그대로 동작).
- 직선 Cut의 "남길 쪽 클릭"은 Alt+클릭에서 **Ctrl+클릭**으로 바뀜(Alt+클릭은 도구 종료).
- Base Mesh Alt+드래그 커터: Flat/Chamfer/Bevel만(Dome은 거부). 깊이 = Height, 표면 바로 위 1% 높이에서 시작(동일 평면 회피).
  대상은 선택된 메쉬(Live Base Mesh 제외), 없으면 도형 중심 아래 메쉬.
- Base Mesh 세션 Auto Apply = Live 해제(Freeze)이며 형상은 그대로. "세션"은 마지막으로 도구를 떠난 뒤 만든 Base Mesh.
- Stabilizer: 드로잉 중 60Hz 타이머. Strength 100%의 시간 상수 0.35초. 마우스를 놓으면 커서까지 따라와 끝남(ZBrush처럼 지연
  위치에서 멈추는 옵션은 없음). Mask(숨김)에는 연결하지 않음.
- Deform: Falloff 거리는 직선(유클리드) 거리 — 굽은 Bend Curve에서는 곡선을 따라 잰 거리가 아님. Mecha 기즈모는 선택 중심에
  표시(Each Point 피벗일 때도 위치는 중심). Bend Curve Scale = 반지름(두께)만, 점 위치는 그대로. Lattice 해상도 변경은 Blender가
  기존 변형을 재샘플(B-Spline에서는 근사). Rigid Pose는 여전히 미구현.
- Mask는 숨김만 했습니다(코드·데이터 유지). 완전 삭제는 승인 후.


## A. 검증되지 않은 것 (가장 중요)
**Windows 11 + Blender 5.0.2 GUI에서 실행된 적이 없습니다.** 모든 자동 테스트는 Linux headless `bpy 5.0.1`입니다.
headless에는 창·실제 이벤트가 없으므로 아래는 **GUI 미검증**입니다:
- Workspace 생성(`workspace.duplicate`) 및 타이머 기반 왼쪽 영역 분할, 왼쪽 Properties(Tool 탭) 도구 목록 표시.
- Tool Header의 공통 Shape 팔레트 표시·클릭, 팝업(`wm.call_panel`) 위치·크기.
- 실제 이벤트 순서: Esc, 더블클릭(OS가 PRESS+DOUBLE_CLICK을 함께 보내는 경우 포함), 트리플 클릭 시간창(최대 0.72초,
  12px), RMB 단일/더블 타이밍, Free Draw 중 MOUSEMOVE 빈도, Lasso 드래그 그리기.
  → 상태기계 자체는 같은 클래스에 가짜 이벤트를 넣는 테스트(68개)로 검증했지만 GUI 이벤트 우선순위를 증명하지는 않습니다.
- WorkSpaceTool 키맵(LMB/RMB/Esc/Space)이 Object Mode 기본 키보다 우선하는지.
- Loft의 Live 갱신은 depsgraph 핸들러로 headless에서 동작 확인(커브 점/오브젝트 이동). GUI에서 편집 모드로 커브를 고칠 때의
  갱신 빈도/성능은 미측정.
- ZBrush: 실제 ZBrush가 없어 **ZBrush가 쓴 OBJ 파일로는 테스트하지 않았습니다**(파일 내용을 바꿔 ZBrush 수정을 흉내 냄).
  ZBrush의 OBJ 축/스케일 관례(위아래 뒤집힘 등)는 사용자 환경에서 Forward/Up/Scale로 맞춰야 할 수 있습니다.

## B. 구현됐지만 범위가 좁은 것 (부분 구현)
- **Base Mesh**: 뷰에 수직인 평면 위 독립 솔리드만. Surface Follow / Project(곡면을 따라 휘는 장갑판)는 미구현.
  Dome의 Edge Height는 최소 Height의 1% (0이면 닫힌 솔리드를 만들 수 없음). Dome 해상도 상한(내부 점 12,000개).
  Bevel/Chamfer 폭이 너무 크면 Blender bevel clamp로 줄어듦. 원근 뷰에서는 윤곽이 평면에 원근 투영됨(그 뷰에서 보면 일치).
- **Curve Lasso**: 핸들은 정렬된 대칭 핸들(좌우 길이/방향 독립 아님). 첫 점 클릭은 '닫기'라서 첫 점을 각진 점으로 바꾸려면
  다른 점을 먼저 찍은 뒤 조정해야 함. 급한 곡선은 자기교차할 수 있음(이때는 획을 유지하고 경고).
- **Loft/Surface**: 열린/닫힌 커브 혼합 불가. 각 커브의 첫 스플라인만 사용. 섹션 순서는 활성 커브부터 가까운 순서(또는 이름).
  연속성(G1/G2), 트리밍, 진짜 NURBS 패치 없음. Cap은 n-gon(비평면일 수 있음).
- **ZBrush Bridge**: OBJ만, GoZ 아님. 다시 가져오면 UV·셰이프 키·커스텀 속성은 OBJ에 담긴 것만 남음. 머티리얼은 슬롯 목록만 복사.
  OBJ 그룹이 여러 개면 하나의 메쉬로 합쳐 원래 오브젝트에 넣음(사용자 오브젝트끼리 Join하는 것은 아님).
- **Esc 동작 변경**: 이제 Esc는 항상 선택 도구로 돌아갑니다. 그리던 획만 지우고 도구에 남고 싶으면 Backspace/Ctrl+Z로 점을 지우세요.
- Mecha 도구 4개(Cut/Split/Mask/Base Mesh)는 모든 Workspace의 Object Mode T툴바에 보입니다(Blender 도구 등록이 전역).
  단축키(Space/B/C)는 MECHA LAB 탭에서만.
- 우클릭 선택(Right-Click Select) 키맵 사용자는 Mecha 도구 중 RMB가 선택 대신 팝업/종료로 동작.
- Mask: **면 단위**, Cut/Boolean 보호 없음, Weight/Pose 없음. Live Cut(Auto Apply OFF)에서는 Edge Finish 미적용.
  Smart Fuse는 실제로 겹친 닫힌 메쉬만.

## B-2. 0.9.0 기능의 범위
- Mesh Curve: Twist는 시작→끝 선형 누적(구간별 제어 없음). 경로에 기존 tilt가 있으면 더해짐. Rotation은 단면/복제본 기준.
  Edit Mode 점 더블클릭 키맵은 Blender의 다른 Curve 더블클릭 동작보다 먼저 받음(Mecha 경로가 아니면 통과) — GUI 미검증.
- SubD Plane: Crease는 선택 엣지에 값 쓰기만(전용 시각화 없음). Apply All은 Simple→CC→Solidify 순서만 적용하고 그 밖의
  사용자 모디파이어는 남김.
- Radial: Ring Rotation은 링 중심(3D 커서 위치에 놓인 캐리어 원점) 기준. 오브젝트 회전과 함께 쓰면 둘 다 적용됨.
- Gap Split: Gap Width는 대상 중심 깊이에서 화면 픽셀로 환산 → **직교 뷰에서는 정확, 원근 뷰에서는 깊이에 따라 약간 다름**.
  오목한 도형에서 Gap이 오목부보다 크면 거부. Live(Auto Apply OFF) 미지원.
- Split 양쪽 마감은 Cap Split ON일 때만(캡 면이 없으면 '새 엣지'가 없음).

## C. 미구현
- Base Mesh의 Surface Follow / Project.
- GoZ 프로토콜, ZBrush 자동 작업(DynaMesh 등은 사용자가 ZBrush에서 직접).
- Mask Protect / 정확 윤곽 / Weight Extract, Pose(Rigid/Soft), FBX/Asset Browser 커터, 사용자 키 설정 전용 UI,
  Workspace 템플릿 .blend. (Radial Array 개별 방향은 0.9.0에서 Copy Rotation / Rotate Each Copy로 구현.)
