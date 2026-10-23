# RETURN HANDOFF → ChatGPT — Mecha Lab 0.24.27 (Claude Code, 2026-10-14)

## 0.24.27
- ZIP sha256 `33754e94ef1ef6536afaf5d8b1a16260d00dae352cf353645cd2c32c36d37cee`. `workspace_ui.MCH_OT_hotkey.invoke`: `only_empty`의 PASS_THROUGH는 이벤트가 수식키 없는 S일 때만(바꾼 키는 항상 실행).

## 0.24.26
- ZIP sha256 `7e8e6301056efde94949aa767ea78921282cd1ab570bf5f183d9b6bc5847287a`. `mech_ridge.simplify_closed`: 점 ≤ CLICKED_MAX(48) 이고 엣지 중앙값 ≥ CLICKED_EDGE(10 px)면 찍은 다각형 = DP 없이 중복 · 1° 미만만 제거. `roof_bmesh`: `is_convex`면 프리즘을 경사 변 평면들로 `_clip`(정확, 불린 없음) + remove_doubles / dissolve_degenerate, 열린 엣지 있으면 불린 경로; 오목 = `_boolean_difference_each`(커터마다 모디파이어, MANIFOLD → 결과가 안 닫히면 EXACT use_self). `_tidy_roof` · `grid_cut`의 정리 단계는 `cg._safe_step`. `_finish_safe`: 베벨이 찢으면 폭 ×0.5 / ×0.25, 그래도 안 되면 생략 + Object['mch_mridge_notes'].
- `plate_detail.build_mesh(p, name)`(rebuild에서 분리), `engrave(context, loops, projector, tool)`: 현재 설정으로 디테일 메쉬 → 타깃 BVH 최근접점 기준 표면 반사 → CUTTER_ATTR → `boolean_result` DIFFERENCE → `cg.flat_cut_faces` → `commit_mesh`. `live_subtract.perform(..., tool)` DETAIL에서 살아있는 디테일 없으면 engrave; `lasso_sketch.commit(alt)` DETAIL*도. `live_subtract.apply`: 전체 smooth 강제 삭제 → `cg.flat_cut_faces`(커터 면 flat + 경계 sharp_edge).

## 0.24.25
- ZIP sha256 `925cdaf045ed6813bdf434a1c057885123b848773abd7b4fc672ca6ca6448fc6`. `mech_ridge`: `ends` / `swap_axis` → `pattern`(PATTERN_ITEMS) + `turn` + `custom`('1' / '0' 문자열). `sloped_edges(poly, pattern, turn, custom)` → 나머지 변 = ends(커터 없음 + 이웃 이등분선 생략, 0.24.24와 같음). LONG = `end_edges(swap=turn 홀수)`. 첫 외곽의 마스크를 Object['mch_mridge_mask']에 저장 → 패널 엣지 버튼 `mch.mridge_edge_toggle`(Custom으로 전환, 마지막 경사 변은 못 끔), `mch.mridge_turn`. 프리즘 높이 = 능선 최고 × 1.5 + 5(Shed가 전체 폭으로 올라가도 안 잘림).

## 0.24.24
- ZIP sha256 `46522f02ccf80b3bb8872c0c9f053fbdb358a6a32b4f2e0f64698824dbac31a5`. 새 `mech_ridge.py`(Armor Plate PRESETS 'MRIDGE' → `perform_plate`가 `mech_ridge.perform`로). 픽셀 공간(z도 픽셀): `simplify_closed`(DP) → `ccw` → 외곽 프리즘 − 변마다 볼록 커터(`wedge_planes`: 변 안쪽, 양 모서리 이등분선 사이(0.5 px 겹침), 경사면 위) 합집합을 Exact Boolean 한 번(use_self) = 정확한 straight-skeleton 지붕(볼록 / 오목 모두). remove_doubles · dissolve_limit → `mark_edges`(1 능선, 2 바깥 위 엣지) → `_finish` 베벨(둥근 베벨 면은 face layer) → `mark_creases`(평면이라 각이 있는 엣지 = 진짜 주름 → sharp, 둥근 베벨 내부 제외) → `grid_cut` + dissolve_degenerate → `_lay_on_surface`(뷰 레이로 표면, 평활 노멀 × 높이·k, k = 월드/픽셀 중앙값). Scene / Object `mch_mridge`, `mch.mridge_apply`(Enter 목록).
- `core_geometry.tidy_rim`: dissolve_degenerate 후 `_snap_rim`(정리 전 커터 벽 평면들로 테두리 점 교대 투영, 폭 이내 이동만). `crisp_shading`(베벨 면 smooth = 둥근 베벨일 때, 경계 엣지 sharp, 커터 면 flat), `drop_custom_normals`('custom_normal' 속성 제거). `finish_new_edges(..., crisp=True)`, `mch_cut.finish_crisp`.

