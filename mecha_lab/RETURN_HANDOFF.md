# RETURN HANDOFF → ChatGPT — Mecha Lab 0.23.6 (Claude Code, 2026-10-14)

## 0.23.6
- ZIP sha256 `33b9ca16680a13a214137287b000b6defd8868158563617a0027eafc631566e6`. `cloth_wrinkle` v40 `_skin_pattern`: `pillow(vec, f, groove, radius)` = sqrt(1-(F1/r)²) × smoothstep(edge, 0, groove) × 셀별 높이; croc = 큰/작은 pillow를 노이즈로 섞음 + 미세 결; dragon = pillow 자갈 + 성긴 Voronoi 셀 중 Color.g > 0.7에 원뿔 가시; 새 Skin 6 `CROC_BACK` = FRACT 격자(x 0.8f, y 0.9f) sqrt 판 + |fx-0.5| 용골, 격자 셀 WhiteNoise. Index Switch 7칸, Skin 입력 최대 6.

## 0.23.5
- ZIP sha256 `bc7f813a15d7d35a6b6c834bfcd84699dfa5cca97bc8ff1b60b7aee15bc3626b`. `creature_shell` v12: 입력 뒤에 Organic / Edge Shrink / Shrink Width / Edge Irregular 추가(기존 소켓 identifier 유지). 노이즈 도메인 워프 `Qw`, `facet_field(scale, amp, groove)` 3단계(fs, 1.6fs, 2.6fs) 혼합. 경계 거리 = 옆면 점(|n·Up| < 0.4, 밑면 제외)까지 Geometry Proximity + 노이즈 2개 × Edge Irregular × Shrink Width. 셀별 랜덤 지터는 절벽이 생겨서 뺌. `cloth_wrinkle` v35: Skin Organic / Skin Irregular(`_skin_height`에서 P 워프, `Dj`는 shrink에만 쓰고 가장자리 마무리는 원래 `Db`).

## 0.23.4
- ZIP sha256 `0bc194542d646eb45460b6dcb1b27fe835240bfc886af3fd6e82689e178ef46a`. `cloth_wrinkle` v34: `Fold Direction`(0 Up / 1 Down / 2 Random; `fold_lines`에서 월드 위를 패널 평면에 투영한 `up2`로 주름별 side 결정), 크리처 입력 Skin(0..5) / Skin Scale / Depth / Random / Edge Shrink / Shrink Width / Skin Edge(0..3) / Width / Height, `_skin_pattern`, `_skin_height`(안쪽 / 가장자리 두 주파수를 `near`로 섞음), `SKINS` / `CREATURE` / `apply_creature`, `mch.wrinkle_skin`, `mch.wrinkle_skin_edge`, `mch.creature_brush`(activate 후 flag 켬). 새 `creature_shell.py` v5: GN `MCH_CreatureShell`(Voronoi 셀 기울기 × DISTANCE_TO_EDGE smoothstep 홈 - 높이 연속, 노이즈 Bulge, Attribute Statistic 범위로 Lift N/E/S/W, 월드 아래 Gravity), `attach`, `mch.shell_option`, HUD. `armor_plate.perform_plate`가 `mch_plate.creature`면 attach. 툴바 SKIN / SHELL.

## 0.23.3
- ZIP sha256 `a4f865c0cc84c7151dfae8e731397b7c2ee08dc916b4122482e16f6d7511b8f1`. `cloth_wrinkle` v32 입력 `Fold Asymmetry`, `Fold Thinness`(FOLD_INPUTS), `fold_lines`: 주름별 side(부호 amp), 부호 거리로 steep(`prof_s` + `crease`) / gentle(`prof_g`) 단면, 패널 엣지 중앙값 × 1.3 최소 폭. `curve_tube.ik_drag`(FABRIK + 로프), `ik`/`ik_pin`, 버튼 `ik`.

## 0.23.2
- ZIP sha256 `abdbb6bf35336f396f825390793aea17e11df35405cf0878626e6ec74376b937`. `mirror_tools`: `gesture_base`, `lean_pick(center=)`, `MirrorLeanLogic.center` = (w/2, h*0.18), 오버레이도 그 자리, `MCH_OT_mirror_lean.keep_live`; `bottom_bar` MIRROR = `mirror_lean(keep_live=True)`.
  키맵 V → `mch.tool_pie`. `cloth_wrinkle` GN v31 입력 `Gravity`(Self Object 회전으로 월드 아래 방향, 접선 + 0.25 아래, 높이·테두리 거리 비례). `tool_state` TUBE 라벨 'Mesh Curve', HIDDEN_TOOLS += DRAW.
  `curve_tube`: `spacing_mode`/`spacing`, `source_mesh(src, depsgraph)`(평가 메쉬), depsgraph 핸들러 `_on_depsgraph`(링크 갱신), `MCH_GGT_tube_points`(move_3d 점/굵기 기즈모), `MCH_GGT_tube_bar` + `MCH_GT_tube_slider` + `mch.tube_toggle`, `tube_bar_layout`. 테스트 `test_v0232.py`.

