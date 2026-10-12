# 소스 맵, 파일 취급, 환경

## 실제 배포 소스
`source/RELEASE_v0_5_9/mecha_lab/` — Blender extension directory. Manifest id `mecha_lab`, reported version 0.5.9, min Blender version 4.3.0 (설정값; 공식 지원 검증 주장 아님).
- `__init__.py`: Main panels, operators, Boolean, Smart Fuse, keymaps and shared properties.
- `cut_tools.py`: modal drawing/cut.
- `cut_presets.py`: PNG-to-vector contour extraction and stamp.
- `mask_tools.py`: initial face mask and Extract+Raise, not full protect.
- `mirror_tools.py`: world/local/collection mirrors.
- `radial_array.py`: radial instance/boolean.
- `surface_conform.py`: snap/wrap.
- `blender_manifest.toml`: metadata/version/permissions.

## 미검증 WIP
`source/WIP_v0_6_0_UNVERIFIED/mecha_lab/`: previous assistant's partially patched modal/Undo/pass-through/popup code. May contain keymap or timer race issues. Use as **diff reference only**, not as new authoritative baseline.

## 참고 이미지
`evidence/01_png_nonmanifold.png` = bad vector Cut and error; `02_multiuser_modifier.png` = modifier apply with linked mesh data; `03_smartfuse_and_traceback.png` = Smart Fuse interface and clipped traceback; `04_cut_straight_ui.png` = line editing UI; `05_no_space_menu_and_status_error.png` = missing Space popup; `06_png_contact_sheet.png` = 98 visual examples, **not individual alpha sources**; `07_workspace_tabs_reference.png` = user screenshot of Blender top workspace bar.

## 코드 편집 원칙
- Preserve original extension ID / module references and migration where possible.
- Do not silently change user's original files, preferences, linked mesh instances, startup environment, or UI keymap in other Workspaces.
- No internet-hosted asset repackaging unless licensed/approved. Original screenshot collection is user-provided reference only.