## 0.24.23
- ZIP sha256 `e11cb27d71cfb2387ab79ddb2679732d82346b7f342e77bba9399d1128a9bd20`. `bottom_bar.apply_all_modifiers(context, ob)`: `_unlive` 후 show_viewport인 모디파이어를 순서대로 `safe_apply`(실패 시 중단, (적용 이름, 오류) 반환). `MCH_OT_apply_modifiers_pick`: invoke = 모달(스포이트 커서, 상태줄), LMB = `workspace_ui.object_under_mouse` → 선택 + 적용, Esc / RMB 끝, 나머지 PASS_THROUGH; execute = 선택한 메쉬. `MCH_GGT_object_tidy`에 `TOP_TIDY` 버튼(툴 버튼 위 62 px) + 라벨.
- `creature_plate.engrave(context, loops, projector)`: `_parts`(캐시 없는 점 세트) → `build_mesh(..., carve=True)`(top = 표면 − 법선·(벽 + 모양·높이), bottom = 표면 + 법선·sink) → `boolean_result` DIFFERENCE → `commit_mesh`. `live_subtract.perform`이 CPLATE에서 살아있는 플레이트를 못 찾으면 engrave, `lasso_sketch.commit(alt=True)` CPLATE도 `live_subtract.perform`.
- `base_mesh.perform_base(cutter=True)` / `sketch_commit(cutter=True)`: Creature 프로파일이면 `_perform_cutter`(PUFF_BUILT 크리쳐 = 뒤집지 않은 원래 덩어리를 그대로 cutter로), 아니면 기존 `cut_like_cut_tool`. Dome / Cushion은 여전히 거절.
- `core_geometry.finish_new_edges`: 폭이 clamp 한계보다 크면 `tidy_rim(bm.copy(), width)` → 열린 엣지가 늘지 않고 한계가 커졌을 때만 사용. `tidy_rim`: 커터 면끼리 dissolve_limit(0.5°), 테두리 엣지(0.5×폭) / 두 테두리 점 잇는 엣지(2×폭) / 테두리에서 나가는 엣지(1×폭) 별로 dissolve_degenerate, 단계마다 `_safe_step`(열린 엣지 늘면 복사본으로 되돌림, 안 되면 4조각으로 재시도).
- `workspace_ui`: `MCH_OT_line_width_key`(Object Mode 애드온 키맵 [ / ], poll = 네이티브 툴이 `mecha.*`이고 Screw Stamp / Primitive 아님 → 아니면 Blender의 select_hierarchy로 넘어감), `MCH_OT_sculpt_back`(Sculpt 키맵 G → `mch.select_move`).
- `cut_engine`: 0.24.21 `_sketch_wanted` / `_stroke_to_lasso` 삭제(Sketch 중 프리드로우는 놓으면 `lasso_sketch.add` / `sketch_add`).

## 0.24.22
- ZIP sha256 `3c0998153d3e1e9a093264c78fd483b892f0ba6144901f79364c4e54eff5f46c`. 새 `live_subtract.py`: Alt 외곽(화면 루프 + 고정 뷰)을 오브젝트 `mch_subtract`(JSON)에 저장, `apply`가 `creature_plate.rebuild` / `plate_detail.rebuild` 끝에서 매번 절단 프리즘(`build_cutter_mesh`, THROUGH 깊이) + EXACT Boolean DIFFERENCE로 다시 빼냄(스무스 셰이딩 유지). `pick` = 외곽 아래 레이캐스트로 그 툴의 살아있는 플레이트. `cut_engine._execute_closed`: CPLATE / DETAIL* + `inverted()`이면 `live_subtract.perform`. Apply는 기록 삭제.
- `tool_state`: `line_taper_on`(버튼) + `line_taper`(양, 기본 0.5), `lasso_line.line_loop`는 켜졌을 때만 Taper.

## 0.24.21
- ZIP sha256 `ae6f1687c9e7acb73ff4f96b42ddcc2ce9dce9ad57cd3f0ec55137c7ca0953d7`. `bridge_patch.drape(n, edges, front, depth, passes)`: 그래프 라플라시안 평활 + `min(front, depth)` 반복(앞에서 본 천 덮기), `_build_whole`에서 `crease * 30 * res`회. 표면 위 판정 `on`(깊이 차 / 두께)으로만 Sink.
- `cut_engine`: STROKE 놓을 때 `_sketch_wanted`(lasso_sketch.enabled 또는 Base / Creature Base의 sketch)면 `_stroke_to_lasso` → shape LASSO, stage POINTS(단순화 점), Enter = `_confirm`.
- `base_mesh.init_creature_defaults`(CBASE_START resolution 15, scene['mch_cbase_init']로 한 번): load_post, 등록 직후 타이머, CBASE 활성화 시. `creature_plate` resolution 기본 15.
- `lasso_line.band(..., taper, pressure)`: 점마다 폭(`taper_factor`, `pressure_profile`), 끝 캡도 그 폭. `cut_engine`: event.pressure를 Free Draw 샘플마다 저장, [ / ] = `step_line_width`(modal + 툴 키맵 `mch.line_width_step`). `core_geometry.overlap_edges / overlap_hint` → `perform_closed`가 실패 메시지에 원인 추가 / 성공 시 경고.
- `workspace_ui`: `SCULPT_BRUSHES`, `draw_sculpt_grid`(MCH_PT_tool_list 아래), `MCH_OT_sculpt_brush`(sculpt_target → mode_set SCULPT → brush.asset_activate ESSENTIALS). Object 복귀는 기존 mch.select_move / activate_mecha_tool.

## 0.24.20
- ZIP sha256 `4cb9cff994f6947903c03ea04883ac55b81d1fa2ed44905b69c1676608e3badc`. 새 모듈: `creature_plate`, `belt_maker`, `creature_spike`, `creature_scales`, `scale_brush`, `bridge_patch`, `flower_plate`, `surface_curve`(툴 id CBASE 34, CPLATE 35, BELT 36, SPIKE 37, SCALES 38, FLOWER 39, SCURVE 40, SBRUSH 41, BRIDGE 42). 공통 패턴: Object custom prop SRC_KEY(JSON: loops / path px + `armor_plate.freeze_projector`, target, stamp) + Scene / Object PropertyGroup(LIVE_KEYS, `_update` → rebuild + scene 기본값 갱신) + 모듈 `_CACHE` + Apply 연산자(SRC_KEY 삭제).
- `base_mesh.profile_field`: Chaikin 외곽 + `_dome_points`(rings / rim 인자로 해상도 조절) + 삼각분할, 높이 Puff(코탄젠트 라플라시안 Poisson + CG) / Ridge / Pillow / Scale / Cushion. Bend: `bend_coords`(Band 원호, Angle = `fold_round`: 마이터 접기 + 바깥 / 안쪽 라운드 `_round_offset`), `_bend`가 평평한 캡은 bisect로 잘라서 휨.
- `bridge_patch`: 라쏘 점 레이캐스트(깊이, 정면도, 메쉬 뒷면까지 = middle) → `soft_fill`(가중 하모닉 / 바이하모닉 CG) 표면, `puff_heights`로 폭 방향 둥글기, `local_max`; 기본 `_build_whole`(라쏘 전체 솔리드), Trim to Gap = 기존 틈 + 묻힌 테두리.
- `scale_brush.pack`: 지터 육각 점 → Lloyd 2회 → 보로노이 셀(반평면 클리핑) 안에 프리셋을 최대 크기로(`_fit_scale` 정확, 3개 프리셋 × 6 회전 × 5 위치 중 최대).
- `cut_engine`: 라인 모드면 LASSO / CURVE_LASSO를 STROKE로(누르고 끌고 떼면 적용), shape-changed 검사는 `brush_shape`와 비교. `lasso_line.MODES` + Plate Detail 1 / 2 / 3.
- `workspace_ui`: `mch.hotkey` action REMESH(키 NONE으로 등록, Remesh 패널 Run Key / Hotkeys 상자). Mirror 클릭 적용(0.24.19)은 되돌림.

