# Test Report — Mecha Lab 0.9.0

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 5.0.1 (build a3db93c5b259), **headless / background** |
| Python / OS | 3.11 / Linux 6.18 (클라우드 컨테이너) |
| 사용자 환경 | Windows 11 + Blender **5.0.2 GUI** — **실행 안 됨** |
| 사용자 설정 | 임시 `BLENDER_USER_*` 폴더 사용, 실제 설정·Startup 미사용 |

명령: `<bpy python> tests/run_all.py` · 로그: `tests/test_log_bpy501_v090.txt`
ZIP: `dist/mecha_lab-0.9.0.zip` (sha256 `e0df276daa9dff157904a9c0d55131448da0380a4f99e704daa76a18d85b74b9`)

## 결과: 13개 파일, 621 / 621 통과 (0.8.0의 12개 파일은 회귀 없이 전부 통과)
| 파일 | 항목 | 0.9.0에서 |
|---|---|---|
| **test_v090_features.py** | 70 | **신규** — 아래 표 |
| test_ui_draw.py | 112 | +7: Live SubD, Split Gap + A/B, Live Mesh Curve(DRAW/EDIT), Live Radial 회전 패널 |
| test_stroke_events.py | 68 | 0.8.0 그대로 통과 (Esc, 더블/트리플 클릭, Curve Lasso, Free Draw, Base Mesh 모드) |
| test_base_mesh.py | 83 | 그대로 통과 |
| test_cut_geometry.py | 93 | 그대로 통과 (Split 기본 동작 불변) |
| test_png_shapes.py | 85 | 그대로 통과 |
| test_loft_surface.py | 22 | 그대로 통과 |
| test_zbrush_bridge.py | 17 | 그대로 통과 |
| test_legacy_features.py | 26 | 그대로 통과 (Radial create/bake/Boolean 포함) |
| test_workspace_data.py | 17 | 그대로 통과 (Ortho Lock 포함) |
| test_register.py | 11 | 아이콘 enum 검사 포함 통과 |
| test_zip_install.py | 9 | 0.9.0 ZIP 설치/활성/비활성/재활성 |
| test_performance.py | 8 | 정보용 |

### test_v090_features.py 세부 (70)
| 영역 | 확인 내용 |
|---|---|
| Mesh Curve 그리기 (실제 `PathDrawLogic`에 가짜 이벤트) | 기본 VECTOR, 기존 점 클릭 → Smooth(새 점 없음), 점 더블클릭 토글, 다시 클릭 → Straight, `S`로 새 점 종류, Backspace가 종류 보존, Enter로 Live 생성 + 새 노드, Free Draw 점 AUTO |
| Mesh Curve Live | Object Mode All Smooth, **Smooth 시 실제로 곡선(직선 구간 위로 부풂, 정점 수 증가)**, Resolution → 밀도, Profile Segments, Rotation X/Z, Twist(시작 고정·나머지 회전), 0.9 이전 Live 객체 자동 업그레이드, Bake |
| Curve Array | 복제본 Rotation Z, Twist |
| 키맵 | Curve Edit Mode 더블클릭 키맵이 **활성** |
| SubD Plane | 스택 순서/종류, Simple·CC 동시 작동(면 수 증가 순서), 레벨 0~5, Solidify 값, Edit Mode 표시, Edit Mode 엣지 Extrude + Crease, Apply All 면 수 = 적용 전 평가 결과, 기존 메쉬에 스택 추가 |
| Radial | Rotate Each Copy 기본 OFF(씬/오브젝트), OFF면 모든 복제본이 원본 축 유지(기울어짐 없음), ON이면 회전, Ring Rotation X(XZ 평면으로), Copy Rotation Z(제자리 회전), Start Angle 30°, 이전 배열 자동 업그레이드, Bake |
| Gap Split | Normal 불변, Gap 부피(조각 0.8², 구멍 1.2²), 별도 닫힌 오브젝트, 중심 유지, 직선 Gap(0.2 간격·중심·캡), 폴리라인, 원(곡선), Cap OFF, 너무 넓은 Gap 거부(무변경), Live 모드 거부 |
| 양쪽 마감 | Normal/Gap 각각 A만 Bevel(B 날카로움), 원래 모서리 불변, Swap Sides, 직선 Split B Chamfer, Cut Edge Finish 불변 |
| 2D 모서리 | Sharp/Chamfer/Round 점 수, Corner Width, Segments, 짧은 변 클램프, **Lasso 그리는 중 미리보기**(3 모드), **Rectangle 드래그 중 미리보기**, 둥근 사각 컷 적용 |

## 기능별 상태
| 기능 | 상태 |
|---|---|
| Mesh Curve 곡선 생성/편집, Resolution/Segments, Rotation X/Y/Z, Twist | 구현, 기하·상태기계 headless 검증 / **GUI 미검증** (특히 Edit Mode 더블클릭 키맵) |
| SubD Plane | 구현, headless 검증 / GUI 미검증 (슬라이더 즉시 반영은 모디파이어 직접 갱신이라 문제 예상 낮음) |
| Radial 회전 컨트롤, Rotate Each Copy 기본 OFF | 구현, headless 검증 / GUI 미검증 |
| Gap Split | 구현, headless 검증(직교 뷰 기준 정확) / 원근 뷰 폭은 근사, GUI 미검증 |
| Split 양쪽 독립 Bevel + Swap | 구현, headless 검증 / GUI 미검증 |
| 2D Corner Bevel | 0.8.0 구현 점검 완료(미리보기 포함, 상태기계 테스트) / GUI 미검증 |
| 0.8.0 이전 기능 | 회귀 테스트 전부 통과 |

`GUI_TEST_CHECKLIST_KO.md`(81항목)로 Windows Blender 5.0.2 확인이 필요합니다. headless 통과는 GUI 동작 인증이 아닙니다.
