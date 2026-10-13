# P1/P2 — 최신 기능 변경 요청

## F01. 다중 오브젝트 선택/작업 (중요)
- **Cut:** 동시에 선택된 여러 오브젝트에 같은 도형/뷰 프로젝션으로 적용. 입력 한 번에 여러 대상 Cut; 각 대상 실패는 알리고 정상 대상 적용 여부를 명시, Undo 1회로 전체 복구. 공유 메쉬 안전 처리.
- **Split 및 Gap Split:** 선택된 모든 대상에 같은 절단선 적용. 대상별 분리 결과와 이름/컬렉션 정리. 원본 및 다른 타깃 손상 금지.
- **Mirror:** 선택된 모든 메쉬를 동일한 world/local/cursor 축 옵션에 따라 미러. pivot 선택을 명시하고, 다중 적용·제거/Apply 테스트. 여러 오브젝트가 하나의 Collection Mirror 컨트롤러를 공유할 수도 있도록 설계.
- **Boolean — 사용자의 최종 선택 규칙 (2026-10-13 09:10 이후 명확화):** Blender에서 마지막으로 선택된 **노란색 활성 오브젝트가 커터(cutter)**이고, **나머지 선택 오브젝트 전부가 잘리는 대상(target)**이다. B(Difference)는 `각 비활성 선택 대상 - 노란색 활성 커터`로 독립 실행한다. Union/Intersect도 여러 대상에 같은 활성 커터를 각각 적용한다. 노란색 커터는 원본 유지/삭제 옵션에 따르며 결과 대상으로 취급하면 안 된다. UI에서 `CUTTER: active yellow` / `TARGETS: N other selected`를 표시해 오적용 방지. 이전 문서의 반대 규칙은 폐기.
- 활성 커터 하나로 비활성 선택 타깃 모두에 연산하는 것이 **기본 동작**이다. 잘못 선택하면 사전 경고/취소하고, 성공·실패한 타깃을 구분해 표시하며 원자적 롤백 또는 타깃별 실패 보존 정책을 명시. 커터 원본은 의도된 설정 없이 파괴하지 말 것.

## F02. Base Mesh — 새 베벨 방향 옵션 (2026-10-13 09:10 최종)
**Bevel Sides / Edge Profile Placement** 선택지를 오른쪽 Base Mesh 패널과 우클릭 프로필/설정에 추가.
1. `TOP_ONLY` — 윗면에만 Bevel/Chamfer, 아래쪽 평평하고 날카로움 (기존 기본 동작과 비슷)
2. `BOTTOM_ONLY` — 아랫면에만 Bevel/Chamfer, 윗면 평평하고 날카로움
3. `BOTH` — **윗면과 아랫면 모두** Bevel/Chamfer; 상·하단 Width/Segments 별도 조절 허용 (공통 연결 옵션 가능)
4. `NONE` — Flat/Sharp, 추가 베벨 없음

- 프로필(Flat / Bevel / Chamfer / Rounded/Dome)과 베벨 방향은 다른 축의 설정. `DOME`의 top/bottom/both 의미가 불분명하면 모델링 수학과 예외를 명시하고 UI에서 비활성화 또는 별도 Dome Side 옵션으로 제안. 지원하지 않는 조합을 조용히 무시하지 말 것.
- Bevel Width는 길이 기반 실제 단위, 유효 범위 clamp & 자가 교차 방지, 실시간 변경 후 재생성/바로보기, 마니폴드·노말 검사.
- 기존 `Bevel Bottom Too` 옵션이 있다면 이번 새 토글로 기능을 이전·통합하되 **기존 .blend 값 마이그레이션**. 옵션 이름/프로퍼티 폐기 시 데이터 손실 주의.
- `Alt+드래그`: 현재 그리는 Base Mesh 형상을 Boolean Difference 커터로 사용하고 **기존 요청대로 베벨 방향도 반전**. Top Only→Bottom Only, Bottom Only→Top Only, Both Sides일 때는 위/아래 별도 폭·Segments를 서로 교환, None은 그대로. 일반 드로잉에서는 UI 설정 그대로 적용. Alt+짧은 클릭은 도구 전환이며 커터를 생성하지 않도록 구분.
- Base Mesh 도구에서 **Alt+짧은 클릭으로 빠져나갈 때** 도구가 생성한 미확정 Base Mesh만 Auto Apply. Tool 전환/정상 종료에도 같은 정책. 단, Alt+드래그 중에는 확정까지 종료 금지. 기생성된 다른 오브젝트·사용자가 따로 편집하던 모디파이어 Apply 금지. Undo와 데이터 보존 검증.

## F03. Cut / Split 큰 베벨
- Cut, Split 모두 None/Chamfer/Bevel Edge Finish. 기존의 Split Side A / Side B 독립 옵션 보존.
- **Bevel Width 범위 확대** + 수동 숫자 입력(기본 모델 단위). 작은 Edge나 겹침으로 Blender가 clamp할 경우 사용자에게 유효 적용 폭/경고 출력. 필요시 clamp 옵션과 별도 설정. 기하 안전성 우선.
- Cut에서는 새로 생성된 경계만 bevel(기존 외곽 sharp). Split은 Side A/B의 Width·Segments 독립 제어 및 Swap Sides 유지. Normal/Gap 모두.
- 2D 도형 Corner Round/Chamfer와 3D Edge Bevel을 혼동하지 말 것.

## F04. Split Gap 확정 + 단면
- Enter 외에 시작점 재클릭·아무 지점 더블클릭으로 확정; Gap Width 모델 단위, 양쪽 Cap, Bevel 조합 모두 검증.
- 더블클릭 시 마지막 점 2회 삽입·0 길이 변·면 반전 금지.

## F05. Primitive / 메뉴
- 기존 Geometry Nodes Primitive 5종 및 썸네일 유지. 우클릭 Shape Picker, Shift+A 하위 메뉴, V 빠른 선택 메뉴가 함께 작동하도록 통일.
- Shape Preset 및 PNG vector Cut은 삭제하지 않음. PNG 스탬프 그리기 중 R 회전 복구.

## F06. Smart Fuse 재사용 안정성
- Smart Fuse 생성→확정/취소→다른 메쉬 선택→재생성·확정의 반복 경로, 임시 node group cleanup, depsgraph refresh, active object/selection 유실 재현.

## F07. Mask 단계적 비노출
- 사용자가 Mask는 작동하지 않으므로 없애는 게 낫겠다고 요청. **Mecha Lab UI/Toolbar/Space/V/단축키에서 비노출**, 예전 Mask 관련 오브젝트/Vertex Group/저장 파일/커스텀 속성은 보존. 기존 다른 모듈 import 및 unregister/legacy 파일 역호환 위해 코드 일단 유지. 후속 영구 삭제는 사용자 승인 필요.

## F08. Free Draw 안정화
- 상세 입력·알고리즘·테스트 요구사항: `docs/06_FREE_DRAW_STABILIZER_KO.md`.
- 실시간 Lazy Mouse/Stabilizer, Strength·Lazy Radius·Spacing 슬라이더; 기본 OFF; Cut/Split/Base Mesh 공통 Free Draw 전용.
- Mask는 비노출 상태로 유지; Curve Lasso·기존 Curve Tool은 수정하지 말 것.
