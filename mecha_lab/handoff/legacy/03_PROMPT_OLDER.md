> **[2026-10-13 최종 사용자 UI/UX 수정]** 이 문서의 UI 구성·Cut/Split/Polygon 구분보다 `00_FINAL_UIUX_SPEC_KO.md`가 우선합니다. 특히 **왼쪽 위 공통 브러시 6종, Space 글로벌 도구 팔레트, 오른쪽 활성 도구 설정**으로 구분; Cut과 Split 별개 도구, 별도 Random Polygon 제거.

# Claude에게 보낼 요청문 — Mecha Lab 긴급 교차검토 / 공동개발

당신은 Blender Python API / BMesh / Geometry Nodes / GPU overlay / modal operator, 실제 Blender GUI UX 및 3D geometry에 전문성을 갖춘 엔지니어입니다.

첨부한 **Mecha Lab handoff ZIP**을 **먼저 전부 풀고** 다음을 읽어주세요.
- `01_REQUIREMENTS_KO.md`: 지금까지 사용자 요구사항 전체(최신 사양)
- `02_STATUS_BUGS_RISKS_KO.md`: v0.5.9 현행 상태, 오류 증거, 구현 난관, QA
- `CURRENT_RELEASE_v0_5_9.zip`: 최신 *실제 사용자에게 배포된* 버전
- `WIP_v060_UNRELEASED/`: 이전 ChatGPT가 작업 중이던 **미검증 초안** (배포하면 안 됨)
- `SCREENSHOTS/`: 사용자의 실제 Blender 화면과 오류 캡처

**사용자 환경은 Blender 5.0.2 Windows**입니다. 과거에 사용된 `bpy 5.2.2 Linux`와 다르므로, headless 테스트만 통과했다고 GUI 이벤트 처리가 성공했다고 단언하지 마세요.

## 최우선 문제 6개
1. Cut 상태에서 `Ctrl+Z`가 안 먹고, 연속 컷이 독립적인 Undo/Redo가 안 됨.
2. Space 툴 팔레트가 실제 사용자 Blender에서 안 뜨거나 Cut 모달과 충돌. 메뉴 클릭/도형 설정 변경 때 Esc를 요구함.
3. Cut 우클릭 1회는 이미지 Cut Shape 프리셋 팝업, 우클릭 더블클릭은 종료라는 요구가 **배포본에 반영되지 않음**. 싱글/더블 판정 경쟁 문제까지 해결해야 함.
4. PNG→Vector Cut 결과가 비매니폴드 오류(`Boolean result is non-manifold`)와 지저분한 면/선 형태를 보임. 십자·환기구·격자 등 오목/다중구멍/다중섬 마스크의 watertight 커터를 고쳐야 함.
5. Cut/Boolean 모디파이어 적용이 `Modifiers cannot be applied to multi-user data`로 실패한 사례. 공유 mesh data 안전 분리 / rollback 필요.
6. Smart Fuse는 사용자 환경에서 오류 발생. 폭·곡률과 대상 seam만의 필렛·챔퍼 구현이 실제로 안정적인지 검증 필요.

## 요청사항
1. 기존 소스의 모달 구조 및 Keymap을 독립적으로 감사하고, **장기 단일 Modal Operator / timer re-arm / WorkspaceTool** 접근의 장단점을 비교해 안정적인 아키텍처를 추천해주세요.
2. UI는 3DCoat처럼 `Space = 큰 아이콘+이름 도구 메뉴`, Cut→Boolean→Smart Fuse→Mirror 우선, 활성 도구 세부 설정만 N패널. Mecha Lab 모드 ON 동안만 사용자 키 지정이 유효하고 OFF면 기본 Blender 단축키 보존.
3. Cut은 도형을 그리면 바로 적용, Enter/좌더블 확정, Alt=보존 쪽 반전, Split Both, 지속 모드. 패널을 클릭하거나 Rectangle/Circle/Polygon 모드를 변경할 때 Cut 종료/ESC 요구 금지. Ctrl+Z/redo도 작동해야 함.
4. Custom Cut Shape는 **PNG를 벡터 폐곡선으로 변환**, 저장하고 썸네일 갤러리에서 선택해 Cut 프리셋으로 씀. 이전 3DCoat Sketch Box/복셀 Alpha Boolean은 되살리지 마세요. Cut edge only bevel/chamfer adjustable width/segments.
5. Mask는 Cut과 동일한 드로잉 도형, Alt로 일부 차감, 누적+유지. 마스크 영역을 Boolean/Cut에서 실제로 보호, Split/Cut/Extract & Raise/Weight Falloff/Pose에 활용. **현재 v0.5.9의 FACE 마스크는 실제 보호 기능이 아니라는 사실**을 기준으로 설계해주세요.
6. 상대적으로 어렵지 않은 기존 기능 Mirror/Array/Asset Library는 유지하되 Radial Array 복제물 로컬축 회전, FBX asset cutter 가져오기, 포즈 툴 Rigid/Soft도 단계적으로 지원해 주세요.
7. 복잡한 Smart Fuse가 근본적으로 불가능한 교차 조건에서는 완전 구현됐다고 주장하지 말고 범위/대체 알고리즘을 제시해주세요.
8. 사용자가 원하는 **하드서피스/메카용 빠른 조작감**이 우선입니다. 렌더/뷰포트 FPS와 UI 이벤트를 함께 검사하고, 마우스 무브마다 Boolean 전체를 계산하지 마세요.

## 작업 산출물 요청
- (A) `확인된 버그`와 `추정 문제`를 명확히 나눠서, 파일/함수/근거/재현 단계/심각도 P0~P3를 작성.
- (B) 특히 위 6개 항목 각각 **현실적인 구현 가능성, 알고리즘, 위험, 성능 비용**을 정리.
- (C) 가장 시급한 P0부터 **실제 코드 수정**, 반드시 별도 버전/ZIP으로. 원본 v0.5.9 변경 금지.
- (D) Blender 5.0.2 GUI 테스트가 없으면 미검증이라고 명시. 다른 bpy가 있으면 해당 버전 정보와 테스트 로그 제공.
- (E) 모든 새 기능은 대상 객체/원본/모디파이어/Undo 손실이 없는지 regression 수행.
- (F) ChatGPT에게 다시 전달할 **짧은 기술 핸드오프(어떤 파일을 어떻게 수정했고, 어떤 테스트가 남았는지)**와 새 ZIP 제공.

목표는 코드를 억지로 많이 추가하는 게 아니라 **실제 사용자 손에서 제대로 작동하는 Cut 중심 작업 도구**입니다. 완벽히 구현되지 않은 기능을 완료 처리하지 마세요.
