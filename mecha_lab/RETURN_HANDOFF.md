# RETURN HANDOFF → ChatGPT — Mecha Lab 0.18.2 (Claude Code, 2026-10-14)

## 0.18.2
- ZIP sha256 `d42bf7acb06f73f9a1ecfc407cbe069f6b7d73c29cc50d1701d429138a0b315a`. `workspace_ui.dial_factor()`(pref `dial_flip`, 기본 True = -1), `DialSession.turn`과 `station_gizmos` 각도 접근자에 곱함.

## 0.18.1
- ZIP sha256 `e417cde7d73a648552f71bfce2e03a1a1735abc94c23c3b900edcca0401e65ce`. `primitive_hud`: `SEG_COL`, `SEG_LABELS`(구간 +/− 초록 + 라벨).

## 0.18.0
- ZIP sha256 `9fd397beacf579662cd3e784e451d42c5786bdce1fcbf3c6891bb4673364a5cf`, 1438/1438. 신규 `mirror_hud.py`: `BUTTONS`, `targets`(MECHA LAB + Mecha Mirror 선택), `hud_layout`, `is_on`,
  `mch.mirror_hud_option`(X/Y/Z/BISECT/FLIP → setup_mirror), `MCH_GGT_mirror_hud`, 라벨 핸들러.

## 0.17.0
- ZIP sha256 `619ec073ecd210bfebb787b059d81a8eaa51fc6abd10f471b5e117c0b9b9316a`, 1425/1425. 신규 `random_panels.py`: `sample_seeds/assign(KDTree)/lloyd/panel_outline/edge_pieces`,
  `MCH_PG_Random`(Scene.mch_random, 값 바꾸면 regenerate), 세션 Scene ID prop `mch_random_session`(target, faces, objects),
  `regenerate/start/finish`, 연산자 `random_panels/random_reroll/random_finish/random_toggle`, `MCH_GT_random_slider`,
  `MCH_GGT_random_hud`, `hud_layout/slider_spec`. `armor_plate.create_plate`(공용), `screen_patch(min_spacing=)`.

## 0.16.0
- ZIP sha256 `6abd7c3046e7322f11f965f46f24eb0973abee5848a8c6c954e7d6797547475c`, 1401/1401. 신규 `armor_plate.py`: `PRESETS`(크기 비율), `preset_values`, `resample_loop`, `screen_patch`
  (delaunay_2d_cdt, 엇갈린 격자), `pick_surface`(판/파트 건너뜀), `project_patch`(시선 투영 + 짧은 재투영, 빗나간 점 = 평면),
  `build_region`(join_triangles), `surround_mesh`, `perform_plate`(face_extract 파트 생성), `cycle_preset`, `MCH_PG_Plate`(Scene.mch_plate),
  `mch.plate_preset`, `draw`. `cut_engine`: 모드 `PLATE`(대상 불필요, 닫힌 외곽, 휠 = 프로필, 색). `tool_state` PLATE(25, native
  `mecha.armor_plate`), `workspace_ui.MCH_TOOL_armor_plate`, `ui_tool_settings.draw_plate`.

## 0.15.0
- ZIP sha256 `76313363f6015ed9231289d0e15ba829ff0037cf08d2dd9c45837529fbc6b5c5`, 1365/1365. `workspace_ui.icon_tile` = template_icon + 이름 버튼. `bottom_bar`: `side_tools/side_layout/side_left`,
  `MCH_GGT_side_toolbar`, pref `side_toolbar`; `MCH_PT_tool_list` DEFAULT_CLOSED. 신규 `primitive_hud.py`: `hud_target/target_points/
  hud_layout/slider_spec/slider_value/coplanar_faces/coplanar_cached/commit_station`, `MCH_OT_hud_mode/hud_apply`, `MCH_GT_hud_slider`
  (Python Gizmo), `MCH_GGT_prim_hud`. `primitive_place`: `mode_sub`, `DialSession.signs/update_signs`, `place_handles(signs=)`, 겹침 빨간 점선,
  `overlapping_meshes(exclude=)`. `station_sweep`: `bend_up/bend_side`(기존 각도+방향과 합산), `ngon_loop`, kind `NGON`, preset `PRISM`,
  build 결과 `ring_size`. `station_primitive`: props `bend_up/bend_side/corner_finish…/cap_finish…`, `edge_tag/_finish`(bmesh bevel),
  `migrate_bend/migrate_object`(load_post), `total_bend`, `add_segment/remove_segment`, `BEND_LEVELS/bend_level/cycle_bend`,
  `apply_object`, 연산자 `station_segment/station_bend_cycle`. `station_gizmos`: `facing`, 새 `station_handles`(up/side/twist/height_bot/folds/
  signs), `SIGNS`, 접힘 점 gizmo.

