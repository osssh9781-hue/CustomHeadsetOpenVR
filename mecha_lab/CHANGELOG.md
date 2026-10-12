# CHANGELOG

## 0.9.0 — Mesh Curve 수정, SubD Plane, Radial 회전, Gap Split, 양쪽 독립 베벨 (2026-10-13)

기준: 0.8.0. 기존 기능은 제거·대체 없이 확장. 검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 Mesh Curve (Panel / Curve 도구 → 이름 "Mesh Curve", Curve Lasso와 무관)
- **직선처럼만 생기던 원인 3가지 수정**: (1) 모든 점이 VECTOR 핸들로 생성(Free Draw 포함), (2) Edit Mode 점 더블클릭 →
  Smooth 키맵이 v0.5.9부터 `active = False`로 등록돼 한 번도 동작하지 않음, (3) Straight/Smooth 버튼이 Edit Mode 전용이라
  Object Mode에서 비활성.
- 직선(VECTOR) 그리기는 기본값 그대로. 그리는 중 기존 점 클릭/더블클릭 = Straight ↔ Smooth, `S` = 새 점 종류, Backspace가
  점 종류를 보존. Free Draw 점은 AUTO(부드러움). Edit Mode 더블클릭 키맵 활성화(Mecha 경로가 아니면 통과).
- 새 Live 설정(Object.mch_live): Curve Resolution(경로 resolution_u), Profile Segments(원형 단면), Rotation X/Y/Z(스윕: 단면 회전,
  Curve Array: 복제본 회전), Twist(시작→끝 누적 비틀림, Set Curve Tilt). `All Smooth / All Straight`(Object Mode).
- 0.9 이전에 만든 Live 오브젝트는 처음 값을 바꿀 때 노드 그룹을 한 번 재생성.

### P0 SubD Plane (새 도구)
- `Create SubD Plane`: 3D 커서에 Plane + `Simple SubD → Catmull-Clark SubD → Solidify`. 두 SubD를 **동시에** 쓰고 레벨 슬라이더
  각각(0~5). Thickness / Offset / Even Thickness / Use Creases, Edit Mode 선택 엣지 Crease, `Apply All`(스택 순서대로 데이터 적용),
  `Add SubD Stack to Selected`. 모든 모디파이어 Edit Mode 표시.

### P1 Radial Array
- Ring Rotation X/Y/Z(배열 전체 회전), Copy Rotation X/Y/Z(복제본 로컬 회전), Start Angle(이름 정리), Rotate Each Copy **기본 OFF**
  (씬 기본값과 오브젝트 모두). 원본 방향은 메쉬에 그대로, 배열 회전은 별도 노드. 이전 배열은 처음 수정 시 노드 그룹 재생성.
- 기울어짐 점검: 복제본 회전은 Rotate Each Copy가 켜져 있을 때만 Z축으로 일어나며, 기본값이 ON이던 것이 "원하지 않는 회전"의
  주원인이었음. OFF에서는 모든 복제본이 원본 축을 유지함을 테스트로 확인.

### P1 Gap Split
- Split Mode: Normal(기존) / Gap. Gap Width(모델 단위)만큼 띠를 제거: 닫힌 도형은 윤곽을 ±Gap/2 오프셋한 두 커터로
  (안쪽 = 조각, 바깥쪽 = 남는 원본), 2점 직선은 ±Gap/2 두 평면, 폴리라인/곡선도 지원. 중심선 유지, Cap 옵션, 각각 별도 오브젝트.
  Gap이 도형에 비해 너무 크면 메시지와 함께 거부, Auto Apply OFF에서는 안내 후 거부.

### P2 Split 양쪽 독립 마감
- Side A(남는 원본) / Side B(`_Split`) 각각 None/Chamfer/Bevel, Width, Segments, `Swap Sides`. Normal/Gap/직선 모두,
  새 절단 경계만 처리(원래 모서리 불변 테스트). Split은 이제 이 설정을 쓰고, Cut의 Edge Finish는 Cut 전용.

### P2 2D Corner 점검
- 0.8.0의 Sharp/Chamfer/Round, Corner Width(px, 이름 정리), Corner Segments, Lasso 그리는 중·Rectangle 드래그 중 미리보기가
  실제 상태기계에서 동작함을 테스트로 확인. 새 기능 추가 없음.

## 0.8.0 — 입력 P0 수정, Base Mesh, Loft/Surface, ZBrush Bridge (2026-10-13)

