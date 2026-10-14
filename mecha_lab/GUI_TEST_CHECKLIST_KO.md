# GUI 수용 테스트 체크리스트 — Mecha Lab 0.15.0 / Windows 11 / Blender 5.0.2

**새 파일**(File > New > General)에서 진행하세요. 실제 작업 파일로 테스트하지 마세요.
Window > Toggle System Console을 켜 두고, 오류가 나오면 **콘솔 전체 텍스트**를 복사해 전달해 주세요.
각 항목에 ✅ / ❌ / 메모를 적어 주시면 다음 수정에 그대로 사용합니다.

## G. 0.15.0
- [ ] 패널 아이콘: 큰 그림 + 아래 이름 버튼(길쭉한 빈 버튼 없음)
- [ ] 뷰포트 왼쪽(기본 도구 막대 옆)에 둥근 툴 버튼 목록 + 이름, 누르면 툴 바뀜, 지금 툴 주황색. 왼쪽 MECHA LAB TOOLS는 접혀 있음
- [ ] 반투명 도형 오른쪽에 + / − / ✓ 버튼과 슬라이더가 따라다님. −를 누르면 빨간색, ✓ = 빼기
- [ ] 슬라이더 좌우로 끌기: 원기둥 세그먼트 / 다각기둥 면 수가 바뀜
- [ ] 같은 크기 도형으로 빼기 직전: 겹치는 면이 빨간 점선 + 빨간 글씨
- [ ] Station: 위아래 + 좌우를 같이 꺾기, 비틀기 다이얼, 폭/두께 네모, 길이 화살표
- [ ] 다이얼을 오른쪽으로 돌리면 도형도 오른쪽으로(기본 도형·Station 모두)
- [ ] Polygon Prism: 위/아래 끝 + / − 로 구간 추가/삭제, 꺾은 곳 바깥 점 클릭 = 직각 → 밴드 → 직각, Bevel/Chamfer
- [ ] Station 선택 후 ✓(+) = 겹친 메시에 합쳐짐, ✓(−) = 파짐

## H. 0.14.4
- [ ] Base Mesh에서 그냥 그리면 주황색 선, Alt를 누르고 그리면 빨간색 선

## I. 0.14.3
- [ ] Primitive 도구에 들어가도 파란 도형이 안 뜸. 도형을 누르면 뜸
- [ ] 면의 네모 = 그 면만 크기, 화살표 = 그 축으로 이동, 다이얼 3개 = 회전(자연스러운지), 모서리 점 = 전체 크기
- [ ] 도형 돌린 뒤 Ctrl+Z = 돌리기 전으로, Ctrl+Shift+Z = 다시
- [ ] Top X / Top Y, Bevel / Chamfer: 미리보기와 Enter 결과 둘 다 반영
- [ ] Enter 뒤 깜빡임·글리치 없음(외곽선만 남음), 도형 움직이면 다시 반투명
- [ ] Station Primitive 핸들로 늘린 뒤 Ctrl+Z = 늘리기 전(파란 도형 안 나옴)
- [ ] Base Mesh: 기울어진 면/둥근 면 위에 그리면 표면에 붙어서 생김. Stick to Surface 끄면 예전처럼
- [ ] 왼쪽 툴 메뉴: 아이콘 위 / 이름 아래 타일, 아이콘을 눌러도 실행. 아이콘 크기가 적당한지
- [ ] 아이콘 크기 바꾸고 Blender 껐다 켜도 유지

## J. 0.14.2 아이콘 크기
- [ ] N 사이드바 > Mecha Lab > Icon Size: Panel Icons를 올리면 도구·도형 썸네일이 커짐, 내리면 작아짐
- [ ] Bottom Toolbar를 올리면 아래 버튼과 이름이 커지고 겹치지 않음
- [ ] Viewport Handles를 올리면 Primitive 도형 화살표·다이얼이 커짐
- [ ] Small / Normal / Large / Huge 버튼
- [ ] Blender를 다시 켜도 값 유지(Preferences 저장 시)