## 0.14.4
- ZIP sha256 `9d1f28552f9af14e4ab6922f6820457903589b3681a0c4127df5d07e2128ce1a`, 1315/1315. `cut_engine._COLORS`에 BASE(주황) / BASE_INV(빨강), `stroke_color(mode, inverted)`.

## 0.14.3
- ZIP sha256 `60c5632b16f86f805f8383c8d95db75b597111d1658c10362eee877c502a3858`, 1313/1313. `primitive_place`: `top_factors`, `ghost_geometry(top=(x,y))`, `ghost_shape`(bevel/chamfer),
  `st_shape` 캐시, props `top_x/top_y/edge/edge_width/edge_segments`(show 기본 False), 도형 기록 `HISTORY/snapshot/restore/note_change/
  settle/ghost_undo/ghost_redo` + `mch.place_undo/redo/undo_key`(Ctrl+Z), `place_handles`(X+..Z- 네모, MX/MY/MZ 이동, RX/RY/RZ 다이얼,
  U0/U1 점), `move_along`, `uniform_size`, `DialSession`, `COMMITTED/mark_committed/ghost_fill_alpha`, 면 컬링. 합칠 때 live Base Mesh 동결.
  `station_gizmos`: `note_handle_edit/flush_handle_undo`(ed.undo_push). `station_primitive.create`: 도형 숨김.
  `base_mesh`: `surface_align`, `embed`, `surface_frame`, `frame_for`, `_WithEmbed`. `workspace_ui`: `icon_tile`, 툴 목록 격자,
  `save_sizes/load_sizes`(config/mecha_lab/ui_sizes.json).

## 0.14.2
- ZIP sha256 `d87a87ef336679dbe52ae6b93a0e4afbe9c3ec3e79656634f7966e4f72aeb610`, 1260/1260. `workspace_ui`: prefs `icon_scale / toolbar_scale / handle_scale`, `isz(base)`, `handle_scale()`,
  `draw_icon_sizes`, `MCH_OT_icon_size_preset`, `MCH_PT_icon_size`. 모든 `template_icon(... scale=)`은 `isz()` 경유.
  `bottom_bar.toolbar_layout(..., factor)`. `primitive_place.MCH_GGT_place` / `station_gizmos` draw_prepare에서 scale_basis × handle_scale.

## 0.14.1
- ZIP sha256 `a7c73a85c561308b550d36667b2e6c51ffd4dbbcb6f294433af5daceb35f8b2c`, 1247/1247. `base_mesh`: `MCH_PG_BaseMesh.sketch`(기본 True), Scene ID prop `mch_base_sketch`(JSON: frame 4x4 +
  items [{op ADD/SUB, groups}]), `sketch_triangles`(delaunay_2d_cdt output 1 + faces_orig, 순서대로 더하기/빼기), `_boundary_loops`,
  `sketch_regions`, `sketch_add`, `sketch_commit(cutter)`, `_create_live_base`(perform_base에서 분리), `_sketch_cutter_targets`,
  POST_VIEW `_draw_sketch`, 연산자 `mch.base_sketch_commit / _key / _clear / _undo`. `cut_engine._execute_closed` BASE 분기,
  `workspace_ui._tool_keymap('BASE')`에 Enter / Alt+Enter / Esc / Backspace.

## 0.14.0
- ZIP sha256 `d02dc9f2137be4b32d94f667342739ff348449ac86c403d5199eb3cc89b5f3e9`, 1219/1219. 신규 `primitive_place.py`: `ghost_geometry(kind, size, segments, top)`(순수, 6종: BOX/CYLINDER/PILL/
  SPHERE/CONE/CAPSULE), `stadium`, `resize_face`(비대칭), `place_handles`, `align_rotation`, `overlapping_meshes`(BVH overlap +
  ray parity), `pick_union_target`, `commit(context, st, subtract)`(core_geometry.boolean_result + finish_new_edges + commit_mesh),
  `MCH_PG_Place`(WindowManager.mch_place), `MCH_GGT_place`, POST_VIEW 반투명 그리기, `TOOL_KEYMAP`, `MCH_PT_place_shapes`.
  `workspace_ui.MCH_TOOL_primitive`(`mecha.primitive`), `tool_state` PRIMITIVE native = `mecha.primitive`.
  `cut_engine.stamp_cursor_point`(창 좌표 그대로). `bottom_bar.MCH_OT_bar_tool` + `bar_tip`(툴팁 = 이름). `primitive_tools.draw_kind_grid`.

