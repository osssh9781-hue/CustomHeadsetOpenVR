# Mecha Lab — 새 Claude Code 세션용 시작 안내

## 이 패키지의 목적
**사용자 최종 결정: Blender 5.0.2 / Windows 11에서 사용할 전용 `MECHA LAB` Workspace + Cut 중심 모델링 애드온을 안정적으로 구축.** 기존 긴 N패널과 Space 키만 의존하던 UI를 재구성하는 작업이며, 전체 프로젝트의 기능 유지·안정화가 필요합니다.

### 먼저 읽을 파일 (이 순서)
1. `CLAUDE.md` — 개발 규칙, 우선순위 및 완료 조건
2. `docs/00_LATEST_USER_DECISIONS_KO.md` — *가장 최신 결정*; 이전 설계와 충돌 시 이 문서 우선
3. `docs/01_WORKSPACE_UIUX_KO.md` — Workspace 화면 구조, 도구/브러시/설정 구분
4. `docs/02_ALL_FEATURES_KO.md` — 모든 기능 요구사항 (완료 여부 주장 아님)
5. `docs/03_BUGS_AND_REALITY_KO.md` — 실제 스크린샷에 근거한 문제와 미구현 목록
6. `docs/04_ENGINEERING_ROADMAP_KO.md` — 구현 단계, 작업 순서, 위험 관리
7. `docs/05_TEST_ACCEPTANCE_KO.md` — Blender GUI / headless 수용 테스트
8. `docs/06_SOURCE_MAP_KO.md` — 기준 코드 및 WIP 구분

### 코드 디렉터리
- `source/RELEASE_v0_5_9/mecha_lab/` : 마지막으로 사용자에게 배포한 v0.5.9 원본 코드 **그대로**. 개발 기준점. `archives/ORIGINAL_v0_5_9.zip`도 보존.
- `source/WIP_v0_6_0_UNVERIFIED/mecha_lab/` : Undo / UI 패스스루 / 우클릭 팝업을 시도하던 초안. **미배포, GUI 미검증이며 릴리스로 간주하면 안 됨.** 참고용만.
- `evidence/` : 사용자가 제공한 오류·UI 스크린샷과 원본 알파 컨택트시트(개별 PNG 98장이 아님).
- `legacy/` : 이전 인계 문서. **충돌 시 새 `docs/00`과 `docs/01`이 우선.**

### Claude Code에 기대하는 동작
- 맨 먼저 전체 소스를 읽고 실제 구현/미구현/재현 문제를 분리하세요.
- Blender **5.0.2 GUI**가 없으면 입력/팝업/키맵은 미검증으로 명기; `bpy 5.2.2` 등록 성공만으로 작동 완료 선언 금지.
- 1차 목표는 Workspace + 공통 브러시 UI + 활성 도구 설정의 실행 가능한 최소 프로토타입과 입력 충돌 해결입니다.
- 실제 변경 코드를 별도 `output/` 또는 버전 폴더에 만들고 ZIP, 변경 기록, 테스트 로그, 잔여 버그를 제공하세요. 원본 변경 금지.

### 전달 텍스트
`PROMPT_TO_CLAUDE_CODE_KO.md` 내용을 Claude Code 대화에 붙여 넣으세요. 프로젝트 폴더를 Claude Code의 작업 디렉터리로 열면 `CLAUDE.md`도 읽을 수 있습니다.
