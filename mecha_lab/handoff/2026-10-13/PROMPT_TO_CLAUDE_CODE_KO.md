Claude Code, 이전에 네가 개발했던 Mecha Lab v0.7.0에 추가 수정 요청이 있습니다. 이번에는 ChatGPT가 v0.7.1과 v0.7.2까지 수정했으므로, 첨부 ZIP을 풀고 `START_HERE_KO.md`, `CLAUDE.md`, `docs/01_NEW_USER_REQUESTS_KO.md`, `docs/02_TESTS_AND_RISKS_KO.md`를 먼저 읽어 주세요. **기준 소스는 `source/MECHA_LAB_v0_7_2_CURRENT_BASE.zip`입니다.** 기존 v0.7.0으로 되돌리면 안 됩니다.

중요한 사용자 요청은 ① Esc 선택 도구 복귀, ② 시작점에서 멀어도 더블클릭하면 Lasso/Curve Lasso 자동 닫힘, ③ 기존 3회 클릭 선택 복귀 유지 및 충돌 해결, ④ 공통 Curve Lasso는 처음부터 부드러운 곡선, Free Drawing은 클릭 방식이 아닌 실제 마우스 드래그, ⑤ 라쏘로 직접 새로운 독립 입체를 만드는 Base Mesh 도구(우클릭 Flat·Chamfer·Bevel·Rounded/Dome 단면 선택), ⑥ 선택 오브젝트의 ZBrush 왕복 브리지(자동 합치기·자동 DynaMesh 금지), ⑦ 여러 커브를 NURBS처럼 연결하는 Loft / Surface 및 가능하면 Sweep/Rail 기능입니다.

**기존 독립 Curve Tool은 수정하지 말아 주세요.** 곡선 라쏘와 혼동하면 안 됩니다. 기존 Workspace의 왼쪽 도구 메뉴/좌상단 공통 Shape/오른쪽 설정, Cut/PNG/Boolean/Mask 개선, Ortho Lock 등도 보존해 주세요.

P0 입력/라쏘/프리핸드부터 실제 코드로 수정·검증하고, 그다음 Base Mesh, 이후 ZBrush Bridge와 Loft/Surface 순서로 진행해도 됩니다. 설치 가능한 ZIP과 변경 로그, Blender 5.0.2 GUI 체크리스트, 테스트 로그를 주세요. 무조건 다 했다고 주장하지 말고 실제 완성·부분구현·미구현을 구분해 주세요. 사용 환경은 Windows 11, Blender 5.0.2입니다.