## 0.24.19
- ZIP sha256 `6e441cca809dbce5fd9d8d4f16966a9d8aeff594fd0fca5f5a5b9cde273c0bbf`. `mirror_tools.MirrorLeanLogic.handle`: LEFTMOUSE(Shift 없이) / RIGHTMOUSE → `pick_side(scene, ±1)`(제스처 중심에서 화면 ±200 px 지점으로 `lean_pick`, 잠긴 축 유지, 가리킨 피벗이 있으면 그대로) 후 'BAKE'. `LeanModal.modal`: 'BAKE'는 keep_live와 상관없이 finish_apply(인스턴스는 finish_live와 같음). RMB 취소 제거(Esc만), 상태줄 / 설명 갱신.

## 0.24.18
- ZIP sha256 `982e1941b3a622a6698265fd3c280c3687788acad0f6f61b57c0b4537514b921`. `cut_engine.StrokeLogic`: `_begin` / LEFTMOUSE PRESS에서 `free_drag`를 더 이상 켜지 않음(LASSO 드래그 연속 점 제거, 코드 경로는 남김). `tool_state.SHAPES` LASSO 설명 갱신. `workspace_ui.enter_apply_target`: box_hide_apply는 선택에 숨김 메쉬가 없어도 현재 툴이 HIDE면 뷰 레이어의 숨김 메쉬로 대상. `WindowManager.mch_show_custom_shapes`(기본 False, 모양 팝업의 접기 줄), `box_hide.split_off(context, ob)`(사본에서 Box Hide 모디파이어 제거 → 볼륨과 INTERSECT boolean_result → 이름_Hidden, 원본은 set_cap(True) 후 apply) + `MCH_OT_box_hide_split`(패널 버튼). 아이콘 `icons/line_curve.png` = 원을 촘촘히 찍은 굵은 S선(PIL 굵은 선 이음새 실금 방지). `make_icons_v02417.lasso_key`(키캡용, 애드온에는 안 넣음).

## 0.24.17
- ZIP sha256 `07d4733bd536ff4e2ebc2565e5648e5725195a5398b94344db164620df5c6291`. `workspace_ui.MCH_OT_hotkey`: action SHAPES(L, `wm.call_panel('MCH_PT_shape_popup')`) / TOOL(+ `tool` enum, `activate_mecha_tool`). register_keymaps: L + `tool_key_ids()`마다 type 'NONE' 항목(TOOL_ACTIONS CUT / SPLIT / PLATE 제외), 끝에 `load_hotkeys(items)`. `hotkey_id(item)` = (idname, action, tool), `save_hotkeys` / `_hotkeys_path`(config/mecha_lab/hotkeys.json), `MCH_OT_hotkeys_save` / `MCH_OT_hotkeys_reset`(파일 삭제 + 키맵 재등록). draw_hotkey_editor에 "Tools (left list)". `curve_tube`: 모드 LINE(`TUBE_MODES`, `LINE_MODES` = LINE + 0.24.10 REPEAT_SAME), build에서 샘플 반지름 1 / 테이퍼 1로 tube_mesh, handle_world / point_radius / rad 기즈모가 LINE에서 꺼짐, `draw_line` = 튜브 설정, Line Curve 툴은 mode='LINE'. 아이콘 stem: HIDE hide, PLATE armor, DETAIL detail1, DETAIL2 detail2, DETAIL3 detail3, SCREW screw, WRINKLE cloth, TUBE tube, TUBE_SAME line_curve.

## 0.24.16
- ZIP sha256 `a1b3b0dd64d24375126a17ffad0ea4962c805f8e0d4f30757a6d999e7d7eba87`. `cloth_sim`: Object 속성 `mch_pcloth_puff`(0 ~ 5, 기본 1, _slider_update = 표시만), `puff_pressure(base, puff)`(base ≥ 1이면 base × puff, 아니면 puff ≥ 1에서 base + (puff - 1) × 3), `sim_values(..., puff)`는 puff ≠ 1일 때만 pressure 덮어씀(1이면 프리셋 그대로), `redo` / `set_sliders`가 puff를 넘기고 새 천에 유지.

## 0.24.15
- ZIP sha256 `827eb58468eabb786725342811e274859dbe69d07b030cc8713853b89ffb348f`. `mirror_tools.LeanModal`(invoke / _status / _end / modal 믹스인): `MCH_OT_mirror_lean(MirrorLeanLogic, LeanModal, Operator)`, `MCH_OT_instance_mirror_lean(InstanceMirrorLogic, LeanModal, Operator)` - 등록된 연산자 클래스를 상속하면 Blender가 부모의 파이썬 클래스를 잃음(0.24.13 회귀). `pointed_object(context, projector, xy, skip)`(scene.ray_cast, 선택 / 피벗 / 리그 제외), `world_center(ob, matrix)`, `MirrorLeanLogic.point_at`(on_move 먼저: 맞으면 pivot_center = 그 오브젝트 중심, 축 = 선택 중심→그것의 최대 성분, flips[i] = 그쪽이 +, setup_mirror(..., center=pivot_center)), InstanceMirrorLogic도 pivot_center를 기준면 원점으로. `mirror_targets_kind(context)`('MESH' / 'INSTANCE' / None), `start_mirror(context, keep_live, report)`: MESH → mirror_lean(keep_live), INSTANCE → instance_mirror_lean, None → 경고(선택된 타입 표시). `workspace_ui.MCH_OT_hotkey` MIRROR와 `bottom_bar.MCH_OT_object_tidy` SYMMETRY / MIRROR가 이것만 호출.

