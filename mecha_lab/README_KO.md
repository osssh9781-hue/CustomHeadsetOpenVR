# Mecha Lab 0.10.0 — 설치 · MECHA LAB Workspace · 사용법

> **검증 수준:** Linux headless Blender **5.0.1**(`bpy`)에서 자동 테스트 17개 파일 / 875개 항목이 통과했습니다.
> **Windows 11 + Blender 5.0.2 GUI에서는 실행된 적이 없습니다.** `GUI_TEST_CHECKLIST_KO.md` A절을 먼저 확인해 주세요.
> 문제가 남아 있으면 N > Mecha Lab > Workspace & Hotkeys > **Run Mecha Lab Self Test** 결과(클립보드)를 보내 주세요.

기준 소스: ChatGPT v0.9.3 (Claude 0.9.0 + ChatGPT Deform 0.9.1 + Primitive 0.9.2/0.9.3). 변경 내용은 `CHANGELOG.md` 0.10.0.

## 0.10.0 빠른 안내
- **Alt+짧은 클릭** = 선택 모드 ↔ 마지막 Mecha 도구, **Alt+드래그** = 도구별 보조(Cut: 안쪽 남기기, Base Mesh: 파내기).
- 닫기: 아무 곳 **더블클릭** / **시작점 클릭** / Enter. Esc = 획 취소 후 선택 모드. 3회 클릭 기능은 없어졌습니다.
- **V** = 빠른 메뉴(Cut, Boolean, Base Mesh, SubD Plane, Split, Radial), **Space** = 전체 메뉴, **Shift+A > Mecha Lab**.
- **Boolean**: 대상들을 먼저, **커터를 마지막(노란색)**으로 선택. 대상이 여러 개여도 각각 처리.
- Cut / Split / Mirror: 선택된 메쉬 모두에 적용.
- Base Mesh: Bevel Sides(Top / Bottom / Both / None), 도구를 떠나면 이번에 만든 도형만 Apply.
- Free Draw: Stabilizer(Lazy Mouse) ON/Strength/Radius/Spacing.
- Deform: 라티스/벤드 커브 점 클릭 → Move/Rotate/Scale 기즈모, Falloff로 주변까지 변형.
- PNG 모양: R / Shift+R 15° 회전. Mask는 숨김(데이터 유지).

## 1. 설치
1. 기존 Mecha Lab을 비활성화·제거 (Edit > Preferences > Add-ons).
2. Get Extensions > ▾ > **Install from Disk…** → `dist/mecha_lab-0.10.0.zip` (압축 풀지 말 것).
3. 설치만으로는 어떤 Workspace도 바뀌지 않습니다.

## 2. MECHA LAB Workspace
N 사이드바 > Mecha Lab > `Open MECHA LAB Workspace` (또는 탭 메뉴 / F3). 현재 탭을 복제해 새 탭을 만들고,
왼쪽 도구 목록 · 뷰포트 왼쪽 위 공통 Shape 팔레트 · 오른쪽 현재 도구 설정 구성을 만듭니다. 다른 탭과 Startup File은
건드리지 않습니다(Startup 저장은 확인 창이 있는 별도 버튼).

도구 목록: **Cut, Split, Base Mesh, SubD Plane, Primitive**, Boolean, Smart Fuse, Mirror, Curve Array, Radial Array, Mesh Curve,
**Deform**, **Loft / Surface, ZBrush Bridge**, Surface Conform, Assets, Remesh, Live Result. (Mask는 0.10.0에서 숨김)
`Space` = 큰 아이콘 도구 메뉴(MECHA LAB 탭에서만). Sidebar의 접힌 `Tools (fallback list)`도 항상 있습니다.

## 3. 공통 입력 규칙 (Cut / Split / Mask / Base Mesh)
| 입력 | 동작 |
|---|---|
| LMB | 현재 Shape로 획 시작 |
| **더블클릭 (어디서든)** | Lasso/Curve Lasso를 마지막 점 → 시작점으로 자동으로 닫고 적용. 점을 추가하지 않음 |
| Enter / 첫 점 클릭 | 닫고 적용 |
| **Esc** | 미완성 획을 버리고 **Blender 선택 도구(Select Box)로 복귀**. 이미 적용된 컷은 유지 |
| **같은 자리 빠른 좌클릭 3회** | 2번째 = 확정, 3번째 = 선택 도구 복귀 (점 편집 클릭은 세지 않음) |
| RMB 1번 | Cut/Split/Mask: Shape·PNG 팝업 / **Base Mesh: 단면 프로필 팝업** |
| RMB 더블 | 도구 종료 |
| Ctrl+Z | 획 중: 마지막 점 / 획 밖: 컷 하나 = Undo 한 단계 |
| Backspace · Ctrl+Shift+Z | 점 삭제 · 점 복구 |
| Shift / Alt / F | 45° 스냅 / 반전(안쪽 유지·마스크 지우기) / Lasso 열린 선 |

## 4. 공통 Shape 팔레트
- **Lasso**: 클릭으로 직선 다각형. LMB를 누른 채 끌면 그 구간은 자유곡선으로 그려집니다. 2점 + Enter = 직선 컷.
- **Curve Lasso**: 처음부터 매끄러운 닫힌 스플라인(Catmull-Rom/Bezier). 점 클릭 = 각진 점 ↔ 부드러운 점,
  점·Bezier 핸들 드래그, `Curve Samples`/`Curve Smoothness`.
