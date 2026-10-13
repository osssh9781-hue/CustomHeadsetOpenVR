# RETURN HANDOFF → ChatGPT — Mecha Lab 0.10.0 (Claude Code, 2026-10-13)

## 1. 기준과 결과물
- 기준: **ChatGPT v0.9.3** 무수정 ZIP(`reference/CHATGPT_v0_9_3/mecha_lab-0.9.3_ORIGINAL_UNMODIFIED.zip`, sha256 `3b66e845…`).
  v0.9.3 = Claude 0.9.0 + ChatGPT `deform_tools.py`(0.9.1) + `primitive_tools.py`(0.9.2/0.9.3) + 작은 UI/등록 수정.
  v0.9.1 Deform 원본 사본: `reference/CHATGPT_v0_9_3/deform_tools_v091.py`.
- 결과 ZIP: `dist/mecha_lab-0.10.0.zip` (sha256 `708f3c10d42c3569fc350ca27e1b565e54f712a38a9dbd4e2ff6e87540e46b9f`).
- 소스: `addon/mecha_lab/`. 테스트: `tests/` (17개 파일 875/875, 로그 `tests/test_log_bpy501_v0100.txt`).
  ChatGPT의 Primitive 테스트는 `tests/chatgpt_v093/`(하드코딩 경로만 바꾸면 실행됨, 통과).
- 문서: `CHANGELOG.md`(0.10.0 절), `KNOWN_LIMITATIONS.md`(0절), `test_report.md`(코드/headless/GUI 별도 열),
  `GUI_TEST_CHECKLIST_KO.md`(A절 = 0.10.0), 인수인계 원문 `handoff/2026-10-13-v093/`.

## 2. 가장 중요한 사실 (과장 금지)
- **모든 검증은 Linux headless bpy 5.0.1.** Windows 11 / Blender 5.0.2 GUI에서는 한 번도 실행되지 않았습니다.
- 사용자 보고 B01 Mirror / B02 Loft / B03 Smart Fuse는 **headless에서 v0.9.3 그대로도 재현되지 않았습니다.** 0.10.0은 GUI에서만
  생길 수 있는 원인을 고쳤습니다(아래 3). 실제 원인 확인은 사용자의 **Run Mecha Lab Self Test** 결과(클립보드)와 콘솔 로그로.
- "코드에 있음 ≠ headless 통과 ≠ GUI 동작". test_report.md 표를 그대로 유지해 주세요.

## 3. 사용자 보고 고장별 조치 (원인 → 수정 → 테스트)
| ID | 원인(확인/추정) | 수정 위치 | 테스트 |
|---|---|---|---|
| B09 | 해제가 중간에 예외로 멈추면 클래스가 남아 다음 활성화가 `already registered`로 실패하고, 그 뒤 등록(Mirror/Radial/Surface 하위 패널·키맵·툴)이 모두 빠짐. 두 사본(예전 Add-on + 확장) 동시 활성도 같은 증상 | `addon_safety.py`(purge_stale, run_steps), `__init__.register/unregister`(롤백, 단계별 해제), 모듈 상태 리셋, 패널 경고 | test_registration_recovery (38), zip 3사이클 |
| B01/B02/B03 | (추정) B09, 그리고 **왼쪽 도구 목록이 Properties 편집기**라서 `wm.tool_set_by_id`가 3D View가 아닌 컨텍스트에서 실패 → 툴이 mecha.cut에 고정 → 패널이 계속 Cut, LMB가 Cut. Fuse: 다른 오브젝트의 미확정 미리보기가 패널을 점유, Undo 후 `active` 플래그만 남아 재생성 거부 | `workspace_ui.set_native_tool`(3D View temp_override), `tool_state.effective_tool`(`mch_native_at_choice` 고착 감지), `StrokeLogic.invoke`(다른 도구 선택 시 PASS_THROUGH), `fuse_is_live`/`fuse_target_from_context`/`_purge_fuse_groups`, Mirror Apply/Remove 다중 | test_v0100_regression, test_self_test |
| B04 | 두 번째 클릭이 `DOUBLE_CLICK` 없이 `PRESS`로만 오는 환경 | `StrokeLogic._on_lmb`: `last_press`(시간+DBL_PX) 자체 판정, `CLOSE_PX`×UI Scale, 편집 클릭 뒤 DOUBLE_CLICK은 편집으로 처리. 3회 클릭 제거 | regression B04 |
| B05 | 기존 점 더블클릭 = PRESS 토글 + DOUBLE_CLICK 토글 → 원상복귀 | `PathDrawLogic._toggle_once` | regression B05 |
| B06 | 0.7 리팩터에서 PNG 스탬프 R 회전 누락 | `cut_engine.rotate_stamp`, `MCH_OT_stamp_rotate`(툴 키맵 R/Shift+R, poll=PNG일 때만), `draw_stamp_cursor`(WorkSpaceTool.draw_cursor) | regression B06 |
| B07 | B04와 동일 경로 + 열린 선은 시작점 클릭 미지원 | `_hit_start` 열린 선 허용 | regression B07 ×3 + 열린 선 |
| B08 | 사용자 요청 | `tool_state.HIDDEN_TOOLS/VISIBLE_TOOLS`, `NATIVE_TOOLS`에서 mask 툴 제외, `mch.draw_mask`는 경고만. 코드/데이터 유지 | regression B08 |
| B10 | 슬라이더 상한 0.5, clamp 결과 미표시 | `core_geometry.finish_new_edges(clamp, label)`, `FINISH_NOTES`, `cut_engine._with_finish_notes`, `MCH_PG_Cut.finish_clamp` | regression B10 |

