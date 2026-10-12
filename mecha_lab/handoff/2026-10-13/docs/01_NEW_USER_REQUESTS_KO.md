# 2026-10-13 최신 확정 추가 요구사항 (최우선)

## 1. 입력 / UI UX 수정 [P0]

- **Esc → 일반 선택 모드:** Cut / Split / Mask / 새 Base Mesh 등 도구를 사용하다 `Esc`를 누르면 현재 미확정 획만 취소하고 Blender 일반 선택 도구로 복귀. 완료한 컷은 취소하지 말 것. 현재 v0.7.2의 '획만 취소하고 도구 잔류' 동작을 사용자가 원하지 않음.
- **Lasso / Curve Lasso 더블클릭 완전 자동 폐합:** 시작점 근처로 돌아가지 않아도 마지막 클릭 위치에서 시작점으로 자동 연결, 확정/실행. 연속 입력 중 double-click event로 중복 정점을 삽입하거나 길이 0 엣지를 만들지 말 것.
- **빠른 좌클릭 3회 → 선택 도구 복귀:** v0.7.1 기능을 유지하되 더블클릭 확정과 충돌하지 않는 상태기계 필요. 2번째 클릭 확정/3번째 선택 복귀를 구분해야 함.
- **Ctrl+Z는 컷 하나당 한 단계**, 메뉴와 뷰포트 입력 자유롭게 접근. Esc를 눌러야 패널을 누를 수 있는 구조 금지.
- **Cut/Split 우클릭 한 번 = 공통 Shape/PNG 프리셋, 더블 우클릭 = 도구 종료.** 새 Base Mesh의 단일 우클릭은 아래 단면 모양 프리셋 메뉴.
- **Workspace 레이아웃 유지:** Blender 상단 MECHA LAB 작업공간, 왼쪽 큰 아이콘+이름 도구 목록, 뷰포트 좌상단 모든 도구가 공유하는 Brush/Shape 팔레트, 오른쪽 현재 도구 설정만. Space 도구 선택 팝업, 충돌 시 확실한 왼쪽 fallback. Cut과 Split은 별도 도구.

## 2. 공통 Shape 팔레트 정리 [P0]

- `Lasso`: 기존의 직선 세그먼트/클릭 기반 자유 폴리라인 도형. 별도의 랜덤 Polygon 도구 불필요.
- **`Curve Lasso`: 처음부터 곡선으로 연결되는 매끄러운 폐합 윤곽.** 현재 '각진 라쏘를 만든 후 꼭짓점 클릭으로 둥글림 단계 조절'은 원하는 기본 모드가 아님. 제어점으로 베지어/스플라인을 만들고 샘플 해상도·편집 핸들 조절. Lasso와 Curve Lasso는 별개.
- **`Free Drawing`: 클릭마다 점 하나 찍는 도구가 아닌 진짜 연속 드로잉.** 마우스 PRESS→MOVE 연속 샘플링→RELEASE 완료. 샘플 간격/스무딩 옵션. `Cut/Split/Base Mesh`의 닫힌 Freehand Lasso와 `Mask`의 열린 Brush Stroke 출력을 분명히 구분. 현재 v0.7.2의 Mask Brush Stroke 패치는 유지.
- Rectangle / Circle / Ellipse / PNG Vector Shape 썸네일 / 새 Lasso·Curve Lasso·Free Draw. 공통 Shape 선택이 모든 드로잉 도구에서 공유돼야 함.
- 도형 **윤곽선 코너 라운드/챔퍼** 옵션과 절단된 **3D 엣지 베벨/챔퍼** 옵션은 서로 다른 설정으로 분리.
- **명시적인 금지:** 기존 독립 **Curve Tool 자체는 수정하지 말 것**. 이번 추가 요구는 공통 *Curve Lasso* 및 Free Drawing에 관한 것만임.

## 3. 신규 도구: `Base Mesh from Shape` [P1]

**목적:** 현재 Mask의 Face 단위 Extract가 부정확/어렵다면 그것과 상관없이, 사용자가 라쏘·Curve Lasso·Free Drawing 등으로 그린 화면 윤곽 그대로 **새로운 입체 메쉬 오브젝트**를 만들 수 있어야 함. 원본을 잘라내거나 마스크를 추출하는 도구가 아닌 독립 생성 도구.

