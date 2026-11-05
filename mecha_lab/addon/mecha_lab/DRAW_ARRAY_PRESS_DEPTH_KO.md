# MECHA LAB v0.24.102 — Draw Array / Press Tilt & Edge / Side Depth Guide

기준: v0.24.101 Group Focus 기반, 기존 기능 유지. ZIP을 Blender 애드온으로 설치합니다.

## 1. Draw Group Array

1. 완성된 척추 마디 등 여러 부품을 그룹으로 만든 뒤 그룹 핸들을 선택합니다.
2. Curve Array(Along Curve) 도구/패널로 이동해서 **Draw Array from Selected Group**을 선택합니다.
3. 뷰포트 안에서 마우스 왼쪽으로 경로를 드래그하고 놓습니다. 우클릭 또는 Esc는 취소합니다.
4. 새로 선택되는 DrawArray 컨트롤러의 **Copies** 슬라이더로 개수를 1~200개까지 변경합니다.
5. Scale, Start, End, Follow Path, Roll로 배치 변경. 원본 그룹은 그대로 남습니다.
6. 생성된 `MCH_DrawArray_Path` 커브는 Edit Mode에서 직접 수정 가능합니다. 오브젝트 모드 복귀 후 0.6초마다 변화가 확인되면 자동 재배치됩니다.
7. Remove Draw Array는 복제본, 컨트롤러와 해당 경로만 제거하고 원본 그룹은 보존합니다.

주의: 원본의 Mesh/Curve 객체 데이터는 연결 복제(Linked Data)하며, 각 마디는 강체처럼 배치됩니다. 마디 자체가 휘어지지는 않습니다. 독립 생성된 메시 데이터를 바꾸려면 원본을 수정합니다. 그룹 전체가 아닌 선택된 그룹의 각 렌더링 가능한 부품을 연결 복제합니다. 200개 제한은 무거운 원본 그룹으로 인한 과부하를 줄이기 위한 것입니다.

## 2. Press Cut Tilt / Bevel & Chamfer

Press Cut 옵션에 새로운 항목을 추가했습니다.
- **Tilt Left/Right**: 스탬프 바닥을 좌우로 기울임 (-65° ~ +65°)
- **Tilt Up/Down**: 스탬프 바닥을 상하로 기울임 (-65° ~ +65°)
- **Stamp Edge**: Cut Settings(기존 설정), Sharp, Chamfer, Bevel
- **Edge Width**: 절단된 새 테두리의 베벨·챔퍼 너비
- **Bevel Segments**: 둥근 베벨의 세그먼트 수

기존 Curve Left-Right/Up-Down과 Tilt는 별개입니다. 절단 처리에 임시로 적용된 Edge Finish 설정은 실행 후 기존 Cut 설정으로 복귀합니다. 일부 복잡한 메쉬에서는 베벨 폭이 크면 커팅이 실패할 수 있으니 작은 값부터 테스트하세요.

## 3. Base Mesh — Side Depth Guide (초기 구현)

1. Base Mesh 도구를 선택한 상태에서 **Depth Guide Mode**를 켭니다.
2. 정면에서 베이스 메쉬 **라인/실루엣을 먼저 그려서 생성**합니다. Sketch First가 켜져 있다면 Enter로 확정합니다.
3. 생성된 **Live Base Mesh**를 선택한 채 뷰포트를 측면으로 돌립니다. 정면과 수직에 가까운 측면 뷰를 권장합니다.
4. Base Mesh 설정의 **Draw Side Guide** 버튼을 누른 후 측면에서 깊이선 가이드를 한 획으로 그립니다.
5. 선의 가시 축 위치에 따라 기존 베이스 메쉬의 단면들이 깊이 방향으로 이동합니다. 정면에서 본 원래 실루엣은 유지됩니다.
6. Height/Bevel 등 Live 설정을 변경해도 깊이 가이드가 재적용됩니다. Clear Guide로 제거할 수 있습니다.

제약: 이번 버전은 한 축에 대해 단일 깊이 값을 지정하는 **측면 단면 가이드**입니다. 자기 교차나 뒤로 되돌아가는 곡선, 임의의 3차원 곡면을 자유 변형하는 기능은 아닙니다. Live Base 상태에서만 적용할 수 있으므로 Base Mesh 도구를 빠져나와 자동 Freeze되기 전에 가이드를 적용해야 합니다.

## 검증

Python 구문 전체 검사, 숫자 보간 유닛 테스트, ZIP 파일 무결성 검사 수행. Blender 5.3 beta 실제 GUI에서의 모달 이벤트와 부울 결과는 현재 실행 환경상 검증하지 못했으므로 테스트용 메쉬에서 먼저 확인해 주세요.
