# 최우선 확정 UI/UX 요구사항 — Mecha Lab (사용자 직접 수정안)

**중요: 이 문서는 기존 01_REQUIREMENTS_KO.md 및 03_CLAUDE_PROMPT_KO.md에 있는 UI/툴 분류 설명과 충돌할 때 우선합니다.** 이는 사용자 승인된 설계 요구사항이며 **현재 구현 완료를 의미하지 않습니다.** Blender 5.0.2에서 실제 GUI 검증이 필요합니다.

## 1. 3개 독립 UI 영역 — 역할을 섞지 말 것

### A. 3D View 왼쪽 위: 공통 브러시/도형 선택 팔레트 (Global Shape/Stroke Palette)
도구별로 사각형/원/라쏘 입력을 다시 만들지 않는다. Cut, Split, Mask, Panel Line 등 도형을 그리는 기능이 이 **동일한 입력 팔레트**를 공유한다. 왼쪽 상단에 보이는 작고 간결한 고정 또는 팝오버 팔레트.

공통 브러시 종류 (**이 6종이 기본**):
1. **Lasso**: 사용자가 자유롭게 꼭짓점을 클릭해 윤곽을 만드는 직선/각진 라쏘. 기존 'Random Polygon / 불필요한 랜덤 다각형'은 별도 옵션에서 제거한다. 임의 다각형은 Lasso 자체가 담당한다.
2. **Curve Lasso**: 포인트를 선택하고 위치와 베지어 핸들을 편집해 곡선 윤곽을 만든다. 커브 에디팅은 개별 독립 도구 대신 이 **브러시 프리셋의 편집 모드**에 둔다.
3. **Rectangle**: 사각형.
4. **Circle**: 원형.
5. **Ellipse**: 타원형. Circle과 명시적으로 구분.
6. **Brush Stroke**: 마스크 페인팅용 자유 스트로크, 크기/부드러움(Falloff) 조절. 컷에 사용할 때는 닫힌/두께 있는 스트로크 커터로 변환해야 하며, 마스크 도구에서는 누적 칠하기로 작동.

- 동일 팔레트에서 Corner Rounding/Bevel, Chamfer, Width, Curve Resolution(segments), 포인트/핸들 편집을 노출. 사용자가 **라쏘 윤곽의 모서리 자체**를 둥글게/각지게 만드는 컨트롤이다.
- Cut 결과 메시의 절단 **엣지 자체를 베벨/챔퍼**하는 Edge Finish는 별도 **오른쪽 Cut/Boolean 설정**에 둔다. 서로 다른 두 종류의 bevel/chamfer를 혼동하지 말 것.
- PNG → 벡터화 Cut Custom Shapes 및 사용자 제작 프리셋은 같은 팔레트의 별도 **썸네일 갤러리**에서 선택. 파일별 저장, 이름 변경, 덮어쓰기, 삭제, 공유/가져오기 지원. 생성된 프리셋은 단순 PNG 픽셀 커터가 아니라 닫힌 벡터 윤곽이어야 한다.
- Cut 등 드로잉 도구 사용 중 **우클릭 1회 = 이 공통 Shape Preset 팝업**, **우클릭 더블클릭 = 현재 드로잉 도구 종료**. 도형 변경 시 Esc 불필요. 팝업과 더블클릭 간 입력 경쟁/동작 충돌 테스트 필수.

### B. Space: 큰 '도구' 선택 메뉴 (Global Tool Palette)
ZBrush Brush Picker / 3DCoat 메뉴 같은 **큰 아이콘+이름**의 그리드/팔레트. 이것은 드로잉 도형 선택 메뉴가 아니라 **작업 종류** 선택 메뉴이다. **Cut과 Split은 하나의 버튼이 아니라 명확하게 분리된 독립 도구**이다.

화면상의 기본 순서: **Cut → Split → Boolean → Smart Fuse → Mirror**가 첫 그룹. 나머지 Mask, Array, Panel/Curve, Surface Conform, Pose, Asset Library, Basic Remesh 등을 다른 그룹으로 배치. Cut을 누른 후 우클릭하면 위 A의 공통 도형/프리셋 메뉴를 띄움.

Space 메뉴가 Blender 키맵 충돌로 사용자 버전 5.0.2에서 신뢰할 수 없다면, 기능 누락시키지 말고 **3D View 왼쪽 세로 툴바(Blender Sculpt처럼 아이콘+명칭)**로 동일 도구 팔레트를 구현. Space 메뉴를 제공한 경우에도 Blender의 기본 Space 동작과 충돌하지 않도록 Mecha Lab Mode 활성 상태로 한정, 끄면 원래 키맵 복귀.