## K. 0.14.1 Base Mesh 스케치
- [ ] Base Mesh 도구에서 사각형/라쏘를 그리면 메시 대신 주황색 모양이 남음
- [ ] 겹치게 하나 더 그리면 외곽선이 하나로 합쳐져 보임
- [ ] Alt + 그리기: 안쪽 = 구멍, 가장자리 = 파인 모양
- [ ] Backspace = 마지막 모양 취소, Ctrl+Z도 한 획씩
- [ ] Enter = 메시 생성, 주황색 사라짐. 패널에서 프로필 바꾸면 메시 갱신
- [ ] 메시 위에 스케치 후 Alt+Enter = 그 모양으로 파임
- [ ] Esc = 스케치 지움, 한 번 더 Esc = 도구 나감
- [ ] 뷰를 돌린 뒤 그려도 같은 평면에 붙음
- [ ] 패널 Sketch First 끄면 예전처럼 바로 메시

## L. 0.14.0
- [ ] Cut 도구에서 PNG 스탬프 / 내장 스탬프(삼각형, 오각형 등)를 고르면 미리보기가 마우스 커서 바로 위에 붙어 다님
  (N 사이드바·왼쪽 도구 영역을 열고 닫아도)
- [ ] 아래 툴바에 마우스를 올리면 "Cut  (C)"처럼 이름만 나옴. 아이콘 밑에 이름이 보임
- [ ] 오른쪽 N 사이드바 > Mecha Lab: 다른 도구일 때 "Primitive Shapes" 격자가 보이고, 도형을 클릭하면 Primitive 도구 + 반투명 도형
- [ ] Primitive 패널·RMB 메뉴의 도형 격자가 고르게 정렬됨(계단식 아님)
- [ ] 반투명 도형이 보이고, 화살표로 한쪽만 늘어남, 다이얼로 회전, 가운데 링으로 이동
- [ ] 메시 클릭 = 도형이 그 표면으로 이동(표면 방향으로 섬)
- [ ] Enter = 겹친 메시에 합쳐짐, 도형은 남아 있음. 아무것도 안 닿으면 새 오브젝트
- [ ] Alt를 누르면 빨간색, Alt+Enter = 파냄
- [ ] Pill Cylinder: 단면이 알약 모양
- [ ] Seam Chamfer / Smooth: 이음새만 깎임
- [ ] Ctrl+Z: 합치기는 취소되지만 도형 위치·모양은 그대로
- [ ] Esc = 도형 숨김 + Select

## M. 0.13.2 아머
- [ ] Primitive 패널 ARMOR: 어깨/무릎, 윗팔/허벅지, 아랫팔/종아리, 몸통, 헬멧 생성 → 모양 확인
- [ ] 지점 골라 Crown(볼록함)·Thickness·폭 조절, Mirror로 좌우 한 쌍 만들기

## N. 0.13.1
- [ ] 지점 선택 후 ← → 버튼: 판이 옆으로 꺾임 (평평한 채로)
- [ ] Fold / Tight / Band 바꿔 보기: Tight 90°가 거의 직각
- [ ] 지점의 Profile Here = Round: 그 앞 구간이 박스 → 원으로 이어짐
- [ ] 뷰포트: 지점 점 클릭 = 선택, + 클릭 = 삽입, 각도 다이얼·방향 다이얼·폭/두께/길이 화살표 드래그
- [ ] Mirror 도구로 미러 → 지점 편집해도 미러 유지 → Enter(Apply) 후 더 이상 재생성 안 됨

## O. 0.13.0 Station Primitive
- [ ] Primitive 도구 → 프리셋 6개 각각 생성, 모양 확인 (헬멧/장갑판/타이어 커버/자동차/덕트/평판)
- [ ] Multi-Bend: S1 각도 바꾸면 뒤 구간이 따라 돌고 S2/S3 값은 그대로
- [ ] Add Station → 30° 꺾임이 이어짐, 반경 0/0.3 바꿔 보기(접힘 ↔ 부드러움)
- [ ] Asymmetry: 왼쪽 두께만 키우기, 릿지 높이
- [ ] 저장 → 다시 열기 → 계속 편집, Cut 하면 "frozen" 메시지, Apply

## P. 0.12.0 (먼저)
- [ ] MECHA LAB 뷰포트 아래 가운데 툴바 8개, 현재 도구 주황, 버튼 클릭으로 도구 전환, 마우스 올리면 툴팁
- [ ] Preferences > Mecha Lab: 툴바 크기 S/M/L, 아이콘 아래 이름
- [ ] Q = 파이 메뉴, Shift+Q = Select ↔ 마지막 도구 (도형 유지), Layout 탭에서는 Q = Blender Quick Favorites
- [ ] N = 사이드바, V = 아무 일 없음
- [ ] Cut 자동 대상: A 선택 상태에서 B 위에 그리면 B만 잘림, 이어서 다른 파츠도 Select 없이 바로
- [ ] T 또는 헤더 "Selected Only": 선택한 것만 잘림
- [ ] 빈 곳에서 사각형을 시작해 파츠 위까지 드래그 → 잘림

