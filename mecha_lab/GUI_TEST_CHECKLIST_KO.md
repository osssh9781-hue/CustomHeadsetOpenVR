# GUI 수용 테스트 체크리스트 — Mecha Lab 0.23.14 / Windows 11 / Blender 5.0.2

**새 파일**(File > New > General)에서 진행하세요. 실제 작업 파일로 테스트하지 마세요.
Window > Toggle System Console을 켜 두고, 오류가 나오면 **콘솔 전체 텍스트**를 복사해 전달해 주세요.
각 항목에 ✅ / ❌ / 메모를 적어 주시면 다음 수정에 그대로 사용합니다.

## A00000000000000000000000000000. 0.23.14 (미검증)
- [ ] 같은 어깨 판(cm 단위 장면)에 Cloth Plate를 다시 만들 때 파편 덩어리가 아니라 정상 판이 나오는지
- [ ] 큰 판에서 값 조정 → 작은 판 새로 그리기: 주름·Puff가 작은 판 크기에 맞는지; 비슷한 크기 판은 지난번과 같은 숫자인지
- [ ] 프리셋 저장(작은 판) → 큰 판에서 불러오기

## A0000000000000000000000000000. 0.23.13 (미검증)
- [ ] 패딩 Cloth Plate: 핀치가 얇은 V자로 파고드는지, 가운데 X자 능선이 없는지
- [ ] Space가 툴 메뉴를 열지 않는지; 라쏘 그리는 중 Space 누른 채 마우스 이동 → 외곽선 전체 이동, 놓으면 계속 그리기
- [ ] 사각형 / 원을 드래그하는 중 Space → 모양 전체 이동

## A000000000000000000000000000. 0.23.12 (미검증)
- [ ] 새 Cloth Plate 가운데가 평평한지, HUD Center Calm 슬라이더 0 ↔ 100 %

## A00000000000000000000000000. 0.23.11 (미검증)
- [ ] 새 Cloth Plate가 0.23.2처럼 테두리 주름이 깔끔한지 (중앙까지 번지지 않는지)
- [ ] HUD Surface Detail 슬라이더로 비대칭 잔주름을 켜고 끄기
- [ ] Padding / Puffer: 주름이 안으로 파고드는지, Folds In 슬라이더 0 / 1

## A0000000000000000000000000. 0.23.10 (미검증)
- [ ] PANEL CLOTH 박스 슬라이더: Puff 낮추면 덜 부푸는지, Gravity 낮추면 덜 처지는지 → Re-bake
- [ ] 큰 판(몸통)에서 Sim: Blender가 멈추지 않는지, 걸리는 시간
- [ ] Detail 1 → 3 올리고 Re-bake
- [ ] 큰 판 / 휜 판에서 천이 뒤집히지(몸 안쪽으로 들어가지) 않는지

## A000000000000000000000000. 0.23.9 (미검증)
- [ ] Cloth Plate 헤더 Sim 토글 + 프리셋 → 라쏘 → 바로 천 시뮬 결과(시간이 얼마나 걸리는지)
- [ ] 패널 PANEL CLOTH 박스: _PCloth 선택 시 프리셋 버튼으로 다시 굽기
- [ ] Panel Cloth 대화창: Preset을 바꾸면 값이 채워지는지, Collide Region / Body / None
- [ ] 세로 면(팔, 몸통 옆)에서 Cloth / Canvas 프리셋이 아래로 처지는지

## A00000000000000000000000. 0.23.8 (미검증)
- [ ] HUD Pinch 1(큰 주름) / Pinch 2(작은 주름) 슬라이더가 따로 움직이는지
- [ ] Cloth Plate 패널의 Panel Cloth 버튼: 대화창 값(Pressure / Shrink / Pin / Split ...) → 확인 후 `_PCloth` 오브젝트, 원본 숨김
- [ ] Edit Mode에서 면 선택 → F3 Panel Cloth
- [ ] Through 소매 두 판 선택 → Panel Cloth → 하나의 링
- [ ] 실제 PC(Windows)에서 걸리는 시간

## A0000000000000000000000. 0.23.7 (미검증)
- [ ] 헤더 Through 토글(Armor / Cloth Plate): 팔에 띠를 그으면 앞판 + 뒷판이 생기는지, Crease 값으로 꺾인 곳에서 나뉘는지
- [ ] 원근(Perspective) 뷰에서 Through 영역이 라쏘와 맞는지
- [ ] Through 판의 Face Size 슬라이더(실시간 재생성)
- [ ] Cloth 타입 Puffer / Cotton / Drape, Crumple 슬라이더는 N 패널 입력에 있음(HUD 슬라이더는 아직 없음)

