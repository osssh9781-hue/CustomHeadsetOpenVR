# Claude Code에게 보낼 메시지

이 프로젝트는 네가 만든 Mecha Lab v0.8.0 이후 ChatGPT가 추가한 v0.9.1 Deform, v0.9.2 Primitive, v0.9.3 Primitive Icons까지 이어진 Blender 확장입니다. 새로 전달한 압축 파일을 풀고 `START_HERE_KO.md`부터 읽으세요. 현재 실제 기준은 **v0.9.3** (`baseline/...zip`은 무수정 원본, `source/mecha_lab/`는 개발용 소스)입니다.

현재 사용자 Windows Blender 5.0.2 GUI에서 Mirror 전체 먹통, Loft 실패, Smart Fuse 첫 사용 후 재사용 실패, Lasso/Cut 더블클릭 닫기 실패, Curve/Panel 라인이 점으로 보이거나 곡선화되지 않음, Mask 미작동, Split Gap Enter로만 확정되는 문제를 보고했습니다. **새 기능보다 고장 난 기존 기능을 우선 복구**하십시오. v0.9.3 설치 시 `MCH_PG_Brush already registered` 오류도 발생했으니, 재시작/중복 버전/등록 예외 후 정리 로직을 확인하십시오.

새 UX 규칙은 `docs/02_INPUT_UX_SPEC_KO.md`에 있습니다. 최신 의사결정에 따라 *뷰포트 3회 클릭 토글은 폐기*하고 **Alt+짧은 좌클릭으로 선택 모드↔마지막 사용 도구 전환**합니다. Alt+드래그는 도구별 보조 기능이므로 둘이 충돌하면 안 됩니다. 사용자가 Alt+MMB 선택 기능은 명시적으로 취소했으니 **절대 추가하지 마십시오**. Lasso / Split Gap은 시작점을 찍거나 뷰포트 아무 곳에서 더블클릭해 닫고 적용하며 Enter도 유지하십시오. PNG 컷 프리셋은 드로잉 중 **R 회전**을 복구하십시오. **V**는 마우스 위치에 Cut / Boolean / Base Mesh / SubD Plane / Split / Radial Array 중심 빠른 메뉴, **Shift+A**는 Blender 기본 Add 메뉴의 `Mecha Lab` 하위 메뉴에서 Primitive(5종)·Base Mesh·SubD Plane 등을 생성하게 해주세요.

다중 선택에서는 **Cut/Split/Mirror는 선택된 모든 타깃**에 작동해야 합니다. **Boolean은 활성(노란색) 오브젝트가 커터이고, 나머지 선택 오브젝트가 모두 잘리는 대상**입니다. 다중 대상에 같은 단일 커터를 각각 적용합니다. 과거의 반대 선택 규칙은 잘못 정리된 것이니 적용하지 마십시오.

Base Mesh에서는 `Alt+드래그`로 생성한 형상을 Boolean Difference 커터로 사용하고, 단면의 베벨은 **Top Only / Bottom Only / Both Sides / None**을 선택 가능하게 해주세요. 예전에 사용자가 원한 **Alt로 베벨 위아래 반전**도 유지하십시오. Alt+드래그에서는 Boolean과 방향 반전을 함께 적용하며 Top↔Bottom, Both의 경우 서로 다른 상/하 폭을 교환하고 None은 변화 없음.  Both는 상하 별도 폭·세그먼트를 허용하십시오. 도구를 정상 종료할 때(Alt 짧은 클릭 포함) **현재 Base Mesh 도구가 만든 미확정 결과만 자동 Apply**하고, 작업 중인 다른 오브젝트의 모디파이어를 적용하면 안 됩니다. 자동 적용으로 원본 데이터가 손상되지 않도록 검증하고 Undo가 가능해야 합니다.

Cut 및 Split Edge Bevel은 현재보다 큰 폭을 지원하고 실제 겹침 제한 여부를 사용자에게 알려주세요. Split Side A/B 설정은 유지하면서 Cut에도 같은 종류의 Edge Finish를 제공해야 합니다. Split Gap은 더블클릭·시작점 클릭이 Enter처럼 완결되어야 합니다.

Mask는 기능이 고장 나므로 **UI와 전용 단축키에서 안전하게 숨기는 방향**으로 진행하십시오. 기존 저장 파일의 Mask 데이터, 메쉬, Vertex Group, 다른 기능까지 삭제하지 마십시오. 코드 완전 제거는 추가 승인 전 금지입니다.

**Free Draw Stroke Stabilizer 신규 요청 (2026-10-13 09:50):** 연속 Free Draw가 마우스보다 천천히 움직이며 부드럽게 추종하는 ZBrush Lazy Mouse 같은 보정을 추가해 주세요. Free Draw 공통 UI의 Stabilizer ON/OFF, Smoothing Strength(0–100%), Lazy Radius(픽셀), Stroke Spacing을 슬라이더로 조정하며 **드로잉 중에** 반영되도록 구현합니다. Mask는 숨기며 Cut/Split/Base Mesh Free Draw에 재사용. 기존 Lasso·Curve Lasso·독립 Curve Tool은 변경하지 않습니다. 정확한 조건은 `docs/06_FREE_DRAW_STABILIZER_KO.md`에 있습니다.

**필수:** `docs/01_PRIORITY_BUGS_KO.md`, `docs/02_INPUT_UX_SPEC_KO.md`, `docs/03_NEW_FEATURES_KO.md`, `docs/04_REGRESSION_ACCEPTANCE_KO.md`를 반영하고, 실제 소스를 수정한 설치 가능 ZIP과 테스트 로그, GUI 수동 검증표, 미해결 사항, 다음 ChatGPT에게 전달할 변경 보고서를 작성하십시오. 기존 Curve Tool(직선 VECTOR에서 컨트롤 포인트를 Smooth로 전환하는 기능), Curve Lasso, Deform, Loft, Primitive, ZBrush OBJ Bridge, Ortho Lock 및 Workspace를 조용히 제거하지 마십시오. GUI에서 실행하지 못한 동작은 '미검증'이라고 분명히 쓰십시오.