## Q. 0.11.3
- [ ] Lasso 패널의 도형 버튼 6개 → 클릭/드래그로 찍기
- [ ] V = Tool Menu, N = Quick Menu, F = Select / Move (MECHA LAB, Object Mode)
- [ ] 도형을 바꾼 뒤 Ctrl+Z → 도형이 그대로
- [ ] Cable 패널 "Convert to Object (Mesh)"
- [ ] Curve Lasso: 직선으로 시작, 점 클릭 → 약/중/강/직선, 파란 핸들 드래그
- [ ] 메쉬 선택 후 Mirror 도구 → 즉시 미러, 마우스 기울인 쪽으로 복사, Enter 적용, Esc 취소, Shift+클릭 축 추가
- [ ] Radial Array 조작 중 충돌이 다시 나면 blender.crash.txt 전달

## R. 0.11.2 (먼저)
- [ ] Preferences > Add-ons에서 Mecha Lab이 **하나만** 있고 버전 0.11.2인지 (예전 ChatGPT 0.10.x 사본이 있으면 제거 후 재시작)
- [ ] N > Mecha Lab > Workspace & Hotkeys > Run Mecha Lab Self Test → 클립보드 내용 전체 전달 (특히 "real 3D View projection" 줄)
- [ ] 일반 Cube Cut이 실패하면 상태 표시줄/Info 편집기의 **메시지 전체**(대괄호 포함) 전달

## S. 0.11.1 우선 확인 (Cut/Split 롤백 + Select / Move)
- [ ] 1. 새 파일 기본 Cube → Cut Rectangle 드래그 → 잘림("whole object" 오류 없음)
- [ ] 2. Curve Lasso / Lasso Cut → 닫기(더블클릭/시작점/Enter) → 잘림
- [ ] 3. Split → 두 조각
- [ ] 4. Alt 누른 채 Cut 시작 또는 그리는 중 Alt → 안쪽만 남음
- [ ] 5. Ctrl+드래그 Rectangle → 누른 점이 중심
- [ ] 6. Split Gap / Bevel 값 적용
- [ ] 7. 메뉴 맨 위 Select / Move → 이동 기즈모, 클릭/Shift+클릭 다중 선택, 이동 가능. W 단축키도 동일. Preferences에서 키 변경
- [ ] 8. Cut 획 도중 W(Select / Move) → 획 취소(아무것도 안 잘림) → Cut 다시 선택 → 새 획으로 정상 Cut
- [ ] 9. 메쉬 여러 개 선택 후 Cut / Split → 겹친 것 모두 처리
- [ ] 10. Add-on 설치 → 활성 → Blender 재시작 후 정상 (콘솔 오류 없음)
- [ ] MCH_Box(Primitive) Cut → 잘리고 보고에 "live primitive baked first"
- [ ] Alt+빈 곳 클릭이 더 이상 모드를 바꾸지 않음

