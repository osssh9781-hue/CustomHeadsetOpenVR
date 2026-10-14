# Test Report — Mecha Lab 0.21.1

## 0.21.1 결과: 39개 파일, 1749 / 1749 통과 (`tests/test_log_bpy501_v0211.txt`). 보내주신 FBX 조각과 생성 메쉬를 Cycles로 나란히 렌더해 비교, 뷰포트 팝업·패널 조작은 미검증.

## 0.21.0 결과: 38개 파일, 1633 / 1633 통과 (`tests/test_log_bpy501_v0210.txt`). 로봇 모양은 Cycles CPU 렌더로 확인, 뷰포트 팝업·N 패널 조작은 미검증.

## 0.20.4 결과: 37개 파일, 1581 / 1581 통과 (`tests/test_log_bpy501_v0204.txt`).

## 0.20.3 결과: 37개 파일, 1578 / 1578 통과 (`tests/test_log_bpy501_v0203.txt`).

## 0.20.2 결과: 37개 파일, 1576 / 1576 통과 (`tests/test_log_bpy501_v0202.txt`). 모양은 Cycles CPU 렌더로 확인, 뷰포트 조작은 미검증.

## 0.20.1 결과: 37개 파일, 1565 / 1565 통과 (`tests/test_log_bpy501_v0201.txt`). Cloth Plate 모양은 Cycles CPU 렌더로 확인, 뷰포트 팝업 조작은 미검증.

## 0.20.0 결과: 37개 파일, 1558 / 1558 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0200.txt`). 주름 미리보기는 Cycles CPU 렌더로 확인. 뷰포트 팝업 조작은 미검증.

## 0.19.3 결과: 35개 파일, 1518 / 1518 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0193.txt`). Sketch 버튼·키 입력은 GUI에서 실행하지 못함 — 미검증.

## 0.19.2 결과: 34개 파일, 1505 / 1505 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0192.txt`). 뷰포트 버튼·팝업 고정은 GUI에서 실행하지 못함 — 미검증.

## 0.19.1 결과: 33개 파일, 1475 / 1475 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0191.txt`). 우클릭 메뉴·F9 조정 창은 GUI에서 실행하지 못함 — 미검증.

## 0.19.0 결과: 32개 파일, 1459 / 1459 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0190.txt`). GUI(HUD 버튼·슬라이더 드래그)는 실행하지 못함 — 미검증.

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

## 0.18.0 결과: 31개 파일, 1438 / 1438 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Mirror HUD 배치·아이콘, X/Y/Z·Bisect·Flip 즉시 반영, 마지막 축 보호, Apply·Remove | O | O | **미검증 (화면)** |

## 0.17.0 결과: 30개 파일, 1425 / 1425 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 중심점 샘플·Lloyd·칸 나누기, 윤곽 단순화·Gap·뒤집힘 거부, 테두리 조각 | O | O | 미검증 |
| 6면 박스 위 판 여러 개(박스 그대로, 닫힘, 새 면), 프로필 섞임 | O | O | 미검증 |
| Density·Panel Size·Seed(같은 Seed = 같은 배치)·Reroll | O | O | 미검증 |
| Edge Pieces 객체, Mirror(모디파이어 + 한쪽만), Apply / Cancel, 편집 모드 선택 면만, 구면 | O | O | 미검증 |
| HUD 배치·슬라이더 | O | O (계산) | **미검증 (화면)** |

## 0.16.0 결과: 29개 파일, 1401 / 1401 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 새 면 패치(테두리 다시 나누기, 꼭짓점 유지, 넓이 정확, 구멍, 큰 판 자동 경량) | O | O | 미검증 |
| 6면 박스 위 판: 별도 오브젝트, 박스 그대로, 새 면(대부분 사각형), 테두리 0.1 px 이내, 표면 위, 닫힌 솔리드 | O | O | 미검증 |
| 판 위에 그리면 아래 메시에, 휠 = 프로필, 곡면(구) 위에 붙음, 프로필 버튼 라이브 | O | O (가짜 이벤트) | **미검증** |
| 메시 밖 = 메시지, 일부 밖 = 생성 + 알림 | O | O | 미검증 |

## 0.15.0 결과: 28개 파일, 1365 / 1365 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 아이콘 타일 = 큰 그림 + 이름 버튼 | O | O (그리기 호출) | **미검증 (모양)** |
| 왼쪽 떠 있는 툴 목록(배치, 여러 줄, 툴팁) | O | O (계산) | **미검증** |
| HUD 배치(오른쪽, 화면 안, 끝 버튼), 슬라이더 값/범위, 모드 | O | O | **미검증 (클릭/드래그)** |
| Station Apply + 합치기 / − 파내기 / 안 닿으면 확정 / 빼기 실패 메시지 | O | O | 미검증 |
| 겹치는 면 검사(같은 크기 6면, 큰 도형 0, 높이만 다름 4면) | O | O | **미검증 (빨간 점선)** |
| Up/Down + Left/Right 동시, Twist, 예전 Bend 변환(모양 동일) | O | O | 미검증 |
| 다이얼 방향(보는 쪽으로 뒤집기) | O | O (계산) | **미검증 (드래그)** |
| Polygon Prism: 서서 시작, Sides 3–64, 베벨/챔퍼, 위/아래 구간 ±, 접힘 점 순환, 모든 조합 닫힘 | O | O | 미검증 |

