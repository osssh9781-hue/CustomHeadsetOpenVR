# Workspace 기반 Mecha Lab UI/UX — 구현 지시

## 목표 레이아웃 (Blender 상단 Workspace 탭)

```text
[Layout] [Modeling] [Sculpting] [MECHA LAB] [UV Editing] ...
┌────────────────────────────────────────────────────────────────────┐
│ TOOLS (왼쪽)   │ BRUSH/SHAPE (뷰포트 왼쪽 위)          │ OPTIONS (오른쪽)│
│ [Cut]          │ [Lasso][Curve Lasso][Rect][Circle]    │ Cut Depth      │
│ [Split]        │ [Ellipse][Stroke][Custom Thumbnails]  │ Auto Apply     │
│ [Boolean]      ├───────────────────────────────────────┤ Edge Finish    │
│ [Smart Fuse]   │                                       │ Width/Segments │
│ [Mirror]       │              3D VIEWPORT              │ ...            │
│ [Mask]         │                                       │                │
│ [Array] ...    │                                       │                │
└────────────────────────────────────────────────────────────────────┘
Space → floating large-icon TOOL selector (same tools as left toolbar)
RMB while drawing → floating thumbnail SHAPE selector (NOT tool selector)
```

## 실제 Blender API/UX 설계 시 주의
- 상단의 `MECHA LAB`은 Blender `WorkSpace`, 일반 애드온 N패널 탭이 아닙니다. GUI 컨텍스트에서 기존 Workspace를 **복제/생성**하고 이름·지역 구성을 설정한 후 재사용 가능한 방식으로 구성하세요. 다른 Workspace의 레이아웃 변경 금지.
- Tool 목록은 `WorkSpaceTool`/3D View Toolbar(T-region) 또는 호환되는 Blender 네이티브 UI 패널/팝오버로 구현. 사용자 요구는 **큰 아이콘+읽을 수 있는 이름**; 텍스트만 나오거나 아이콘만 나오는 팝업은 수용 불가.
- 상단/왼쪽 위 공통 브러시 팔레트는 Blender Tool Header/Popover, 화면 고정 패널 등을 비교. 단순 GPU draw handler 출력만으로 클릭 UI가 생기는 것이 아니므로 native event handling과 hit testing을 정확히 처리하세요.
- 오른쪽 Sidebar(`N`)는 **현재 활성 Tool 하나의 설정만**. 모드 바꾸자마자 panel 상태 반영. Cut/Split 둘을 한 버튼으로 합치지 마세요.
- Space 팝업/단축키는 `context.workspace` 기반으로 활성/비활성화. Workspace 외부에서는 Blender 기본 입력 복원. Blender의 Space=Play Animation 설정, 타 애드온 키맵 충돌 체크.
- Blender 5.0.2 GUI가 없으면 Workspace 생성, 키 이벤트, 화면 배치, 메뉴 클릭/드로잉 모드의 정확한 작동은 반드시 미검증이라고 표시.

## 인터랙션 상태 머신 (추천)
IDLE → TOOL_ACTIVE_READY → DRAWING → EDITING_POINTS(optional) → CONFIRM/APPLY → TOOL_ACTIVE_READY.
TOOL_ACTIVE_READY/DRAWING 중 다른 Tool/Shape 옵션을 클릭하면 현재 미완료 stroke만 폐기하거나 안전하게 보존하고 새 상태로 즉시 이동. 모달이 패널 이벤트를 먹지 않도록 설계.

## Cut vs Split vs Shape 간 구분
- Cut: 현 Geometry에 Difference / (Alt 시 Intersection 유사) 적용. 기본 그린 영역 삭제. 한 도형 확정 뒤에도 도구 유지.
- Split: 그린 경계로 두 솔리드 생성, Cap/보존 옵션. N-패널 내 작은 'Split Both' 버튼과 혼동 금지.
- Shape Lasso: 사용자가 클릭한 점들로 만드는 **임의 외곽선**, 별도 Random Polygon 버튼 삭제.
- Curve Lasso: 동일 외곽선을 베지어 제어점으로 편집. Rectangle / Circle / Ellipse / Brush Stroke는 독립적인 프리셋.
- Brush/Shape 프리셋은 Cut, Split, Mask, Panel Line/Curve 등에서 재사용. 단 Tool마다 허용하지 않는 프리셋은 명확히 disabled + 설명.

## 데이터 설계(제안)
- Tool ID, Shape ID, per-tool properties, global brush profile, per-workspace enable state, hotkey mapping을 분리.
- PNG custom vector shapes: source PNG path/hash, normalized closed contours with hole/island hierarchy, preview PNG, editable Bezier data, import settings를 저장. .blend 전환 후에도 재사용.
- Scene/workspace level tool state vs add-on preferences distinction. Blender 파일 내 저장할 상태와 머신 전역 저장할 단축키/프리셋 라이브러리 위치를 분리.
- 핫키를 누른 채 모달에 갇히는 설계보다 네이티브 Tool 전환을 우선 검토. `Space`와 `Ctrl+Z`/RMB 이벤트 처리를 독립 시나리오로 검증.

## 수용 테스트
1. Blender 5.0.2에서 기존 `.blend`를 연 뒤 버튼 하나로 `MECHA LAB` Workspace 생성/전환. 기존 탭 변경 없음.
2. 탭 전환 시 전용 키맵 동작 범위가 바뀜. `Layout`으로 나오면 기본 Space, B/C 동작 복구.
3. 왼쪽 Cut / Split / Boolean / Smart Fuse / Mirror 도구 이름+큰 아이콘 표시.
4. 상단 왼쪽 shape palette 6종+썸네일, 선택하면 실제 동작 변화. 옵션 변경할 때 ESC 불필요.
5. 오른쪽에는 선택한 도구 설정 하나만. Cut/Split 독립.
6. `Space` 팝업의 아이콘과 이름 정상 표시 및 클릭 전환; GUI 테스트 실패하면 왼쪽 고정 도구가 동작하는 fallback 제공.
7. RMB 팝업은 shape 목록을 띄우며, RMB 더블은 exit; 실수로 popup 뒤에 더블 종료 못 하는 문제 없음.
8. Ctrl+Z/Redo, 연속 Cut, 메뉴 클릭 및 다른 편집기 클릭 정상.
9. 재실행/파일 저장·재오픈/탭 삭제·생성/애드온 disable 후에도 충돌·중복 핫키 없음.
