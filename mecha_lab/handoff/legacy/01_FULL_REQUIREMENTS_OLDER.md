> **[2026-10-13 최종 사용자 UI/UX 수정]** 이 문서의 UI 구성·Cut/Split/Polygon 구분보다 `00_FINAL_UIUX_SPEC_KO.md`가 우선합니다. 특히 **왼쪽 위 공통 브러시 6종, Space 글로벌 도구 팔레트, 오른쪽 활성 도구 설정**으로 구분; Cut과 Split 별개 도구, 별도 Random Polygon 제거.

# Mecha Lab — 전체 요구사항 및 구현 기준 (2026-10-13)

> 사용자 실제 작업 환경: **Blender 5.0.2, Windows 11**. 우선 5.0.2에서 동작 검증하고 나중에 4.5/5.2를 확장할 것. 최신 *배포* ZIP은 `mecha_lab_v0_5_9_menu_mask_extract_beta.zip`이고, `WIP_v060_UNRELEASED/`는 다음 버전용 **미출시·미검증** 작업 사본이다.

## A. 제품 지향 / 우선순위
- 메카닉·하드서피스 컨셉 모델링용. 직접 도형을 그리고 → 즉시 절단 → 연속으로 반복 → 프리셋으로 재사용 → 필요 시 수정하는 3DCoat/BoxCutter 스타일 워크플로.
- 주요 목적: **최소한의 조작, 입력 지연 최소화, 원본 보호, 확실한 Undo, 높은 곡면 품질**.
- Blender N패널 길이를 줄이고, Space 도구 팔레트와 활성 도구 설정 패널을 분리.
- Cut → Boolean → Smart Fuse → Mirror가 메뉴의 1~4번째. 나머지는 Mask / Shape Presets / Array / Curve / Surface Conform / Pose / Asset Library / Remesh 순으로.
- 사용자는 5090 GPU가 있는 고사양 Windows PC를 사용하나 Boolean/BMesh CPU 처리 비용은 별도로 고려.

## B. Cut / Split — 최우선
1. 대상 메쉬 한 개를 선택하여 스크린/뷰포트 방향에서 자유선·직선·사각형·원·커스텀 다각형·정규 N-gon으로 직접 자름. 불린 커터를 사전에 모델링할 필요 없어야 함.
2. **기본 입력은 도형 안쪽 삭제, 바깥쪽 유지**. `Alt` 누르고 그리면 **안쪽 유지, 바깥쪽 삭제**. `Split Both`는 양쪽을 각각 별도 오브젝트로 보존, 선택적으로 절단면 Cap.
3. **배치 완료 직후 Auto Apply** 기본 ON. Auto Apply OFF면 Cut 윤곽·커터 편집 가능한 Live 모드. 실행 후 삭제한/살린 영역을 다시 클릭하도록 요구하면 안 됨.
4. Cut 모드는 연속 유지. `Enter` 또는 **좌클릭 더블클릭** = 현재 한 획/도형 확정 후 다음 획 대기. `Esc` = 현재 미완성 획만 취소. 다른 도구/패널 옵션 클릭은 Esc 없이 수행. 완성한 결과는 유지.
5. 드로잉 모드: Free Draw / Straight Polyline / Bezier Point Line / Rectangle / Circle / Polygon / Regular N-gon / Imported Custom Shape. `Shift+클릭` 직선/45° 각도 스냅. `Backspace` 마지막 점 삭제.
6. 기존 꼭짓점을 다시 클릭할 때 **각진 상태→약한 곡선→중간→강한 곡선→각진 상태** 순환, 포인트는 선명한 화면 핸들, 커브는 양쪽 Bezier 핸들을 직접 드래그. 점 이동 가능. 포인트 클릭과 새 포인트 추가의 충돌 방지.
7. 원·곡선 분할 수, Free Draw 샘플 간격, 단순화 허용 오차, 표면 투영 방향/깊이/품질 조절. 원형 커터의 낮은 48 고정 segments 개선.
8. **Cut 중 우클릭 1회** = 이미지 썸네일 Cut Shape 팝업, **우클릭 더블클릭** = Cut 종료. RMB 단/더블 구분 시 팝업을 먼저 열어버리는 경쟁 조건 방지. LMB 더블클릭에도 마지막 포인트 중복 생성 금지.
9. **Cut 후 Ctrl+Z** = 직전 컷 한 번만 취소, Ctrl+Shift+Z 다시 실행. 그리는 중 Ctrl+Z는 최근 점/스트로크 되돌리기. Cut 모드를 유지하는 동시에 Blender 전체 undo stack을 오염시키면 안 됨.
10. 드로잉 모달이 N패널/다른 Blender 편집기/Space 팝업의 클릭·키입력을 가로채면 안 됨. 마우스가 패널로 이동하면 해당 UI를 그대로 누를 수 있어야 함.

