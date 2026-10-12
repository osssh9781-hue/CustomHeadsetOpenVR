# Mecha Lab v0.5.6 — Mirror 사용 설명서

기존 Claude v0.5.5 Hard Surface 개선 소스를 유지하고 Mirror 기능만 추가한 버전입니다.

## 설치

Blender `Edit → Preferences → Get Extensions → Install from Disk`에서 `mecha_lab_v0_5_6_mirror_bpy_tested.zip` 설치 → 활성화 → 3D View에서 `N` → `Mecha Lab` → **Mirror | World / Local / Collections**.

이전 Mecha Lab을 설치했다면 먼저 비활성화하거나 제거하세요. 같은 `mecha_lab` Extension ID를 사용합니다.

## 1. 월드 기준 미러 (World Mirror)

1. 메쉬 하나 또는 여러 개 선택.
2. `Axis Space = World` 지정.
3. `Mirror Plane Center = World Origin`이면 월드 X/Y/Z=0을 기준으로 미러합니다. `3D Cursor`를 선택하면 **현재 3D 커서 위치**를 통과하는 글로벌 축 평면을 사용합니다. 커서의 회전각은 무시합니다.
4. `X / Y / Z` 중 원하는 축 활성화 (여러 축 동시 가능).
5. `CREATE / UPDATE MIRROR` 클릭.
6. 비파괴 `MCH_Mirror` 모디파이어가 생성됩니다. 재설정 후 버튼을 다시 누르면 업데이트합니다. `Apply`로 확정하거나 `Remove`로 취소 가능합니다.

월드 미러는 고정된 월드 정렬 Empty를 미러 기준으로 사용하므로 **메쉬 오브젝트가 회전했거나 원점이 치우쳐 있어도 월드 기준으로 대칭**됩니다. Empty는 뷰포트에서 작은 좌표축으로 보일 수 있습니다.

`Bisect`는 축을 넘어선 원본 메쉬를 잘라내므로 사용 목적에 맞을 때만 켜세요. `Merge`, `Clipping`, `Merge Distance`도 제공합니다.

## 2. 로컬 기준 미러 (Local Mirror)

`Axis Space = Local` → 축 선택 → `CREATE / UPDATE MIRROR`. Blender 기본 Mirror 모디파이어처럼 각 오브젝트의 **자체 원점과 로컬 좌표축**을 사용합니다. Local로 전환하면 이전 월드 기준 Empty는 더 이상 참조하지 않으며 필요 없으면 자동으로 정리됩니다.

## 3. 컬렉션 전체 좌우 배치 (Collection Mirror)

메카닉 팔·다리·관절 여러 파츠를 컬렉션 단위로 배치할 때 사용합니다.

1. 월드 원점 부근에서 팔 등 여러 부품을 만들고 하나의 `ARM` 컬렉션에 넣습니다. 컬렉션의 `Instance Offset`은 보통 (0,0,0)으로 두면 관리하기 쉽습니다.
2. `Parts Collection`에서 `ARM`을 선택합니다.
3. `Pair Axis = X` 및 `Pair Center = World Origin`을 지정합니다.
4. **3D 커서를 장착할 위치**(예: 월드 X=3, Y=0, Z=1)로 옮긴 뒤 `CREATE COLLECTION PAIR` 클릭.
5. 생성되는 `MCH ARM - MASTER`(선택된 인스턴스)를 이동·회전·크기 조절하세요. `MCH ARM - MIRRORED` 인스턴스는 반대편으로 실시간 따라갑니다.
6. 원본 `ARM` 컬렉션 안의 파츠를 수정하면 **두 인스턴스 모두 함께 갱신**됩니다.

3D 커서가 미러 중심과 정확히 같으면 초기 위치가 겹치는 것을 방지하기 위해 `Start Offset` 값(기본 1m)만큼 마스터를 대칭축의 +방향으로 배치합니다.

- `Pair Center = 3D Cursor`는 *생성 시점*의 커서 위치를 대칭면으로 사용합니다. 이 경우에도 `Start Offset`만큼 벌려서 배치됩니다.
- `MCH ... - Symmetry Center`는 리그 기준 컨트롤입니다. 이 컨트롤을 회전하면 더 이상 글로벌 정렬 미러가 아니라 **회전한 기준 평면**을 쓰게 됩니다. 월드축 고정이 필요하면 피벗 회전을 건드리지 마세요.
- `MCH ... - Mirror Axis`는 반사 방향용 컨트롤입니다. 스케일을 임의 수정하지 마세요.
- `Remove This Mirror Rig`를 누르면 **자동 생성된 컨트롤 및 컬렉션 인스턴스만 삭제**하며, 원본 컬렉션의 메쉬와 오브젝트는 그대로 남습니다.
- 좌/우는 같은 원본을 참조하는 컬렉션 인스턴스입니다. 개별 인스턴스의 내부 부품을 편집하려면 원본 컬렉션을 편집하세요. 개별 파츠를 독립 메쉬로 바꾸는 자동 실체화는 이 버전에 포함되지 않습니다.

## 성능 및 주의사항

- 월드/로컬 미러는 Blender의 네이티브 `Mirror` 모디파이어를 사용합니다.
- 컬렉션 미러는 **메쉬 복사 없이** Collection Instance 2개와 Copy Transforms 제약을 사용합니다. 최종 메쉬로 변환하지 않는 동안 비교적 가볍습니다.
- 컬렉션의 원본 부품이 월드 원점에서 멀리 배치돼 있으면 Instance Offset 및 로컬 모델 배치에 따라 예상 위치가 달라질 수 있습니다.
- 컬렉션 미러의 반사 쪽은 **음수 스케일**을 사용합니다. 게임 엔진 익스포트나 노멀·탄젠트 처리 시 인스턴스 실체화 후 변환 적용과 표면 검사 등이 필요할 수 있습니다.
- Blender 5.2.2 Linux headless `bpy`에서 핵심 생성, 이동·회전 라이브 링크, 적용·제거, 3축 반사, 다중 메쉬를 테스트했습니다. UI 마우스 입력·FPS와 Blender 4.5 실제 실행은 별도 검증이 필요합니다.