## A000000000000000000000. 0.23.6 (미검증)
- [ ] Skin 버튼으로 6가지 순환(마지막 Croc Back), 악어 비늘이 둥글게 부푼 모양인지, 도마뱀 가시
- [ ] Croc Back 줄 방향이 원하는 방향인지(지금은 판 로컬 X/Y 고정)

## A00000000000000000000. 0.23.5 (미검증)
- [ ] Shell HUD: Organic / Edge Shrink / Shrink Width / Edge Irregular 슬라이더 - 경계가 휘고, 안쪽 넓고 바깥 좁게 쪼개지는지
- [ ] Skin HUD: Organic / Edge Irregular 슬라이더
- [ ] 큰 판에서 Shell 반응 속도(Detail 5)

## A0000000000000000000. 0.23.4 (미검증)
- [ ] 서 있는 면에 Cloth Plate: 주름의 가파른 쪽이 위, 완만한 쪽이 아래 / Fold Direction Down·Random
- [ ] 하단 툴바 Skin: 5가지 스킨, HUD 스킨 버튼·가장자리 버튼, 가장자리로 갈수록 비늘 작아짐
- [ ] 하단 툴바 Shell: 갑각판 모양, Lift N/E/S/W 버튼, Bulge / Gravity 슬라이더, HUD 위치(판 왼쪽)
- [ ] Skin/Shell 누른 뒤 일반 Cloth / Armor Plate 버튼을 누르면 크리처 레이어가 꺼지는지

## A000000000000000000. 0.23.3 (미검증)
- [ ] Cloth Plate 주름이 한쪽 가파름 / 반대쪽 완만, Fold Asymmetry / Fold Thinness 슬라이더
- [ ] Mesh Curve IK 버튼: 점 드래그 시 사슬이 길이 유지하며 따라오는지, Pin Start

## A00000000000000000. 0.23.2 (미검증)
- [ ] 왼쪽 Mirror 버튼: 기울이기 제스처, Enter/클릭 후에도 미러 모디파이어가 살아 있는지; Symmetry/Mirror 방향 표시가 화면 아래 가운데
- [ ] V = 도구 파이
- [ ] Cloth Plate Gravity 슬라이더로 주름이 아래로 처지는지
- [ ] Mesh Curve(툴바 Curve): 선택 상태에서 흰 점/주황 점 드래그, 아래 버튼 줄 버튼·슬라이더, Repeat에 내 오브젝트 링크 후 그 오브젝트 수정 시 따라 바뀌는지, Distance 간격

## A0000000000000000. 0.23.1 (미검증)
- [ ] Tube 점 옆 주황 핸들 드래그 → 그 점만 굵기 변경, 헤더 Radius 표시

## A000000000000000. 0.23.0 (미검증)
- [ ] 하단 툴바 Tube → 바로 그리기, 클릭으로 점, 솔리드 튜브가 바로 보이는지, 흰 점·연결선 표시
- [ ] 선 위 클릭 = 삽입, 드래그, Ctrl+휠 점 굵기, X 삭제, Enter 끝 / Edit Points로 다시 편집
- [ ] N 패널: Radius, 테이퍼, Profile, Cap, Hole, Twist, B-Spline, Closed, Repeat(구 / 고른 오브젝트, Count), Apply

## A00000000000000. 0.22.2 (미검증)
- [ ] Armor Plate + Surface: 앞에서 점 찍고 옆으로 돌려 계속 찍기 → Enter → 판이 표면에 맞게, 팝업 슬라이더로 수정
- [ ] Cloth Plate + Surface, Line + Surface(띠)

## A0000000000000. 0.22.1 (미검증)
- [ ] Q 한 번: Select ↔ 마지막 도구 왕복, Shift+Q: 도구 파이
- [ ] 로봇 인간형 패널에 몸통/머리 없음
- [ ] Cut/Split + Surface: 점이 표면에 붙고, 화면을 돌려도 선이 메쉬에 붙어 있는지(앞쪽 진하게, 가려진 부분 흐리게), 표면 따라 선, 점 드래그
- [ ] 팔을 한 바퀴 감고 Enter → 팔과 몸통이 Gap만큼 떨어져 별도 오브젝트, Ctrl+Z로 되돌리기

## A000000000000. 0.22.0 (미검증)
- [ ] Robot Base Mesh 인간형 패널에 Chest (Ribs) / Pelvis / Head, 팝업 슬라이더 이름(어깨 폭, 가슴 …)이 부위에 맞게
- [ ] Bulge Shape 0 → 1 → 2(둥근 → 원기둥 → 네모), 범위 크게 움직이는지
- [ ] Top/Bottom Notch, Top/Bottom Hole + Depth, 깊이 합 100 %에서 관통
- [ ] 헤더 Line 버튼: Lasso 2점 + Enter / Stroke로 띠, Cut = 홈, Armor/Cloth/Base = 띠, 폭·끝 모양
- [ ] Detail Stamp: 원점이 바닥인 메쉬 → Add Selected → Start Stamping → 표면에 붙어 따라오는지, 클릭 배치, Ctrl/Shift/Alt+휠, 우클릭 종료, Blender 재시작 후 프리셋 유지

