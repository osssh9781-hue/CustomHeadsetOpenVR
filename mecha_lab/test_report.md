# Test Report — Mecha Lab 0.11.1

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 5.0.1 (build a3db93c5b259), **headless / background** |
| Python / OS | 3.11 / Linux 6.18 (클라우드 컨테이너) |
| 사용자 환경 | Windows 11 + Blender **5.0.2 GUI** — **실행 안 됨** |
| 사용자 설정 | 임시 `BLENDER_USER_*` 폴더 사용, 실제 설정·Startup 미사용 |
| 기준 | ChatGPT v0.9.3 무수정 ZIP (sha256 `3b66e845…a1e4cd`) |

명령: `<bpy python> tests/run_all.py` · 로그: `tests/test_log_bpy501_v0111.txt`
ZIP: `dist/mecha_lab-0.11.1.zip` (sha256 `fb8960ae4fc08a273b09cb6d1cfca01a7efda2da8d16ee193d1ec480423f0593`)

**변경 전(v0.9.3 무수정)에도 같은 headless 테스트는 모두 통과**했습니다(경로 누락 2건 제외). 즉 사용자 보고 고장 대부분은
headless로 재현되지 않았고, 아래 "GUI 검증" 열은 전부 미검증입니다.

## 0.11.1 결과: 18개 파일, 1007 / 1007 통과
`test_v0100_regression.py` 108항목(0.11.0 96 → Alt 클릭/드래그 블록을 0.11.1 블록으로 교체). 나머지 17개 파일 항목 수 그대로.

| 요청 테스트 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 1. Cube Rectangle Cut | O | O (부피 8 → 6) | 미검증 |
| 2. Curve / Lasso Cut | O | O | 미검증 |
| 3. Split | O | O | 미검증 |
| 4. Alt 반전 (누를 때 / 그리는 중 / Alt+클릭 점) | O | O | 미검증 |
| 5. Ctrl 중심 그리기 | O | O | 미검증 |
| 6. Split Gap / Bevel | O | O (기존 Split Gap·Bevel 테스트) | 미검증 |
| 7. Select / Move 메뉴 + W 단축키 | O | 등록·키맵·버튼 그리기만 (실제 기즈모/입력 없음) | **미검증** |
| 8. Select / Move 후 Cut/Split 재진입 | O | O (툴 변경 → 모달 CANCELLED, 새 모달 새 획으로 Cut) | 미검증 |
| 9. 다중 오브젝트 Cut / Split | O | O (F01) | 미검증 |
| 10. 설치·활성·재시작 | O | 설치·비활성·재활성 3회 (재시작 = 새 프로세스는 headless 미실행) | **미검증** |
| MCH_Box(Live Primitive) Cut "whole object" | O | O (재현 → 수정) | 미검증 |
| 일반 Cube "whole object" | — | 재현 안 됨 | 미검증 |
| Alt 모드 전환 코드 제거 | O | O (메서드·연산자·키맵 없음 확인) | — |

## 0.11.0 결과: 18개 파일, 995 / 995 통과
| 신규/변경 | 항목 | 내용 |
|---|---|---|
| test_mechanical_toolkit.py | 99 | **신규** — 사양서 13절: Face Extract(곡면·노멀 방향·원본 유지·챔퍼 3모드 수치·Outward·외곽/측면 엣지·쉘·오프셋·설정 유지·다중 오브젝트), Armor(한 방향만 두께/챔퍼/베벨, 6프리셋 형상 변화와 서로 다름, 회전·스케일, Y 가지별 길이·폭, 능선 6프로필, 방향 회전, 곡면, 설정 복사), Edge Molding(파츠 경계·별도 오브젝트·폭/높이/베벨 독립·프로필·중앙선·면 경계), Curve Array(개수·커브 편집 갱신·Fit·Offset·Deform·World X/Y 배치), Curve Deform, Cable(두 오브젝트 클릭·끝점 고정·노멀 출발·처짐·점 추가·두께·프로필·테이퍼·Edge to Cable), Hollow(다중·내부 쉘·방향·개구부·Rim·과두께 검출·Reset/Apply) |
| test_v0100_regression.py | 96 | +탭 이동 시 Base Mesh 자동 Apply 3, +Tab 통과 1 |
| test_ui_draw.py | 130 | +새 도구 5개 패널(라이브 파츠/Armor Y/몰딩/쉘/배열/케이블) |
| test_self_test.py | 4 | 자가 진단 12단계로 확장, 데이터 잔여 없음 |

| 0.11.0 기능 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 탭 이동 시 Base Mesh 자동 Apply | O | O (판정 함수) | 미검증 (타이머) |
| Face Extract Basic (모든 슬라이더) | O | O | 미검증 |
| Armor Sculpt (방향·프리셋·능선·전환) | O | O | 미검증 |
| Edge Molding | O | O | 미검증 |
| Hollow / Shell | O | O | 미검증 |
| Mesh Along Curve (Deform / Array / 배치) | O | O | 미검증 |
| Cable Generator (클릭 모달은 로직만, Edge to Cable) | O | O | 미검증 |
| Tab으로 Edit Mode, 설정 유지 | O | O (모달 Tab 통과·재선택 유지) | 미검증 |
| Undo / Redo | O (UNDO 플래그) | 실행 불가(headless) | 미검증 |

## (0.10.0) 결과: 17개 파일, 875 / 875 통과
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
| ~~Alt 짧은 클릭/드래그, Alt+클릭 복귀~~ (0.11.1에서 삭제) | — | — | — |
| V 빠른 메뉴 / Shift+A | O | 등록만 | 미검증 |
| Boolean 활성=커터 다중 대상 | O | O | 미검증 |
| Cut/Split 다중 대상, 실패 보존 | O | O | 미검증 |
| Base Mesh Bevel Sides / Both 별도 폭 / Alt 커터 / 세션 Auto Apply / 마이그레이션 | O | O | 미검증 |
| Deform 기즈모(Mecha) | O | 수학·드래그 로직 O, 기즈모 표시·클릭 미검증 | 미검증 |
| Deform Blender 기즈모 + Proportional | O | O (`transform.rotate/resize` + proportional로 단일 점 → 주변 변형 확인) | 미검증 |
| Free Draw Stabilizer | O | O (떨림 감소/지연 증가 수치, dt 독립, 지연 원, 종료) | 미검증 (프레임/타이머 체감) |
| 자가 진단 버튼 | O | O | 사용자 실행 필요 |

`GUI_TEST_CHECKLIST_KO.md`의 0.10.0 항목을 Windows Blender 5.0.2에서 확인해 주세요. headless 통과는 GUI 동작 인증이 아닙니다.