## T. 0.11.0 Mechanical Toolkit (설계서 13절)
### T0. 공통
- [ ] 왼쪽 도구 목록에 Face Extract / Edge Molding / Hollow / Shell / Mesh Along Curve / Cable 아이콘, 클릭 시 오른쪽 패널 전환
- [ ] Base Mesh 도형을 만든 뒤 Layout 등 다른 탭으로 이동 → 돌아오면 도형이 Live 해제(Apply)되어 있음
- [ ] Self Test 결과 RESULT 12/12
### T1. Face Extract (Basic)
- [ ] 곡면 메쉬에서 Tab → 면 여러 개 선택 → Basic Extract: 별도 파츠, 노멀 방향으로 돌출, 원본 그대로, Edit Mode 유지
- [ ] 패널 슬라이더(Height / Thickness / Offset / Chamfer 3모드 / Direction / Bevel / Bevel Angle / Outer Edge)가 즉시 반영
- [ ] 파츠 선택 해제 후 다시 선택 → 같은 값 표시, Tab 전환 후에도 유지
- [ ] 두 오브젝트를 함께 Edit Mode로 → 각 오브젝트의 선택 섬마다 파츠
### T2. Armor Sculpt
- [ ] North Thickness만 올리면 북쪽만 두꺼워짐, East Chamfer / West Bevel 각각 독립
- [ ] Straight / Cross / Y / X / S / Z 모두 형상이 변함, Rotation / Scale X·Y / Offset
- [ ] Y: South Length, North Width 등 가지별 조절
- [ ] Ridge Profile Sharp / Flat / Round / Box / Groove / Split 차이, Surface Transition
- [ ] Direction Rotation으로 N/E/S/W 방향 회전, Mirror
- [ ] 여러 Armor 파츠 선택 후 Copy Settings
### T3. Edge Molding
- [ ] 파츠 선택 → From Extracted Panel Boundary: 별도 오브젝트, 폭/높이/베벨 각각 조절, 프로필 5종
- [ ] Edit Mode 면/엣지 선택에서 생성, Armor 중앙선에서 생성
### T4. Curve Array / Curve Deform
- [ ] 메쉬(+커브) 선택 → Curve Array: 커브 따라 반복, 커브 점 편집 시 갱신, Count / Fit / Offset / Rigid·Deform
- [ ] Curve Placement World X/Y/Z: 기준선이 축 위로, 제어점은 자유, 생성 후 변경
- [ ] Deform Along Curve: 커브 핸들로 메쉬가 휨, Start Offset / Rotation / Scale / Axis
### T5. Cable
- [ ] Two-Point Cable: 서로 다른 메쉬 표면 두 점 클릭 → 케이블, Esc 취소, 그리는 중 Tab 통과
- [ ] Sag / Handle Angle / Length / Curvature / Midpoint / Twist / Control Points ±
- [ ] Thickness / Start / End / Taper / Round·Square·Ribbon·Oval·Custom
- [ ] Edit Mode 엣지 선택 → Edge to Cable, 생성 후 커브 Edit Mode 편집
### T6. Hollow / Shell
- [ ] 여러 메쉬 선택 → Hollow, 두께/방향/Even/Rim, Edit Mode 면 선택 → Openings, Check, Apply / Reset
### T7. Undo / 기존 기능
- [ ] 각 생성·슬라이더 변경 후 Ctrl+Z / Ctrl+Shift+Z
- [ ] Split / Boolean(활성=커터) / Mirror / Lasso / Curve Lasso / Free Draw / Alt 클릭 / ZBrush Bridge 이상 없음

