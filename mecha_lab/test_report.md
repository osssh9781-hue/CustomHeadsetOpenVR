# Test Report — Mecha Lab 0.10.0

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 5.0.1 (build a3db93c5b259), **headless / background** |
| Python / OS | 3.11 / Linux 6.18 (클라우드 컨테이너) |
| 사용자 환경 | Windows 11 + Blender **5.0.2 GUI** — **실행 안 됨** |
| 사용자 설정 | 임시 `BLENDER_USER_*` 폴더 사용, 실제 설정·Startup 미사용 |
| 기준 | ChatGPT v0.9.3 무수정 ZIP (sha256 `3b66e845…a1e4cd`) |

명령: `<bpy python> tests/run_all.py` · 로그: `tests/test_log_bpy501_v0100.txt`
ZIP: `dist/mecha_lab-0.10.0.zip` (sha256 `708f3c10d42c3569fc350ca27e1b565e54f712a38a9dbd4e2ff6e87540e46b9f`)

**변경 전(v0.9.3 무수정)에도 같은 headless 테스트는 모두 통과**했습니다(경로 누락 2건 제외). 즉 사용자 보고 고장 대부분은
headless로 재현되지 않았고, 아래 "GUI 검증" 열은 전부 미검증입니다.

## 결과: 17개 파일, 875 / 875 통과
| 파일 | 항목 | 0.10.0 |
|---|---|---|
| test_v0100_regression.py | 92 | **신규** — B01–B10, F01/F02/F08, Alt, V/Shift+A |
| test_deform.py | 109 | **신규** — 단일 점 회전/스케일이 주변 메쉬 변형, Resolution, Bend twist/radius, 드래그 |
| test_registration_recovery.py | 38 | **신규** — B09 잔여 등록·해제 중 예외·등록 중 예외·두 사본 |
| test_self_test.py | 4 | **신규** — 인-블렌더 자가 진단이 데이터를 남기지 않음 |
| test_zip_install.py | 19 | 비활성/재활성 **3회**, 키맵 중복 없음 |
| test_ui_draw.py | 113 | 모든 패널 draw (Mask 툴바 도구 제외로 1 감소) |
| test_stroke_events.py | 68 | 새 사양으로 2개 수정(Alt는 드래그, 3회 클릭 제거) |
| test_cut_geometry.py / test_legacy_features.py | 93 / 26 | Boolean 선택 규칙 새 사양(활성=커터)으로 수정 |
| test_base_mesh / png_shapes / loft / zbrush / workspace / register / performance / v090 | 83/85/22/17/17/11/8/70 | 그대로 통과 |
| tests/chatgpt_v093/* (Primitive) | 26 + 11 + 출력형 | 경로만 바꿔 수동 실행, 통과 |

## 기능별 상태 (docs/04 C: 서로 다른 열)
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| B09 등록 자가 복구, 두 사본 경고 | O | O (38) | 미검증 |
| B01 Mirror world/local/cursor × XYZ, 다중, 변경/Apply/Remove, Collection | O | O | 미검증 (원인 재현 못 함) |
| B02 Loft | O (변경 없음) | O (기존 22 + 자가 진단) | 미검증 (원인 재현 못 함) |
| B03 Smart Fuse 10회, 상태 복구, 고아 그룹 정리 | O | O | 미검증 |
| 도구 목록 → 툴 전환(3D View 컨텍스트), 고착 시 선택 도구 우선 | O | 일부(판정 로직만, 실제 창 없음) | 미검증 |
| B04 아무 곳 더블클릭(PRESS만 와도) / 시작점 클릭 | O | O | 미검증 (실제 이벤트 순서) |
| B05 Mesh Curve 더블클릭 1회 전환 | O | O | 미검증 |
| B06 PNG R 회전 + 커서 미리보기 | O | O (미리보기 그리기 자체는 GPU라 미검증) | 미검증 |
| B07 Split Gap Enter/시작점/더블클릭 | O | O | 미검증 |
| B08 Mask 숨김, 데이터 보존 | O | O | 미검증 |
| B10 큰 베벨, 제한 메시지, Clamp | O | O | 미검증 |
| Alt 짧은 클릭/드래그, Alt+클릭 복귀 | O | O (모달 로직; Object Mode CLICK 키맵은 등록만) | 미검증 |
| V 빠른 메뉴 / Shift+A | O | 등록만 | 미검증 |
| Boolean 활성=커터 다중 대상 | O | O | 미검증 |
| Cut/Split 다중 대상, 실패 보존 | O | O | 미검증 |
| Base Mesh Bevel Sides / Both 별도 폭 / Alt 커터 / 세션 Auto Apply / 마이그레이션 | O | O | 미검증 |
| Deform 기즈모(Mecha) | O | 수학·드래그 로직 O, 기즈모 표시·클릭 미검증 | 미검증 |
| Deform Blender 기즈모 + Proportional | O | O (`transform.rotate/resize` + proportional로 단일 점 → 주변 변형 확인) | 미검증 |
| Free Draw Stabilizer | O | O (떨림 감소/지연 증가 수치, dt 독립, 지연 원, 종료) | 미검증 (프레임/타이머 체감) |
| 자가 진단 버튼 | O | O | 사용자 실행 필요 |

`GUI_TEST_CHECKLIST_KO.md`의 0.10.0 항목을 Windows Blender 5.0.2에서 확인해 주세요. headless 통과는 GUI 동작 인증이 아닙니다.
