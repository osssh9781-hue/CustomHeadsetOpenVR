# 최종 결정 사항 (2026-10-13 대화 기준) — 이전 문서보다 우선

**UI의 최종 중심은 Blender 상단의 `MECHA LAB` Workspace 탭입니다.** 사용자가 기존 Layout/Modeling/Sculpting 옆에 새 작업공간 탭을 추가해도 좋다고 승인했습니다. 기존 N패널에 모든 기능을 길게 늘어놓거나 Space 팝업 하나에만 의존하는 방식은 더 이상 선호안이 아닙니다.

### 3개 역할은 절대 섞지 말 것
1. **전체 작업 도구(Tools)** — 전용 Workspace의 3D View **왼쪽 세로 목록/툴바**. `Cut`, `Split`, `Boolean`, `Smart Fuse`, `Mirror`를 명확히 별도 항목으로 상단 배치; 뒤에 `Mask`, `Array`, `Panel/Curve`, `Pose`, `Surface Conform`, `Assets`, `Remesh`. 큼직한 아이콘과 이름. `Space`를 누르면 이 전체 도구 목록의 큰 아이콘 팝업(보조 접근 수단). Space가 어렵다면 왼쪽 목록은 반드시 계속 제공.
2. **공통 도형/브러시(Brush/Shape)** — 3D View **왼쪽 위 작은 팔레트**. `Lasso`, `Curve Lasso`, `Rectangle`, `Circle`, `Ellipse`, `Brush Stroke`와 사용자 제작 **이미지 썸네일 Custom Cut Shapes**. Cut/Split/Mask/Panel/Curve가 이 동일한 선택 시스템을 공유. 개별 `Random Polygon` 항목은 삭제. '클릭으로 자유롭게 꼭짓점을 만드는 Lasso'가 그 역할.
3. **현재 도구 세부 설정(Contextual Properties)** — 3D View **오른쪽**에는 선택된 도구 한 개의 Width/Depth/Auto Apply/Edge Finish 등만 표시. 모든 도구 옵션을 한 번에 늘어놓지 말 것.

### 확정된 세부 행동
- `Cut`과 `Split`은 **별개 도구**. Cut은 기본 내부 삭제/바깥 유지, `Alt`로 반전. Split은 양쪽 보존 및 단면 Cap 옵션.
- 드로잉 입력: `Enter` 또는 LMB 더블클릭 확정, 연속 작업 유지; `Esc`는 현재 미완성 획만 취소; `Shift+클릭` 직선 스냅; Backspace 마지막 점; Undo/Redo는 매 컷 독립 기록.
- **RMB 한 번**은 현재 도구와 공통 Shape/Thumbnail Presets 팔레트, **RMB 더블클릭**은 도구 종료. 단/더블 충돌 없이 동작해야 함. 옵션 또는 메뉴 클릭 시 Esc를 강요하지 말 것.
- Curve Lasso/베지어 점 편집: 점 다시 누르기마다 `직각→약한 라운드→중간→강한→직각`, 핸들 시각 표시/드래그. 도형 모서리 Round/Chamfer와 절단된 실제 메쉬의 Edge Finish Bevel/Chamfer는 **서로 별개의 설정**.
- `Mask`도 같은 라쏘/커브/직사각/원/타원/Brush Stroke로 누적 페인팅. `Alt`로 차감; 보호·Cut·Split·Extract+Raise와 Weight/Pose에 사용.
- 사용자 PNG를 자체 벡터화 후 Custom Cut Shape로 등록해 이미지 썸네일로 재사용. 기존 voxel Alpha Boolean이나 3DCoat 3-View Sketch 복원 **금지**.
- 하나의 `MECHA LAB` Workspace에서만 커스텀 단축키 활성, 다른 Workspace에서는 일반 Blender 입력 유지. 사용자 변경 가능. 단축키 구현상 workspace 감지 + 명시적 Mecha Mode 이중 가드 권장.
- Core 기능( Cut/Boolean/Mirror/Array ) 손상 금지, 느린 전체 Boolean을 마우스 이동마다 실행하지 말 것.

### Workspace 영속성/설치
- Workspace는 사용자 `.blend`/Startup 환경과 연결되는 성질이 있어 add-on만 설치했다고 무조건 영구 탭이 나타난다고 가정하지 말 것.
- `Create / Open MECHA LAB Workspace` 기능 또는 재현 가능한 UI 설치 절차 제공. 선택적으로 **사용자가 명시적으로 승인했을 때만** Startup File에 저장해 기본 Workspace로 유지.
- 현재 프로젝트의 레이아웃이나 작업공간을 파괴하지 말 것. 백업/복원 및 비활성화 경로 마련. Workspace 삭제 이후도 애드온 상태 안전해야 함.
