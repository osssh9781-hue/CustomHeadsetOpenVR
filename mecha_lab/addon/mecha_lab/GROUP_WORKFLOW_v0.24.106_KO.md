# Mecha Lab v0.24.106 — Group Workflow / Mirror / Duplicate

기준: v0.24.105_RestrictData_Fix. 기존 Press Cut, Base Mesh, Draw Array 등 모듈 보존.

## 변경한 내용

1. **메쉬 클릭 그룹 선택:** Mecha Lab의 Select 상태에서 뷰포트 내 메쉬에 한 번 클릭하면 그 메쉬가 속한 최상위 그룹을 선택합니다. 빈 공간 클릭, Shift/Ctrl/Alt 조합 입력은 Blender의 기존 동작을 따릅니다. 그룹 Empty를 클릭할 필요가 없습니다. 마우스 아래 실제 메쉬를 Ray Cast로 판정하여 이전에 활성화된 다른 오브젝트를 잘못 선택하던 문제를 개선했습니다.
2. **더블클릭 그룹 진입:** 그룹 메쉬를 더블클릭하여 Scope 진입. 내부 직접 자식 메쉬는 일반 클릭으로 개별 선택, 하위 그룹은 클릭으로 그룹 선택/더블클릭으로 추가 진입. Scope의 Up/Exit로 한 단계 돌아갑니다.
3. **새 부품 자동 편입:** 기존의 Auto-add New Parts 기능 유지(기본 ON). Scope 내부에서 생성된 독립적인 새 Mesh/Curve 등을 그룹에 자동 배치(타이머 방식). 그룹에 추가된 부품의 월드 트랜스폼은 유지.
4. **Alt+X 그룹 전체 라이브 미러:** 그룹 전체 선택 후 Alt+X를 누르면 그룹의 GN Repetition으로 Mirror/Kaleido를 시작합니다. 마우스 제스처 또는 X/Y/Z로 축 지정, 클릭으로 라이브 미러 확정, Esc로 기존 반복 상태 복원. WORLD/LOCAL 좌표 선택은 Mirror 패널의 Space 옵션을 따릅니다. 기존 RADIAL 반복 중에는 KALEIDO 방식으로 결합. Grid 반복 중엔 명시적으로 경고 후 동작하지 않도록 보호합니다. *그룹 미러는 Mesh Mirror Modifier가 아니라 비파괴적인 Collection Repeat입니다. 따라서 Mirror Bisect는 지원하지 않습니다.*
5. **Shift+D 복제 시 미러 기준 유지:** 그룹 Collection에 들어있지 않은 외부 미러 Pivot까지 필요한 경우 복제합니다. 중첩 그룹 전체를 하나의 원본→사본 대응표로 관리하고, 모디파이어의 mirror_object/object/offset_object 참조를 복제본에 다시 연결해 원본과 사본의 미러 독립성을 강화했습니다. 개별 메쉬에 걸린 Mirror Modifier는 Apply되지 않습니다.
6. **그룹 패널:** 하위 그룹의 계층 인덴트, 펼침/접힘, 이름 변경(그룹/컬렉션 참조도 동기화)을 추가했습니다. Scope 외부 표시 모드 Normal / Ghost (Wire) / Hidden을 선택할 수 있습니다. Ghost는 반투명이 아닌 와이어 표시입니다.
7. **등록 시점 보호:** v0.24.105의 RestrictData 안전 초기화(등록 이후 타이머로 그룹 초기화/키맵 등록)를 유지합니다.

## 권장 검증 순서

1. 빈 Blender 파일에서 Cube 2~3개 생성 후 Mecha Group 만들기.
2. Mecha Lab Select 상태에서 그룹 메쉬 **한 번 클릭 → 전체 그룹**, **더블클릭 → 내부 Scope** 확인.
3. Scope 내부에서 별도 메쉬 생성 → 그룹 자동 편입 확인. 상위 Scope 복귀.
4. 그룹 전체 선택 → **Alt+X → 마우스 이동으로 축 지정 → 클릭 확정**, 그룹을 움직였을 때 라이브 미러 확인.
5. 그룹 내부 메쉬에 기존 Mirror Modifier/월드 Pivot 적용 → 그룹 **Shift+D** → 복사 그룹 이동·회전 후 미러가 유지되는지 확인. 원본 Pivot과 복사 Pivot이 다른지 Modifier의 Object 필드 확인.
6. 그룹 안에 그룹을 넣고 2~5단계 반복.
7. 그룹 패널의 트리 접기/펼치기 및 Outside Scope = Normal/Ghost(Wire)/Hidden 테스트.
8. 애드온 비활성화/재활성화, 파일 저장/재열기, Undo/Redo, 다른 드로잉 도구의 클릭 동작을 검사.

## 알려진 제한

- **Blender 5.3 Beta에서 실제 GUI 구동 테스트를 수행하지 못했습니다.** Python AST/compileall, ZIP CRC 검사 및 가짜 Blender 오브젝트 기반 중첩 그룹 미러 피벗 복제 테스트를 수행했습니다. 실제 모달 키맵 입력과 Geometry Nodes는 설치 후 Blender에서 확인해야 합니다.
- **Ghost 모드는 Blender 표준 와이어 표현**입니다. 반투명 셰이딩 오버레이는 구현하지 않았습니다.
- **중첩 그룹을 포함한 일반 Collection 내부 사용자 정의 비그룹 하위 컬렉션의 모든 경우**를 자동 복제하는 것은 테스트되지 않았습니다.
- Alt+X 그룹 미러는 그룹 반복 시스템의 한 모드이므로 Grid 반복과 동시 실행하지 않습니다. RADIAL은 KALEIDO로 전환됩니다.
- 실제 Mesh Mirror처럼 그룹 단위 Bisect(원본 일부 절단)는 지원하지 않습니다.

## 문제가 생겼을 때

현재 애드온을 비활성화한 뒤 Blender를 재시작하고 새 ZIP을 설치하세요. 이전 버전으로 되돌리기 위해 v0.24.105 ZIP은 별도로 보관하는 것을 권장합니다. 문제 발생 시 Blender System Console의 Traceback과 정확한 조작 순서를 공유해주세요.