## 0.14.4 결과: 27개 파일, 1315 / 1315 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Base Mesh 빼기 선 = 빨간색(더하기 주황과 다름), Cut 색 그대로 | O | O (색 값) | **미검증 (화면)** |

## 0.14.3 결과: 27개 파일, 1313 / 1313 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 위/아래 크기(부피 공식), 피라미드, 베벨·챔퍼(닫힘), 실제 메시 반영 | O | O | 미검증 |
| 이동 화살표(축 방향만, 기준점 고정), 전체 크기 점, 다이얼 3개(드래그 기준) | O | O (계산) | **미검증 (드래그)** |
| 도형 되돌리기/다시(드래그 = 한 단계), Enter 후 기록 초기화 | O | O | 미검증 |
| 도형 고르기 전 숨김, Station 생성 시 숨김 | O | O | 미검증 |
| Enter 직후 외곽선만, 살아 있는 Base Mesh 동결 | O | O | **미검증 (화면)** |
| Station 핸들 실행 취소 단계 | O | O (기록 시점) | **미검증** |
| Stick to Surface(기울어진 면 법선, 바닥 묻힘, 구면 더 깊게, 끄면 예전) | O | O | 미검증 |
| 아이콘 버튼 타일, 왼쪽 툴 메뉴 격자 | O | O (그리기 호출) | **미검증 (모양)** |
| 아이콘 크기 파일 저장/읽기 | O | O | 미검증 (재시작) |

## 0.14.2 결과: 26개 파일, 1260 / 1260 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 설정 3개(기본 1.0), 프리셋 버튼 | O | O | 미검증 |
| 썸네일 전부 Panel Icons 적용(소스 검사) | O | O | **미검증 (화면)** |
| 아래 툴바 크기·간격·가운데 정렬 | O | O | **미검증 (화면)** |
| 핸들 크기 배율 | O | X (그리기 불가) | **미검증** |

## 0.14.1 결과: 25개 파일, 1247 / 1247 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 스케치 합치기/구멍/노치/두 조각/섬/전부 빼기/모서리 공유 | O | O | 미검증 |
| 획 → 스케치(메시 안 생김), Alt 획 = 빼기, Backspace | O | O (가짜 이벤트) | 미검증 |
| Enter = 라이브 Base Mesh(부피 정확, 구멍 저장, 프로필 변경 재생성) | O | O | 미검증 |
| Alt+Enter = 아래 메시에 포켓, Esc = 지우기, 빈 스케치 Enter 거부 | O | O | 미검증 |
| Sketch First 끔 = 예전 즉시 생성 / Alt 커터 | O | O | 미검증 |
| 주황색 스케치 그리기 | O | X (그리기 불가) | **미검증** |

## 0.14.0 결과: 24개 파일, 1219 / 1219 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 6가지 도형 형상(닫힘, 바깥 방향, 크기), 알약 부피 | O | O | 미검증 |
| 비대칭 크기 조절(반대 면 고정), 핸들 배치, 표면 정렬 | O | O | **미검증 (드래그)** |
| Enter 합치기(겹친 메시 / 없으면 새 오브젝트), 활성 오브젝트 우선 | O | O | 미검증 |
| Alt+Enter 빼기, 안 닿으면 변경 없음, Chamfer 이음새 | O | O | 미검증 |
| 라이브 Station Primitive 동결 후 빼기 | O | O | 미검증 |
| 반투명 그리기 / Alt 빨간색 / 클릭 이동 | O | X (그리기 불가) | **미검증** |
| 스탬프 커서 = 마우스 위치 | O | O (좌표만) | **미검증 (화면)** |
| 툴바 툴팁 = 버튼 이름, 이름 표시 기본 켜짐 | O | O | 미검증 |
| 패널·RMB 메뉴 도형 격자 | O | O (그리기 호출만) | **미검증 (모양)** |

## 0.13.2 결과: 23개 파일, 1172 / 1172 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Curved Plate (정점 수, 크라운 높이, 두께 일정, 높은 크라운) | O | O | 미검증 |
| 아머 5종 (닫힌 쉘, 경고 없음, 사람 크기, Blender 생성·편집) | O | O | 미검증 |