## A. 0.10.0 우선 확인 (사용자 보고 항목)
### A0. 설치 / 등록 (B09)
- [ ] 기존 Mecha Lab(확장 + 예전 Add-on 방식 모두) 비활성/제거 → Blender 재시작 → `mecha_lab-0.11.0.zip` Install from Disk → 오류 없음
- [ ] Preferences에서 비활성 → 활성 3회 반복: `already registered` 오류 없음, N 패널 Mirror 하위 패널 보임
- [ ] (가능하면) 예전 버전을 일부러 같이 켠 상태에서 0.10.0 활성 → 오류 대신 N 패널 상단에 "Another Mecha Lab copy" 경고
- [ ] N > Mecha Lab > Workspace & Hotkeys > **Run Mecha Lab Self Test** → 결과 줄(RESULT x/y)이 하단에 표시, 클립보드 내용을 붙여넣어 전달
### A1. 도구 전환
- [ ] 왼쪽 도구 목록에서 Cut → Mirror → Loft → Smart Fuse → Boolean 순서로 클릭: 오른쪽 패널이 매번 바뀜
- [ ] Mirror 선택 후 큐브 위 LMB: 컷이 생기지 않고 일반 선택 (Cut 도구가 남아 있지 않음)
### A2. Mirror (B01)
- [ ] 큐브 2개 선택 → World / X → CREATE: 둘 다 미러, 축 Y 추가 후 다시 CREATE: 갱신
- [ ] 3D Cursor 중심, Local 모드 각각 X/Y/Z
- [ ] Apply: 선택된 둘 다 적용, Remove: 형상 유지
- [ ] Collection Mirror: Parts 컬렉션 선택 → CREATE PAIR → MASTER 이동 시 반대편 따라옴 → Remove
### A3. Loft (B02)
- [ ] 커브 2개(Shift+A > Curve) 선택 → Loft → 표면 생성, 커브 점 편집 시 갱신, Apply
- [ ] 활성 커브 = 첫 단면, Sweep(경로 활성)
### A4. Smart Fuse (B03)
- [ ] 겹친 큐브 2쌍으로 생성→Confirm, 다른 쌍 생성→Cancel, 다시 생성→Confirm (연속 3회 이상) 모두 성공
- [ ] 미리보기를 확정하지 않은 채 다른 두 메쉬 선택 → 패널에 CREATE 버튼과 "Unconfirmed preview on …" 안내
### A5. Lasso / Split Gap / Curve (B04 B05 B07)
- [ ] Lasso 4점 → 시작점에서 먼 곳 더블클릭: 닫히고 적용, 한 번만 잘림
- [ ] Lasso 4점 → 시작점 근처(약 14px) 클릭: 닫히고 적용
- [ ] Curve Lasso: 점을 한 번 클릭 = 각/부드러움 전환, 점 위 더블클릭은 닫지 않음, 빈 곳 더블클릭은 닫음
- [ ] Split Gap: Enter / 시작점 클릭 / 아무 곳 더블클릭 각각 확정, 양쪽 Cap·Side A/B 베벨 유지
- [ ] Mesh Curve(직선 그리기) → 찍은 점 더블클릭: 곡선으로 바뀜(한 번만 전환), 다시 한 번 클릭: 직선
### A6. PNG R 회전 (B06)
- [ ] PNG 모양 선택 → 대기 상태에서 커서에 윤곽 미리보기, R / Shift+R로 15° 회전
- [ ] 드래그 중 R로 회전 → 놓았을 때 잘린 모양이 미리보기와 같음
- [ ] PNG가 아닌 모양에서 R = Blender 기본(오브젝트 회전)
### A7. Mask (B08)
- [ ] 도구 목록 / Space / V / T 툴바에 Mask 없음
- [ ] 예전 파일의 마스크 데이터(Attribute/Vertex Group)가 그대로 있음
### A8. Bevel (B10)
- [ ] Cut Edge Finish Bevel 폭 0.5 이상 입력 가능, 작은 컷에서 큰 폭 → 결과 메시지에 "limited to about …"
- [ ] Clamp Overlap OFF 시 메시지 "exceeds the safe …"
### A9. Alt / 메뉴 (docs/02)
- (0.11.1에서 Alt+클릭 모드 전환 삭제 — S절 참고)
- [ ] 직선 2점 Cut의 면 선택 단계: 클릭 = 그쪽 제거, Alt+클릭 = 그쪽 남기기 (0.11.1: v0.9.3 방식 복구)
- [ ] 3번 빠른 클릭이 더 이상 선택 모드로 보내지 않음
- [ ] V = 마우스 위치에 6개 빠른 메뉴, Space = 전체 메뉴, Shift+A 맨 아래 `Mecha Lab` 하위 메뉴(기존 항목 그대로)
- [ ] Alt+MMB는 기본(뷰 회전 관련) 그대로
### A10. Boolean / 다중 대상 (F01)
- [ ] A, B 선택 후 C를 마지막으로(노란색) 선택 → Difference: A−C, B−C, 패널에 CUTTER: C / TARGETS: 2
- [ ] 큐브 3개 선택 + Cut 한 번 → 셋 다 잘림, Ctrl+Z 한 번으로 모두 복구
### A11. Base Mesh (F02)
- [ ] Bevel/Chamfer × Top Only / Bottom Only / Both / None 모양 확인, Both에서 Same Top/Bottom 끄고 위/아래 폭 다르게
- [ ] Dome 선택 시 Bevel Sides 대신 안내 문구
- [ ] 메쉬 위 Alt+드래그 → 그 모양으로 파인 포켓, 입구에 베벨(Top Only 설정이면 반전되어 입구 쪽)
- [ ] 도형 2개 그린 뒤 Alt+클릭(또는 Esc/다른 도구) → 그 2개만 Live 해제, 그 전에 있던 Live Base Mesh와 다른 오브젝트 모디파이어는 그대로, Ctrl+Z 가능
### A12. Free Draw Stabilizer (F08)
- [ ] Free Draw + Stabilizer ON: 선이 마우스를 천천히 부드럽게 따라옴, 지연 원과 줄이 보임
- [ ] Strength 0 → 100 차이, Lazy Radius 크게 하면 원 안 움직임에 선이 멈춤
- [ ] 마우스 정지 시 선이 계속 따라와 멈춤, 놓으면 끝까지 부드럽게 이어지고 긴 직선 점프 없음
- [ ] OFF일 때 기존과 같은 느낌, Lasso / Curve Lasso / 사각형 등은 변화 없음
- [ ] Cut / Split / Base Mesh 모두에서 결과 정상, 드로잉 전 슬라이더 조작 가능
### A13. Deform 포인트 조작
- [ ] 메쉬 선택 → Deform → Create Lattice Cage: 바로 점 편집, 점 클릭 → Move(화살표)/Rotate(원)/Scale(박스·바깥 원) 기즈모
- [ ] 점 하나 선택 후 Rotate/Scale 드래그 → 주변 점과 메쉬가 함께 변형, 드래그 중 휠 = Falloff 반경, Esc/RMB = 취소
- [ ] Shift+클릭/B로 여러 점 → 함께 변형, Pivot: Selection Centre / Each Point / 3D Cursor
- [ ] Resolution X/Y/Z 슬라이더(편집 중에도) → 분할 변경, 기존 변형 유지
- [ ] Gizmo: Blender 선택 시 Blender 기즈모 + Proportional Editing(반경/부드러움 동기화), Done Editing 후 원래 설정 복귀
- [ ] Bend Curve: 점 클릭 → X(커브 방향) 회전 = 그 부분만 비틀림, 다른 축 회전 = 휘어짐, Scale = 그 부분 두께
- [ ] Done Editing → 다시 Edit Controller: 형태 유지, Apply 전에는 원본 메쉬 데이터 그대로, Apply 후 컨트롤러 삭제

