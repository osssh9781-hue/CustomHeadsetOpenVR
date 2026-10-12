# Mecha Lab — 현행 상태 / 버그 증거 / Claude 조사 우선순위

기준 시점: 2026-10-13. 파일은 **배포 v0.5.9**와 **작업 중 v0.6.0 초안**을 구분합니다. 작업 중 코드는 확정·배포된 적 없는 미검증본입니다.

## 확인된 배포 v0.5.9 구성 (파일 검사)
- `__init__.py` 메인 UI, Space 도구 메뉴, Boolean, Smart Fuse, Panel/Cure/Remesh, keymap
- `cut_tools.py` 모달 Cut
- `cut_presets.py` PNG 벡터 프리셋 / 스탬프
- `mask_tools.py` *폴리곤 면 단위* 마스크, Solidify 추출
- `mirror_tools.py` Mirror
- `radial_array.py` Radial/Boolean
- `surface_conform.py` Surface Snap/Wrap

## 파일 검사로 확정한 현재 구조적 취약점
1. `cut_tools.py:MCH_OT_draw_delete_cut.modal()`은 우클릭을 `ESC`와 한 분기로 처리하여 **요구한 RMB shape popup이 현재 배포본에 없음**.
2. 같은 모달은 Cut 다회 반복을 한 오퍼레이터 세션으로 잡는 경로가 있어 **각 컷을 독립 Undo로 취소하는 흐름이 부족**. Ctrl+Z 사용자 환경에서 불능 제보.
3. 키맵은 `__init__.py:register()`에서 `Object Mode`와 `3D View`에 Space/B/C를 걸고 활성 상태 토글. **키맵 등록 존재 = 실제 5.0.2 GUI에서 호출됨**은 아님. 사용자 환경에서 Space 메뉴 불능 제보. 3D View/Blender playback/map/모달 처리 우선순위 검토.
4. `mask_tools.py`는 FACE/INT attribute 기반 *면 전체* 마스크와 `Solidify` Extract에 한정; **실제 Protect-Boolean / 정확한 경계분할 / Split Mask / Weight Pose 미구현**.
5. `cut_presets.py:apply_stamp()`에서는 evaluated boolean mesh에 non-manifold edges가 생기면 `Boolean result is non-manifold; lower simplify or change stamp size` 오류와 함께 실패. 사용자가 이 정확한 문구를 스크린샷으로 보고했음. 복잡한 PNG contour + concave/hole/mesh 교차에서 원인 추적 필요.
6. `cut_tools.py` 기본 동작은 Cut 연속 작업·UI 키입력·메뉴 변경과 충돌. `Ctrl+Z`, 팝업, 다른 도구 전환에서 문제 재현 필요.
7. `v0.5.9`에 별도 Edge Finish (new edge only), true Bezier vertex + handles, global user-editable keymap, full Weight Pose, true Shape-mask Protect는 **없음**.
8. 사용자가 첨부한 98가지 알파의 **컨택트시트**는 개별 PNG 파일이 아니라 저해상도 합성 이미지이므로 개별 원본 검수/고해상도 요청이 바람직.

## 화면에서 직접 보고된 오류/문제 (SCREENSHOTS 폴더)
- `png_boolean_nonmanifold.png`: PNG 스탬프 컷 후 예기치 않은 곡선/선 파손, 하단 빨간 오류: `Boolean result is non-manifold; lower simplify or change stamp size`. 기대: Cut과 같은 매끈한 외곽선과 닫힌 솔리드.
- `boolean_multiuser_data.png`: `Modifiers cannot be applied to multi-user data` (데이터 공유 오브젝트에서 Auto Apply). v0.5.9에 일부 자동 분리 대응 코드가 있는 것으로 기록되나 일반 Cut / Smart Fuse / Remesh 전 경로 테스트 필요.
- `ui_error_and_no_space_menu.png`: 상태 바의 다른 Python Traceback과 Space 팝업 불능. **에러 메시지 전체 미제공이므로 원인 추측 금지.**
- `ui_cut_line_straight_only.png`: 베지어 핸들이 없는 선형 Cut / line UI.
- `user_alpha_sheet_98.png`: 원하는 PNG 컷 참고용 프리셋 모음.

## 미출시 `WIP_v060_UNRELEASED/` 검토 주의
- `cut_tools.py`에서 `Ctrl+Z`, UI PASS_THROUGH, 우클릭 단/더블 분기, 스토크 완료 후 timer 기반 rearm을 수정하려는 초안.
- `__init__.py`에서 우클릭 프리셋 메뉴 추가 초안.
- **미검증이고 타이머 재시작/undo/keymap/reload 간 경쟁 조건 가능**. 지금 당장 안전한 완성본으로 배포하지 말 것. Blender GUI에서 시나리오 테스트 후에만 배포.

