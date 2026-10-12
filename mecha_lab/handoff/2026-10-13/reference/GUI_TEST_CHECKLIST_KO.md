# GUI 수용 테스트 체크리스트 — Windows 11 / Blender 5.0.2

**새 파일**(File > New > General)에서 진행하세요. 실제 작업 파일로 테스트하지 마세요.
Window > Toggle System Console을 켜 두고, 오류가 나오면 **콘솔 전체 텍스트**를 복사해 전달해 주세요.
각 항목에 ✅ / ❌ / 메모를 적어 주시면 다음 수정에 그대로 사용합니다.

## 0. 설치
- [ ] 0.5.x 제거 후 `mecha_lab-0.7.0.zip` Install from Disk → 오류 없이 활성화
- [ ] 설치 직후 상단 탭 목록이 변하지 않음 (MECHA LAB 탭이 자동으로 생기지 않음)

## 1. Workspace
- [ ] N > Mecha Lab > `Open MECHA LAB Workspace` → `MECHA LAB` 탭 생성·이동
- [ ] Layout / Modeling / Sculpting 탭 내용이 그대로
- [ ] 새 탭: 왼쪽 좁은 영역에 큰 아이콘+이름 도구 목록이 보임 (안 보이면 그 영역에 무엇이 보이는지 스크린샷)
- [ ] 뷰포트 왼쪽 위 Tool Header에 Lasso … Brush Stroke + PNG 썸네일 버튼
- [ ] 오른쪽 Sidebar가 Mecha Lab 탭이고 현재 도구 설정만 보임
- [ ] T 툴바에 Mecha Cut / Split / Mask 아이콘, 기본 활성 도구가 Mecha Cut
- [ ] 버튼을 다시 눌러도 탭이 중복 생성되지 않음
- [ ] `Repair MECHA LAB Layout`: 왼쪽 영역을 닫은 뒤 실행하면 복구

## 2. 도구 전환
- [ ] 왼쪽 목록에서 Cut / Split / Boolean / Smart Fuse / Mirror 클릭 → 오른쪽 설정이 즉시 바뀜, Esc 불필요
- [ ] Space → 큰 아이콘 도구 팝업, 클릭으로 전환
- [ ] Layout 탭으로 이동 후 Space = Blender 기본 동작(재생 또는 사용자 설정), B = 박스 선택, C = 원 선택
- [ ] MECHA LAB 탭에서 B = Boolean Difference(2개 선택 시), C = Cut 도구

## 3. Cut (큐브 하나)
- [ ] Rectangle 선택 → 큐브 위 드래그 → 놓자마자 구멍. 도구 유지
- [ ] 연속 3번 컷 → `Ctrl+Z` 3번이 컷을 하나씩 되돌림, `Ctrl+Shift+Z`로 다시
- [ ] Lasso: 점 4개 클릭 → 더블클릭 → 적용. 마지막 점이 두 번 찍히지 않음
- [ ] Lasso 그리는 중 `Ctrl+Z` / `Backspace` = 마지막 점만 삭제
- [ ] Lasso 그리는 중 `Esc` = 획만 취소, 도구 유지
- [ ] Lasso 그리는 중 오른쪽 Sidebar 값 변경 / 팔레트에서 다른 Shape 클릭 → Esc 없이 동작(그리던 획은 버려짐)
- [ ] Lasso 그리는 중 다른 에디터(Outliner 등) 클릭 → 정상 동작
- [ ] Alt 누르고 그리기 → 안쪽만 남음
- [ ] Lasso 2점 + Enter → 반쪽 하이라이트 → 클릭한 쪽 삭제
- [ ] Circle / Ellipse / Brush Stroke / Curve Lasso(점 재클릭 라운드) 각각 1회
- [ ] RMB 한 번 → 잠시 후 Shape 팝업. RMB 더블클릭 → 도구 종료(Select Box). 더블클릭이 팝업 때문에 막히지 않음
- [ ] (그리는 중에도) RMB 한 번 = 팝업, 더블 = 종료
- [ ] Edge Finish = Bevel, Width 0.05 → 새 구멍 테두리만 둥글고 큐브 모서리는 그대로
- [ ] Depth = From Surface, 0.3 → 관통하지 않는 홈
- [ ] 원근 뷰(Numpad 5로 전환)에서 원형 컷이 화면에 그린 원과 일치

## 4. Split / 공유 메쉬
- [ ] Split 도구 Rectangle → `<이름>_Split` 오브젝트 생성, 두 조각 모두 닫힘 (Cap ON)
- [ ] Alt+D 복제본이 있는 큐브를 Cut → 기본 설정에서 복제본은 그대로, 오류 없음
- [ ] Shared Mesh = All Linked Copies → 두 복제본 모두 잘림
- [ ] Boolean 도구로 Alt+D 메쉬에 Difference → "multi-user" 오류 없이 적용

## 5. PNG
- [ ] Import PNG(흰 문양/검정 배경, 구멍·여러 섬 있는 것) → 썸네일 표시
- [ ] Custom 선택 → 클릭 스탬프 / 드래그 크기 → 비매니폴드 오류 없이 적용
- [ ] Select > Select All by Trait > Non Manifold (Edit Mode)로 결과 확인: 선택되는 엣지 없음
- [ ] 기존 v0.5.9 프리셋도 목록에 보이고 동작

## 6. Smart Fuse
- [ ] 겹친 두 메쉬 → Create Live Smart Fuse → 패널이 오류 없이 그려짐 → Confirm
- [ ] 떨어진 두 메쉬 → 설명 메시지 후 원래 상태 유지(소스가 숨겨지지 않음)

## 7. 저장 / 재시작 / 비활성화
- [ ] 파일 저장 → Blender 재시작 → 파일 열기 → MECHA LAB 탭과 도구 동작
- [ ] 애드온 비활성화 → Space/B/C가 Blender 기본으로, 오류 없음 → 재활성화
- [ ] MECHA LAB 탭 삭제 후에도 Sidebar/Space 오류 없음

## 8. 성능 (선택)
- [ ] 10만 면 메쉬에서 원형 컷 1회 체감 시간: ____ 초 / 그리는 동안 끊김 여부: ____