## 0.24.13
- ZIP sha256 `2e99a81d7cddf0273708fbc272f7b501d5e6231c936f223c26196c0e88fbed8d`. `mirror_tools`: `is_collection_instance`, `instance_twins` / `remove_instance_twins` / `add_instance_twin`(반사 행렬을 matrix_world로 가진 숨긴 Empty `INSTANCE_AXIS` 아래에 같은 콜렉션 인스턴스 `INSTANCE_TWIN`, COPY_TRANSFORMS target=원본 WORLD → owner LOCAL), `plane_reflections(origin, axes, enabled)`, `InstanceMirrorLogic(MirrorLeanLogic)`(start / frame / _apply_live / restore_all / describe), `MCH_OT_instance_mirror_lean`(MCH_OT_mirror_lean 상속). `workspace_ui.MCH_OT_hotkey` MIRROR: 메쉬 선택이 없고 콜렉션 인스턴스가 선택돼 있으면 instance_mirror_lean.

## 0.24.12
- ZIP sha256 `4cee1206061bc8027c9d0f197441ec14c4dc67a9fc8f4a8abdd70ab0034c9e9c`. `__init__`: `fuse_setup(context, target, source)`(예전 operator 본문, 실패 시 정리 후 raise), `fuse_confirm(context, target)`(에러 문자열 / None), `fuse_confirm_live(context, obs)`(라이브 미리보기 확정, 선택 / 활성 복원), `_clear_fuse_seam(ob)`(`_FUSE_EDGE_ATTRIBUTE` 삭제: setup 전 대상 / 소스, confirm 후 대상). `fuse_build_group(source, solver)`: 두 메쉬가 닫혀 있으면 MANIFOLD, 이음새 0이면 EXACT로 다시. `MCH_OT_fuse_create`: 2개 이상, 먼저 fuse_confirm_live, 3개 이상은 거리순으로 setup + confirm(진전 없을 때까지 반복, 이름으로 추적). `cut_engine._confirm_fuse`를 perform_closed / perform_line 앞에서 호출.

## 0.24.11
- ZIP sha256 `d6a19ae92a64f7093a2d7aecf1160481066c94762ce12ebdf60b8b5b1ddd4d33`. `box_hide._sharers(vol, skip)` / `_detach_sharers(context, vol, owner)`: perform에서 대상의 볼륨을 바꾸기 전에 같은 볼륨을 가리키는 다른 메쉬마다 볼륨 복사본(오브젝트 + 메쉬)을 만들어 모디파이어 Volume 입력을 바꿈, `vol[VOL_KEY] = owner.name`. show_all / apply는 `_sharers`가 비었을 때만 볼륨 삭제. `lasso_sketch.commit` HIDE: `mch_cut.targets`가 SELECTED면 auto_targets ∩ 선택, ACTIVE면 ∩ 활성.

## 0.24.10
- ZIP sha256 `f94b74c3adf34f1c10149fb24573923d3e20b991840b8d8c0288eee3afc5dea5`. 새 툴 id `DETAIL3`(enum 32, 네이티브 `mecha.plate_detail3`, SHAPE_TOOLS / lasso_sketch.MODES / cut_engine 모드 집합에 추가)와 `TUBE_SAME` = Line Curve(enum 33, 네이티브 없음). `plate_detail`: kind `FLAT`, `KINDS['DETAIL3']`, `TOOL_OF_KIND`, 속성 `flat_h`(LENGTHS, 기본 FLAT_FRAC 0.02), rebuild FLAT = `build_detail(region, [], flat_h, lift=...)`(층 없음 → 판 하나 + 벽). `curve_tube`: 모드 `REPEAT_SAME`(`REPEAT_MODES`), repeat_mesh에서 sc = size × radius / 원본 크기(점 반지름 / 테이퍼 무시), `new_tube(..., mode)`, `tube_draw.mode`, `start_draw(..., mode)`; `activate_mecha_tool('TUBE_SAME')` → 활성 오브젝트가 REPEAT_SAME 튜브면 편집, 아니면 새로. `tool_owns(context, ob)`: Line Curve 오브젝트(REPEAT_SAME)는 TUBE_SAME 툴에서만, 나머지 튜브는 TUBE 툴에서만 HUD / 패널. `draw_line` = Line Curve 패널. Mesh Curve의 Mode 토글은 TUBE / REPEAT만, Line Curve는 안 바뀜. 기본값(mch_tube_defaults.mode)에는 REPEAT_SAME 없음.

## 0.24.9
- ZIP sha256 `f8262d1b2c7b421f474ddf8a3143dc59f714f73a6c354bd0016ce56fae07b96d`. `core_geometry.boolean_result`가 `_boolean_result`를 감쌈: "does not intersect"이고 대상에 켜진 MIRROR 모디파이어가 있으면 `mirror_reflections(target)`(축 조합별 월드 반사 행렬, mirror_object 있으면 그 기준) → `_cutter_with_reflections`로 커터 + 반사 복사본(면 뒤집음) 메쉬를 잠시 커터에 끼워 다시 실행, 끝나면 원래 메쉬 복원 / 임시 메쉬 삭제.

## 0.24.8
- ZIP sha256 `83aadd89d98fa3014d37de1106a660b3c07ce3927e48508f31bbb36fddec3fc2`. `workspace_ui.MCH_OT_hotkey`: action에 PLATE / MIRROR 추가, `only_empty`(선택이 있으면 PASS_THROUGH → Blender Scale), invoke에서 MIRROR = `mch.mirror_lean(keep_live=True)`. Object Mode 키맵: Alt+X MIRROR, S SPLIT(only_empty), Alt+A PLATE. `HOTKEY_LABELS`로 키 편집 목록 이름.

