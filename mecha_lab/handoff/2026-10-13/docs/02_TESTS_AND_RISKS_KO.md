# 권장 개발 우선순위 · 위험 · 수용 기준

## 실행 순서
- **P0:** 입력 안정화(Esc, double-click 자동 폐합, triple-click 상태기계, 곡선 Lasso, 진짜 Free Drawing, UI 클릭/Space/RMB)부터. 이전 v0.7.2 기능 보존.
- **P1:** 새 Base Mesh Shape 생성. Flat→Chamfer/Bevel→진짜 Rounded/Dome, 우클릭 단면 프리셋, Live/Edit 가능한 형태.
- **P2:** ZBrush Bridge와 Loft/Surface. 각각 분리 개발해도 됨. GoZ와 동적 Loft 갱신은 구현에 검증이 필요.

## 기술적 함정
1. Blender에서 `DOUBLE_CLICK` 이벤트가 `PRESS`를 대체하거나 중첩되는 OS 차이 고려, 중복 vertex 방지. ESC와 triple click, double click이 시점별로 명확히 동작하도록 상태기계로 처리.
2. 드래그 프리핸드는 `MOUSEMOVE` 연속 수집(소음 필터/간격/스무딩/단순화). 열린 Brush Stroke vs 닫힌 Free Draw 분리.
3. Curve Lasso는 Catmull-Rom/Auto Bézier 등 연속 보간, 기본값부터 둥글고 핸들/정점 조절 가능. 별도의 Curve Tool에는 영향 금지.
4. Base Mesh는 임의 2D 폐합 경계 triangulation, cap/sidewall solid, correct normals/winding, non-manifold 검증 필요. Dome은 **경계 안쪽으로 보간되는 높이장** 또는 강건한 내부 메쉬가 필요. 오목 다각형에서 naive center fan/offset이 실패할 수 있음.
5. Loft는 커브 arc-length 정규화/재샘플링, 방향/위상/시작점 정렬, 열린·닫힌 커브, 여러 프로파일 순서, twist 제어, solidify/cap 처리 필요. Native NURBS와 보간된 Polygon surface 차이 보고.
6. 자동 GoZ는 ZBrush 버전/설치/프로토콜 검증 없이는 약속하지 말고 OBJ/FBX fallback 허용. 내보내기 전 메쉬 강제 결합 금지.
7. 작업공간과 키맵 등록·해제, 팝업/GUI 패널 그리기 등은 headless만으로 최종 검증 불가. 타깃 GUI 체크리스트 제공.

## 기하/상태 테스트 요구
- Lasso/Curve Lasso를 시작점에서 먼 곳에서 더블클릭 확정: 닫힌 연속 외곽, 중복점과 zero-length edge 없음.
- 트리플클릭으로 선택 복귀 시 2회 클릭 확정과 충돌 없고 Undo 단계 정상.
- Esc → 실제 Blender 선택 도구 복귀, 미확정 선 폐기, 이미 완료한 메쉬 변경은 유지.
- Free Draw: PRESS + 다수 MOUSEMOVE + RELEASE → 연속 샘플 기록(단순 점 몇 개가 아님).
- Curve Lasso: 포인트 간 곡선 연속, 해상도 조절에 따라 곡선 샘플 증가.
- Base Mesh Flat/Chamfer/Bevel/Dome 모두 독립 메쉬 생성, 폐합 솔리드의 manifold/winding 검사, 단면 간 실질적 정점 위치/형상 차이 확인.
- Dome은 경계에서 0에 가까운 높이, 내측 면이 볼록한 형태이며 일반 Bevel과 명백히 다른 프로파일.
- Loft: 2 열린 커브, 3개 이상 프로파일, 서로 다른 포인트 수, reverse direction, closed loop, 커브 이동에 따른 Live 반영 확인.
- Cut/Boolean/PNG/Mask/Mirror/Ortho Lock/Alt+D Undo 회귀 없음.

## Windows Blender 5.0.2 실제 GUI 테스트 필수
- 왼쪽 Workspace 도구 목록이 표시되고, 공통 Shape 팔레트와 오른쪽 설정이 올바르게 동작.
- Space가 애니메이션 재생 대신 Tool Popup을 열거나 적어도 fallback을 정상 제공.
- Esc/우클릭 단일·더블/좌클릭 더블·트리플의 키입력 충돌 없이 동작.
- 라쏘 원거리 더블클릭으로 확정; Free Draw 마우스 움직임을 실제로 따라감.
- Rounded/Dome 실제 곡률 확인, Base Mesh RMB 프리셋 선택, Loft Live 변화 확인.

## 보고 형식
각 기능을 `완료/실행 검증`, `구현됐으나 GUI 미검증`, `부분 구현`, `미구현`으로 나누어 보고. Blender 버전과 환경 명시. 설치 ZIP/소스/테스트 스크립트/로그/변경 이력/남은 한계 제공. headless 통과를 GUI 동작 인증으로 서술 금지.
