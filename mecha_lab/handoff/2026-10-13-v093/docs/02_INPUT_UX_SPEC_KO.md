# 입력·단축키 UX 최종 의사결정 (이 문서가 과거 지시보다 우선)

## 전역 원칙
- 모든 전용 조작은 MECHA LAB Workspace 및 해당 활성 도구에서만 작동해야 하며, 일반 Layout/Modeling의 Blender 기본 조작은 유지.
- UI 버튼·툴 목록·Properties 등은 언제든 클릭 가능; 도형 모달이 입력을 붙잡고 있어 Esc를 강제하지 않음.
- 완료한 각 Cut/Split/Base Mesh는 별도 Undo 기록, Blender Ctrl+Z/Redo와 충돌하지 않음.
- **기존 '뷰포트 3회 클릭→선택 모드'는 제거/비활성화.** Curve Lasso 점 클릭 및 더블클릭 확정과 충돌함.
- **Alt+MMB 오브젝트 선택은 사용자 취소; 구현 금지.** MMB 기본 뷰 회전 유지.

## 클릭 동작
| 입력 | 활성 드로잉 도구 | 선택 모드 |
|---|---|---|
| 좌클릭/드래그 | 도형 입력·작업 실행 | 일반 Blender 선택 |
| 좌클릭 더블클릭 | 시작점에서 멀어도 도형 자동 닫고 적용 (곡선·라쏘·Split Gap) | 기본 Blender 더블클릭 |
| 시작점 근처 좌클릭 | 닫힌 도형 자동 닫고 적용 (시작점 스냅 허용) | 기본 선택 |
| Enter | 현재 획 적용/확정 | 기본 Blender 동작 |
| Esc | 그리던 획 취소 후 선택 모드 | 기본 Blender 동작 |
| **Alt+짧은 좌클릭** | **현재 도구 → 일반 선택 모드**, 완료된 작업 유지 | **오브젝트 위에서 Alt+짧은 좌클릭 → 마지막 사용 도구 복귀** (오브젝트가 없으면 선택 유지) |
| **Alt+드래그** | 현재 도구의 보조 동작, 아래 참조 | 명시적 툴 액션 없으면 Blender 기본 동작 |
| RMB 1회 | Cut/Split: 공통 도형 프리셋 / Base Mesh: Flat·Bevel·Chamfer·Dome 프로필 / Primitive: 5종 팝업 | Blender 기본 컨텍스트 메뉴 |
| RMB 더블클릭 | 해당 도구 종료 (기존 요구 유지, 실제 GUI 타이밍 검증) | Blender 기본 동작 |
| V | 마우스 위치에 Tool Quick Menu | MECHA LAB 작업공간 내 빠른 도구 메뉴 |
| Shift+A | Blender Add 메뉴 + Mecha Lab 하위 메뉴 | 동일 |

### Alt 조작 충돌 방지
- Alt+클릭과 Alt+드래그는 **마우스 PRESS 시점이 아니라 RELEASE 시점에서 총 이동 픽셀/시간을 판정**. 클릭 경계 테스트가 필요하며 떨림 허용.
- Cut의 기존 Alt 보존/삭제 반전은 **Alt+드래그**에서 유지.
- Base Mesh의 **Alt+드래그**는 그려진 입체를 Boolean Difference 커터로 사용하면서, **그 커터의 베벨 위/아래 방향을 반전**(Top↔Bottom)한다. Both일 때 위/아래 설정값이 다르면 교환, None은 그대로. 이 두 동작은 사용자가 모두 요청한 사항이므로 둘 다 보존.
- Base Mesh에서 `Bevel Sides`는 평소 드로잉용으로 명시적으로 선택하며, Alt+드래그 시에는 그 설정을 반전한 커터를 사용. Alt+짧은 클릭은 모드 복귀만 하고 베벨이나 불린을 실행하지 않는다. 적용 여부가 혼란스러우면 UI에 현재 동작을 표시한다.
- Split이나 다른 도구의 Alt+드래그 기능이 이미 존재하면 보존하고 문서화. 무작정 통일하지 말 것.

### 빠른 메뉴
- **V**: Cut / Boolean / Base Mesh / SubD Plane / Split / Radial Array를 기본 6개 큰 아이콘+이름으로 마우스 위치에 표시, 입력 포커스와 Space 메뉴 충돌 방지.
- **Space**: 기존 전체 도구 메뉴 유지. Blender 기본 애니메이션 재생과 키맵 우선순위 충돌 검사.
- **Shift+A**: 기존 Blender Add 메뉴 안 `Mecha Lab` 서브메뉴. Box/Cylinder/Sphere/Cone/Capsule, SubD Plane, 가능한 신규 Base Mesh 생성 진입점. 기존 기본 항목 제거 금지.

## Free Draw 안정화 추가
- 연속 Free Draw에서 Stabilizer 보정은 드로잉 중 실제로 커서를 지연 추종해야 한다. 상세 요구사항 `docs/06_FREE_DRAW_STABILIZER_KO.md`.
- Alt+클릭 전환과 Alt+드래그 기능이 섞이지 않도록 필터가 PRESS/RELEASE 판단을 바꾸거나 입력을 먹지 않게 구현.