## B. 0.9.0 이전 항목 (아래 내용 중 바뀐 점: T 툴바에 Mask 없음, B = 활성(노란색) 커터로 Boolean, 3회 클릭 기능 제거, Alt+클릭 = 도구 종료)

## 0. 설치
- [ ] 이전 버전 제거 후 `mecha_lab-0.11.0.zip` Install from Disk → 오류 없이 활성화
- [ ] 설치 직후 상단 탭 목록이 변하지 않음 (MECHA LAB 탭이 자동으로 생기지 않음)

## 1. Workspace
- [ ] N > Mecha Lab > `Open MECHA LAB Workspace` → `MECHA LAB` 탭 생성·이동
- [ ] Layout / Modeling / Sculpting 탭 내용이 그대로
- [ ] 새 탭: 왼쪽 좁은 영역에 큰 아이콘+이름 도구 목록이 보임 (안 보이면 그 영역에 무엇이 보이는지 스크린샷)
- [ ] 뷰포트 왼쪽 위 Tool Header에 Lasso … Brush Stroke + PNG 썸네일 버튼
- [ ] 오른쪽 Sidebar가 Mecha Lab 탭이고 현재 도구 설정만 보임
- [ ] T 툴바에 Mecha Cut / Split / Mask 아이콘, 기본 활성 도구가 Mecha Cut
- [ ] 버튼을 다시 눌러도 탭이 중복 생성되지 않음
- [ ] `Repair MECHA LAB Layout`: 왼쪽 영역을 닫은 뒤 실행하면 복구

## 2. 도구 전환
- [ ] 왼쪽 목록에서 Cut / Split / Boolean / Smart Fuse / Mirror 클릭 → 오른쪽 설정이 즉시 바뀜, Esc 불필요
- [ ] Space → 큰 아이콘 도구 팝업, 클릭으로 전환
- [ ] Layout 탭으로 이동 후 Space = Blender 기본 동작(재생 또는 사용자 설정), B = 박스 선택, C = 원 선택
- [ ] MECHA LAB 탭에서 B = Boolean Difference(2개 선택 시), C = Cut 도구

