# Claude Code에 보내는 복사·붙여넣기 메시지

당신은 Blender Python API / BMesh / Geometry Nodes / WorkspaceTool / Blender UI / Modal Operator / Undo/Redo / GPU Overlay에 숙련된 엔지니어입니다.

첨부한 폴더 `MechaLab_ClaudeCode_Workspace_Handoff`를 Claude Code의 프로젝트 디렉터리로 열고 `CLAUDE.md`와 `START_HERE_KO.md`부터 읽어주세요. `docs/00_LATEST_USER_DECISIONS_KO.md` 및 `docs/01_WORKSPACE_UIUX_KO.md`가 UI/UX 최우선 최신 사양입니다.

### 이번 작업의 가장 중요한 새 결정
사용자는 기존의 긴 Blender N패널이나 Space 팝업 하나에 의존하는 방식 대신 Blender 상단 Layout/Modeling/Sculpting처럼 **`MECHA LAB` 전용 Workspace 탭**을 만드는 방식을 승인했습니다.

Workspace 안에서 **(1) 왼쪽 큰 아이콘+이름의 Tool 목록(Cut, Split, Boolean, Smart Fuse, Mirror... 순서), (2) 뷰포트 왼쪽 위 모든 툴에 공통인 Shape/Brush 팔레트(Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Brush Stroke + Custom PNG Vector Shapes), (3) 오른쪽에는 현재 선택 Tool의 설정만** 보이게 구현해 주세요.

Space를 누르면 위 전체 Tool 목록과 같은 큰 아이콘 메뉴가 열리게 하고, Cut 작업 중 RMB 한 번은 전체 Tool이 아니라 **공통 Shape/Thumbnail preset 팝업**, RMB 더블은 도구 종료입니다. Space가 Blender 5.0.2에서 충돌하면 반드시 좌측 고정 Tool 목록으로 모든 기능을 쓸 수 있도록 하세요. 다른 Workspace에서는 Blender 원래 단축키가 유지돼야 합니다.

### 심각한 실제 버그와 우선순위
- Cut 중 `Ctrl+Z`가 먹지 않고 메뉴/도형 변경 때 `Esc`가 필요합니다. 독립 Undo/Redo 및 모달 이벤트 통과/도구 전환부터 해결하세요.
- PNG Vector Cut는 `Boolean result is non-manifold` 오류와 지저분한 면을 실제 사용자 화면에서 보였습니다. 다양한 concave/holes/stamps에 대해 watertight cutter 및 안전한 failure handling을 구현하세요.
- 공유 메쉬(`Alt+D`)에서 Modifier Apply가 실패했습니다. 안전한 데이터 복사 + rollback이 필요합니다.
- Smart Fuse는 사용자 환경에서 오류 제보. 실제 재현하고 할 수 있는 부분/한계를 명확히 구분하세요.
- Cut과 Split을 별도 Tool로 분리하고, Edge Finish Bevel/Chamfer는 **새 절단 엣지만** 지정. Lasso 도형의 둥근 모서리와 혼동하지 마세요.
- Mask는 누적 도형 페인팅/Alt 지우기/Protect/Cut/Split/Extract & Raise/Weight Pose를 요청했습니다. 현재 코드의 면 단위 Mask는 아직 실제 Cut 보호를 못 합니다.
- Blender 5.0.2 Windows가 실제 사용 환경입니다. 이전 headless bpy 5.2.2에서 등록한 사실만으로 GUI 기능이 동작한다고 주장하지 마세요.

### 소스 원칙과 deliverables
`source/RELEASE_v0_5_9/mecha_lab/`가 최종 *배포* 베이스입니다. `source/WIP_v0_6_0_UNVERIFIED/`는 미출시 초안이므로, 꼭 읽되 신뢰할 수 있는 완성본으로 간주하지 말아주세요. 기존 코드/버전을 덮어쓰지 마세요.

1. 소스를 읽고 **구현된 기능 / 부분 구현 / 미구현 / 재현 버그**를 분리하여 짧게 보고.
2. `MECHA LAB` Workspace + 공통 Brush Palette + Contextual right panel + left Tool list의 **실행 가능한 MVP**를 우선 개발하고, Cut modal/Undo/Space/UI 클릭 문제를 고치세요.
3. 가능하면 코드와 별도 Blender Extension ZIP, Workspace 생성/복원 절차 또는 Template, 테스트 스크립트/로그, `CHANGELOG.md`, `KNOWN_LIMITATIONS.md`, 다음 작업자를 위한 `RETURN_HANDOFF.md`를 만들어 주세요.
4. 작업이 많으면 **P0 기능을 실제로 안정화한 결과부터 먼저 제출**하고 나머지는 P1/P2 백로그로 남기세요. 작동하지 않는 기능을 완성이라고 쓰지 마세요.
5. 질문 없이 진행 가능한 설계는 진행하되, 실제 Blender 5.0.2 GUI에 접근할 수 없는 경우 해당 항목을 `NOT TESTED`로 명시하세요. 사용자 파일과 Startup File은 사용자의 명시적 허락 없이 수정하지 마세요.

최종 목표는 Blender 안에서 ZBrush/3DCoat처럼 빠르고 편하게 **Cut / Split / Mask / Boolean을 공통 브러시로 사용하는 실무용 메카닉 툴**입니다. 디자인 문서가 아니라 실제 실행 가능한 코드와 검증 결과가 필요합니다.