## C. Boolean + Edge Finish
- 두 메쉬를 선택할 때 노란색 활성 메쉬를 Target, 나머지를 Cutter로 사용. `B` 기본 = Difference. Union/Intersect/Slice도 버튼 지원. Auto Apply ON/OFF, 적용 후 Cutter 보존 옵션. FBX 임포트 커터 및 Blender Asset Library에 저장된 커터 선택·배치.
- 적용 전 `obj.data.users>1`인 공유 데이터(Alt+D 등)의 싱글 유저 분리를 안전하게 처리. 공유 링크 해제 사실을 명시하고 원본 보존.
- Cut/Boolean **새로 생성된 절단 경계만** Finish: Off / Bevel(둥글게, Width·Segments·Profile) / Chamfer(평면, Width) 선택. 이미 존재하던 전체 오브젝트 모서리에 Bevel 적용하지 말 것. 정확한 교차/경계 엣지 추적이 필요.

## D. Mask — Shape / Weight 공통 입력
- Cut과 동일한 Rectangle/Circle/Polygon/Freehand/Polyline/Bezier/PNG vector stamp 입력으로 3D 메쉬 위에 보호 마스크 누적; `Alt+드로잉`은 지정 영역 마스크만 차감. Clear/Invert/Hide/Toggle. 일반 드로잉은 반복해 누적되고 Clear 전까지 유지.
- Protect: 실제 Cut/Boolean/Slice가 보호 영역에 영향을 못 미치게 해야 함. 단순 면 선택/오버레이로 끝나면 미완성. 이 부분은 2D projection→3D region and mesh splitting 문제이므로 우선 설계/검증 필수.
- Mask -> Cut(영역 삭제), Invert Cut, Split Both(솔리드 두 조각), Extract(새 표면 파츠), Extract & Raise(외부로 돌출 및 두께). 마스크 경계를 따라 **정확히 토폴로지 분할**하는 모드와 기존 Face 단위 빠른 선택 모드를 분리.
- Weight Paint/vertex group 마스크 추가 가능: soft falloff, raise height, thickness, smooth, inverse; 정점이 낮게 분포된 모델에서는 원하는 윤곽을 얻지 못하는 한계를 설명. Mask to Weight.

## E. Custom Shapes / PNG→벡터 프리셋
- 제공한 **98개 알파 디자인이 한 장에 배열된 스크린샷**은 디자인 참고 및 승인 대상이지 원본 개별 PNG 98개가 아님. 작은 섬·구멍·반투명 안티앨리어싱·잡음이 생기는 부분을 고품질로 추적하려면 개별 원본 PNG가 최선.
- 사용자가 PNG를 가져오면 **픽셀/복셀 불린이 아니라, 임계값+윤곽 추적+곡선 피팅+폐곡선 구멍/섬 보존**으로 벡터 커터 저장. 저장한 도형은 다른 `.blend`에서도 사용. 등록/수정/삭제/이름 변경/Overwrite, 썸네일 이미지 미리보기.
- 썸네일 그리드로 나사 십자·육각 소켓·환기구·그릴·SF 장식 등을 선택 후 Stamp. Width/Rotation/Depth/Flip/Resolution. 연속 찍기. 마우스 위치/현재 시점 투영과 표면법선 방향 중 선택.
- 현재 스크린샷에서 PNG 스탬프 불린 결과가 비매니폴드 오류를 내고, 표면에 예기치 않은 선/찢김 발생. 윤곽만 예쁘게 보이면 되는 것이 아니라 **watertight 커터와 안전한 boolean result** 필요. 오류를 `simplify 낮춰보세요`로만 해결하도록 하면 안 됨.
- 이전 Alpha Boolean(복셀 기반), 3-View Sketch/Sketch Box는 **삭제 유지**. PNG를 새 Cut 프리셋 입력으로 쓰는 것은 별도(계속 요구).

## F. Smart Fuse
- 두 개의 겹치는 메쉬 선택 → 교차 경계만 Fillet(둥근 곡면) 또는 Chamfer(플랫 경사면) 생성, Width·Segments·Profile 조절, Soft Fuse 별도. 원본 보호 및 live preview / Apply.
- 실제 사용자 환경에서 **오류가 발생**했음. 테스트한 간단한 큐브에서 생성되는지만 확인하지 말고 교차/접촉/겹침, 얇은 메쉬, 거친 토폴로지, 개방된 셸, 여러 모디파이어 조건에서 오류 재현. 범용 자동 seam-fillet이 어려운 경우 제한 조건·실패 이유를 명확히 제시.

