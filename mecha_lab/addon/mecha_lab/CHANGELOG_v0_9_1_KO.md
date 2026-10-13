# Mecha Lab v0.9.1 (v0.9.0 기반 Deform MVP)

기존 v0.9.0의 Python 모듈은 제거하지 않음. 추가/변경: `deform_tools.py` 신규, `__init__.py` 등록, `tool_state.py`의 기존 Pose 자리 → Deform, `ui_tool_settings.py`의 Pose 더미 → 실제 패널, `blender_manifest.toml` 버전.

## 추가한 기능

- 다중 메쉬 **Create Lattice**: 선택 오브젝트의 계산된 월드 바운딩 박스를 중심으로 통합 케이지 생성; X/Y/Z 포인트 수(2~32)와 Strength 실시간 조절.
- **Edit Points**: 점 클릭 → 네이티브 Move / Rotate / Scale(G/R/S) 기즈모 선택, Proportional Editing, Falloff 반경 및 타입 설정.
- **Create Bend Curve**: 메시의 로컬 최장축으로 커브 생성, 초기 직선 커브 상태에서 메쉬의 이동/회전 없이 원본 형상 보존. 커브 컨트롤 점을 이동하면 휘어짐; Twist/Taper/Resolution 지원.
- **Reset / Apply / Remove**. Apply 시 앞쪽 모디파이어까지 합쳐 베이크하여 평가 결과를 유지, 뒤쪽 모디파이어는 보존. Alt+D 연결 원본은 그대로 유지.
- 이전 v0.9.0 Cut, Split, Curve Lasso, SubD Plane, Mesh Curve, Loft/Sweep, ZBrush Bridge 등 코드는 유지.

## 검증 환경/결과

- Linux bpy 5.2.2 (헤드리스, Windows Blender 5.0.2 GUI 미검증).
- Lattice 2개 메쉬 동시 적용, 분할 수 조절, reset, apply, 원본 유지.
- Rotate point + Proportional Editing: 주변 20개 케이지 점 변형.
- Bend Curve 3축 + 비회전 / 회전 오브젝트: Rest 형태 보존, 컨트롤 점 이동 시 변형, Twist/Taper 차이, Reset 원복.
- SubD → Deform, Deform → Bevel 복합 스택 Apply: Before/After 결과 일치, 다른 Alt+D 원본 미변경.
- UI 드로어 5개 상태 검사, 해당 UI 아이콘 유효성 검사, add-on register/unregister.

## 제한사항

- 메카닉 부품이 변형 없이 움직이는 진정한 Rigid Deform은 미구현. 이번 버전은 Soft Lattice와 1개 오브젝트용 Bend Curve.
- 직접 제작한 ZBrush식 커스텀 기즈모가 아니라 Blender 네이티브 변형 도구를 사용.
- Proxy Mesh Deform은 미구현. 원본 메쉬의 정점 수가 매우 적으면 부드러운 변형 한계 있음.
- Windows Blender 5.0.2 GUI에서 Workspace/단축키/기즈모 실제 조작은 아직 미검증.
