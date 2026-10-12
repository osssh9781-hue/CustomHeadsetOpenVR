# Test Report — Mecha Lab 0.7.0

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 모듈 **5.0.1** (build a3db93c5b259), PyPI wheel, **headless / background** |
| Python | 3.11.17 |
| OS | Linux 6.18 (클라우드 컨테이너) |
| 사용자 목표 환경 | Windows 11 + Blender **5.0.2 GUI** — **이번에 실행 불가 (GUI 없음)** |
| 사용자 설정 | 테스트는 `BLENDER_USER_*`를 임시 폴더로 지정해 실행 (실제 사용자 설정/Startup 미사용) |

명령: `<bpy가 설치된 python> tests/run_all.py` · 로그: `tests/test_log_bpy501.txt`
ZIP: `dist/mecha_lab-0.7.0.zip` (sha256 `95bf71e4bee9b31ec28f279e5258a20b24369327eb80d8ad80703ab612b56fc7`)

## 결과 요약: 358 / 358 통과

| 파일 | 수준 | 항목 | 내용 |
|---|---|---|---|
| test_register.py | 정적/등록 | 11 | 등록·해제 2회 반복, 잔여 클래스 없음, **모든 아이콘 이름이 5.0 enum에 존재**, v0.5.9의 잘못된 아이콘(`MOD_NODES`) 검출 |
| test_ui_draw.py | 등록 + UI 로직 | 79 | 모든 패널 draw를 검증용 가짜 layout으로 실행: prop 이름, enum 값, 연산자 ID/속성, 아이콘. 14개 도구 × Workspace 안/밖 × Shape별, 팔레트, 팝업, 단축키 poll 범위, Smart Fuse 라이브 패널 |
| test_cut_geometry.py | headless 기하 | 85 | 7개 Shape 컷 manifold, 부피 정확성, Alt 반전, Split(+Cap OFF), Edge Finish가 원래 모서리 불변, Alt+D 정책 2종, v0.5.9 multi-user 회귀, 모디파이어 스택 보존, 실패 시 무변경(교차 없음/자기교차/전체삭제/셰이프키), 직선·폴리라인 컷, 비균일 스케일+경사 뷰, **원근 frustum**, From Surface 깊이, 원기둥/구/열린 메쉬, 다중 대상, Live 모드+확정, Mask, Smart Fuse(겹침 성공, 떨어짐·접촉 안전 거부) |
| test_png_shapes.py | headless 기하 | 85 | 십자·링·25홀 벤트·1px 슬롯·대각 접촉·체커보드·구멍 속 섬·노이즈·계단 마스크: 교차 없음, 정점 공유 없음, 관통/포켓 컷 manifold. 실제 PNG 파일 import, schema-1 자동 업그레이드 |
| test_stroke_events.py | **시뮬레이션 이벤트** | 41 | 실제 연산자와 같은 `StrokeLogic`에 가짜 이벤트 주입: 더블클릭 확정·점 중복 없음, 획당 FINISHED 1회, Ctrl+Z/Shift+Z/Backspace, Esc, 뷰포트 밖 pass-through, Shape/도구 변경 시 폐기, RMB 단일(간격 후 팝업)/더블(종료)/두 번 PRESS, Space, 드래그/클릭 구분, Alt, 2점 측면 선택, Split, Curve Lasso 라운드 순환, 실패 시 CANCELLED, RMB 게이트 |
| test_workspace_data.py | headless 데이터 | 14 | 화면 설정 함수(영역 배치 불변), 태그 감지, 등록이 Workspace를 만들지 않음, 키맵 항목이 모두 게이트 연산자, 해제/재등록 시 키 잔여·중복 없음 |
| test_legacy_features.py | headless 연산자 | 26 | Mirror 생성/적용(Alt+D), Radial 생성/확정/Boolean, Boolean Union/Intersect, Slice, Remesh, Mask Extract, Surface Conform, 이전 연산자 ID |
| test_zip_install.py | 설치 | 9 | `extensions.package_install_files`로 ZIP 설치·활성화, 환경설정 등록, 비활성화 시 단축키 제거, 재활성화 |
| test_performance.py | 성능(정보) | 8 | 아래 표 |

### v0.5.9 재현 결과 (같은 환경)
- Mirror Apply on Alt+D 메쉬: `Modifiers cannot be applied to multi-user data` — **재현** (스크린샷 02와 동일). 0.7.0 통과.
- Smart Fuse 라이브 패널: 아이콘 `MOD_NODES`가 5.0에 없음 — **재현**(정적 검사). 0.7.0 수정.
- PNG 대각 접촉/체커보드 마스크: `Raster silhouette created non-manifold cutter` — **재현**. 0.7.0 통과.
- PNG "Boolean result is non-manifold"(스크린샷 01 문구): 깨끗한 큐브·구·원기둥에서는 **재현 안 됨**.

### 성능 (headless, 1회 측정, 원형 64분할 관통 컷, Auto = Manifold→Exact)
| 면 수 | Auto (ms) | Manifold (ms) |
|---|---|---|
| 320 | 14 | 15 |
| 5,120 | 58 | 58 |
| 20,480 | 116 | 117 |
| 81,920 | 490 | 436 |

(Exact 단독은 81,920면에서 약 945ms였음. 1M 면은 측정하지 않음. GUI 드로잉 지연은 측정 안 함.)

## NOT TESTED (GUI 필요) — `GUI_TEST_CHECKLIST_KO.md`
Workspace 생성/영역 분할/기본 도구 지정, 왼쪽 도구 목록 실제 표시, Tool Header 팔레트 표시·클릭, 실제 이벤트 순서와
더블클릭 타이밍, RMB 팝업 위치, Space와 다른 키맵 충돌, WorkSpaceTool 키맵 우선순위, 오버레이 드로잉, GPU 백엔드별
선 두께, Windows 경로/권한, Blender 5.0.2 고유 차이, 실제 사용자 .blend 파일.