## 0.24.7
- ZIP sha256 `5f8b31097d584013b268ace1eb3aa575efae3626dd5b3dbcb3e7e804a170564f`. `cut_presets`: `_scan()`(os.scandir, mtime이 바뀐 JSON만 파싱 → `_INDEX[stem] = (mtime, name, source)`), `preset_items`는 (scan, preview collection id) 키가 같으면 캐시 반환, `preset_icon`은 `_THUMBS`에 경로 기억, `_small_thumb`은 120 KB 넘는 원본에 `<stem>_thumb.png`(192 px) 한 번 생성, `import_png`는 `save_thumbnail`로 192 px PNG만 저장, 일괄 불러오기는 refresh=False 후 `_refresh_previews()` 한 번. `workspace_ui.purge_stale_keymap_items()`(register에서 툴 등록 전): addon 키컨피그의 `3D View Tool: Object, Mecha *` 키맵 삭제(register_tool은 기존 키맵을 다시 만들지 않음) + `STALE_KEYMAP_IDS`(`mch.stamp_scale`) 항목 삭제.

## 0.24.6
- ZIP sha256 `f998927f74222572dd0ff0419d5806ecbf782dcca444ada21b6f9ad70b1f44ad`. `cut_presets.MCH_OT_import_cut_png`: `files` (OperatorFileListElement) + `directory`, 파일마다 import_png, mode AUTO(알파 최소 < 0.999면 ALPHA). `MCH_OT_stamp_scale`와 휠 키맵 제거. test_v02319 시간 검사는 머신 속도에 민감(0.24.4 코드로도 0.52 ~ 0.61초).

## 0.24.5
- ZIP sha256 `b67a52f9c48ff0a725229f0335d2696de3e215c189e98c437d91ef8fc5a64ed1`. `workspace_ui.ENTER_APPLY` + `enter_apply_target` + `MCH_OT_enter_apply`(Object Mode 키맵 RET / NUMPAD_ENTER, 도구 키맵의 스케치 Enter가 먼저). `cut_engine.object_under` / `double_click_leave`(exit_tool + mch.select_move), 모달 POINTS에서 점 ≤ 1일 때 DOUBLE_CLICK / 빠른 재클릭, invoke에 DOUBLE_CLICK이 오면 나가기. `screw_stamp`: 키맵 DOUBLE_CLICK(leave) 먼저, `_LAST`로 첫 클릭 나사 되돌림. `cut_presets`: filter_glob png/jpg/jpeg, 알파 없으면 LUMINANCE, 비-PNG는 Blender로 PNG 저장. `MCH_OT_stamp_scale`(휠, CUSTOM일 때만). `base_mesh._rebuild_update`가 CARRY_KEYS를 Scene.mch_base로 복사. `base_mesh.cut_like_cut_tool` = auto_targets + perform_closed('CUT'), sketch_commit(cutter)는 현재 뷰 projector로 화면 루프 만들어 같은 경로(뷰 없으면 옛 경로).

## 0.24.4
- ZIP sha256 `30cbb736ab1ec444ad5c2af777e22af560757a0de6f9110a6723c9c86503af15`. `cloth_sim._slider_update`는 `mch_pcloth_dirty`만 표시, `MCH_OT_panel_cloth_refresh` = redo(현재 값). `plate_detail`: `wall_profile(height, wall_angle, foot)` → (거리, 높이) 목록(원호 6단 + 벽), `build_rise`는 레벨 목록으로 자르고 np.interp로 높이(ROUND/CHAMFER도 같은 경로), 속성 wall_angle / foot(LENGTHS에 foot, fractions에 wall_angle), `RISE_PRESETS` + `MCH_OT_pdetail_rise_preset`(FOOT_FRAC 0.6).

## 0.24.3
- ZIP sha256 `4d6158f3bc875127692f8b87e805932ed3f928b089eb255bdacecdfa5f63111a`. `curve_tube._on_depsgraph`: Repeat 커브가 없으면 즉시 리턴, 있으면 `_source_sig`(src.data 이름, matrix_world, 평가된 bound_box, 평가 메쉬 점/면 수 + |co| 합)를 `_SIGS`와 비교, `rebuild` 끝에 시그니처 기록. `loft_surface._on_depsgraph`: 라이브 로프트 없으면 리턴, `_curve_sig`(행렬 + 스플라인 점/핸들/반지름/틸트) 비교, `safe_rebuild`에서 기록. 두 모듈 undo_post / redo_post → `_UNDO_QUIET` 0.3초. `cut_engine`: HIDE 스케치에서 스케치 없을 때 Alt는 추가, `auto_targets`에서 None 건너뜀. `lasso_sketch` 안내: HIDE는 Enter: hide, Alt+Enter: show again.

## 0.24.2
- ZIP sha256 `ed26f08ab74b146d4acbc855b987ec8d04a719283e873fac47e30b4ea82eb78a`. `plate_detail`: SPACING_PX 20, 거리 = float 레이어 `d` 한 번(`_field_layer`), `cut_iso(bm, key_layer, level, eps, carry)`가 새 정점에 선형 보간(새 레이어가 BMVert를 재할당하므로 외곽선은 좌표/노말로 미리 복사), 나사 원도 레이어. 경계 옆면 = 아래 띠 높이 정점 포함(`mids`). `_queue` 디바운스 0.15초(타이머 재등록), undo_pre / redo_pre에서 대기 비움. `cloth_sim`: 0.23.25 파일 + 슬라이더(Tension 1이면 tension_stiffness 손대지 않음, slack ≤ 2.5배), Scene.mch_pcloth_fast(foreach_get/set 들어올림), undo_pre에서 타이머 해제.

## 0.24.1
- ZIP sha256 `9201b09a7ab74818472980db0561aa4c3fccdde51e3fe5d539243ce57b5f9521`. `lasso_sketch.MODES` + DETAIL / DETAIL2 / HIDE, commit 분기(plate_detail.perform, box_hide.perform + auto_targets), 키맵 `lasso_sketch_modes()`, 헤더 Sketch 버튼 enabled = MODES 또는 BASE. `plate_detail`: `lift`(LENGTHS에 포함, 위/아래 모두 이동), RISE_PROFILES ROUND(smootherstep) / CHAMFER(직선) / DOME / FOOT, `build_rise`는 등거리선 링(RISE_SEGMENTS 8, Chamfer 1)으로 자르고 링 안은 선형 높이, set_sharp_from_angle 60°. `simplify` = dissolve_limit 0.6°, 휜 면은 `surface_curvature`(영역 패치 엣지의 노말 각/길이 90 %)로 칸 크기 g = √(8·0.0012·size/κ) 격자 seam으로 막고 합친 뒤 seam 해제, 일직선 2가 정점 제거.