기준: ChatGPT **v0.7.2** (`reference/CHATGPT_v0_7_2/`). v0.7.1(트리플 클릭, Ortho Lock)과 v0.7.2(마스크 레이캐스트,
열린 Mask Brush Stroke, Edge Finish 엣지 수 진단)는 유지. 독립 Curve Tool(Panel/Curve, `mch.draw_path`)은 수정하지 않음.
검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 입력 / UI
- **Esc → 선택 도구 복귀**: 획 중이든 대기 중이든 Esc는 미완성 획만 버리고 `builtin.select_box`로 전환. 적용된 컷 유지.
  (대기 중 Esc는 도구 키맵의 `mch.exit_tool`, 팝업 대기 중 Esc도 동일.)
- **더블클릭 자동 폐합**: Lasso/Curve Lasso는 시작점 근처가 아니어도 더블클릭 위치에서 마지막 점→시작점으로 닫고 적용.
  DOUBLE_CLICK은 점을 추가하지 않고, 같은 마우스다운에 PRESS+DOUBLE_CLICK이 함께 와도 4px 이내 중복 점은 버림,
  시작점 위의 마지막 점도 제거 → 길이 0 엣지 없음.
- **트리플 클릭 상태기계 정리**: v0.7.1 카운터 유지, 단 Curve Lasso 점 토글/드래그·핸들 클릭(편집 클릭)은 세지 않음.
  v0.7.2에서 같은 점을 세 번 누르면 도구가 꺼지던 충돌을 테스트로 재현 → 수정.
- **Curve Lasso 재설계**: 처음부터 부드러운 닫힌 스플라인(Catmull-Rom 탄젠트 → 3차 Bezier 구간). 점 클릭 = 각/부드러움 토글,
  점·Bezier 핸들 드래그(정렬된 대칭 핸들), `Curve Samples`, `Curve Smoothness`. 이전의 "각진 라쏘 + 꼭짓점 라운드 단계" 제거.
- **Free Draw**: Shape 이름을 Brush Stroke → Free Draw로. PRESS→MOUSEMOVE 연속 샘플→RELEASE, 간격/스무딩/단순화.
  Cut/Split/Base Mesh는 닫힌 외곽선, Mask는 열린 브러시(v0.7.2). Lasso에서도 LMB를 누른 채 끌면 연속으로 그려짐.
- **Outline Corners**: Lasso/Rectangle의 2D 모서리 Round/Chamfer(px) — 3D Edge Finish와 분리된 설정.
- 우클릭: Cut/Split/Mask = Shape/PNG 팝업, **Base Mesh = 단면 프로필 팝업**, 더블 = 종료.

### P1 Base Mesh from Shape (새 도구 `mecha.base_mesh`)
- 공통 Shape(Lasso/Curve Lasso/Rect/Circle/Ellipse/Free Draw/PNG)로 그린 윤곽을 뷰 평면에 투영해 **새 닫힌 솔리드** 생성.
  표면 위(윤곽 아래 메쉬가 있으면) 또는 3D 커서 평면. 원본 메쉬 무변경.
- 프로필: Flat, Chamfer(윗면 경계 1세그먼트), Bevel(윗면 경계 N세그먼트), **Rounded/Dome**(경계까지 거리 기반 높이장,
  densified 경계 + 내부 격자의 Constrained Delaunay → 오목 윤곽에서도 면 뒤집힘 없음). Roundness/Height/Edge Height/
  Resolution/Border Width/Segments/Offset/Bevel Bottom.
- 구멍(PNG 링)·여러 섬 지원. 자기교차·너무 작은 윤곽은 메시지와 함께 거부(오브젝트 생성 안 함).
- **Live**: 윤곽과 설정이 오브젝트에 저장되어 값 변경 시 재생성, RMB 프로필 선택도 선택된 Live 오브젝트에 반영. Freeze.
- 경사 뷰에서 거의 일직선인 경계 점 사이 sliver 삼각형이 잘못 분류되던 문제를 테스트로 찾아 **교차 parity 분류**로 해결.

### P2 Loft / Surface (부분)
- Loft: 2+ 커브, 호 길이 재샘플, 방향/시작점 자동 정렬, Catmull-Rom 단면 보간(Smoothness), Cap Ends, Thickness(Solidify),
  Flip, Twist, Close Loft, 섹션 순서 이동/개별 Reverse. Sweep: 단면+경로(평행 이동 프레임, 스케일, 비틀림).
- 커브 수정 시 depsgraph 핸들러로 **Live 갱신**, Apply로 확정. CAD NURBS 패치가 아닌 보간 폴리곤 표면.

