# Mecha Lab — Claude Code 후속 개발 인수인계 (2026-10-13)

**기준 버전은 v0.9.3**이며 `baseline/mecha_lab-0.9.3_ORIGINAL_UNMODIFIED.zip`은 대화에서 마지막으로 배포된 설치 ZIP 그대로입니다. 원본을 수정하지 마십시오. 수정은 `source/mecha_lab/`를 복사해 별도 작업 디렉터리에서 수행하십시오. 이 패키지에는 **수정 요청서만 추가**되었습니다. 아래 기능을 이미 구현했다고 주장하지 마십시오.

**실사용 환경:** Windows 11 / Blender 5.0.2. 본 파일에서 사용자 제보는 Blender 5.0.2 GUI에서 발생한 것으로 간주하고, 코드에서 독립 재현했다고 단정하지 마십시오. Claude Code는 자신이 실제 실행한 테스트만 결과에 기록하십시오.

읽을 순서:
1. `PROMPT_TO_CLAUDE_CODE_KO.md` — 복사해 실행할 지시문
2. `docs/01_PRIORITY_BUGS_KO.md` — 고장 증상과 필수 복구
3. `docs/02_INPUT_UX_SPEC_KO.md` — 서로 충돌하는 입력 조작 통일
4. `docs/03_NEW_FEATURES_KO.md` — 기능 확장 및 마지막 Base Mesh 베벨 요청
5. `docs/06_FREE_DRAW_STABILIZER_KO.md` — 마지막 요청인 Free Draw 실시간 보정과 슬라이더
6. `docs/04_REGRESSION_ACCEPTANCE_KO.md` — 재현 및 합격 기준
7. `docs/05_PRODUCT_BOUNDARIES_KO.md` — 기존 워크플로·보존할 기능

**최상위 우선순위:** 새 기능을 늘리기 전에 Mirror, Loft, Smart Fuse, Split Gap, Cut/Curve 입력, 마스크가 고장 난 현재 버전부터 안정화하십시오. 수정을 여러 단계의 설치 ZIP으로 나눠도 됩니다. 실패한 기능과 사용자 확인이 필요한 GUI 항목은 숨기지 마십시오.