## G. Mirror / Arrays / Surface Conform / Pose
- Mirror: World (기본 X/Y/Z, 월드 원점/3D커서), Local, Collection 인스턴스 양쪽 배치. 원본 부품 여러 개를 `ARM/LEG` 컬렉션으로 구성 → 좌우 대칭 인스턴스 배치 → 원본 수정 양쪽 반영. Live link, Bisect/Clipping/Merge/Apply.
- Curve Array: 점으로 편집 가능한 커브 따라 소스 메쉬 반복, 간격·각 포인트별 크기·Live/Apply. 실시간은 인스턴스 유지.
- Radial Array: 3D 커서 중심, 특히 세계 Z축 타이어 트레드/볼트 반복, Count/Radius/Start Angle/Arc, 크기/높이 조절. **복제 메쉬의 로컬축이 원치 않게 돌아가지 않도록 Rotate Each Copy 기본 OFF**. 복제 메쉬 전체를 타이어에 Boolean Difference/Union/Intersect. 겹친 커터를 계산할 때 solver 안전성 검증.
- Surface Snap(형태 유지) / Wrap(곡률에 맞게 휨), Offset/Strength.
- Pose: Rigid Pose(기계 부품 단위 이동/회전), Soft Pose(Lattice/Armature/Weight deformation), Rotate/Scale/Bend/Twist, falloff. 원본 비파괴, 컨트롤러 조작. 마스크/웨이트로 영향 영역 설정.

## H. UI / 키맵 / 입력
- Space를 누르면 **큰 아이콘 + 텍스트** Tool Palette (3DCoat 스타일); Cut → Boolean → Smart Fuse → Mirror 우선. 선택한 도구의 옵션만 오른쪽 패널에 표시.
- `MECHA LAB MODE` ON일 때만 Space/B/C 및 사용자 지정 키 활성화. OFF면 Blender 기본 키맵 복원. 사용자가 UI에서 단축키 저장/수정/충돌 감지.
- Tool 상태 바꾸거나 Rectangle→Circle 전환 시 Cut modal 종료 강요 금지. N패널·다른 편집기 클릭 자유롭게.
- Cut/Mask/Panel/Curve/Pose mask 등 **공통 Drawing Engine** 사용. Enter/LMB double=confirm, Shift=straight/snap, Alt=tool-specific inverse, Backspace=point back, Esc=stroke cancel. RMB menu + double-RMB exit는 사용자 지정 가능하게 고려.
- 모든 메뉴, 설정, 오류를 사용자가 Blender 5.0.2에서 실제로 눌러 보면서 검증. 헤드리스 `bpy` register만 통과해도 키보드·마우스 팝업까지 검증된 것은 아님.

## I. Panel Line / Curve / Asset / 기본 Remesh
- Panel Lines: 도형으로 표면에 패널라인 홈, Width/Depth, 점 수정, Straight/Bezier, 미리보기/확정.
- Curve Profile: Rect/Circle/Polygon/Custom 3D 단면, 점·핸들 편집, 저장 프리셋.
- Asset Library: 직접 만든 메쉬·프리셋 등록/불러오기, 메카용 FBX 커터 임포트, `blend` asset integration.
- One-click Voxel Remesh, Join, Smooth, modifier apply with backups, Sculpt Move 버튼은 유지.
- **삭제된 기능을 다시 넣지 말 것:** Smart Remesh형 Hard Surface Cleanup, AI/Organic Retopo, 기존 voxel-alpha boolean, 3-View Sketch.

## J. 성능과 정확도
- 목표: 3D 드로잉은 입력 즉시 오버레이 반응, geometry recompute는 release/confirm 또는 쓰로틀링된 프리뷰. fps/시간/메모리 측정하여 성능 개선. 소스 유실/원본 공유 오브젝트 변경/부분 적용 금지.
- Boolean Exact 처리, 비매니폴드/자기교차, 열린 메쉬, 얇은 커터, 매우 큰 메쉬, 커브 세그먼트 증가에서 유효성 검사. 큐브만이 아닌 실제 하드서피스 + 얼굴/몸 곡면에서도 확인.
- Smooth By Angle/Weighted Normal은 **셰이딩을 개선**할 뿐 저세그먼트 실루엣 기하를 고치지 못함. Segment slider + 선택적 국소 세분화와 자동 노멀은 별개 옵션으로 제공.
- Undo/Redo, 취소, 중간 실패 롤백, 파일 저장 후 재열기, add-on unregister/reload 안전성 필수.