## 실질적인 난관 / 권장 기술 접근
| 영역 | 어려움 | 최소 품질 기준 / 실험 |
|---|---|---|
| Modal Cut/Undo/UI | Blender event dispatch / Modal/Undo/timer | 한 획당 명확한 Undo/Redo, 사용 중 N패널 클릭, 팝업, 툴 스위칭. 모달 내 PASS_THROUGH만으로 해결된다고 단정 금지. Workspace Tool 아키텍처와 비교. |
| RMB single/double | 클릭 구분이 동일 입력 이벤트를 사용 | single popup 지연 판정·더블 exit 경합 및 사용성 테스트. 대체 키/명시적 exit 검토. |
| Vector Cut PNG | 픽셀 마스크 → 여러 폐곡선·구멍 → 유효 3D solid, concave/hole Boolean | contour winding/holes/triangulation, manifold, computed volume, mixed anti-alias. 최소 십자·링·격자·여러 섬 케이스. |
| Mask Protect | painted region을 Boolean에서 실제 보존 | Boolean 후 보호 영역 되돌리기보다 clip operand to unmasked 3D region 등 안정적 분할 설계; 연결부/캡 검증. Face / exact mask 별도. |
| Smart Fuse | Boolean intersection seam 추출 후 베벨/챔퍼 양면 통합 | 교차곡선 샘플링·edge tagging·manifold·nonuniform scale·thin wall. 지원 조건 명시. |
| Curve handle UI | GPU overlay + hit-test + Bézier data model | 명확한 점과 핸들, 클릭 단계 전환, 드래그, 시점 변경 후 일관됨. |
| Array orientation | 회전 중심/메쉬 로컬 basis 혼동 | world/local transform 분리하고 1개 복제의 x/y/z방향 테스트. |
| Cut edge finish | 전체 Bevel이 아니라 **new cut edges only** | boolean에서 새 엣지 식별/attribute/tag하고 restricted bevel. |
| Weight Extract/Pose | 마스크 부드러움·메쉬 재분할·라티스 변형 | Rigid vs Soft로 나눠 구현/벤치마크. |
| GUI performance | Python boolean / remesh가 mousemove마다 재실행 | 드로잉 GPU overlay, caching, background preview throttle, confirm-only final. |

## 제안 QA 매트릭스
- 공식 사용자 환경 **Blender 5.0.2 Windows**를 반드시 별도 GUI 검증. Headless `bpy 5.2.2` 정적/런타임 통과만으로 GUI 입력 보장 불가.
- Cut/Mask × 모든 도형 타입 × Alt on/off × Enter/double-click × UI 클릭 × RMB single/double × Ctrl+Z/Redo × open/close × 여러 번 연속.
- Geometry: 큐브, low-poly cylinder, UV sphere, 기계 솔리드 + 복잡 곡면 + boolean history, open shell, nonuniform scale, shared mesh data, collections/instances.
- PNG: 십자(오목), 링(내부 구멍), 구멍 20개 그릴, 슬릿·얇은선, 반투명 antialias, 여러 섬, 큰 이미지, 작은 stamp.
- 검사: no crash, non-manifold edges after closed-solid operations, silhouette accuracy, surface normals, no lost objects/modifiers/materials, Undo/Redo and file reload.
- 무거운 실시간 연산은 사용자가 명시적으로 확정할 때만; 가능하면 1만/10만/100만 폴리곤 시간/메모리 비교.

## 제안 우선순위 (현실적)
**P0** Cut modal/Undo/Space/UI/RMB 고치기, 공유 메쉬 자동 처리, PNG non-manifold 원인 재현.
**P1** 커브·포인트 핸들 입력, Cut 벡터 PNG의 정확도, new-edge Bevel/Chamfer, curve quality.
**P2** Mask Protect/Cut/Split/Extract with precise boundaries, Weight Pose/Extract, FBX cutter Asset Library.
**P3** Smart Fuse 강건화, custom shortcut editor, screenshot thumbnail gallery, Array orientation, remaining pose/surface optimizations.

## 개발 규칙
- 최신 배포 v0.5.9는 보존. 기존 소스에 바로 덮어쓰지 말 것.
- 사용자에게 확인 안 된 기능은 구현 완료라고 발표 금지.
- 재현 테스트, 코드 diff, regression 결과, .zip build, 설치 스텝, 미검증 항목을 반드시 출력.