## 0.24.0
- ZIP sha256 `d6fa728a865c38c3a7a8c1b8965faccb92fe5314c371d3aca70ba24024191f7c`. 새 `plate_detail.py`: 영역 = armor_plate.plate_meshes(SPACING_PX 7) 삼각형 패치 → 외곽선까지 거리(numpy 선분 거리) → `cut_iso`(마칭 트라이앵글로 등거리선을 따라 정확히 자름, 나사 원도 같은 방식) → 면마다 높이(띠) → 정점 키 (v, h, sector)로 위/아래/벽 생성(띠 경계가 정점에서 꼬이는 곳은 낮은 띠만 정점 분리 → 모든 엣지 2면). 나사 = 볼록 모서리 이등분선 위 w1/2 지점. `build_rise` = smoothstep 등 프로파일 × Height, 벽 없음. Object.mch_pdetail(라이브, 0.05초 타이머로 모아서 rebuild), Scene.mch_pdetail(분수 JSON). 도구 DETAIL / DETAIL2(SHAPE_TOOLS, cut_engine 모드). 새 `screw_stamp.py`: revolve 프로파일(Dome / Post / Socket), Cross = CDT 링 + 슬롯 벽/바닥; 도구 SCREW(키맵 클릭 / Alt+클릭 / Esc), Object.mch_screw 라이브, Join = bmesh로 부모 메쉬에 합침. `cloth_sim`: Object.mch_pcloth_tension / _gravity(업데이트 → 0.4초 타이머 → redo), `sim_values`(shrink / tension, tension_stiffness 15×t).

## 0.23.27
- ZIP sha256 `4a414b288d585b594f853e0b7e35f7f5484df0276ddf4bfa0d4d6b84cf8512ad`. `workspace_ui.MCH_PT_lasso`(bl_order 1, poll = mch_brush 있으면 항상) → `ui_tool_settings.draw_shape_options(layout, context, effective_tool)`. draw_cut / draw_mask / draw_base / draw_hide 안의 호출 제거. 헤더 모양 줄 `enabled = tool in SHAPE_TOOLS` 제거. `cut_engine.ALT_RED`, `stroke_color(mode, inverted)` = inverted면 ALT_RED(SPLIT 포함), `_COLORS`에서 *_INV 제거. 옛 검사 test_v0141 / v02317 색 기대치 수정.

## 0.23.26
- ZIP sha256 `e3ea3d9bb5298b6b806988eeeab6027f3bc9df0d1a9515dde75a6e8c37d4ed72`. 새 `fold_patch.py`: 패턴(획 리스트, Catmull-Rom) → `height_map`(획마다 최근접 거리 하나, 스무스 맥스) → float 이미지 `MCH_FoldPatch_<핸들>`(RES 512). GN 그룹 `MCH_FoldPatch`: Object Info(RELATIVE) 역행렬 → 핸들 공간 → Wrap(s = R·atan2(y, z+R)) / Taper / Image Texture(Cubic, Clip) × Fade × 근처 → Normal × Depth, Mirror X = 미러 위치로 한 번 더. 핸들 Object.mch_fold(PropertyGroup, 업데이트 → push). load_post에서 이미지 다시 만듦. 패널 MCH_PT_fold_patch(bl_order 4).

## 0.23.25
- ZIP sha256 `baa0c9a383320fda16771485a1a32ff206f3541edccdcd3ce67705111990c6cb`. `MCH_GGT_wrinkle_hud` = 0.23.22(커밋 1d26196) 그대로(_ensure_sliders / refresh 제거 - draw_prepare에서 기즈모를 만들려던 것이 버튼 배치를 깨뜨린 것으로 봄, 실제 Blender에서 확인은 못 함). HUD_SLIDERS = False, 사이드바 mch_cloth_scale 유지.

## 0.23.24
- ZIP sha256 `2478d031dfe78ad37a70bed8b54cd6198b3241635df0514e6ce98d3146b020b6`. `cloth_wrinkle.HUD_SLIDERS = False` → `slider_keys` = () (슬라이더 코드는 남아 있음, True로 되돌릴 수 있음). `tool_state.sidebar_select(context)` = bottom_bar.in_select: Primitive Shapes / Detail Stamp / High Poly / Icon Size / Tools / Workspace 패널 poll에 추가. Robot(BASE), Shell(PLATE), Tube(TUBE) 패널 poll에 hud_for.

## 0.23.23
- ZIP sha256 `4f1008d348a16c1a8236fe3c0fe1f3dccd5e7aa76c6b9cc6dd261172fa4ec024`. `MCH_GGT_wrinkle_hud._ensure_sliders`(setup / refresh / draw_prepare에서 빠진 슬라이더 기즈모 생성). `Object.mch_cloth_scale`(IntProperty %, update → `set_overall_scale`), HUD 세터도 `set_overall_scale`, 필드 동기화는 `_SYNC` 가드(Blender 5는 애드온 속성과 커스텀 속성이 따로라 ob[...]로는 안 됨).

## 0.23.22
- ZIP sha256 `dd59e6b0a7823258f0e14f74544371b1c1806d9454f99fa16f7789ebbbe39b24`. 새 `lowpoly.py`: `build_mesh` = REMESH(VOXEL, 크기 / Detail) → DECIMATE COLLAPSE(Faces × 3) → `flatten_sides`(BFS로 면 묶기(각도), 작은 묶음 병합(면적 0.3 %), 경계 정리 8회, 점 = 최소제곱(평면들 + keep 0.001), 묶음 내부 엣지 dissolve → 엔곤, 일직선 2가 점 제거) → DECIMATE DISSOLVE(Flat Merge). 라이브 `MCH_LP_Bevel`(ANGLE) + `MCH_LP_Normals`. Scene `mch_lowpoly`, 오브젝트 키 `mch_lowpoly_source`.

