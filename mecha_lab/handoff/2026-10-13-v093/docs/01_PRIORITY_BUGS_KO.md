# P0 — 현재 사용자 제보된 고장/회귀

**각 항목은 사용자 보고이며 이 인수인계 작업에서 자체 재현한 버그가 아닙니다.** 먼저 Windows Blender 5.0.2 GUI에서 재현, 콘솔 로그 확보, 최소 재현 .blend 또는 독립 스크립트 생성 후 수정 바랍니다.

| ID | 기능 | 사용자 보고 | 요구되는 수정/검사 |
|---|---|---|---|
| B01 | Mirror | 관련 기능이 전부 먹통 | World/Local/Collection Mirror 생성·실시간 반영·Apply·Remove, 단일/다중 선택, 모디파이어 순서와 Context, 오류 UI 확인 |
| B02 | Loft | 기능이 작동하지 않음 | 최소 2개 커브→Loft, Sweep, 커브 편집 시 갱신, Apply, 실제 UI에서 활성 오브젝트 선택 규칙 검사 |
| B03 | Smart Fuse | 첫 실행만 성공, 이후 실패 | 반복 호출 5~10회, 노드 그룹/임시 객체 정리, 이전 컨트롤러/모디파이어 누수, 상태 초기화 확인 |
| B04 | Cut/Lasso | 시작점 근처가 아니면 더블클릭 확정이 작동하지 않음 | 뷰포트 아무 곳에서 좌클릭 더블클릭으로 닫고 실행; 시작점 근처 단일 클릭도 닫기; 길이 0인 마지막 변 생성 금지 |
| B05 | Mesh Curve/Panel Curve | 선이 직선/점만 나와 원하는 곡선이 나오지 않음 | `mch.draw_path` 등 기존 독립 Curve Tool 동작 확인; VECTOR 직선→기존 점 선택→Smooth/Bezier 전환 및 곡선 렌더/샘플 수 확인. Curve Lasso는 별도 유지 |
| B06 | Alpha / PNG Cut | 프리셋 드로잉 중 R키 회전 기능 사라짐 | 드로잉/스탬프 중 R로 형상 회전 모드 또는 기존 회전 동작 복구; 수치 각도와 미리보기/확정 확인; Blender 일반 R 동작과 모드별 충돌 방지 |
| B07 | Split Gap | Enter를 눌러야만 적용, 시작점을 클릭해도 확정 실패 | 시작점 클릭/더블클릭 어디서든/Enter 모두 똑같이 Gap Split 확정, 양쪽 Cap·베벨 유지 |
| B08 | Mask | 사용자 환경에서 계속 미작동 | Mask 도구·팝업·단축키를 UI에서 안전하게 숨기고 데이터 호환성 유지. 관련 코드 삭제·데이터 삭제 금지 |
| B09 | Add-on 등록 | `MCH_PG_Brush already registered` 오류 캡처 | 중복 설치/리로드/부분 register 실패 cleanup, 예외 발생시 class/props/keymap 일관성, disable/re-enable 순환 테스트 |
| B10 | Bevel | 폭 부족 / 때때로 생략 | Cut/Split 폭 상한 확대, clamp 중단 여부와 실제 적용 엣지 수 표시, Live/Apply 모드 일치 확인 |

**참고 코드:** `source/mecha_lab/cut_engine.py`, `base_mesh.py`, `mirror_tools.py`, `loft_surface.py`, `workspace_ui.py`, `ui_tool_settings.py`, `cut_presets.py`, `__init__.py` 등을 먼저 검토하십시오. 현재 버전 기능 보유 여부와 정상 동작은 별개입니다.

**중요 제약:** Shape Corner Chamfer/Round(그리는 2D 도형 모서리)와 Edge Finish Bevel/Chamfer(실제 3D 절단 경계)는 별개의 옵션입니다. 둘을 합치지 마십시오.