## 4. 새 기능 구조
- **입력**: Alt는 놓을 때 판정(`ALT_CLICK_SEC`=0.5, `ALT_DRAG_PX`=5×UI). 대기 중 Alt 누름 = `stage 'ALTWAIT'`, 그리는 중 = `alt_pending`.
  짧은 클릭 = `_leave_tool`(→`exit_tool`: `mch_last_tool` 저장, Base Mesh 세션 Auto Apply). Object Mode `Alt+LEFTMOUSE CLICK` →
  `mch.alt_click_return`(오브젝트 레이캐스트, 없으면 PASS_THROUGH). `V` = `mch.quick_menu`(`MCH_PT_quick_popup`, `ts.QUICK_TOOLS`),
  `Shift+A` = `MCH_MT_add_mecha`(VIEW3D_MT_add.append). 모두 MECHA LAB Workspace에서만, Preferences 토글.
- **Boolean**: `boolean_roles()` — 활성 = 커터, 나머지 선택 = 대상. 대상별 safe_apply, 실패 대상은 원상태, 하나라도 실패하면 커터 유지.
- **Cut/Split 다중**: perform_closed/perform_line 대상별 try, `_target_report(skipped, failed)`. 대상 1개일 때는 기존처럼 예외.
- **Base Mesh**: `bevel_sides`(TOP/BOTTOM/BOTH/NONE), `bevel_width_bottom/segments_bottom/bevel_link`, `side_values(p, flip)`,
  `_bevel_rims`, `perform_base(..., cutter=True)` → `_perform_cutter`(Z 반전 + 1% 띄움 → Boolean Difference), `SESSION_KEY`
  씬 ID 속성 + `auto_apply_session`(freeze + `ed.undo_push`), `bottom_too` → BOTH 로드 마이그레이션.
- **Stabilizer**: `stabilizer.LazyStabilizer`(순수 파이썬). StrokeLogic `_stroke_start/_stroke_sample/_stroke_finish`, 60Hz `stab_timer`,
  overlay에 지연 원/줄. 브러시 속성 `stab_enable/stab_strength/stab_radius/stab_guide`, 간격은 기존 `stroke_spacing`.
- **Deform**: v0.9.1 ID 유지(`mch.deform_lattice/bend/edit/finish_edit/gizmo/reset/apply/remove`) + 신규 `mch.deform_transform`
  (기즈모 모달/실행/리두), `mch.deform_step`, `MCH_GGT_deform`(Mecha 기즈모), Falloff 오버레이. 순수 수학: `falloff_weight`,
  `compute_weights`, `transform_point`, `apply_falloff`(Bend: 접선 성분 회전 → tilt, Scale → radius). 씬 설정 `Scene.mch_deform_tool`,
  컨트롤러 값 `Object.mch_deform`(v0.9.1 필드명 유지 + `bend_count`, `applied_twist/taper`). 툴 ID는 계속 `POSE`(라벨 Deform).
- **자가 진단**: `self_test.run()` — 임시 씬에서 핵심 연산자 실행, 끝나면 생성 데이터 전부 삭제, 결과 클립보드.

## 5. 지켜야 할 규칙 (사용자 결정)
- 활성(노란색) = Boolean 커터. Alt+MMB 추가 금지. 3회 클릭 토글 부활 금지. Mask는 숨김만(삭제는 승인 후).
- Base Mesh 자동 Apply는 그 도구가 그 세션에 만든 Live 결과만. 다른 오브젝트/모디파이어 절대 Apply 금지.
- Shape Corner(2D)와 Edge Finish(3D) 분리 유지. Curve Lasso ≠ Mesh Curve(Curve Tool). ZBrush는 OBJ(GoZ 아님), 자동 Join 금지.
- 기존 연산자 ID 삭제 금지, 사용자 .blend/Preferences/Startup 무단 변경 금지.
- Windows GUI에서 실행하지 않은 것은 "미검증"으로 표기.

## 6. 남은 일 / 다음 단계
1. 사용자 GUI 체크리스트 A절 결과와 Self Test 결과 수집 → B01–B03이 남아 있으면 그 로그로 원인 확정.
2. Stabilizer 체감(60Hz 타이머, Strength 곡선) 조정은 사용자 피드백 필요.
3. Deform: Rigid Pose 미구현, 곡선 거리 기반 Falloff, Mecha 기즈모의 Each Point 표시.
4. Mask: 사용자 승인 시 코드 정리 여부 결정.
5. 키 설정 전용 UI, Base Mesh Surface Follow, GoZ 등 기존 미구현 목록은 KNOWN_LIMITATIONS C절 그대로.