## A00000000000. 0.21.1 (미검증)
- [ ] Humanoid Forearm / Upper Arm / Thigh / Calf 추가 → 관절 없이 한 덩어리, 보내준 조각과 비슷한 비율
- [ ] 팝업 슬라이더 여러 열로 표시, 드래그 시 실시간 변경(Bottom Width, Taper Start, Muscle Split, Groove, Twist, Bend, Top Notch, Slant 등)
- [ ] N 패널 Limb Shape 목록

## A0000000000. 0.21.0 (미검증)
- [ ] N > Mecha Lab > Robot Base Mesh 패널: 4가지(Humanoid/Industrial × Sleek/Rugged) Whole Body, 부위 버튼 8개
- [ ] 파츠 선택 시 팝업: 슬라이더 드래그로 실시간 변경, Sleek/Rugged·Humanoid/Industrial·디테일 버튼, 새 랜덤
- [ ] 아랫면/윗면 모양 버튼(Style → Round → Square → Polygon), 변 수 슬라이더, Shape Change
- [ ] 베벨 폭/세그먼트/각도, Apply 후 일반 메쉬, Ctrl+Z

## A000000000. 0.20.4 (미검증)
- [ ] Section Height 슬라이더, 다음 Cloth Plate가 같은 숫자로 시작하는지
- [ ] 팝업 ✓(Save Preset) → 이름 입력, 프리셋 버튼 메뉴에서 불러오기/삭제, Blender 재시작 후에도 남는지

## A00000000. 0.20.3 (미검증)
- [ ] 왼쪽 버튼: Symmetry(기울여서 대칭, Enter 적용), Mirror(살아 있는 미러 + 팝업 Apply/Remove)
- [ ] 하단 툴바/Q 파이에 Symmetry 이름

## A0000000. 0.20.2 (미검증)
- [ ] Cloth Plate: 낱개 긴 주름(가는 시작, 반대편 직전까지), Randomness 슬라이더, Fold Tilt, Fan Mix
- [ ] 섹션 회전 / 솔기 모양 버튼 / Section Start·End·Move, 칸마다 둥근 쿠션
- [ ] 같은 도구를 다시 쓰면 직전 값이 유지되는지, 새 파일에서도 도구 설정 유지
- [ ] 아머 플레이트 Make High Poly: 원래 모양 그대로(울퉁불퉁하지 않게)
- [ ] Cut/Split 엣지 마감 폭 10 m까지

## A000000. 0.20.1 (미검증)
- [ ] Cloth Plate: 외곽은 붙고 안쪽이 부풀고, 테두리에서 부채꼴 주름(길이 제각각)
- [ ] 종류 ◀ ▶(Padding/Denim/Leather), Edge Trim(Piping/Binding/Welt), Sections, Reset
- [ ] 슬라이더를 움직이면 뷰포트에서 바로 바뀌는지 (0.20.0에서 안 바뀌던 문제)

## A00000. 0.20.0 (미검증 — headless 테스트만 통과)
- [ ] Cloth Wrinkle 도구: 라쏘 → 천 레이어, 팝업 종류 ◀ ▶(Padding/Denim/Leather), 새로고침, Height/Depth/Scale/Direction/Edge Soft/Detail/Thickness 슬라이더
- [ ] 우클릭 Make High Poly로 주름 하이폴, Apply로 확정
- [ ] 아머 플레이트 팝업 N/E/S/W, 랜덤 조각, Chamfer/Bevel 전환, Rim 슬라이더
- [ ] 라인 Width/Move/Turn, 높이를 크게 해도 라인이 같이 커지지 않는지, 어깨에서 높은 판이 울퉁불퉁하지 않은지

## A0000. 0.19.3 (미검증 — headless 테스트만 통과)
- [ ] 도형 버튼 옆 Sketch 버튼 켜기 → Cut: 라쏘 여러 개 그리기, Alt로 빼기, Enter로 한 번에 컷 (Alt+Enter = 안쪽 남기기)
- [ ] Armor Plate / Split도 같은 방식, Backspace 마지막 취소, Esc 지우기, 스케치가 도구 색으로 보이는지
- [ ] 끄면 예전처럼 바로 적용
- [ ] Tool Active / Reset Axis / Origin 버튼이 왼쪽 중간에 크게 보이는지

