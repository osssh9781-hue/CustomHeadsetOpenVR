# Mecha Lab v0.5.9 — 도구 팝업 및 마스크 추출 시험 버전

## 추가·수정
- N > Mecha Lab > **MECHA LAB MODE**를 켜면 Space 도구 메뉴 및 B/C 단축키가 활성화됩니다. 끄면 Mecha Lab 단축키가 비활성화됩니다. **이 버전은 사용자 지정 키 설정 UI를 아직 제공하지 않습니다.**
- 3D 뷰포트에서 Space를 눌러 선택 가능한 도구 목록(Cut, Boolean, Smart Fuse, Mirror, Mask, Curve/Array 등)을 엽니다. 선택한 도구의 설정 패널만 오른쪽에 표시됩니다. N 패널의 **TOOLS | SPACE** 버튼으로도 메뉴를 열 수 있습니다. Blender 기본 Space 동작과 충돌할 수 있으므로 `MECHA LAB MODE`를 끄면 원래 단축키를 사용합니다.
- Cut 모달에서 Space는 더 이상 컷을 적용하지 않고 도구 메뉴로 이동합니다. Enter/더블클릭을 컷 확정에 사용할 수 있습니다. 오른쪽 메뉴로 클릭하면 현재 모달 입력이 종료되어 클릭을 전달하도록 변경했습니다.
- Boolean/일반 Cut의 모디파이어 적용 전 mesh.data.users>1이면 현재 오브젝트의 메쉬 데이터를 자동 복제합니다. 기존 linked duplicate 연동은 해당 오브젝트에 대해서만 끊깁니다.
- **MASK / EXTRACT**: Cut과 같은 Rectangle / Circle / Polygon / Polyline / Freehand 도형으로 현재 화면에서 보이는 메쉬 폴리곤에 **면 단위 마스크**를 누적해 기록합니다. Alt+드로잉은 지웁니다. 입력 선을 완성할 때만 마스크를 업데이트합니다. 현재 선택된 면을 마스크에 추가하는 버튼도 제공합니다.
- 마스크가 있는 메쉬에서 **EXTRACT & RAISE**를 누르면 마스크된 표면만 별도 오브젝트로 추출하고 `MCH_MaskExtrude` Solidify 모디파이어로 바깥 방향으로 돌출시킵니다. 두께는 패널 및 생성 결과 모디파이어에서 조절 가능합니다. 원본 메쉬를 보존합니다. 마스크는 Clear Mask로 삭제할 때까지 누적됩니다.

## 실행 방법
1. 기존 Mecha Lab을 비활성화·제거한 뒤 ZIP 파일을 Blender Preferences > Get Extensions > Install from Disk로 설치합니다.
2. N > Mecha Lab 에서 **MECHA LAB MODE** 토글을 켭니다.
3. 마우스를 3D 뷰포트에 두고 **Space**를 누르거나 `TOOLS | SPACE` 클릭 → `05 MASK / EXTRACT` 선택.
4. 대상 메쉬 선택 → 마스크 도형 선택 → `DRAW / ALT ERASE MASK`. Enter로 영역 확정, Alt로 영역 삭제, Q로 그리기 도구 종료.
5. `Raise Thickness` 조절 → `EXTRACT & RAISE`. 별도 메쉬로 솟은 결과가 생성됩니다.

## 제한사항 — 중요
- **Mask Protect(Cut/Boolean 영향 차단)는 아직 미구현입니다.** v0.5.9의 마스크는 표면 면 단위 선택, 추출 및 돌출용입니다.
- 마스크는 **원본 메시의 면 단위**로 저장되므로 낮은 폴리곤 밀도에서는 경계가 울퉁불퉁합니다. Cut 도형과 정확히 같은 표면 경계를 분할하는 알고리즘은 아닙니다.
- Space 팝업의 운영체제·Blender 5.0.2 GUI 키 입력과 모달 상태 전환은 별도 실사용 검증이 필요합니다. Blender 5.2.2 headless bpy에서 애드온 등록, 메뉴 클래스 등록, UI 도구 선택 상태, 마스크 추출과 Solidify 결과의 매니폴드 상태, 멀티유저 메쉬 모디파이어 적용을 검증했습니다.
- Blender UI의 기본 Space 할당이 사용자 키맵에 의해 우선될 수 있습니다. 메뉴가 열리지 않으면 N 패널의 `TOOLS | SPACE` 버튼을 사용하거나 Edit > Preferences > Keymap에서 다른 Space 할당을 확인하세요.
- Smart Fuse의 사용자 화면 오류는 아직 재현·수정하지 않았습니다.
- Undo/Redo의 Cut 별 개별 기록, 사용자 지정 단축키 변경 UI, RGB/알파 자동 보정, Edge Finish 등의 이전 요구는 이번 패치 대상이 아닙니다.