## 0.23.1
- ZIP sha256 `40c90b05879f4bc74a37b8b88009f55330569a53b93119382a80bade467ade36`. `TubeLogic.handle_world` / `_near_handle` / `radius_text`, `drag_kind` POINT / RADIUS, 그리기에 주황 핸들 + 연결선.

## 0.23.0
- ZIP sha256 `acaefe96cb9e9c3319ce4d55cceb66f16d25dfc6aeda91277f9b727f2753307a`. 신규 `curve_tube.py`: 점 = 오브젝트 커스텀 속성 `mch_tube_pts`(x,y,z,r), `Object.mch_tube`(MCH_PG_Tube, 값 변경 시 `rebuild`), `Scene.mch_tube_defaults`.
  순수 `path_samples`(Catmull-Rom / 클램프 B-Spline / Linear, 닫힘), `frames`(평행 이동), `profile`, `tube_mesh`(캡 Flat/Round/Open, Hole, 부피로 노멀), `arc_points`, `repeat_mesh`, `sphere_source`. `TubeLogic` + `mch.tube_draw`(POST_VIEW 점/선), `mch.tube_apply`, 패널 `MCH_PT_tube`.
  도구 `TUBE`(enum 27, 네이티브 없음) — `activate_mecha_tool`에서 `start_draw`, `bottom_bar.BAR_TOOLS`/`PIE_SHARED['RADIAL']`, `ui_tool_settings.DRAWERS['TUBE']`. 테스트 `test_v0230.py`.

## 0.22.2
- ZIP sha256 `7da9482b1e03ee42f2d2c6b6bd5ce1e6bd8bfd3a1e1406ce7a02b4f763b4525c`. `surface_lasso.MODES` += PLATE/WRINKLE (`PATCH_MODES`), `SurfaceLogic.surface_view`(평균 법선 방향 OrthoProjector, 외곽이 화면 40 % 안에), `_finish_patch` → `armor_plate.perform_plate` / `cloth_wrinkle.perform_wrinkle`(스크린 루프 + 그 Ortho 시점 = FrozenProjector 대신 ortho로 저장되어 라이브 재생성 가능), Line 모드면 `lasso_line.band`. 테스트 `test_v0223.py`.

## 0.22.1
- ZIP sha256 `4af3ae8763ee90122bfd0953153ec4c13548ab3d663feafa87546040160e296c`. 키맵: Q → `mch.toggle_last_tool`, Shift+Q → `mch.tool_pie`. `robot_base.UI_PARTS['HUMANOID']`/`BODY_HUMANOID`에서 TORSO/CHEST/PELVIS/HEAD 제외(코드는 남김).
  신규 `surface_lasso.py`: brush `surface_mode`/`surface_gap`, `SurfaceTarget`(BVH, 로컬 좌표), `trace`(현을 법선 따라 표면에 투영), `membrane`(루프 비누막 디스크 + 바깥 링), `split_along_loop`(Solidify Gap 커터 + EXACT 불리언 → 조각 분리, 조각 1개면 원래대로), `SurfaceLogic` + `mch.surface_lasso`(POST_VIEW 그리기). `cut_engine.StrokeLogic.invoke`에서 Surface면 이 연산자로 넘김. 테스트 `test_v0222.py`.

