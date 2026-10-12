# CHANGELOG

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