### C. 3D View 오른쪽: 활성 도구의 세부 옵션 패널 (Contextual Options)
한 번에 Cut / Split / Boolean / Smart Fuse / Mirror... 전체 옵션을 펼쳐 긴 N패널을 만들지 말 것. **선택된 도구 1개에 해당하는 설정만** 나타나야 한다. 브러시 모양/라쏘 종류는 A에 있으므로 오른쪽에 불필요하게 중복하지 않음. 예: Cut일 때 Cut Depth, Auto Apply, Keep Inside/Outside, Edge Finish (Off / Bevel / Chamfer + Width / Segments), 상세 품질 설정만.

## 2. 입력 UX 통합 규칙
- Cut과 Split은 Space 도구 메뉴에서 **각각 별도로 선택**. 공통 브러시 팔레트는 유지하되 선택된 Tool에 따라 적용 행동이 다르다.
- Cut: 일반 드로잉은 안쪽 제거, Alt+드로잉 안쪽 보존; 도형 완성 시 즉시 적용, Cut 도구는 계속 활성화.
- Split: 선택 영역/나머지를 둘 다 별도 메쉬로 생성, 필요 시 Cap; Cut의 삭제 옵션과 혼동하지 않는다.
- Mask: 같은 브러시로 마스크 누적, Alt+드로잉 지정 부분 지우기, Clear까지 보존. 브러시 스트로크는 이 도구에서 특히 중요하다.
- Point editing: 선택된 기존 점 다시 클릭 시 직각→약한 곡선→중간→강한 곡선→직각 반복, 곡선 핸들 두 개 표시/드래그. Lasso와 Curve Lasso 간 스위치는 동일 편집 엔진으로 처리.
- 모든 드로잉 도구: Enter 또는 좌클릭 더블클릭 확정. Shift+클릭 직선/스냅, Backspace 마지막 점 삭제, Esc 현재 도형만 취소, Ctrl+Z/Shift+Ctrl+Z 되돌리기/다시 실행. 더블클릭은 마지막 점 중복 생성 금지.
- 마우스가 오른쪽 설정 패널이나 다른 Blender 편집기로 이동하면 모달이 이벤트를 독점하지 말아야 하며, 도형·툴 교체 때 Esc 강요 금지. 메뉴를 클릭하면 현재 미완성 획은 안전하게 취소하고 새 설정 적용.
- Mecha Lab Mode일 때만 사용자 재설정 가능한 단축키 작동; OFF면 Blender 기본 키로 복원. 뷰포트에서 브러시/툴을 바꾸는 데 한 번의 클릭만 필요.

## 3. 필수 UI 수용 기준 (Blender 5.0.2 GUI 테스트; bpy headless로 대체 불가)
1. Mecha Lab Mode ON → Space → 아이콘+이름이 있는 도구 팔레트 표시; Cut 선택 → 오른쪽에 Cut만 표시.
2. Space → Split 별도 선택; 현재 브러시 형태는 변경 없이 Split 설정만 표시.
3. Cut 중 RMB 한 번 → Rectangle/Circle/Ellipse/Lasso/Curve Lasso/Brush Stroke/PNG Custom Shapes 썸네일 표시.
4. RMB 더블클릭 → Cut 종료. 한 번 클릭만으로 먼저 팝업이 떠 더블클릭 종료를 방해하지 않음.
5. Cut 작업 중 패널의 도형·Corner Bevel·Chamfer·Width·Segments 조절 가능하고 Esc가 필요 없음.
6. Curve Lasso 점을 다시 클릭하면 둥글기 단계가 바뀌고 핸들이 보이며 드래그로 편집됨.
7. Mask에서 Brush Stroke로 여러 번 칠하고, Alt로 일부 지우며, 누적 마스크 유지.
8. Cut/Split에서 Enter, LMB 더블클릭, Undo/Redo가 정확히 작동하고 연속 편집 유지.
9. Mecha Lab Mode OFF → 일반 Blender Space/B/C 및 타 애드온 입력을 불필요하게 가로채지 않음.
10. UI 메뉴로 마우스를 이동해 눌러도 사용자 입력이 먹통이 되지 않음.

## 4. 구현할 때 주의할 점
- Blender `bpy` Headless에서 클래스 register가 성공하는 것과 Space 키 이벤트 / Modal PASS_THROUGH / 팝업 클릭 / PNG 썸네일 버튼이 GUI에서 실제 작동하는 것은 완전히 다름.
- 가능한 UI는 Blender 공인 API만 사용. 사용자 환경 Blender **5.0.2** 기준, 필요하면 Tool Bar fallback. 아이콘이 작은 text-only 메뉴로 대체되어선 안 됨.
- WIP 코드는 검증되지 않은 작업본이다. 기존 Cut/Boolean/Mirror/Array 기능 회귀 방지. 사용자가 기존 프리셋 데이터를 잃지 않도록 마이그레이션 정책을 지정.
