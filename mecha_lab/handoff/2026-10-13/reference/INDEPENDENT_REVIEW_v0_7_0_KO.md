# Mecha Lab 0.7.0 — ChatGPT 독립 교차 점검 (2026-10-13)

## 범위와 주의
- 사용자 제공 `mecha_lab-0.7.0.zip`, `test_report.md`, `KNOWN_LIMITATIONS.md`, `RETURN_HANDOFF.md`를 검토했다.
- **Claude의 358/358 통과는 Claude 제공 보고서의 기록**이며, 제공된 설치 ZIP에는 `tests/`가 없어 358개 전체를 독립 재실행하지 않았다.
- 독립 테스트 환경: Linux headless Python 3.13.5 + `bpy 5.2.2 LTS`. 사용자의 실제 Windows 11 / Blender 5.0.2 GUI와 다르다.

## 실제 수행한 점검
1. 제공 ZIP SHA-256이 Claude 보고서 값(`95bf71e4bee9b31ec28f279e5258a20b24369327eb80d8ad80703ab612b56fc7`)과 일치.
2. ZIP 안 Python 12개 모듈 모두 AST 구문 분석 통과.
3. `bpy 5.2.2`에서 소스 패키지 import, `register()`, `unregister()` 정상.
4. 두 큐브 Boolean Difference: `FINISHED`, 결과 닫힘(비매니폴드 엣지 0), 계산된 부피 약 3.2.
5. Alt+D 식 공유 메쉬의 한 오브젝트 Boolean Difference: `FINISHED`, 공유 데이터 분리됨. 다른 복제본의 원래 6면 유지, 대상 12면.
6. 두 겹친 큐브 Smart Fuse 생성: `FINISHED`, live 활성화, 4개 관련 모디파이어 생성. 복잡 형상 품질/Confirm은 이번에 별도 검증하지 않음.

## 보완 또는 사용자 GUI 확인이 필요한 곳
- **P0: Workspace 생성/화면 분할:** `workspace_ui.py`의 `workspace.duplicate`, 타이머 기반 `screen.area_split`, Properties Tool 영역 배치가 실제 5.0.2에서 정상 동작하는지. `MCH_PT_tool_list`는 `bl_space_type='VIEW_3D'`이면서 `poll`에서 Properties 영역을 요구하는 특수한 연결에 의존. 왼쪽 도구 목록이 안 보일 가능성 있으므로 직접 확인 필요. Sidebar fallback은 있음.
- **P0: 실제 마우스/키보드 이벤트:** Space, RMB 단일/더블, 좌클릭 더블, 메뉴 클릭 시 패스스루, Ctrl+Z를 GUI에서 반드시 검증해야 함. headless의 상태 머신 시뮬레이션은 GUI 이벤트 우선순위를 증명하지 않음.
- **P0: 사용자의 모델 테스트:** 기존 스크린샷의 PNG 비매니폴드 오류와 Smart Fuse 오류를 사용자의 원본 .blend 복사본으로 재현/확인. 깨끗한 큐브만으로 일반화 불가.
- **P1: Mask 실제 보호/정확 윤곽**, Pose, FBX 에셋 커터는 미구현 상태. `mask_tools.py`의 면 단위 마스크는 Cut/Boolean을 막지 못함.
- **P1: Radial Array의 개별 복제본 회전**은 수정하지 않았으며, `Scene.mch_settings.radial_follow` 기본값이 True. 사용자가 보고한 로컬 방향 회전 문제의 원인 후보임.
- **P1: Curve Lasso 핸들 편집은 완전한 독립 Bezier 핸들이 아닌 대칭 라운드 형태**, PNG 윤곽도 Chaikin/RDP 기반이며 완전한 벡터 베지어 피팅이 아님.
- **P2: 원본 백업·재현성:** 작업물에 사용 전 새 .blend에서 테스트. Startup File 저장은 확인 전 실행 금지.

## 우선 다음 단계
1. Blender 5.0.2에서 설치하고 새 General 파일을 만든 뒤 Workspace, Tool Header, 왼쪽 도구 목록 확인.
2. Cut (Rectangle) 3회 → Ctrl+Z 3회, Space, 우클릭 단일/더블, 사이드바 값을 획 중 변경하는 행동 확인.
3. Cut PNG 스탬프(십자/구멍/슬롯), Smart Fuse(겹침/비겹침), Alt+D Boolean 확인.
4. 실패 시 GUI 화면 및 Window > Toggle System Console의 전체 traceback 확보.
5. GUI 확인 후 0.7.1 수정 범위 결정. 불완전한 상태로 기존 블렌드 파일에 덮어쓰거나 애드온을 완제품으로 선언하지 않음.

## GitHub 주의
- Claude의 푸시 실패(403)는 GitHub 쓰기 권한 문제. 제공된 ZIP을 설치하거나 로컬에서 개발하는 데 GitHub 연결은 불필요.
- 오류 메시지에 등장한 `osssh9781-hue/CustomHeadsetOpenVR`가 실제 Mecha Lab용 저장소인지 확인하기 전에는 권한을 추가하거나 그 저장소에 애드온 코드를 밀어 넣지 말 것.