## 0.23.21
- ZIP sha256 `57f7e2575a0aaa62473d5ba48b8bed04d7110bcf2b321ae9ecd6377c89afa755`. `tool_state.hud_for(context, tools)` = effective_tool in tools. poll에 추가: armor_plate(PLATE), random_panels(PLATE), creature_shell(PLATE), curve_tube 두 그룹(TUBE), robot_base(BASE, 별칭 `_ts`), cloth_wrinkle(WRINKLE). armor_plate / cloth_wrinkle / robot_base에 모듈 수준 tool_state import 추가.

## 0.23.20
- ZIP sha256 `adcb019e14fbdbd4d251393c29b89fec6f501fa0fcb33b29c2fc47e1f4c7778f`. `cloth_wrinkle._refresh(ob, mod)`(interface_update, update_tag, data.update_tag, 3D 뷰 tag_redraw)을 `set_input`과 `scale_all`이 같이 씀.

## 0.23.19
- ZIP sha256 `bde23129b6fea46dba6fd79bdba9e9a438b263145dc5349c37be3e2824175660`. `cloth_wrinkle`: 슬라이더 `all_scale`(종류 ALLSCALE, 맨 앞) → `scale_all(ob, factor)` = SIZE_INPUTS − {Trim Width, Trim Height} × factor + 셸 두께, fold_lines 한 번, 지난번 값도 기억. 현재 값 `ob['mch_all_scale']`(Reset = 100).

## 0.23.18
- ZIP sha256 `fd99be01744a2b71174a89970e024e15d9cc35105df475ba4664ff78400fb629`. `base_mesh._profile_rims` / `_profile_one`(bmesh.ops.bevel 대신): 윗 / 아랫면을 drop만큼 내리고 inset_region(thickness, depth)을 단계별로(Chamfer 1, Bevel = 1/4 원) - drop = min(Width, 높이 × 0.95 / 양쪽이면 0.48). 겹침(면 뒤집힘, 윤곽 밖 점, 면적 증가)이면 Width × 0.7로 재시도, 노트는 `ob['mch_base_notes']` → LIVE 패널. `mirror_hud.shown_for_tool`: Select 또는 MIRROR 도구에서만.

## 0.23.17
- ZIP sha256 `7e0ab8c89ab2c1a7d876e2a390614457577eb27c13d2b5be38a43c8b0e05ca09`. `box_hide` GN v3: Mesh Boolean MANIFOLD / FLOAT 두 개 + Switch(입력 Manifold = 대상 비매니폴드 엣지 0), Cap 끄면 그 결과에서 볼륨 표면 Epsilon(크기 × 1e-4) 안의 면 삭제. 볼륨은 `_combine`(EXACT UNION / DIFFERENCE, 작은 메쉬)으로 하나의 닫힌 덩어리. `cut_engine`: HIDE도 `mch_cut.targets`를 따름, 색 = Cut 주황. 패널에 depth_mode / depth / targets.

## 0.23.16
- ZIP sha256 `a0e1deb11dddf65768c9996238e07ca8decb8b28847e074bae635f0e8e33fa02`. 새 `box_hide.py`: GN 그룹 `MCH_BoxHide`(Object Info Relative → Mesh Boolean Difference Exact, Self Intersection → Cap 끄면 볼륨 표면에서 Epsilon 안의 면 삭제). 볼륨 오브젝트 = `cg.build_cutter_mesh` 프리즘들을 이어 붙임(hide_set, hide_select, 키 `mch_hide_volume`), Alt 복원 = `cg.boolean_result(볼륨 − 모양)`, 비면 Show All. `cut_engine` 모드 'HIDE'(항상 Auto Target, 닫힌 모양만), `tool_state` 'HIDE'(enum 28), `workspace_ui.MCH_TOOL_box_hide`, Scene `mch_hide`(cap, mirror).

## 0.23.15
- ZIP sha256 `a7a7cac6be32384cafdc42573e6012adf22c5a8606bf25bd790c740b052b6e11`. `cloth_wrinkle.py` / `cloth_sim.py` = 커밋 b77013d(0.23.9). cloth_wrinkle 위에 다시 넣은 것: SIZE_TAG / `recalled` / `with_sizes` / `clamp_lengths`(0.23.14 + Crumple·Billow), Billow 프리셋 값 낮춤. test_v02310~v02312 삭제, test_v02313 → test_v02315(Space + 지난번 값), 0.23.10 이후 클로스 때문에 고쳤던 옛 테스트(v0200, v0234, v0238, v0239)는 0.23.9 버전으로.

## 0.23.14
- ZIP sha256 `61f3abe51220749d0c33ceab7e2d181a0188986dce8fbccd571e380333b5501f`. `cloth_wrinkle.set_input`: SIZE_INPUTS 값을 기억할 때 `<이름>@size` = 그 판의 `mch_wrinkle_size`도 기억(`_thickness@size`도). `recalled(values, size)`: 비율 0.5~2 = 그대로, 그 밖 = ×비율, @size 없는 길이 값은 버림. `capture`(프리셋 저장)에 @size 포함, `with_sizes`로 예전 프리셋은 선택된 판 크기로 간주. `_wrinkle_layer`와 creature 경로가 `recalled` 사용.

## 0.23.13
- ZIP sha256 `9d4796a89b028d766f5d8444d703730f70693fadc7f454b6515e7e5808560d63`. `cloth_wrinkle`: `fold_lines` Fold In 프로필 clip(1 - d / max(w/2, min_w))^1.6, 폭 ×0.75, min_w = 엣지 1.5배, Blur 1회; `_membrane(bm, dist)` (Jacobi 400회, -Δu = 1, 테두리 0, max = 최대 테두리 거리) → 점 속성 `mch_edge_smooth`, GN Puff가 이것을 사용(없으면 Db). Center Calm 기본 0.9.
- `cut_engine.StrokeLogic`: SPACE PRESS/RELEASE = `space_xy`, 그 사이 MOUSEMOVE는 `_space_move`(pts / redo / anchor / press_xy 이동). Space 툴 메뉴 키맵 제거(3D View, 그리기 툴, Primitive). `mch.space_tools` 연산자와 `space_menu` 설정은 호환용으로 남김(키 없음, UI 숨김).

