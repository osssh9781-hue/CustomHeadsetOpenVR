# 프로젝트 설계 기준 및 기존 기능 보호

## UI 기본 구조
- `MECHA LAB` 전용 Blender Workspace 상단 탭.
- 왼쪽 도구 목록은 큰 아이콘+제목: Cut, Split, Boolean, Base Mesh, SubD Plane, Smart Fuse, Mirror, Radial, Primitive, Loft, Deform 등.
- 뷰포트 왼쪽 위는 **도구 공통** Shape Brush 선택: Lasso(직선 각), Curve Lasso(기본 곡선), Rectangle, Circle, Ellipse, Brush Stroke, PNG Custom Presets. 불필요한 Random Polygon 중복 제거.
- 오른쪽은 현재 선택 도구 옵션만. `Space` 전체 메뉴, `V` 핵심 6개 빠른 메뉴. RMB는 현재 도구 컨텍스트별 프리셋.
- Cut과 Split은 완전히 다른 도구이며 Shape Brush만 공유. 점 편집용 Curve Tool은 Curve Lasso와 별개.

## 기존 기능 현황과 범위
- v0.9.3 소스는 Cut/Split/Bevel/Chamfer, Boolean, Base Mesh 4 Profiles, SubD Plane(SIMPLE+CATMULL_CLARK+SOLIDIFY), Primitive 5 GN shapes, Deform Soft Lattice/Bend/Twist, Loft/Sweep, ZBrush OBJ round-trip, Mirror/Collection Mirror, Radial/Curve Array, PNG shape assets, Ortho Lock 등이 포함된 것으로 보임.
- '**소스에 구현이 있음**'은 '**사용자 Windows GUI에서 작동함**'과 다름. 특히 현재 Mirror/Loft/Smart Fuse/Curve는 사용자에게 고장 신고 있음.
- SubD Plane: Simple Subdivision 및 Catmull-Clark 슬라이더 동시에 독립 노출. Solidify 두께/오프셋, Apply All. 두 종류 사이 라디오 택일식 UI로 바꾸지 말 것.
- Radial: Rotate Each Copy 기본 OFF, 전체 및 개별 X/Y/Z 회전, 소스 로컬 방향 보존.
- 기존 ZBrush 브리지는 OBJ 왕복이며 GoZ라고 홍보하지 말 것. 자동 Join하지 않음.
- Deform Rigid Pose와 실제 Mask 보호 기능은 미완성으로 간주. 사용자 최신 요청인 Mask UI 비노출 우선.
- Smooth Curve Lasso는 기존 VECTOR→Smooth Curve Tool을 대체하지 않음.
- 폐쇄/오픈 커브의 서로 다른 의미와 입력(더블클릭 종료)이 겹치지 않도록 UI 문구를 명시.
- 현재 아티스트 목표는 **ZBrush 대형 크리처/메카 베이스→Blender에서 화면 위 직접 Cut/Boolean/Array/모디파이어 상세 작업**. 사용자 데이터 파괴와 UI 복잡화 최소화.

## 개발 원칙
- 사용자 .blend와 전역 Preferences/Startup File은 명시적 확인 없이 변경하지 않음.
- 모델/커터 원본과 Alt+D shared mesh 데이터 안전성 우선, 실패 시 롤백.
- 실시간 미리보기와 적용(Apply)을 분리, 무단 자동 적용은 Base Mesh 도구 자신의 생성 오브젝트 종료 시로 제한.
- 새 기능을 넣으면서 기존 Operator ID를 삭제하지 말 것(기존 저장 데이터/단축키 호환). 필요시 deprecated alias.
- 심각한 회귀가 생기면 기능을 새로 늘리기보다 안정화 먼저.

- **Boolean 선택 규칙 최종 확정:** 노란색 활성 오브젝트는 커터, 나머지 선택 오브젝트는 대상. 이전에 노란색을 대상으로 설명한 문서보다 이 항목을 우선.
- **Free Draw Stabilizer:** 실시간 Lazy Mouse 옵션 추가, 원래 다른 도형 브러시는 건드리지 않음.