### P2 ZBrush Bridge (부분)
- OBJ 파일 기반 Send / Import Back. 오브젝트마다 개별 파일(자동 Join 없음), ID(`mch_zb_id`)와 매니페스트(파일, 시각,
  내보낼 때의 world matrix), 바뀐 파일만 다시 가져와 원래 오브젝트 로컬 좌표로 변환해 메쉬 교체, 이전 메쉬 백업,
  이름 변경/삭제/파일 누락/공유 메쉬 처리, 축·스케일 설정, ZBrush 실행 파일 선택 실행. **GoZ 프로토콜은 구현하지 않음**
  (설치 경로가 있으면 정보로만 표시).

### 기타
- Ortho Lock(v0.7.1): 잠금 상태로 저장한 파일을 다시 열면 타이머가 자동 재시작(v0.7.2는 버튼을 다시 눌러야 했음).
- 새 아이콘 7개(Base Mesh, Loft, ZBrush, 프로필 4종). 매니페스트 0.8.0.

## 0.7.2 / 0.7.1 (ChatGPT)
`addon/mecha_lab/CHANGELOG_v0_7_1_KO.md`, `CHANGELOG_v0_7_2_KO.md` 참고.

## 0.7.0 — MECHA LAB Workspace MVP (2026-10-12)

기준: 배포본 v0.5.9 (`reference/RELEASE_v0_5_9`, 원본 그대로 보존). 미검증 초안 v0.6.0은 참고만 했고 코드를 가져오지
않았습니다(타이머로 Cut 모달을 재시작하는 방식은 경쟁 상태 위험 때문에 채택하지 않음). 검증 수준은 `test_report.md` 참고.

### UI / UX (P0)
- **`MECHA LAB` Workspace**: 버튼·탭 메뉴·F3에서 생성/전환. 현재 탭을 복제해 만들며 다른 탭·Startup File은 변경하지 않음.
  `Repair Layout`, 확인 창이 있는 opt-in `Save as Startup` 제공.
- **왼쪽 큰 아이콘+이름 도구 목록** (Properties 영역 Tool 탭에 표시). 순서: Cut, Split, Boolean, Smart Fuse, Mirror, Mask,
  Curve Array, Radial Array, Panel/Curve, Pose(미구현 표시), Surface Conform, Assets, Remesh, Live Result.
- **공통 Shape 팔레트** (뷰포트 Tool Header, 왼쪽 위): Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Brush Stroke,
  PNG 썸네일 + Custom + Import. 네이티브 버튼이라 GPU hit-test 없음. Shape를 쓰지 않는 도구에서는 비활성 + 안내.
- **오른쪽 Sidebar = 현재 도구 1개의 설정만** (`MCH_PT_main`). 긴 N패널 제거. Sidebar에 접힌 `Tools (fallback list)`.
- **Space** = 큰 아이콘 도구 팝업 (MECHA LAB 탭에서만; 다른 탭은 Blender 기본 Space).
- **Cut과 Split을 별개 도구로 분리.** 별도 Random Polygon / N-gon 항목 제거(Lasso가 그 역할).
- 원본 아이콘 21개(도구 14 + 도형 7) 생성 스크립트 `tools_dev/make_icons.py`.

### Cut 입력 시스템 (P0 버그 수정)
- Cut/Split/Mask를 **네이티브 WorkSpaceTool**로 재구현. LMB 한 번 = 한 획 동안만 모달(`mch.cut_stroke`),
  끝나면 FINISHED → **컷마다 독립 Undo 단계**. 획 사이에는 모달이 없어 `Ctrl+Z`/메뉴/다른 에디터가 정상 동작.
  (v0.5.9: 하나의 장기 모달이 모든 키를 가로채 Ctrl+Z 불가, 메뉴 클릭 전 Esc 필요.)
- 획 도중: 뷰포트 밖 이벤트는 pass-through(팔레트·사이드바·메뉴 클릭 시 Esc 불필요), Shape/도구 변경 시 미완성 획만 폐기,
  `Ctrl+Z`/`Backspace` = 마지막 점, `Ctrl+Shift+Z` = 점 복구, `Esc` = 획만 취소, 더블클릭 확정 시 점 중복 없음.
- **RMB 1번 = Shape 팝업, RMB 더블 = 도구 종료**: 더블클릭 간격(사용자 설정)만큼 기다린 뒤 팝업을 열어 두 번째 클릭을
  삼키지 않음. 대기 중이 아닐 때는 작은 게이트 연산자(`mch.rmb_gate`)가 같은 규칙 처리.
- `Space`는 컷 확정에 쓰지 않음(도구 메뉴). 확정은 Enter / 더블클릭.
- Curve Lasso: 점 재클릭으로 4단계 라운드 순환, 점·핸들 드래그, 핸들 표시.
- 원근(perspective) 뷰에서도 그린 실루엣과 일치하는 **frustum 커터** (v0.5.9는 정사영 가정 prism).
- 2점 직선 컷의 평면도 원근 정확(두 시선 ray를 포함하는 평면).

