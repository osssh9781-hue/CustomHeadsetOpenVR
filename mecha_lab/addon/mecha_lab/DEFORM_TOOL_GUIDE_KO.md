# Mecha Lab v0.9.1 — Deform Tool

## 설치

1. Blender 5.x → Edit → Preferences → Get Extensions → ▼ → Install from Disk.
2. 이 ZIP을 선택해 설치. 기존 Mecha Lab v0.9.0은 먼저 비활성화/제거. Blender를 재시작한 뒤 확인.
3. `MECHA LAB` Workspace → 왼쪽 도구 목록 **Deform** 또는 Space 팝업 → Deform (코드 내부 도구 ID는 기존 저장 파일과 호환을 위해 `POSE` 유지).
4. 오른쪽 Mecha Lab 패널에서 설정. 다른 Workspace도 영향을 받는지 실제 Blender GUI에서 확인 필요.

## Lattice Cage (다중 메쉬 Soft Deform)

1. 메쉬 한 개 이상 선택한 상태에서 **Create Lattice**.
2. 생성된 라티스가 활성 선택 상태가 됨. **X / Y / Z Points**에서 라티스 분할 수 변경 (2~32), **Strength**로 강도 조절.
3. **Edit Points** → 라티스 포인트를 클릭. **Move / Rotate / Scale** 버튼으로 Blender 기즈모를 바꾸거나 **G / R / S** 단축키 사용.
4. **Proportional Editing ON** (기본 설정). Falloff Radius 및 Falloff Type을 오른쪽에서 조절하거나 변형 중 휠로 영향 반경 변경. `O`를 누르면 Proportional Editing 토글.
5. **Exit Edit** → Reset, Apply 또는 Remove.

**중요:** 단일 라티스 포인트의 회전/스케일은 Blender 네이티브 Proportional Editing이 켜져 있어야 주변 포인트로 영향이 퍼짐. 실제 메쉬가 얼마나 매끄럽게 휘는지는 메쉬 정점 밀도에 좌우됨.

## Bend Curve / Twist / Taper (현재 단일 메쉬)

1. 메쉬 한 개를 활성 상태로 선택한 뒤 **Create Bend Curve**.
2. 모델의 가장 긴 로컬 축 방향으로 직선형 Bezier 커브가 생성되며 시작 시 메쉬 위치를 바꾸지 않음.
3. **Edit Points** → Bezier 포인트 G로 이동. Blender의 핸들/기즈모와 Proportional Editing 사용. **Ctrl+T**로 커브 포인트 Tilt, **Alt+S**로 Radius 제어 가능.
4. 오른쪽에서 **Twist**(-360°~360° 이상) 및 **Taper** 스케일과 **Curve Resolution** 조절.
5. Exit Edit → Reset, Apply 또는 Remove.

**주의:** Twist/Taper 슬라이더는 커브 각 포인트 Tilt/Radius를 경로에 따라 다시 설정하므로 수동으로 개별 조정한 포인트 값이 덮어써질 수 있음.

## Apply / Reset / Remove

- **Reset** = 컨트롤러를 최초 직선/원래 격자로 되돌림; 원본 메쉬를 파괴하지 않음.
- **Remove** = Deform 모디파이어와 컨트롤러를 제거. 원본 메쉬는 유지.
- **Apply (bake stack)** = Deform 앞에 있는 모디파이어도 함께 평가/베이크해서 *현재 최종 변형 모습을 유지*. Deform 뒤의 모디파이어는 계속 라이브로 남음. `Alt+D`로 공유된 다른 메쉬를 건드리지 않음. **모디파이어가 있는 작업은 먼저 .blend를 저장하거나 복제해 두는 게 안전함.**
- Shape Keys는 안전을 위해 Apply가 차단됨.

## 구현되지 않은 기능 / 남은 위험

- **Rigid Deform**: 개별 파츠의 형태를 유지하면서 오브젝트들을 이동·회전시키는 모드. 아직 미구현.
- ZBrush처럼 3D 공간에서 직접 조작하는 **전용 커스텀 기즈모**는 미구현. Blender 기본 Transform Gizmo 사용.
- **Proxy Cage / Mesh Deform 바인딩**은 미구현. 현재는 Blender 기본 Lattice modifier로 원본 정점에 변형 적용.
- Bend Curve는 단일 메쉬 대상. Lattice만 다중 메쉬 동시 적용 지원.
- 실제 Windows 11 + Blender 5.0.2 그래픽 UI, 마우스 조작 및 스페이스 팝업은 미검증. Linux bpy 5.2.2 헤드리스 테스트만 실행함.