## 0.13.1
- ZIP sha256 `e5d7c53df793481454502b35a5fe2c28070cd7921ca136728ce8157da2281a6e`, 1152/1152. `station_sweep`: `bend_style`(AUTO/FOLD/TIGHT/BAND), 지점 `profile`(INHERIT/종류), `ring_loop`
  (두 단면 보간), 모든 종류 공통 정점(다각형 꼭짓점 항상 포함). `station_primitive`: `sym_lr`, `FRAMES` 캐시, `station_select /
  station_insert / station_bend_dir`. `station_gizmos.py`: `station_handles(ob)`(순수), `make_accessors`, `MCH_GGT_station_handles`.
  `mirror_tools`: Apply 전 `station_primitive.freeze`.

## 000000. 0.13.0 Station Primitive (Phase 1)
- ZIP sha256 `a9dba3e703b9d92e5f0cbd761033fb0f663bfe871f1a857641868192b83133f9`, 1124/1124. 설계·결과 페이지: https://claude.ai/artifact/QuYhJsnfWbLET7fF97M7fn
- `station_sweep.py`: `profile_loop(kind, p, res, ridge, sides)`(정점 수 고정), `build(spec)` → verts/faces/warnings/frames,
  `preset(name)`. Frame(P,X,T,Z), 지점별 Local 회전 누적, 접힘 = 이등분 마이터, 아크 = pivot 회전.
- `station_primitive.py`: `Object.mch_station`(stations 컬렉션), `rebuild(ob)`(bmesh 정리 + 각도 30° 이상 sharp),
  `freeze(ob)`(cut_engine/Boolean에서 호출), 연산자 create/add/remove/move/apply, `draw(layout, context)`.

## 00000. 0.12.0 (UX 프로토타입의 최소 Blender 버전)
- ZIP `dist/mecha_lab-0.12.0.zip` (sha256 `270841f19e16687320f5e91e0567a7e5b6b414dd5407e8228a1140304417c7fe`), 1074/1074. 프로토타입: https://claude.ai/artifact/DXBX1cyVtgs3w1k2LqToVH (v2.1)
- `cut_engine.auto_targets / _auto_candidate / _loop_samples`, `StrokeLogic.auto_target` (`mch_cut.targets` = AUTO 기본).
- `bottom_bar.py`: `MCH_GGT_bottom_toolbar`(GIZMO_GT_button_2d), `MCH_MT_tool_pie`, `mch.tool_pie`(Q), `mch.toggle_last_tool`
  (Shift+Q), `mch.toggle_targets`(T), `toolbar_layout()`, WM 속성 `mch_last_model / mch_ui_mode`.
- 다음: 옵션 카드(직접 그린 위젯 vs 헤더), Scope/Layers, 미러 평면 기즈모, Quick Place, Box Hide — 프로토타입 기준.

## 0000. 0.11.3
- ZIP `dist/mecha_lab-0.11.3.zip` (sha256 `deed2943d3d8276a383cdf338455d393e508cf337c6d42e01a1f98c9604e2c37`), 1046/1046. CHANGELOG 0.11.3 참고.
- 스탬프: `cut_presets.builtin_shapes / is_builtin / MCH_OT_pick_stamp_shape / draw_builtin_row` (stem 접두사 `MCH_BUILTIN_`).
- Curve Lasso: `StrokeLogic.rounds` + `curve_lasso_loop / corner_handles / ROUND_LEVELS / next_round_level`
  (sharp/overrides 리스트는 구조 유지용으로 남아 있음; `curve_lasso_spline`은 다른 곳 호환용).
- Mirror: `mirror_tools.setup_mirror / mirror_frame / lean_pick / MirrorLeanLogic / MCH_OT_mirror_lean / start_lean_mirror`,
  `workspace_ui.activate_mecha_tool`에서 MIRROR 선택 시 시작. Bisect flip ON = - 쪽 유지 → + 쪽으로 복사.
- Undo: `tool_state` undo_pre/redo_pre 스냅샷, undo_post/redo_post 복원. 단축키 편집: `workspace_ui.hotkey_items`(매번 조회).