### 기하 안정성
- 새 `core_geometry`: 커터를 캡(구멍 포함 삼각분할)+벽이 정점을 공유하는 **닫힌 메쉬로 직접 생성**하고 manifold 검사.
- Boolean은 **베이스 메쉬에 대해서만** 평가(기존 모디파이어는 평가 중 잠시 숨김 → 그대로 유지), 결과 검증
  (전체 삭제 / 교차 없음 / 비매니폴드) 후에만 기록. 실패 시 원본 무변경 + 메시지, Undo 단계도 생기지 않음.
- Solver Auto: 닫힌 메쉬는 Manifold → Exact 폴백, 열린 메쉬는 Exact.
- **공유 메쉬(Alt+D) 지원**: 모든 적용 경로(`Cut`, `Boolean`, `Slice`, `Smart Fuse confirm`, `Remesh`, `Live result`,
  `Mirror apply`, `Radial bake/Boolean`, `Apply Live Cut`)를 `bpy.ops.object.modifier_apply` 대신 데이터 수준 적용으로 교체.
  v0.5.9 오류 "Modifiers cannot be applied to multi-user data"를 headless에서 재현 → 0.7.0에서 해결 확인.
  정책: 이 오브젝트만(기본) / 모든 링크 복제본.
- **Edge Finish (Bevel/Chamfer) — 새 절단 엣지만**: 커터 면에 `mch_cutter_face` 속성을 달아 Boolean 후
  커터 면/원래 면 경계만 bevel. 원래 실루엣 모서리는 테스트로 불변 확인. Lasso 모서리 라운드와 완전히 별개 설정.
- Split: 안쪽은 `<이름>_Split` 새 오브젝트, Cap ON/OFF.
- Depth `From Surface`(고정 깊이 포켓) 추가.

### PNG Custom Cut Shape (P1)
- v0.5.9 비매니폴드 원인 재현: **모서리만 맞닿은 픽셀**(대각선 접촉) → 윤곽선이 한 정점을 공유하는 bow-tie →
  커터가 닫히지 않음. 새 파이프라인은 마스크 정리(점 노이즈/핀홀 제거) + 2×2 saddle 해소 + 단순화 결과의
  자기/상호 교차 검증(실패 시 단순화를 줄여 재시도, 최종적으로 원본 픽셀 윤곽) + 포함 깊이 기반 외곽/구멍/섬 구분.
- PNG 도형이 공통 Shape 팔레트의 일부가 됨(Cut/Split/Mask에서 같은 커터 엔진 사용). 클릭 스탬프 / 드래그 크기.
- Smooth Steps, Remove Specks 옵션, 프리셋 schema 2. v0.5.9 프리셋 자동 업그레이드.

### Smart Fuse (P2, 부분)
- **v0.5.9 Smart Fuse 패널의 크래시 원인 확인**: Live Preview 패널이 Blender 5.0에 없는 아이콘 `MOD_NODES`를 사용 →
  패널을 그릴 때마다 TypeError(스크린샷의 잘린 traceback이 아이콘 enum 목록을 출력하는 형태와 일치). `GEOMETRY_NODES`로 수정.
  모든 소스의 아이콘 이름을 5.0 enum과 대조하는 테스트 추가.
- **두 번째 크래시**: 생성 실패 시 정리 코드가 이미 삭제된 노드 그룹에 접근(ReferenceError). 수정.
- 생성 직후 교차 seam 존재 여부 검사: 떨어져 있거나 면만 맞닿은 메쉬는 설명과 함께 거부하고 원래 상태로 복구.
- 셰이프 키가 있는 메쉬는 거부.

### 호환성
- 이전 연산자 ID 유지: `mch.draw_delete_cut`(→ Cut/Split 도구 활성화), `mch.draw_mask`, `mch.stamp_png_cut`,
  `mch.select_tool`, `mch.cut_finalize`(데이터 안전 적용으로 재작성), `MCH_MT_tool_menu`.
- 저장된 .blend의 선택 도구 enum 번호 유지.
- `mch_enabled`(v0.5.9 세션 토글)는 남겨두었지만 사용하지 않음 — 단축키는 Workspace 범위로 대체.
- manifest `blender_version_min` 4.3 → **4.5** (Manifold solver 필요).

### 제거
- v0.5.9 장기 모달 `MCH_OT_draw_delete_cut` 본체, 긴 N패널(`MCH_PT_cut/boolean/fuse/...`), MECHA LAB MODE 토글 UI.
- 오래된 애드온 내부 문서 `README_v0_5_9_KO.md`, `PNG_CUT_GUIDE_KO.md` (원본은 reference에 보존).