## 0.22.0
- ZIP sha256 `900785f05dcdbc090e31e0945cbd636f41960ce9851cd8a8003cbe77dea30784`. `robot_base`: `tube_mesh`(공용 링 튜브 + 끝 캡/노치/기울기/구멍/관통, 부피 부호로 노멀 정렬), `template_mesh` + `robot_templates.py`(CHEST/PELVIS/HEAD 단면 22/18/26링 × 32각, 높이 방향 스무딩),
  `REGIONS`/`REGION_KEYS` rg1..rg8, `anatomy`, `bulge_shape`/`bulge_width`, `notch_b`(+width), `hole_top`/`hole_top_d`/`hole_bot`/`hole_bot_d`, `UI_PARTS`, `BODY_HUMANOID`, `slider_keys`(LIMB/TEMPLATE/OTHER), `region_label`.
  신규 `lasso_line.py`(`band`, `remove_loops`, `pixels_per_unit`, `line_loop`; brush `line_mode`/`line_width`/`line_caps`; `cut_engine.StrokeLogic._line_mode/_line_path/_line_loops` 훅).
  신규 `detail_stamp.py`(프리셋 = config/mecha_lab/details/*.blend, `add_preset`/`load_mesh`/`delete_preset`, `place_matrix`, `stamp`, `surface_hit`, `StampLogic` + `mch.detail_stamp`, 패널 `MCH_PT_detail_stamp`). 테스트 `test_v0212.py`, `test_v0220.py`, `test_v0221.py`.

## 0.21.1
- ZIP sha256 `28f227289134c4da7e6791060171b5335ec1538150867f21caa73b543d485d4b`. `robot_base.limb_mesh`(인간형 팔다리, 링 + 동심 끝면, 관절 없음), `LIMB_SHAPES`/`LIMB_KEYS`(사용자 Genesis 9 조각 측정값), PG 속성 bottom_w/bottom_d/taper_start/bulge_pos/bulge_offset/split/split_angle/groove(+angle)/ridge(+angle)/twist/bow(+angle)/notch(+width)/slant/top_slant,
  `is_limb`/`slider_keys`(부위별 HUD 슬라이더), `hud_layout(keys=)` 열 나눔. `loft`가 아래로 가는 단면이면 면 뒤집기(산업형 노멀 수정). Scene details 기본 False. 테스트 `tests/test_v0211.py`.

## 0.21.0
- ZIP sha256 `2a5e512f90a5c25c90d186bb953a677b9631b769b8411b10d6918b10eb40f6d8`. 신규 `robot_base.py`: 순수 `build_part(p)`(loft/superellipse/box/cylinder, 끝면 모양 `part_ends`/`end_point`/`ends_ring` — 원/네모/N각 사이 모프, 코너가 링 정점에 오도록 링 수 조정),
  `Object.mch_robot`(MCH_PG_RobotPart, 값 변경 시 `rebuild` + 모디파이어 `MCH_RobotBevel`), `Scene.mch_robot_settings`, `create_part`/`create_body`(BODY 관절 배치, 좌우 별도), ops `mch.robot_add/reroll/toggle/apply`, HUD `MCH_GGT_robot_hud`, 패널 `MCH_PT_robot_base`. 테스트 `tests/test_v0210.py`.

## 0.20.4
- ZIP sha256 `cbbb020992bbcca716dca0103a18ed4c31f90c958aeb7a3d26543c071380271e`. GN 입력 `Section Height`(v29). last_used: 절대값 저장. `capture`/`apply_values`/`user_presets`, ops `mch.wrinkle_preset_save/load/delete`, 메뉴 `MCH_MT_wrinkle_presets`.

## 0.20.3
- ZIP sha256 `f157cdd26be6e04deb19c6b879623c190ab8434b437fe77a7aec1e3a08e0afe1`. `bottom_bar.TIDY` + SYMMETRY(`mch.mirror_lean` INVOKE) / MIRROR(`mirror_tools.setup_mirror`), 도구 라벨 MIRROR → 'Symmetry'.

## 0.20.2
- ZIP sha256 `00ea99cffb7adbe49395b853ec1393eecb15654bd68589cd764819cc23339325`. `cloth_wrinkle` GN v28: 긴 주름 = Python `fold_lines()`가 numpy로 계산한 점 속성 `mch_foldh`(FOLD_INPUTS 변경 시 재계산), 짧은 부채꼴은 GN(Fan Mix),
  섹션 Attribute Statistic 기반(Section Turn/Shape/Bend/Start/End/Move), Center Fade/Patchiness, Randomness 슬라이더. 신규 `last_used.py`(remember/recall, scene PG → JSON, 새 파일만 복원, 백그라운드 제외).
  `armor_plate.remember_plate/recall_plate`. `highpoly.creased_subdiv`(플레이트 HP).

## 0.20.1
- ZIP sha256 `f5e340bd6da5c349c56537645822e8e98e09c5c26f64c40c9f82c2baaf1d4ffd`. `cloth_wrinkle` GN v13: 입력 Puff/Puff Width/Roll/Roll Width/Pinch/Pinch Spacing/Pinch Length/Stitch/Stitch Inset/Stitch Length/Bend/Sections/Fold Sharp/Fan/Trim/Trim Width/Trim Height,
  속성 `mch_edge_dist`(직선 거리), `mch_edge_u`, `mch_edge_len`, `mch_sec_u`, `mch_sec_len`, `mch_fold_room`. `PRESETS`/`apply_preset`, `TRIM_PRESETS`/`apply_trim`, ops `mch.wrinkle_trim`, `mch.wrinkle_reset`.
  `set_input`이 `interface_update` + update_tag + redraw. Solidify even offset 끔.

## 0.20.0
- ZIP sha256 `6c5b1e920f36be1fc29ecbd7c8ccf88de3904dfb32c9e9cbb4a53bdb16766ce2`. 신규 `cloth_wrinkle.py`(GN 그룹 `MCH_ClothWrinkle` v4: Subdivide → 접평면 좌표(Direction/Scale/Seed) → Padding/Denim/Leather → Index Switch → 테두리 마스크(`mch_edge_dist`) → Normal*(h+Lift); 모디파이어 `MCH_Wrinkle` + Solidify `MCH_WrinkleShell`; `perform_wrinkle`, `dense_mesh`, HUD). 도구 `WRINKLE`(`mecha.cloth_wrinkle`).
- `panel_gen`: rims(`rim_n/e/s/w`, `rim_random/seed/count`, `rim_profile`, `rim_slope`, `rim_width`, `rim_height`), facet `facet_width/offset`, crease 높이 = depth × frad × 0.1, 노멀 스무딩 + `updir`(tall blend).

## 0.19.3
- ZIP sha256 `2b6db8b31077fbcde548ec18bdb6106961fecc272f2112ac69c8966f5b9cc72e`. `bottom_bar.active_button_pos`: 왼쪽 중간(높이 60%), `_btn_factor`(toolbar_scale).
- 신규 `lasso_sketch.py`: KEY `mch_lasso_sketch`(mode/frame/proj/items), `add`, `screen_loops`, `commit`(CUT/SPLIT → `perform_closed`, PLATE → `perform_plate`), 키맵 `KEYMAP`, `mch.sketch_toggle`
  (`is_on`/`set_on`: `mch_brush.sketch_first` + `mch_base.sketch` 동기). `cut_engine._execute_closed`가 sketch 모드면 `lasso_sketch.add`.

## 0.19.2
- ZIP sha256 `c3faa3445145ecec90b3f18bf56d405e36a8582e1802e0f1bdbc943ed723ecdd`. `panel_gen`: `facet_lines`/`line_dist`/`facet_value`(bisect + `mch_crease` 엣지 → `face_extract.rebuild`에서 sharp), 로컬 폭 `room()` + `ROOM_SHARE`(0.3) 밴드 축소,
  reflex 코너 miter 1, `_project_factory`가 먼 반대면 히트 대신 nearest. `face_extract` 속성 `facet_*`. `armor_plate`: `BAKED_KEY`, `plate_hp_data`, `dense_plate_mesh`, `mch.plate_lines`,
  miss 점은 가까운 히트 깊이. `highpoly.make_highpoly(..., plate_detail)`. `bottom_bar`: `PIE_SHARED`, `MCH_GGT_tool_active`/`mch.tool_active`, `MCH_GGT_object_tidy`/`mch.object_tidy`.
  `primitive_hud.anchored`/`release_anchor`(팝업 고정, mirror/plate/random/prim). `ui_tool_settings.draw_edge_finish`.

## 0.19.1
- ZIP sha256 `bdcda494dc8c844fd7bc690530af543475b9c57af841207903e4e221b8c7587c`. 신규 `highpoly.py`: `support_width`, `estimate_faces`, `safe_level`, `make_highpoly`(복사본 키 `mch_highpoly_src`), ops `mch.make_highpoly`(REGISTER/UNDO, 속성 = F9 패널) / `mch.highpoly_view`,
  `VIEW3D_MT_object_context_menu` append, `MCH_PT_highpoly`. `bottom_bar`의 side tool list(`side_tools`/`side_layout`/`MCH_GGT_side_toolbar`)와 pref `side_toolbar` 삭제.

## 0.19.0
- ZIP sha256 `1aba16c1a96374eb16b879fd66af7f2e888193ae7744649640178fcc29a75fb9`. `armor_plate`: `plate_meshes`, `SRC_KEY`(`mch_plate_src` JSON: loops/proj/spacing/size), `FrozenProjector`, `freeze_projector`/`thaw_projector`,
  `plate_source`, `pending_plate`, `rebuild_plate`, `apply_plate`; ops `mch.plate_cycle`/`plate_apply`/`plate_cancel`; `MCH_GT_plate_slider`, `MCH_GGT_plate_hud`.
  `spacing` 기본 120(update → 라이브 재생성). `bottom_bar.BAR_TOOLS` + PLATE, `tool_state.QUICK_TOOLS` + PLATE.

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