## 000. 0.11.2
- ZIP `dist/mecha_lab-0.11.2.zip` (sha256 `000db2d3d84a0215dcfd1b55fcd296e59267c1e091a2be5d04af7593676c0aa5`), 1012/1012. 사용자: 0.11.1에서도 일반 Cube 실패 → headless 재현 불가.
- `cut_engine.cut_diagnosis / _boolean_checked`: 빈 결과 시 덮는 정점 비율·픽셀·뷰·Alt·버전을 메시지와 콘솔에. `_leave_edit_mode`.
- `self_test.view_cut_check`: 실제 3D View 투영으로 Cut / Alt Cut / Split.
- 다음 단계: 사용자 메시지의 `shape covers N/M`이 M/M이면 화면 좌표/투영 문제(이벤트 좌표·영역), 일부면 Boolean 평가 문제.

## 00. 0.11.1 (Cut/Split 수정, Alt 모드 전환 롤백, Select / Move)
- ZIP `dist/mecha_lab-0.11.1.zip` (sha256 `fb8960ae4fc08a273b09cb6d1cfca01a7efda2da8d16ee193d1ec480423f0593`), 18개 파일 1007/1007 (`tests/test_log_bpy501_v0111.txt`). GUI 미검증.
- 기준은 Claude 0.11.0입니다. 사용자가 말한 ChatGPT 0.10.1/0.10.2는 받지 못했습니다.
- 아래 4절의 "Alt는 놓을 때 판정 / ALTWAIT / alt_pending / mch.alt_click_return / mch_last_tool"은 **모두 삭제**됨.
  현재 Alt = v0.9.3: `alt_latch`(누를 때) 또는 `alt_held`(LEFT_ALT 이벤트) → INTERSECT. 직선 2점 면 선택 Alt+클릭 = 남기기.
- 모드 전환 대체: `workspace_ui.MCH_OT_select_move`(`builtin.move` + 기즈모) / `MCH_OT_select_move_key`(W, 설정 `select_move_key`).
  StrokeLogic은 `native_tool`이 바뀌면 스스로 CANCELLED → 재진입 시 새 상태.
- `core_geometry.ensure_real_mesh`: 기본 메쉬 폴리곤 0 + 모디파이어 있음(Live Primitive) → 평가 메쉬로 굽힘. Cut/Split/Boolean 전에 호출.
  `boolean_result`: 빈 결과는 다음 솔버로, 모두 빈 결과면 대상·연산·솔버를 담은 "whole object" 오류.
- `workspace_ui.draw_hotkey_editor`: Preferences / Workspace & Hotkeys에 `full_event` 키 편집 행.
- 일반 Cube에서의 오류는 headless 재현 실패 → 사용자 메시지(괄호 부분)와 Self Test 결과로 확인 필요.

## 0. 0.11.0 추가분 (Mechanical Modeling Toolkit)
- ZIP `dist/mecha_lab-0.11.0.zip` (sha256 `8518a39a91c5cd9faf00258f1bd697e6f6a9aea9af9ce2f41ff825aef72c6a84`), 18개 파일 995/995
  (`tests/test_log_bpy501_v0110.txt`). GUI 미검증, Blender 5.3 미실행.
- 새 모듈: `panel_gen.py`(순수 단면 생성기: 경계 루프·로컬 프레임·컬럼별 단면(챔퍼/필렛/외곽)·조화 보간 캡 축소·높이장·
  능선장·인덱스 테이블 조립), `face_extract.py`(Object.mch_extract 설정 + 영역 사본 메쉬 2개, Basic/Armor UI),
  `edge_molding.py`(체인 JSON + 표면 노멀 기준 프로필 스윕), `hollow_shell.py`(GN 개구부 + Solidify + Rim Bevel, 과두께 검출),
  `along_curve.py`(Curve 모디파이어 / GN 배열 / Array+Curve, 배치 모드), `cable.py`(두 점 경로·Edge to Cable·프로필 커브).
- 도구 ID: EXTRACT(20) MOLDING(21) HOLLOW(22) ALONG(23) CABLE(24). 기존 ARRAY(Mesh Curve 경로 배열)와 POSE(Deform)는 유지.
- 단면 좌표 규약: s = 경계에서 안쪽 거리(음수 = 바깥), z = 표면 위 높이. 모든 링은 경계 정점마다 1개 → 항상 닫힌 솔리드.
- 패널은 활성 파츠 또는 `Scene.mch_extract_last / mch_molding_last / mch_cable_last / mch_curve_last`를 표시(Edit Mode 유지 중에도).
- Base Mesh 탭 이동 자동 Apply: `base_mesh._tab_watch` 타이머(미확정 세션이 있을 때만), `check_tab_left()`로 테스트.


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