### 사용 흐름
1. 왼쪽 도구 목록에서 `Base Mesh` 선택. 공통 Shape 팔레트에서 Lasso/Curve Lasso/Rectangle/Circle/Ellipse/Freehand/PNG Shape 선택.
2. 뷰포트에서 윤곽 그림. Lasso는 어떤 위치에서든 더블클릭으로 윤곽을 닫아 확정.
3. 원본을 보존하고 **새 오브젝트** 생성. Height/Thickness/Offset/Resolution 조절, 캡 닫힘, 면 노멀 정리, 재편집할 수 있는 Live 옵션 선호.
4. **Base Mesh 활성 상태에서 우클릭 → 단면 프리셋 팝업(아이콘+이름):**
   - **Flat:** 평평한 윗면과 직선 측면.
   - **Chamfer:** 경계의 직선 사선 깎임.
   - **Bevel:** 경계만 부드럽게 라운드, 폭/세그먼트 조절.
   - **Rounded / Dome:** **경계에서 안쪽 윗면 전체가 볼록하게 부푸는** 유기적인 돔. Bevel로 둥글려 보이게 하는 것으로 대체 금지. Roundness, Height, Resolution 조절.
5. 나중에 곡면 위에 장갑판을 배치할 수 있도록 `Surface Follow / Project` 옵션은 희망 사항. 우선 독립 메쉬로 안정적인 폐합 솔리드부터.

### 안전/품질
- 실루엣 충실도, 물리적 입체/두께, 올바른 face winding / manifold 여부 검사.
- 오목한 다각형, 고해상도 윤곽, 중복점, 자체 교차, 홀/근접 경계 시 실패를 명확히 알리고 원본 보존. Dome은 오목 윤곽에서 단순 center-fan으로 생성하면 면이 밖으로 튀므로 주의.
- 새 도구가 현재 Mask Extract/Boolean/Cut/Undo를 깨지 않도록 회귀 테스트.

## 4. ZBrush ⇄ Blender 브리지 [P2]

- Blender에서 **사용자가 선택한 여러 오브젝트**를 ZBrush로 보내고, 직접 작업한 뒤 Blender로 다시 가져오기.
- **자동 Join 하지 말 것.** 필요하면 사용자가 보내기 전에 선택 오브젝트를 직접 Join.
- ZBrush에서 DynaMesh, Smooth, Remesh 등은 **사용자가 직접 실행**. 자동화 요구가 아님.
- GoZ 프로토콜/설치 경로 연동 가능성 확인. 불확실하면 OBJ/FBX Send + Import Back 경로를 구현하고 진짜 GoZ를 지원하는 척하지 말 것.
- 원본 식별, 임시 파일 위치, 단위/축, 여러 오브젝트 재가져오기 및 실패 복구를 설계.

## 5. 신규 도구: `Loft / Surface` — NURBS처럼 커브 사이 메쉬 [P2]

**목표:** 사용자가 두 개 이상 커브를 만들고 그 사이를 연결해서 **매끄러운 표면 메쉬**를 얻기. 자동차 펜더나 메카 외장곡면처럼 활용.

- **Loft:** 선택한 2개 이상의 3D Curve를 단면/레일 순서대로 연결해 연속적인 곡면 생성.
- **Sweep / Rail (옵션):** 단면 커브 하나를 다른 경로 커브를 따라 보내 입체 형상 생성.
- `Interpolation/Smoothness`, `Curve Samples`, `Surface Segments`, `Thickness`, `Cap Ends`, `Normal`, `Reverse Curve`, `Twist/Alignment`, `Live/Apply` 등 오른쪽 패널에서 조절.
- 커브 수정 시 생성 결과가 **Live 갱신**되는 비파괴 흐름 우선. 필요하면 별도 Apply로 메쉬 확정.
- 열린 곡선/닫힌 곡선, 서로 점 개수가 다른 곡선, 순서 역전, 3개 이상 단면, 끝단 닫힘, 노멀/교차 문제를 고려.
- **CAD의 수학적 NURBS 패치 자체**와 **NURBS-like 유연한 커브 보간 메쉬**는 다름. 먼저 사용자에게 필요한 부드러운 시각적 모델링 결과를 보장하는 방식 권장. 실제 지원 범위를 명시할 것.

## 6. 보존해야 할 기존 기능 및 과거 요청

- v0.7.1: 빠른 3회 클릭 → 선택 복귀, 회전해도 원근이 되살아나지 않는 **Ortho Lock**.
- v0.7.2: 마스크 면 레이캐스팅 인식 개선, Mask 열린 Brush Stroke, 적용된 컷 경계 베벨 엣지 수 진단.
- Cut/Boolean/Png 컷/Shared mesh Modifier Apply/Undo, Space 팝업 및 Workspace 내비게이션, Mirror/Arrays/Surface Conform 기능 보존.
- 현재 Mask는 **Face 단위**이고 Boolean 보호/정밀 웨이트 추출은 아직 미구현. Live Cut Auto Apply OFF에서는 Cut Edge Finish 미적용. Smart Fuse는 제한 있음. Pose 및 FBX Asset Cutter 미구현. 새로 작업하면서 기존 버그를 다시 도입하지 말 것.
