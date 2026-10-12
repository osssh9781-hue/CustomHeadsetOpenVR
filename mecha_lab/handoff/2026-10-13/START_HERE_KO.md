# Mecha Lab — Claude Code 다음 작업 인수인계 (2026-10-13)

**이 프로젝트의 원본 v0.7.0을 작성한 Claude Code에게 다시 전달하는 후속 개발 요청서입니다.**

### 순서
1. `source/MECHA_LAB_v0_7_2_CURRENT_BASE.zip` — 최신 실제 작업 베이스. **v0.7.0이 아닌 이 소스를 먼저 풀 것.**
2. `docs/01_NEW_USER_REQUESTS_KO.md` — 이번에 사용자에게 직접 확인한 변경/추가 요구. **기존 문서와 충돌 시 우선함.**
3. `docs/02_TESTS_AND_RISKS_KO.md` — 수용 테스트, 설계 제약, 구현 우선순위.
4. `docs/03_BASELINE_STATUS_KO.md` — 현재 구현과 미구현 기능의 구분.
5. `reference/` — 예전 요구/테스트/보고서를 참고용으로만 제공. v0.7.0 문서는 최신 소스 상태를 덮어쓸 수 없음.
6. `PROMPT_TO_CLAUDE_CODE_KO.md` — 사용자에게 바로 복사할 메시지.

**핵심:** 기존 독립 Curve Tool은 수정 요청 대상이 아님. 변경 대상은 *공통 Curve Lasso 브러시*임. 새로운 Base Mesh는 Mask Extract와 별개 도구임. 모든 구현 완료 주장은 실행 검증 근거가 필요. 타깃 환경은 Windows 11 + Blender 5.0.2.
