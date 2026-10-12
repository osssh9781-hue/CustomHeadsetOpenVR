# KNOWN LIMITATIONS — Mecha Lab 0.8.0

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

## C. 미구현
- Base Mesh의 Surface Follow / Project.
- GoZ 프로토콜, ZBrush 자동 작업(DynaMesh 등은 사용자가 ZBrush에서 직접).
- Mask Protect / 정확 윤곽 / Weight Extract, Pose(Rigid/Soft), FBX/Asset Browser 커터, 사용자 키 설정 전용 UI,
  Radial Array 개별 방향, Workspace 템플릿 .blend.