- **Free Draw**: LMB를 누른 채 연속으로 그리고 놓으면 적용(간격·스무딩·단순화 옵션). Cut/Split/Base Mesh =
  닫힌 자유 외곽선, Mask = 열린 브러시 스트로크(v0.7.2 그대로).
- Rectangle / Circle / Ellipse / PNG Custom.
- **Outline Corners (Lasso/Rectangle)**: 2D 도형 모서리 라운드/챔퍼. 컷된 3D 엣지의 **Edge Finish와 별개 설정**입니다.

## 5. Base Mesh (새 입체 생성)
Base Mesh 도구 → Shape 선택 → 뷰포트에 윤곽을 그리면 **새 오브젝트**가 생깁니다(원본은 그대로).
윤곽 아래 표면이 있으면 그 표면 위, 없으면 3D 커서 위치에 뷰와 마주보는 평면으로 놓입니다.
RMB = 프로필 팝업: **Flat · Chamfer · Bevel · Rounded/Dome**. Dome은 경계에서 안쪽으로 부푸는 높이장(bevel 아님),
Roundness / Height / Edge Height / Resolution. 선택한 Base Mesh는 Live라서 오른쪽에서 값을 바꾸면 다시 만들어지고,
`Freeze Base Mesh`로 일반 메쉬가 됩니다.

## 6. Loft / Surface
- **Loft**: 커브 2개 이상 선택 → `Create Loft Surface` (활성 커브부터 가까운 순서). 커브를 고치면 표면이 자동 갱신.
  Curve Samples, Surface Segments, Smoothness(0=직선 / 1=부드러움), Thickness, Cap Ends, Flip Normals, Auto Align,
  Twist, Close Loft, 섹션 순서/개별 Reverse. `Apply Surface`로 확정.
- **Sweep**: 커브 2개 선택(활성 = 경로, 다른 것 = 단면).
- CAD의 수학적 NURBS 패치가 아니라 **보간된 폴리곤 표면**입니다.

## 7. ZBrush Bridge (OBJ, GoZ 아님)
선택한 메쉬마다 OBJ 하나씩 내보냅니다(**자동 Join 안 함**). ZBrush에서 Tool > Import → 작업(DynaMesh 등 직접) →
Tool > Export **같은 파일 이름으로** → Blender에서 `Import Back`. 바뀐 파일만 원래 오브젝트의 메쉬를 교체합니다
(변환·모디파이어·재질 슬롯 유지, 이전 메쉬는 `<이름>_preZBrush`로 보관). 축/스케일은 오른쪽 패널에서 조정.

## 8. 0.9.0 추가 기능
- **Mesh Curve** (예전 Panel / Curve): 직선(VECTOR) 그리기 유지. 그리는 중 기존 점 클릭 또는 더블클릭 = 직선 ↔ 부드러운 점,
  `S` = 새 점 종류 전환, Free Draw는 부드러운 점으로 생성. Edit Mode에서도 점 더블클릭으로 전환(v0.5.9부터 꺼져 있던 키맵을 켬).
  오른쪽 Live 패널: All Smooth / All Straight(Object Mode), Curve Resolution, Profile Segments, Rotation X/Y/Z, Twist.
  Curve Array도 같은 Resolution / 복제본 Rotation X/Y/Z / Twist.
- **SubD Plane**: `Create SubD Plane` → Simple SubD + Catmull-Clark SubD + Solidify가 동시에 걸린 Plane. Simple / Catmull-Clark
  레벨(0~5) 슬라이더 각각, Thickness, Offset, Even Thickness, Edge Crease(Edit Mode에서 선택 엣지에 적용), Apply All.
  Edit Mode에서 E로 엣지를 늘리며 계속 모델링. `Add SubD Stack to Selected`로 기존 메쉬에도 적용.
- **Radial Array**: Ring Rotation X/Y/Z(배열 전체), Start Angle, Copy Rotation X/Y/Z(복제본 각각), Rotate Each Copy(기본 OFF).
  원본 방향은 그대로 두고 배열 회전만 따로 조절.
- **Split**: Normal(기존) / **Gap**(Gap Width만큼 띠를 제거하며 분리, 선 중심 유지, 직선·곡선·폴리라인, Cap). 양쪽 독립 마감:
  Side A(남는 원본) / Side B(새 `_Split`) 각각 None/Chamfer/Bevel, Width, Segments, `Swap Sides`. 새 절단 엣지만 처리.
- **2D 모서리**(Lasso/Rectangle): Sharp / Chamfer / Round, Corner Width(px), Corner Segments, 그리는 중 미리보기 (점검 완료).

## 9. 그 밖의 기존 기능
Cut/Split(Edge Finish = 새 절단 엣지만), Boolean, PNG Custom Shape, Alt+D 공유 메쉬 정책, Smart Fuse(제한),
Mirror, Arrays, Surface Conform, Mask(면 단위, v0.7.2 레이캐스트), **Ortho Lock(v0.7.1, 파일을 다시 열어도 유지)**.

## 10. 제거
Preferences > Add-ons > Mecha Lab > Remove. 만든 MECHA LAB 탭은 .blend 안에 남을 수 있습니다.