## A000. 0.19.2 (미검증 — headless 테스트만 통과)
- [ ] 아머 플레이트 → 우클릭 Make High Poly: 원래 모양/챔퍼 그대로, 면만 촘촘 (주름·울퉁불퉁 없음)
- [ ] 판 팝업 Lines 버튼 / 새로고침 / Crease 슬라이더: 윗면에 날카로운 꺾임 라인
- [ ] 얼굴처럼 좁은 판에 Soft Cloth + 큰 베벨/챔퍼: 구겨지지 않는지
- [ ] 원기둥 가장자리 밖까지 그린 판: 뾰족하게 튀는 조각 없는지
- [ ] 툴바 옆 Tool Active 버튼(켜기/끄기), 그 밑 Reset Axis / Origin to Geometry / Origin to 3D Cursor
- [ ] 미러·판·랜덤 패널·프리미티브 팝업이 값 바꿔도 처음 자리에 그대로 있는지
- [ ] Q 파이 Base 칸 밑 Plate, 라쏘 설정 밑 Bevel/Chamfer 슬라이더

## A00. 0.19.1 (미검증 — headless 테스트만 통과)
- [ ] 왼쪽 떠 있는 도구 버튼 줄이 사라졌는지
- [ ] 오브젝트/아머 플레이트 선택 → 우클릭 → Make High Poly → HighPoly 컬렉션에 복사본, 원본 숨김
- [ ] Flat 모드에서 곡면이 매끈하고 판 모서리는 날카로운지
- [ ] 왼쪽 아래 조정 창(F9)에서 Smoothness / Edge Softness 바꾸면 바로 다시 만들어지는지
- [ ] N > High Poly > Show Low / Show High, File > Export > FBX로 하이폴만 선택해서 내보내기

## A0. 0.19.0 (미검증 — headless 테스트만 통과)
- [ ] 하단 툴바 / Quick 팝업에 Plate 버튼, 누르면 Armor Plate 도구
- [ ] 판을 그리면 기본으로 면이 적은 판(Face Size 120), 오른쪽에 Apply / Remove / ◀ ▶ / Height·Chamfer·Bevel·Face Size 슬라이더
- [ ] 슬라이더 드래그 중 판이 바로 바뀌는지, Esc/우클릭 취소 시 원래 값으로
- [ ] Face Size 바꾸면 같은 윤곽으로 면이 다시 만들어짐 (뷰를 돌린 뒤에도 같은 자리)
- [ ] Apply → 팝업 사라지고 일반 메쉬, Ctrl+Z로 되돌아가는지 / Remove → 판 삭제

## B. 0.18.2
- [ ] 반투명 도형 다이얼 X/Y/Z, Station 다이얼(위아래·좌우·비틀기)을 시계 방향으로 돌리면 도형도 화면에서 시계 방향
- [ ] 반대면 Icon Size 패널의 Flip Dial Turning 끄기 → 맞게 도는지

## C. 0.18.1
- [ ] Polygon Prism 선택: 위/아래 끝에 초록 + / − 와 "Add segment" / "Remove segment" 글씨, 누르면 위(아래)에 구간이 붙음/지워짐

## D. 0.18.0 Mirror HUD
- [ ] Mirror 도구로 미러 → 클릭(라이브 유지): 메시 오른쪽에 Apply / Remove / X / Y / Z / Bisect / Flip side
- [ ] X·Y·Z·Bisect·Flip 누르면 미러가 바로 바뀜, 켜진 것 주황색
- [ ] Apply = 굽기, Remove = 지우기

## E. 0.17.0 Random Panels
- [ ] Armor Plate 패널 > RANDOM PANELS > Generate: 메시 오른쪽에 HUD(Reroll / Apply / Cancel / Edge Pieces / Mirror + 슬라이더 2개)
- [ ] Reroll = 다른 배치, Density / Panel Size 슬라이더로 바로 바뀜
- [ ] Edge Pieces 켜면 판 테두리 일부에 조각
- [ ] Mirror 켜면 한쪽 판이 반대쪽에 복사(Mirror 도구 설정 따름)
- [ ] Apply = 유지, Cancel = 이번 배치 지움
- [ ] 편집 모드에서 면 일부 선택 후 Generate: 그 면에만

## F. 0.16.0 Armor Plate
- [ ] 툴 목록에서 Armor Plate → 메시 위에 라쏘 → Enter: 별도 장갑판 생김, 원래 메시 그대로
- [ ] 판 테두리가 그린 선 그대로(로우폴리 박스·스컬프트 둘 다)
- [ ] 그리는 중 마우스 휠: 상태줄에 프로필 이름 바뀜, 그 프로필로 생성
- [ ] 패널 프로필 버튼: 선택한 판이 바로 바뀜. 높이·챔퍼·베벨 슬라이더 라이브
- [ ] 판 위에 또 그리면 아래 메시에 새 판
- [ ] 곡면(구·헬멧) 위에서도 판이 표면에 붙음

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
