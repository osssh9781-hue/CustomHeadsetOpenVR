# 개발 요구사항 전체 (완료 상태를 의미하지 않음)

## P0 핵심 Cut / Split / 공통 스트로크
- Cut 즉시 적용, 클릭 추가 확인 불필요; 기본 안쪽 제거, Alt 누른 획은 안쪽 유지. 열린 선/닫힌 도형을 구분. Auto Apply ON(기본)/OFF(Live).
- 별개 Split: 두 결과 파츠 모두 남기기, Cap Cut 선택, 연속 분할.
- 공통 Shapes: Lasso(점찍기 자유 다각형), Curve Lasso(베지어 핸들), Rectangle, Circle, Ellipse, Brush Stroke 및 커스텀 프리셋. 이미지 썸네일 브라우저.
- Curve: 점 재클릭으로 직각→약곡률→중간→강→직각, 점 위치 이동, 양쪽 Bezier 핸들 직접 드래그; straight / curve 편집 모드. 세그먼트·해상도 및 흔들림 보정.
- Enter/LMB double: stroke 확정; Shift 직선/45도 스냅; Backspace undo last point; Esc only current stroke cancel; Ctrl+Z/Redo usable throughout and **one undo item per cut**.
- 메뉴 클릭, shape 전환 시 모달 종료/ESC 강요 금지, 연속 도구 유지. RMB single shape popup, RMB double tool exit.

## Boolean / Cut Edge Finish
- 두 객체 중 active(target)와 나머지(cutter). B 기본 Difference. Union/Intersect, independent cutter object, user-chosen auto apply, preserve/delete cutter, linked-mesh single-user or explicit consent.
- Asset Browser `.blend` object assets 또는 별도 FBX 파일 불러와 Cutter로 사용. 경로/에셋 참조 저장; 저장된 임의 FBX 파일이 Blender Asset으로 자동 노출된다고 가정 금지.
- Cut/Boolean 결과에서 **새로 생성된 절단 경계만** Off / Bevel / Chamfer 마감. Width, Segments, Profile, Live Preview; 원래 기존 실루엣/샤프 경계 보호.
- Shape Lasso의 코너 round/chamfer 조정은 cutter contour 편집 기능이며, 결과 메시의 Edge Finish와 별개.

## PNG → Vector custom shape presets
- 사용자가 새 PNG를 직접 가져와 컷 프리셋 자동 생성. 흰색/alpha mask, threshold, noise cleanup, vector contour fitting, 여러 islands/holes, concavity, watertight 3D cutter. 사용자 커스텀 저장, thumbnail preview, 이름 변경/수정/삭제, 다른 blend에서도 접근.
- 로우 세그먼트/픽셀 계단 해결. 컷은 가능한 벡터 경계 기반, 화면 투영 및 표면 정렬/normal options, scale/rotate/depth/invert; 반복 스탬프.
- 이전 voxel alpha boolean, live paint alpha boolean, 3-View Sketch/Sketch Box는 재도입 금지. 하지만 현재 `PNG to vector Cut Preset`은 유지·안정화.
- 알파 시트 98개는 개별 정밀 원본이 아닌 참고 컨택트시트. 직접 제공된 개별 이미지 품질 확인 필요. 저작권/라이선스 확인된 프리셋만 기본 탑재하며, 사용자 승인 선행.

## Mask / Extract / Weight / Pose
- 공통 도형 브러시로 여러 번 누적 mask; Alt drawn shape 차감, clear/invert/visible toggle, 꺼도 정보 유지.
- Mask Protect 실제 Cut/Boolean/Split 커터 영향 제한 (그냥 칠해진 면을 강조하는 UI만으로는 미완성). Mask→Cut, Invert Cut, Solid Split, Surface Extract, Extract+Raise, Cap, thickness.
- 정확한 면 경계를 자르는 mode와 빠른 face selection mode 분리; 곡면 projection·mesh density 제한 명시.
- Weight Paint 마스크, blur/falloff, soft raise, thickness, mask-to-weight. Rigid Pose(여러 메카 부품을 형태 유지한 채 관절처럼 이동/회전), Soft Pose(Lattice/Armature/weight-deform, move/bend/twist). Sculpt Move 핫버튼.

## Fuse / Mirror / Array / Curve / Surface / Basic Remesh
- Smart Fuse: 겹친 두 메쉬의 연결부만 fillet(segments/width)/chamfer/soft-fuse. 범용 임의 교차 형상에서 기존 오류 있음. 불가능한 입력 분명한 안내+fallback 필수.
- Mirror: World origin/3D cursor/local; X/Y/Z, Merge/Clip/Bisect; Collection live pair for limbs; original linked instances; Apply/Remove.
- Curve Array: 인스턴스 미리보기, path points + each point scale, spacing, orientation, confirm; Radial Array: Z축 중심, cursor center, count, radius, arc, start angle, Keep Local Orientation 기본(= Rotate Each Copy OFF), array Boolean.
- Panel Lines: draw curve line width/depth, straight/Bezier points, editable profile. Curve Profile: rectangle/circle/polygon/custom section and saved presets.
- Surface Snap / Surface Wrap + bend strength, offsets, conform; Asset Library object presets; Basic Voxel Remesh, Join/Smooth and automatic apply if explicitly selected.

## UI/성능/품질
- 상단 `MECHA LAB` Workspace 탭 + 왼쪽 Tools + 상단 왼쪽 공통 Shapes + 오른쪽 context-only options. Space tool picker as secondary, scoped hotkeys.
- Large clear icon and text, no giant scrolling sidebar. Cut/Split independent tools. User-editable key assignments, no global Blender hotkey regression outside workspace.
- Minimal drawing lag via viewport overlay and delaying expensive mesh eval; performance benchmark and cancellation; true geometric curve resolution vs shading smoothing distinction; default exact boolean if warranted, manifold/shape checks and rollback.

## 명시적으로 제거/제외
- 옛 Alpha Boolean voxel/height stamp, 3DCoat Sketch/3-View, Organic Auto Retopo/AI quad, Smart Remesh 스타일 Hard Surface Cleanup, 별도 Random Polygon Shape.