## 3. Cut (큐브 하나)
- [ ] Rectangle 선택 → 큐브 위 드래그 → 놓자마자 구멍. 도구 유지
- [ ] 연속 3번 컷 → `Ctrl+Z` 3번이 컷을 하나씩 되돌림, `Ctrl+Shift+Z`로 다시
- [ ] Lasso: 점 4개 클릭 후 **시작점에서 먼 곳에서 더블클릭** → 자동으로 닫히고 적용. 점이 두 번 찍히지 않음
- [ ] 같은 자리를 빠르게 3번 클릭: 2번째에 확정, 3번째에 Select Box 복귀
- [ ] Lasso 점을 빠르게 이어 찍어도(서로 다른 위치) 도구가 꺼지지 않음
- [ ] Lasso에서 LMB를 누른 채 끌면 그 구간이 자유곡선으로 그려짐
- [ ] Lasso 그리는 중 `Ctrl+Z` / `Backspace` = 마지막 점만 삭제
- [ ] Lasso 그리는 중 `Esc` = 획 취소 + **Select Box 도구로 복귀**, 직전에 끝낸 컷은 그대로
- [ ] 획이 없을 때 `Esc` = Select Box로 복귀
- [ ] Lasso 그리는 중 오른쪽 Sidebar 값 변경 / 팔레트에서 다른 Shape 클릭 → Esc 없이 동작(그리던 획은 버려짐)
- [ ] Lasso 그리는 중 다른 에디터(Outliner 등) 클릭 → 정상 동작
- [ ] Alt 누르고 그리기 → 안쪽만 남음
- [ ] Lasso 2점 + Enter → 반쪽 하이라이트 → 클릭한 쪽 삭제
- [ ] Circle / Ellipse 각각 1회
- [ ] **Curve Lasso**: 점 3~4개만 찍어도 처음부터 둥근 닫힌 곡선 미리보기, 점 클릭=각/부드러움, 점·핸들 드래그, 원거리 더블클릭 적용
- [ ] **Free Draw**: LMB를 누른 채 원을 그리면 선이 마우스를 따라오고, 놓으면 닫혀서 컷
- [ ] Lasso/Rectangle + Outline Corners = Round → 둥근 모서리 구멍 (Edge Finish와 별개)
- [ ] RMB 한 번 → 잠시 후 Shape 팝업. RMB 더블클릭 → 도구 종료(Select Box). 더블클릭이 팝업 때문에 막히지 않음
- [ ] (그리는 중에도) RMB 한 번 = 팝업, 더블 = 종료
- [ ] Edge Finish = Bevel, Width 0.05 → 새 구멍 테두리만 둥글고 큐브 모서리는 그대로
- [ ] Depth = From Surface, 0.3 → 관통하지 않는 홈
- [ ] 원근 뷰(Numpad 5로 전환)에서 원형 컷이 화면에 그린 원과 일치

## 4. Split / 공유 메쉬
- [ ] Split 도구 Rectangle → `<이름>_Split` 오브젝트 생성, 두 조각 모두 닫힘 (Cap ON)
- [ ] Alt+D 복제본이 있는 큐브를 Cut → 기본 설정에서 복제본은 그대로, 오류 없음
- [ ] Shared Mesh = All Linked Copies → 두 복제본 모두 잘림
- [ ] Boolean 도구로 Alt+D 메쉬에 Difference → "multi-user" 오류 없이 적용

## 5. PNG
- [ ] Import PNG(흰 문양/검정 배경, 구멍·여러 섬 있는 것) → 썸네일 표시
- [ ] Custom 선택 → 클릭 스탬프 / 드래그 크기 → 비매니폴드 오류 없이 적용
- [ ] Select > Select All by Trait > Non Manifold (Edit Mode)로 결과 확인: 선택되는 엣지 없음
- [ ] 기존 v0.5.9 프리셋도 목록에 보이고 동작

## 5-1. Base Mesh
- [ ] 왼쪽 목록에서 Base Mesh 선택 → Rectangle로 빈 곳에 드래그 → 3D 커서 위치에 새 상자, 원본 오브젝트 그대로
- [ ] 큐브 윗면 위에 Lasso → 큐브 표면 위에 새 판(큐브는 무변경)
- [ ] RMB 1번 → Flat / Chamfer / Bevel / Rounded·Dome 아이콘 팝업. 고르면 선택된 Base Mesh가 바로 바뀜
- [ ] Dome: 오목한 별 모양에서 경계부터 부드럽게 부풀고 튀어나온 면이 없음. Roundness/Height/Resolution 변경 반영
- [ ] 오른쪽 Height/Offset 변경이 즉시 반영, `Freeze Base Mesh` 후에는 변경 안 됨
- [ ] Ctrl+Z 한 번 = Base Mesh 생성 하나 취소

## 5-2. Loft / Surface
- [ ] 커브 3개(점 개수 다름) 선택 → Create Loft Surface → 부드러운 면. 커브 하나를 Edit Mode에서 움직이면 면이 따라 바뀜
- [ ] 한 커브 방향이 반대여도 꼬이지 않음 (꼬이면 섹션 행의 Reverse 버튼)
- [ ] 닫힌 원형 커브 2개 + Cap Ends → 닫힌 솔리드. Thickness, Apply Surface
- [ ] Sweep: 원 커브(단면) + 경로 커브(활성) → 튜브