## 0.23.12
- ZIP sha256 `19abf17cf9b7671f6d020caed29f3ad42ff5283990ec5ebf5b8d3c476dd64bf4`. `cloth_wrinkle` GN: 입력 `Center Calm`(뒤에 추가) - pinch × (1 - Calm × smoothstep(0.2, 0.6, Db / max(Db))), Attribute Statistic으로 max(Db). HUD 키 `calm`.

## 0.23.11
- ZIP sha256 `5c19278bbc55bb633a6edc6bbe51ed5f9a1a93efbd1655e776d8568a3dbd33ef`. `cloth_wrinkle.fold_lines`: 메인 `FOLD_H` = 0.23.2 단면(clip(1-(d/w0)^2)^sharp, w0 = 원래 폭, 최소 폭 2.2 엣지), 새 `FOLD_D` = 0.23.3 비대칭 단면(입력 Fold Asymmetry / Thinness / Direction). GN: `smooth_named`(Blur Attribute 3회 / 2회) 후 pinch, `Surface Detail` × FOLD_D 더함, `Fold In`(0/1)으로 부호(1 - 2·FoldIn). 입력 2개 뒤에 추가. `apply_preset`: Fold In = Padding/Puffer 1, Pinch 2 = 0.5 × Pinch, Fan Mix 기본 0.3. HUD 키 `surf_detail`, `fold_in`.

## 0.23.10
- ZIP sha256 `99a8b15ffd1a3e5b204abbd9e945b1d6d43f3bf7f1ca4481f806a4756f6c6b84`. `cloth_wrinkle` PG: `sim_gravity / sim_shrink / sim_pressure / sim_bend / sim_frames / sim_puff / sim_detail / sim_face_px`, `_fill_sim`(sim_preset update), `_spacing(st)`(Sim이면 max(spacing, sim_face_px)). `cloth_sim`: `DETAIL_FACES`, `_decimate`(임시 DECIMATE, 비율은 삼각형 수 기준), `build_cloth_mesh(max_faces)`, 버텍스 레이어 `mch_src_n`으로 조각별 방향 맞춤, `scene_overrides(st)`(Puff가 압력과 음수 shrink에 곱해짐), Draft(≤1500면)는 quality ≤ 4 / collision_quality 2, `bake` 진행 표시(progress_begin 없으면 생략), `redo(..., **over)`, 오퍼레이터 `sliders` 옵션.

## 0.23.9
- ZIP sha256 `d8bc94d28360811a49ee54ff09ac0f01cb78fcc6a639ec10766b288ca19d35b3`. `cloth_sim`: `PRESETS`(9) / `preset_values` / `run_preset`, `panel_cloth(..., bend, shrink_max, random_islands, variation, collider='REGION'|'BODY'|'NONE', preset, remove_faces)`, `_region_collider`(원본 면으로 임시 COLLISION 오브젝트, 끝나면 삭제), 시작 위치 노말 방향 2 × 두께(두께 = max(입력, 크기 × 0.003)), collision_quality 3, 조각별 `mch_shrink` / `mch_pressure` 버텍스 그룹(베이크 후 삭제), Split SEAM(소스 edge use_seam / sharp), `redo` + `mch.panel_cloth_redo`, `draw()` 패널 박스. `cloth_wrinkle`: PG `sim_after`, `sim_preset`(정적 items `_SIM_PRESETS` - 문자열 annotation이라 lambda 안 됨), `_sim_after`가 perform_wrinkle 끝(일반 / Through)에서 run_preset. 헤더 Sim 토글.

## 0.23.8
- ZIP sha256 `2121b1849032f253eaa58ee4e8536b6b416735c2b4ccd3a645af64a024c900f6`. `cloth_wrinkle` v43: 입력 `Pinch 2`(뒤에 추가) - 긴 주름 × Pinch, 부채 × Fan Mix × Pinch 2, max로 합침. `apply_preset`이 Pinch 2 = Pinch(또는 프리셋 Pinch2). 새 `cloth_sim.py`(Panel Cloth): `build_cloth_mesh(parts, cuts, split, angle, noise, seed)` → `setup_cloth`(CLOTH 모디파이어: quality, mass, pressure, shrink_min, effector gravity, pin 버텍스 그룹 `mch_pin`, collision distance) → `bake`(frame_set으로 캐시 채우고 new_from_object) → `panel_cloth(...)`, 오퍼레이터 `mch.panel_cloth`. 몸에 COLLISION이 없으면 임시로 붙였다 제거. GN 시뮬 시도는 폐기(주름 품질 부족).

## 0.23.7
- ZIP sha256 `f9a37f70be4f3ff7e19b44e7e39de3bdb9f80fcf030927c398053be246019886`. 새 `through_region.py`: `through_panels(bm_world, groups, projector, spacing_px, crease_deg)` - 화면 상자 겹치는 면만 남김 → 정면 엣지에서 px/m 추정 후 Face Size까지 엣지 분할 → 라쏘 안 판정, 바깥 점은 엣지 따라 이분 탐색으로 라쏘 경계에 붙임 → 앞/뒤(면 노말·시선) + 이면각 > Crease에서 컴포넌트 분리. `armor_plate.through_plate_meshes` / `_perform_through`(SRC_KEY에 through 번호 + crease, `rebuild_plate`가 같은 번호 패널 사용). `cloth_wrinkle.perform_wrinkle` → `_wrinkle_layer(...)`로 분리, Through면 패널마다 호출. 브러시 `through_mode`, `through_crease`, 헤더 토글. `cloth_wrinkle` v42: `_crumple_height`(입력 Crumple / Size / Sharp / Stretch / Angle / Billow / Billow Size, 뒤에 추가), 타입 PUFFER / COTTON / DRAPE(Type 3..5, 패턴 스위치는 기존 3개 재사용), `apply_preset`이 Crumple / Fan Mix / Sections 설정.

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
