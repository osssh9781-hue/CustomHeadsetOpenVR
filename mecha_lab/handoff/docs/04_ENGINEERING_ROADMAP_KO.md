# 제안 구현 로드맵 — Claude Code에 기대하는 실제 작업

## Stage 0 — 기본 환경과 기준 검사
- Blender 5.0.2 실제 설치/GUI 사용 가능 여부 확인. 없으면 버전을 기록하고 GUI 테스트는 미실행으로 표시.
- v0.5.9 원본을 별도 디렉터리 복제, 버전 업 및 변경 로그. startup.blend와 사용자 기존 .blend를 건드리지 않는 임시 테스트 파일/격리 환경.
- manifest, addon register/unregister, modal and keymaps, current dependencies 구조 요약.

## Stage 1 — 첫 완성 목표: `MECHA LAB` Workspace MVP
- 상단 새 Workspace 탭 생성/전환/제거 경로를 만들고 기존 Layout/Sculpting 탭 유지. 도구 전환이 가능한 3D View left toolbar (이름+아이콘), view upper-left shared shape palette (6 shapes), context-only right options 패널을 구현.
- Cut/Split 분리, 동일 브러시 상태 공유. Space popup는 Workspace 내 보조 탐색, 팝업 동작에 실패해도 left toolbar로 모든 주요 기능을 사용 가능해야 함.
- 선택 Tool ID와 Shape ID 상태를 분리, 나중에 Mask, Curve 추가해도 동일 엔진 재사용 가능하도록 작업.
- Workspace를 현재 .blend에서 만들고 필요 시 opt-in Startup File 저장. 절대 무단 저장·교체하지 말 것.

## Stage 2 — 입력기 및 Undo 정비
- Cut/Split 핵심 UX: Enter / LMB double confirm, RMB single shape chooser, RMB double exit, Alt invert, Shift line snap, ESC current stroke only, menu events passthrough, Shape switch no ESC.
- 일련의 Cut을 각각 Undo 단위로 독립 처리. 재무장 timer modal 구조의 상태 경쟁이 있다면 네이티브 WorkspaceTool/Operator 구조 등 대안을 비교해 실제 수정.
- Cut/Boolean 대상 active object 공유 mesh data 해결, modifier apply fail 시 복구.

## Stage 3 — 기하 품질 및 프리셋
- PNG Vector Contour 데이터 모델/캡/홀/복수 섬, non-manifold 재현테스트 및 수정. 프리셋 썸네일과 사용자 import/save. 98개 참고 시트에서 개별 PNG가 있다고 가정하지 말 것.
- Bezier point/handle hit-test 및 점별 round 단계, curve resolution slider.
- Cut/Boolean의 **new cut edge only** Bevel/Chamfer. Per-shape contour corner rounding과 완전 분리.

## Stage 4 — 마스크/포즈/보조 툴
- Cut/Mask 동일 shared shape engine + brush stroke 누적 mask and alt erase, protect operation/solid split/extract+raise + weight paint/falloff.
- Smart Fuse geometry reliability or narrow supported constraints; Mirror/Array curves/local orientation regression; FBX / Asset Browser cutter support.
- Pose Rigid/Soft, Panel/Curve profiles, Surface, basic remesh all kept or explicitly staged. Need progress matrix, never claim complete by inclusion of button.

## 개발 품질 문턱
- 각 Stage 코드 변경, regression harness, geometric metrics, GUI manual checklist, limitations 기록. 먼저 작은 작동하는 패치를 만들고 큰 통합을 서두르지 말 것.
- 사용자 실제 작업파일을 테스트 입력으로 쓰지 말 것. 스크립트 생성 테스트 mesh 사용; 사용자 원본 데이터와 기존 preferences/Startup File은 보존.
- Stage 1 결과만 안정화됐으면 그 상태를 'MVP'로 릴리스하고 나머지는 backlog로 표시. 모든 요구 구현 완료라고 쓰지 말 것.