## 5-3. ZBrush Bridge
- [ ] 메쉬 2개 선택 → Send → 교환 폴더에 OBJ 2개 (Blender 오브젝트는 따로 유지)
- [ ] ZBrush에서 하나 Import → 수정 → **같은 파일 이름으로 Export** → Blender `Import Back` → 그 오브젝트만 바뀌고 위치/회전 유지
- [ ] ZBrush에서 위아래가 뒤집혀 보이면 Forward/Up 설정 메모 (기본 -Z / Y)

## 5-4. Mesh Curve (0.9.0)
- [ ] Mesh Curve 도구 → Polyline으로 점 4개 → 둘째 점을 다시 클릭 → 그 점이 부드럽게(곡선) 바뀜, 새 점은 안 생김
- [ ] 그리는 중 점 더블클릭 → 직선 ↔ 부드러움 전환 / `S`로 새 점 종류 전환 / Enter로 확정
- [ ] Free Draw로 그리면 매끄러운 곡선
- [ ] 결과 선택 → 오른쪽 All Smooth / All Straight(Object Mode에서 동작), Curve Resolution, Profile Segments, Rotation X/Y/Z, Twist 즉시 반영
- [ ] 경로 선택 → Tab → 점 더블클릭 → 직선 ↔ 부드러움
- [ ] Curve Array: Rotation X/Y/Z와 Twist가 복제본에 반영

## 5-5. SubD Plane (0.9.0)
- [ ] Create SubD Plane → 3D 커서 위치에 Plane, 모디파이어 3개(Simple, Catmull-Clark, Solidify)
- [ ] Simple / Catmull-Clark 슬라이더를 각각 움직이면 둘 다 동시에 반영
- [ ] Thickness / Offset 즉시 반영, Tab → 엣지 선택 → E로 늘려도 모디파이어 결과가 계속 보임
- [ ] 엣지 선택 → Set Crease → 그 엣지가 날카로워짐 / Apply All → 모디파이어 사라지고 형태 유지

## 5-6. Radial Array (0.9.0)
- [ ] 비대칭 부품으로 Radial 생성 → 기본(Rotate Each Copy OFF)에서 모든 복제본이 원본과 같은 방향, 기울어짐 없음
- [ ] Ring Rotation X/Y/Z: 배열 전체가 돌아감 / Copy Rotation X/Y/Z: 각 복제본만 제자리 회전 / Start Angle
- [ ] Rotate Each Copy ON: 타이어 트레드처럼 원을 따라 회전

## 5-7. Split (0.9.0)
- [ ] Split Mode = Gap, Gap Width 0.05 → 사각형/원/직선 Split → 두 조각 사이에 틈, 두 조각 모두 닫힘
- [ ] Gap Width를 바꿔도 틈의 중심이 그린 선 위
- [ ] Side A = Bevel, Side B = None → 원본 쪽 절단 경계만 둥글고 `_Split` 쪽은 날카로움 / Swap Sides 후 반대로
- [ ] Lasso/Rectangle + Outline Corners Round/Chamfer: 그리는 동안 미리보기에 모서리 반영, Corner Width/Segments 반영

## 6. Smart Fuse
- [ ] 겹친 두 메쉬 → Create Live Smart Fuse → 패널이 오류 없이 그려짐 → Confirm
- [ ] 떨어진 두 메쉬 → 설명 메시지 후 원래 상태 유지(소스가 숨겨지지 않음)

## 7. 저장 / 재시작 / 비활성화
- [ ] 파일 저장 → Blender 재시작 → 파일 열기 → MECHA LAB 탭과 도구 동작
- [ ] Ortho Lock ON 상태로 저장 → 다시 열고 궤도 회전 → 원근으로 돌아가지 않음
- [ ] 애드온 비활성화 → Space/B/C가 Blender 기본으로, 오류 없음 → 재활성화
- [ ] MECHA LAB 탭 삭제 후에도 Sidebar/Space 오류 없음

## 8. 성능 (선택)
- [ ] 10만 면 메쉬에서 원형 컷 1회 체감 시간: ____ 초 / 그리는 동안 끊김 여부: ____
