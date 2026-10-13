# 0.14.0 — 반투명 도형 찍기 (먼저 읽어 주세요)

- Primitive 도구를 켜면 고른 도형이 **반투명**하게 나옵니다. 화살표 = 크기(한쪽 면만), 다이얼 = 회전, 가운데 링 = 이동.
- 메시를 클릭하면 도형이 그 표면으로 옮겨 갑니다. 오브젝트 선택은 Shift+클릭 / 드래그 / F.
- **Enter** = 겹친 메시에 합치기(아무것도 안 닿으면 새 오브젝트) · **Alt+Enter** = 빼기(Alt를 누르면 빨간색). 도형은 남아 계속 찍을 수 있습니다.
- 도형: Box / Cylinder / **Pill Cylinder**(단면이 알약) / Sphere / Cone / Capsule. 이음새: Hard / Chamfer / Smooth.
- 아래 내용은 예전 "라이브 파라메트릭 프리미티브"(패널 아래 접힌 칸)에 대한 설명입니다.

# Mecha Lab 0.9.2 — Parametric Primitive (베타)

## 새 기능

MECHA LAB Workspace에서 왼쪽 **Primitive** 도구를 선택합니다. 오른쪽 설정 패널의 **New Box**로 기본 박스를 만들거나 **Shape Picker**로 아래 종류를 선택합니다. Primitive 도구를 사용하는 동안 뷰포트 우클릭도 Shape Picker를 열도록 등록했습니다. Blender 기본 우클릭 키맵과 충돌하면 오른쪽 패널 버튼을 사용하세요.

| 종류 | 라이브 설정 |
|---|---|
| Box | Bottom X/Y, Top X/Y, Height(Z), Bevel, 중심 관통 구멍 |
| Cylinder | Top Radius, Bottom Radius, Height, Radial Segments, 중심 관통 구멍 |
| Sphere | Radius, Segments, Rings |
| Cone | Top Radius(기본 0), Bottom Radius, Height, Segments, 중심 관통 구멍 |
| Capsule | Radius, Total Length, Segments, Rings |

원형 프리미티브도 `Bevel Width / Segments`를 편집할 수 있습니다. 박스/원기둥/원뿔은 `Through Hole (Z)` 옵션으로 세로축 구멍을 만듭니다. 모서리 마감은 Geometry Nodes 뒤에 Blender 기본 Bevel 모디파이어로 적용됩니다.

## 사용 순서

1. 기존 Mecha Lab을 비활성화하고 `mecha_lab-0.9.2_primitives_beta.zip`를 Install from Disk로 설치합니다.
2. 상단 **MECHA LAB** 작업공간을 열고 **Primitive** 도구를 선택합니다.
3. **New Box** 또는 **Shape Picker (RMB)**로 도형 생성.
4. 오른쪽 슬라이더를 움직이면 선택된 도형이 즉시 갱신됩니다.
5. 완성 후 **APPLY TO MESH**를 누르면 Geometry Nodes 및 Bevel 결과를 일반 메쉬로 변환합니다.

일반적인 오브젝트 Move/Rotate/Scale과 별도로 원본 파라미터를 유지합니다. Alt+D 공유 복제본에서 다른 오브젝트의 노드 설정이 변경되지 않도록 노드 그룹을 분리합니다.

## 확인 결과 및 제한

- Linux Blender `bpy 5.2.2`에서 모듈 등록·해제, Box / Cylinder / Sphere / Cone / Capsule 생성, Box 테이퍼·관통 구멍, Cylinder 관통 구멍, Capsule 길이, 타입 변경, Apply, 공유 노드 그룹 분리를 검사했습니다.
- 단순 테스트의 모든 메쉬는 non-manifold edge 0개였습니다. 복잡한 극단값은 실패할 수 있습니다.
- Windows Blender 5.0.2 GUI의 실제 우클릭 이벤트, 패널 배치, Geometry Nodes의 모든 노드 호환성은 아직 미검증입니다.
- Capsule은 UV Sphere의 상·하반구를 벌려 몸통을 형성하는 베타 구현으로, 수학적으로 완벽히 일정한 반경의 CAD 캡슐은 아닙니다.
- 구멍은 Z축 **관통 구멍**이며, 가로 구멍이나 복수 구멍은 미구현입니다. 아주 큰 구멍 또는 자가교차하는 극단적인 파라미터 조합은 결과 검사가 필요합니다.
- 사용자가 기존 모디파이어를 Primitive 뒤에 추가한 후 Apply를 누르면 **현재 평가 결과 전체**가 하나의 일반 메쉬로 굳습니다. Apply 전에 별도로 파일을 저장하세요.

기존 Cut, Split, Base Mesh, SubD Plane, Deform, Loft 기능은 제거하지 않았습니다. 0.9.1 코드를 기준으로 신규 모듈과 UI 연결만 추가했습니다.
