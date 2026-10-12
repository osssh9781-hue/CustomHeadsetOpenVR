# Test Report — Mecha Lab 0.8.0

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 5.0.1 (build a3db93c5b259), **headless / background** |
| Python / OS | 3.11 / Linux 6.18 (클라우드 컨테이너) |
| 사용자 환경 | Windows 11 + Blender **5.0.2 GUI** — **실행 안 됨** |
| 사용자 설정 | 테스트는 임시 `BLENDER_USER_*` 폴더 사용, 실제 설정·Startup 미사용 |

명령: `<bpy python> tests/run_all.py` · 로그: `tests/test_log_bpy501_v080.txt`
ZIP: `dist/mecha_lab-0.8.0.zip` (sha256 `0329fa2d9728dd57a1aae0026f6bdc7a8c19d54c4c0ca243c65fc1d835231a99`)

## 결과: 12개 파일, 544 / 544 통과
| 파일 | 항목 | 내용 |
|---|---|---|
| test_stroke_events.py | 68 | **가짜 이벤트로 실제 StrokeLogic 구동**: Esc→선택 복귀(획 폐기, 완료 컷 유지), 원거리 더블클릭 폐합(PRESS+DOUBLE 중복 점 없음, 0길이 엣지 없음), 트리플 클릭(2번째 확정/3번째 복귀, 점 편집 클릭은 미집계, 서로 다른 위치 연속 클릭은 복귀 안 함), Curve Lasso(기본 곡선, 해상도→샘플 수, 각/부드러움 토글, 핸들 드래그, 원거리 더블클릭 적용), Free Draw 연속 샘플(PRESS+119 MOVE+RELEASE), Lasso 드래그 그리기, Mask 열린 브러시, Base Mesh 모드(대상 없이 시작, RMB=프로필 팝업, 2점 거부), Ctrl+Z/Backspace, RMB 단일/더블, Space, 뷰포트 밖 pass-through, 게이트 |
| test_base_mesh.py | 83 | 4 프로필 × (직사각/오목 별) × (위/경사 뷰): 새 오브젝트 1개, manifold, 바깥 법선, 프로필별 서로 다른 솔리드. 실루엣 일치(<0.01px), 두께, Dome 피크·중간 높이·**뒤집힌 면 0개**·경계 높이, Bevel과 다름, Roundness 0/1, 링+섬(구멍 뚫림 확인), 표면 위 배치·대상 무변경, 자기교차/너무 작음/중복점 거부(오브젝트 미생성), 400점 고해상도 윤곽, Live 재생성(프로필·높이·오프셋), RMB 프로필 연산자, Freeze, 결과에 Cut 동작 |
| test_loft_surface.py | 22 | 열린 커브 2개(역방향 자동 정렬, 정렬 끄면 꼬임으로 입증), 3/4/2점·POLY+BEZIER 3섹션, Smoothness 효과, 모든 섹션 통과, **Live(커브 점·오브젝트 이동)**, 섹션 순서 변경, 닫힌 링+Cap=닫힌 솔리드, Thickness/Apply, Close Loft(토러스형), Twist, 열린/닫힌 혼합 거부, Sweep(Cap, 경로 추종, Live) |
| test_zbrush_bridge.py | 17 | 객체별 OBJ(Join 없음), 선택 복원, 매니페스트/ID, 변경 없으면 가져오지 않음, 변경된 것만 교체, 변환·모디파이어 유지, 백업 메쉬, 무편집 왕복 오차 <1e-5, 이름 변경 추적, 삭제 시 재생성, 파일 누락 보고, Alt+D 공유 메쉬 분리 |
| test_cut_geometry.py | 93 | 기존 0.7.0 기하 회귀 + 새 Curve Lasso 스플라인, 2D 라운드/챔퍼 모서리 Lasso·Rect 컷 |
| test_png_shapes.py | 85 | PNG 마스크 9종 벡터화/컷 (v0.5.9 비교 포함) |
| test_ui_draw.py | 105 | 17개 도구 × Workspace 안/밖 × Shape 패널 draw 검증(prop/enum/연산자/아이콘), 프로필 팝업, Live Base Mesh/Loft/ZBrush 패널, 네 도구 키맵에 Esc, Base Mesh RMB=PROFILE |
| test_legacy_features.py | 26 | Mirror/Radial/Boolean/Slice/Remesh/Mask Extract/Surface Conform/이전 연산자 ID |
| test_workspace_data.py | 17 | 화면 설정, 태그, 게이트 키맵, **Ortho Lock 강제 ORTHO + 파일 로드 시 타이머 재시작** |
| test_register.py | 11 | 등록/해제 2회, 모든 아이콘 이름 5.0 enum 존재 |
| test_zip_install.py | 9 | 확장 ZIP 설치·활성화·비활성화(단축키 제거)·재활성화 |
| test_performance.py | 8 | 320~82k 면 컷 시간(정보) |

## 기능별 상태 (요청 보고 형식)
| 기능 | 상태 |
|---|---|
| Esc → 선택 도구 | 구현됐으나 GUI 미검증 (상태기계 테스트 통과) |
| Lasso/Curve Lasso 원거리 더블클릭 자동 폐합, 중복점 방지 | 구현됐으나 GUI 미검증 |
| 트리플 클릭 선택 복귀(더블 확정과 분리) | 구현됐으나 GUI 미검증 (실제 OS 클릭 간격 미확인) |
| Curve Lasso 곡선 기본 + 핸들 | 구현(대칭 핸들), GUI 미검증 |
| Free Draw 연속 드로잉 / Mask 열린 스트로크 | 구현됐으나 GUI 미검증 |
| Outline Corners(2D) vs Edge Finish(3D) 분리 | 완료/실행 검증 (기하 headless) |
| Base Mesh Flat/Chamfer/Bevel/Dome, Live, 실패 안전 | 기하는 완료/실행 검증(headless). 드로잉·RMB 팝업은 GUI 미검증 |
| Base Mesh Surface Follow / Project | 미구현 |
| Loft / Sweep + Live | 부분 구현 (headless 검증, NURBS-like 폴리곤, 혼합 커브 불가) |
| ZBrush Bridge | 부분 구현 (OBJ 왕복 headless 검증, 실제 ZBrush 미검증, GoZ 미구현) |
| Workspace / 팔레트 / Space / 왼쪽 목록 | 0.7.0 그대로, GUI 미검증 |
| v0.7.1 Ortho Lock, v0.7.2 Mask/Bevel 진단 | 유지 (데이터 수준 테스트) |
| Mask Protect, Pose, FBX 커터 | 미구현 |

## NOT TESTED (GUI 필요)
`GUI_TEST_CHECKLIST_KO.md` 참고. headless 통과는 GUI 동작 인증이 아닙니다.
