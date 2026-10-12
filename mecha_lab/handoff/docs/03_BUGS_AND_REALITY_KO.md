# 배포본 진단 / 관측 증거 / 미완성 요소

## 기준 파일과 상태
- 실제 마지막 배포: `archives/ORIGINAL_v0_5_9.zip` 및 `source/RELEASE_v0_5_9/mecha_lab/`.
- `source/WIP_v0_6_0_UNVERIFIED/...`는 Undo / RMB / UI 이벤트 전달을 개선하려던 초안. 아직 **사용자 GUI에서 검사 또는 배포하지 않았습니다.** 해당 코드를 그대로 정답으로 쓰지 마세요.
- 사용자 Windows 11 + Blender 5.0.2. 과거 Linux `bpy 5.2.2` 기하/등록 테스트는 GUI 성공의 근거가 아닙니다.

## 관측된 문제 및 증거
1. **컷 중 Ctrl+Z 미작동**: 모달 도구가 키 이벤트를 가로채고 Cut 반복 처리의 undo granularity가 문제. 한 컷당 undo 후 도구 계속 유지하도록 재구성해야 함. `evidence/04_cut_straight_ui.png`에서 기존 직선만 보이는 상태도 참조.
2. **Space tool popup 실제 환경에서 작동하지 않음**: 키맵/모달 우선순위, Space 기존 할당, 활성 상태에 대한 GUI 검사 필요. Workspace 내 좌측 toolbar 우선 대체 제공. `evidence/05_no_space_menu_and_status_error.png`.
3. **RMB 클릭 시 Cut 종료**: 사용자는 한 번 RMB=Shape Popup, RMB double=exit 요청. 배포 Cut 코드의 이벤트 처리/팝업 등록 확인 필요.
4. **PNG 벡터 컷 결과 잘못된 면/선 및 비매니폴드 메시**: Blender statusbar에 `Boolean result is non-manifold; lower simplify or change stamp size` 라고 표시됨. 오목 십자, 링, 다중 홀, 얇은 슬롯, 비정상 교차를 재현; algorithm 원인은 확정하지 말 것. `evidence/01_png_nonmanifold.png`.
5. **멀티유저 mesh data 모디파이어 적용 실패**: `Modifiers cannot be applied to multi-user data` 보고. `evidence/02_multiuser_modifier.png`. 이전 일부 대응 코드는 있으나 모든 apply 진입점/Undo 검사 필요.
6. **Smart Fuse 오류 제보**: 스크린샷은 에러의 경로가 잘려 있어 함수/traceback 확정 불가. 다양한 교차 케이스 기하 검사 필요. `evidence/03_smartfuse_and_traceback.png`.
7. **Cut UI에는 Bezier point+handle이 제대로 없고 일부 원/곡면 컷 표면의 패싯이 보임**. shape segmentation과 원본 low-poly geometry/shading 문제 분리.
8. **Radial Array 복제 메쉬의 local orientation이 원하는 방향과 다르게 회전**. 선택 중심과 개별 copy orientation 분리.
9. **마스크/웨이트는 부분 구현만**: v0.5.9의 면 단위 마스크 Extract & Raise가 있으나, Cut/Boolean 실제 Protect와 정확한 폴리곤 윤곽 Split, Weight Pose는 미구현.
10. **기존 긴 N패널 UI가 비직관적**: Tool과 Shape/Brush가 뒤섞임. 사용자가 명시적으로 Workspace 전용 UI로 변경 승인.

## 현재 v0.5.9의 파일 구조
- `__init__.py` : UI/Boolean/Smart Fuse/Misc/keymap
- `cut_tools.py` : line/shape modal Cut; `cut_presets.py`: PNG shape import/stamp
- `mask_tools.py` : coarse face mask/extract; `mirror_tools.py` : world/local/collection mirror
- `radial_array.py` : array+boolean; `surface_conform.py` : surface snap/wrap
- `blender_manifest.toml`: Blender version min 4.3 (이는 **실제 호환성 검증 보증이 아님**).

## 현기능 미구현/미검증 (중요)
- Workspace tab / left tool list / brush palette separation: **미구현**.
- Space modal popup in user's actual Blender: **불능 보고**.
- Ctrl+Z/Redo active cut + independent history: **불능 보고**.
- New Cut Edge Bevel/Chamfer isolated to new edges only: **미구현**.
- Bezier point handles and iterative rounding click: **미구현**.
- Actual boolean protection of Mask: **미구현**.
- Weight Pose/extract: **미구현**.
- FBX Blender asset cutter import: **미구현/확인 필요**.
- General Smart Fuse robustness: **미확인 및 오류 보고**.
- User-defined workspace-only hotkeys GUI: **미구현**.

## 스크린샷 원인 확인 원칙
`evidence/05_no_space_menu_and_status_error.png` 아래 빨간 오류/`evidence/03`에 보이는 traceback은 화면이 잘려 있어 정확한 호출 원인을 확인할 수 없습니다. 로그 제공 전에는 다른 애드온 문제와 혼동하지 마세요.

## 해결 우선순위
**P0** Workspace/UI prototype, Cut modal/undo/input state, menu click accessibility, Space conflicts, RMB popup, critical multiuser safety.  **P1** Vector PNG robust cutter + Cut shape quality, Bezier UX, Cut Edge Finish. **P2** true Mask Protect/Split/Extract, Weight/Pose, Smart Fuse stabilization. **P3** Advanced asset integration, array orientation and other polish. 안전한 독립 기능은 선행/병행 가능.
