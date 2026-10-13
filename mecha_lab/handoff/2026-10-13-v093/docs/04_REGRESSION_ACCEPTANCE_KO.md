# 필수 회귀·GUI 검증 기준

## A. 재현 테스트 (자동/헤드리스 가능한 영역)
1. Blender 5.0.x 환경에서 addon install→enable→disable→enable 3회; `MCH_PG_Brush` 중복 등록/키맵 누수/아이콘 오류 없음. 패널 draw도 실제 호출.
2. Cut/Split 1개 대상 vs 3개 독립 대상; Cap+Bevel+Gap 조합; 결과 manifold/volume 변화, 실패한 대상의 원본 보존, Ctrl+Z 원상 복구. Alt+D shared mesh 보존.
3. Boolean: 선택 A,B,C 중 C가 노란색 active면 **C가 단일 커터, A/B가 각각 타깃**. Difference에서 A−C, B−C 결과 확인, C 원본은 Keep일 때 보존; Union/Intersect와 Auto Apply, Undo, 실패 롤백도 검증.
4. Mirror: 월드·로컬·커서 X/Y/Z, 단일/다중, 생성→변경→적용→제거; Collection Mirror 포함.
5. Loft: 2개의 오픈 커브, 3개 단면, 폐곡선+Caps, Sweep, live curve point 변형, Apply, 모든 결과 유효.
6. Smart Fuse: 연속 10회 생성·취소/확정, 중복 컨트롤러·고아 node group 없음; 실패 시 원본 유지.
7. Cut/Curve Lasso: 처음 점에서 먼 곳의 더블클릭→닫기, 시작점 재클릭→닫기, Enter 확정, Esc 취소, 점 편집 더블클릭 Sharp/Smooth와 충돌 없음.
8. Split Gap: Enter, 시작점 클릭, 임의 위치 더블클릭 각각 단독 테스트; Width 0에 근접/넓은 폭, 양측 독립 Edge Finish 유효.
9. Base Mesh: Flat/Bevel/Chamfer/Dome × Top/Bottom/Both/None 중 유효 조합, 다른 폭·세그먼트; 캡슐 등 Primitive와 혼동 금지; Alt+드래그 불린; Tool 종료 Auto Apply는 생성 객체에만.
10. Curve/Panel: VECTOR 선으로 시작→점 클릭/더블클릭→Smooth 베지어 적용 시 실제 곡선 점이 증가하고 곡선 모양이 변함; 기존 `mch.draw_path` 기능 보존.
11. PNG preset Rotate R 키 가상 입력: 회전 미리보기와 커터 변환/Boolean 결과 일치.
12. Hide Mask: Tools/Space/V/Workspace에 Mask가 표시되지 않고 과거 .blend Mask 데이터는 유지.

## B. GUI 수동 확인 필수 — Windows Blender 5.0.2
- Workspace MECHA LAB 전용 탭 진입; 왼쪽 아이콘/공통 브러시/오른쪽 선택 도구 설정이 실제 표시됨.
- 모달 입력 중 사이드바 조작, Ctrl+Z, 마우스 wheel/MMB 뷰 회전, Space/V/Shift+A 메뉴 동작.
- Alt+**짧은** 좌클릭 선택모드 전환↔오브젝트 위 마지막 도구 복귀 / Alt+**드래그** 보조 동작. 이동 경계·키 업/다운 순서 검증.
- 더블클릭 종료와 시작점 클릭 종료; 메쉬가 의도치 않게 추가로 한 번 더 잘리지 않음.
- Cut, Split, Base Mesh, Boolean, Mirror, Loft, Smart Fuse를 새 .blend 파일에서 실제 손으로 사용. 특히 연속 Smart Fuse 3회.
- Bevel 확대 시 유효 폭과 메시지, Split Edge A/B 비대칭, Base Mesh Both Top/Bottom 시각적 확인.
- 같은 ZIP 단독 설치/활성화, 기존 버전 제거 후 재시작, 기존 프로젝트 호환성.

## C. 제출 조건
- 결과 ZIP(필수), 변경한 파일 목록, 최소 재현 .blend 또는 스크립트, 테스트 로그(Blender 버전/OS), GUI 검사표(통과/실패/미검증), Known Limitations, ChatGPT 핸드오프를 각각 제출.
- 패치한 기능마다 '코드에 존재', 'headless 통과', 'Windows GUI 검증'을 **서로 다른 열로 구분**.
- 사용자 보고 오류를 재현하지 못하면 추측으로 단정하지 말고 로그를 요청.

## D. Free Draw Stabilizer 신규 테스트
- `docs/06_FREE_DRAW_STABILIZER_KO.md`의 정적·실시간 입력 테스트 추가. 단순 후처리 스무딩만 해서는 미달.
- v0.9.3에서 기존 Cut/Split/Base Mesh/Curve Lasso/Bezier/Alt/R/RMB/Space/V 입력 회귀 없을 것.