## 0.13.1 결과: 22개 파일, 1152 / 1152 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 옆으로 꺾기(±90°, 평평 유지, 닫힌 솔리드) | O | O | 미검증 |
| Fold / Tight / Band (Tight 90° 경고 없음) | O | O | 미검증 |
| 지점별 단면(정점 수 동일, 중간 링 = 평균, 박스→원 닫힌 솔리드) | O | O | 미검증 |
| 방향 버튼, Left = Right, 구간 삽입(끝점 유지) | O | O | 미검증 |
| 핸들 배치(점/+/다이얼/화살표), 다이얼 라디안↔도, 대칭 폭 핸들 | O | O | **미검증 (드래그)** |
| Mirror 라이브 유지 · Apply 시 동결 | O | O | 미검증 |

## 0.13.0 결과: 21개 파일, 1124 / 1124 통과
로그 `tests/test_log_bpy501_v0130.txt`, ZIP `dist/mecha_lab-0.13.0.zip` (sha256 `a9dba3e703b9d92e5f0cbd761033fb0f663bfe871f1a857641868192b83133f9`).
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 단면 7종 · 비대칭 · 릿지 (정점 수 고정, 값 검증) | O | O | 미검증 |
| 지점 사슬 30°+45°, 시나리오 E(앞 지점 수정 후 뒤 상대각·값 유지) | O | O | 미검증 |
| 접힘 마이터(부피 보존), 감싸기 200°, 자동 세그먼트, 반경 보정 경고, Step/Smooth, 뾰족 끝 | O | O | 미검증 |
| 프리셋 6개 메시 유효성 | O | O | 미검증 |
| Blender: 생성·실시간 재생성·지점 추가/삭제/이동·Shell·저장 후 재편집·Cut/Boolean 동결·Apply·패널 그리기 | O | O | **미검증** |
| 뷰포트 핸들 | 없음 | — | — |

## 0.12.0 결과: 20개 파일, 1074 / 1074 통과
로그 `tests/test_log_bpy501_v0120.txt`, ZIP `dist/mecha_lab-0.12.0.zip` (sha256 `270841f19e16687320f5e91e0567a7e5b6b414dd5407e8228a1140304417c7fe`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 자동 대상 / 선택만 (Cut·Split·Lasso, 잠금·와이어 제외, 원근 뷰) | O | O | 미검증 |
| T 토글, 헤더 토글 | O | 키맵 등록 | 미검증 |
| Q 파이 / Shift+Q | O | 키맵·상태 로직 (팝업 표시는 불가) | **미검증** |
| 하단 툴바 (기즈모 버튼, 크기, 이름 표시) | O | 등록·아이콘·배치 계산 (그리기 불가) | **미검증** |
| V/N 해제 | O | O | 미검증 |
| 기존 0.11.x 테스트 | — | 키 변경에 맞춰 3항목 수정 후 통과 | — |

## 0.11.3 결과: 19개 파일, 1046 / 1046 통과
로그 `tests/test_log_bpy501_v0113.txt`, ZIP `dist/mecha_lab-0.11.3.zip` (sha256 `deed2943d3d8276a383cdf338455d393e508cf337c6d42e01a1f98c9604e2c37`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 스탬프 도형 6종 (로드·정규화·실제 Cut) | O | O | 미검증 (아이콘 표시) |
| V / N / F 단축키 | O | 등록만 | **미검증** |
| Ctrl+Z 후 도형·도구 유지 | O | 복원 함수 O (실제 Undo는 headless 불가) | **미검증** |
| Cable → Mesh | O | O | 미검증 |
| Curve Lasso 직선 시작 / 클릭 순환 / 핸들 | O | O | 미검증 |
| Lean Mirror (축 선택, ±방향, Shift 추가, Enter 적용, Esc 복구) | O | O (가짜 이벤트) | **미검증** (오버레이·실제 마우스) |
| Radial Array 충돌 | — | 재현 안 됨 | **미해결 (crash 로그 필요)** |

## 0.11.2 결과: 18개 파일, 1012 / 1012 통과
로그 `tests/test_log_bpy501_v0112.txt`, ZIP `dist/mecha_lab-0.11.2.zip` (sha256 `000db2d3d84a0215dcfd1b55fcd296e59267c1e091a2be5d04af7593676c0aa5`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 실패 메시지 진단(덮는 정점 수·픽셀·뷰·Alt·버전) | O | O (전체 덮음 / Alt 빗나감) | 미검증 |
| Edit Mode에서 Cut / Split | O | O | 미검증 |
| Self Test 실제 3D View 투영 Cut / Alt Cut / Split | O | O (bpy의 실제 RegionView3D 1574x954 원근 + 대역 원근/직교) | 사용자 실행 필요 |
| 일반 Cube "whole object" | — | 재현 안 됨 | **미해결 (사용자 메시지 필요)** |

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
