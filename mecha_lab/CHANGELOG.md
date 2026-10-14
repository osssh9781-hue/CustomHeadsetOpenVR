# CHANGELOG

## 0.23.1 — Tube: 점마다 주황 굵기 핸들 (2026-10-14)

- 각 점 옆에 **주황 점(굵기 핸들)**: 드래그하면 **그 점의 굵기만** 바뀜(점에서 핸들까지 거리 = 그 점의 반지름), 드래그 중 헤더에 `Radius: 0.xxxx` 표시. Ctrl+휠도 그대로.
- 테스트: 45개 파일 1961/1961 (`tests/test_log_bpy501_v0231.txt`). ZIP sha256 `40c90b05879f4bc74a37b8b88009f55330569a53b93119382a80bade467ade36`.

## 0.23.0 — Tube / Curve 도구 (Nomad 방식) (2026-10-14)

- 새 도구 **Tube**(하단 툴바, Shift+Q 파이의 Radial 칸 아래). 고르면 바로 그리기 시작.
  클릭 = 점 추가(메쉬 위면 표면에, 아니면 마지막 점 깊이의 허공), **선 위 클릭 = 점 삽입**, 점 드래그 = 이동, **Ctrl+휠(점 위) = 그 점 굵기**, X / Delete(점 위) = 삭제, Enter / 우클릭 / Esc = 끝(살아 있음), 가운데 버튼·휠 = 화면.
- 검은 커브 선이 아니라 **처음부터 솔리드 메쉬**. 점은 흰 점 + 연결선으로 표시.
- **Tube 모드**: Radius, Start / End Size(테이퍼), Profile Round / Square / Flat(Ratio), Sides, Cap Flat / Round / Open, **Hole**(속 빈 파이프), Rotate, Twist.
- **Repeat 모드**: 고른 오브젝트(비우면 구)를 커브를 따라 Count개, Size, Follow Radius(점 굵기 따라 크기), Align to Curve.
- 커브: Smooth(점을 지남) / **B-Spline**(Nomad처럼 부드럽게) / Linear, **Closed**, Resolution. N 패널 Tube / Curve: Edit Points(다시 편집), Apply(일반 메쉬).
- 미리보기 `reference/tube_tool_v0230.png`(둥근 테이퍼 튜브 / 네모 파이프+Twist / Repeat 구). 테스트: 45개 파일 1958/1958 (`tests/test_log_bpy501_v0230.txt`). ZIP sha256 `acaefe96cb9e9c3319ce4d55cceb66f16d25dfc6aeda91277f9b727f2753307a`.

## 0.22.2 — Surface Lasso로 Armor Plate / Cloth Plate (2026-10-14)

- Armor Plate / Cloth Plate 헤더에도 **Surface** 버튼: 점을 메쉬 표면에 찍고(화면을 돌려가며 옆면까지 이어 그리기 가능) **Enter = 그 외곽선으로 플레이트 생성**. 만들어진 플레이트는 기존처럼 살아 있음(팝업 슬라이더·프리셋 그대로, Apply까지 수정 가능).
- **Line + Surface**: 표면을 따라 그은 선을 Line Width 폭의 띠 플레이트로.
- 원리: 그린 영역의 평균 표면 방향에서 똑바로 본 시점으로 외곽선을 넘겨 기존 플레이트 계산을 그대로 사용. 그래서 한 판은 **한쪽에서 보이는 범위(대략 반 바퀴 미만)** 까지 — 팔을 완전히 한 바퀴 감는 판은 두 장으로 나눠 주세요.
- 핀·소켓 커넥터(3단계)는 하지 않음.
- 미리보기 `reference/surface_lasso_plate_v0222.png`(앞면에서 옆면까지 그린 판). 테스트: 44개 파일 1912/1912 (`tests/test_log_bpy501_v0222.txt`). ZIP sha256 `7da9482b1e03ee42f2d2c6b6bd5ce1e6bd8bfd3a1e1406ce7a02b4f763b4525c`.

## 0.22.1 — Q 한 번으로 왕복, 인간형 몸통/머리 제외, Surface Lasso 1단계 (2026-10-14)

- **Q = Select ↔ 마지막 도구**(Tab처럼 Q 하나로 왔다갔다). 도구 파이는 **Shift+Q**로 이동. (Preferences에서 예전에 키를 직접 바꿔 저장했다면 그 설정이 우선)
- 로봇 베이스 메쉬 인간형: **몸통(갈비/골반)·머리 버튼과 Whole Body에서 제외**(직접 만드시는 부분). 인간형 = 어깨, 윗팔, 아랫팔, 허벅지, 종아리, 발.
- **Surface Lasso**(Cut / Split, 헤더 **Surface** 버튼 + Gap): 클릭한 점이 **메쉬 표면에 붙고 3D로 저장** → 그리는 중에 화면을 돌려도 선이 메쉬에 붙어 있음.
  점 사이 선은 **표면을 따라감**. 점 드래그로 수정(뒤쪽에 가려진 점은 안 잡힘), 첫 점 클릭 = 닫기, **Enter = 루프를 따라 분리**(Gap 두께, 정확 불리언, 조각마다 별도 오브젝트, 큰 쪽이 원래 이름), Backspace = 마지막 점, Esc / 우클릭 = 취소, 가운데 버튼·휠 = 화면 이동.
  루프가 부위를 한 바퀴 감지 않으면(예: 윗면에만) 메쉬를 안 바꾸고 알려줌.
- 테스트: 43개 파일 1902/1902 (`tests/test_log_bpy501_v0221.txt`). ZIP sha256 `4af3ae8763ee90122bfd0953153ec4c13548ab3d663feafa87546040160e296c`.

## 0.22.0 — 갈비/골반/머리, 과한 슬라이더, 불지 모양, 위아래 노치·구멍, 라인 라쏘, 디테일 스탬프 (2026-10-14)

**Robot Base Mesh**
- 인간형 몸통을 **Chest (Ribs, 갈비)** 와 **Pelvis (골반)** 로 나눔 + **Head**. 보내주신 BODY / HEAD 조각에서 높이별 단면을 재서 부드럽게 만든 형태가 기본(`robot_templates.py`).
  부위마다 슬라이더 8개 — 갈비: 어깨 폭, 가슴(대흉근), 등/광배, 갈비 벌어짐, 허리, 목 밑, 승모근, 숙임 / 골반: 엉덩이 폭, 허리, 엉덩이(뒤), 배, 사타구니, 골반 두께, 아래 폭, 기울기 / 머리: 두개 폭, 두개 길이, 뒤통수, 턱 폭, 턱끝, 얼굴 납작, 정수리, 목 굵기.
  **Anatomy Detail**: 0 = 단순 타원, 1 = 잰 형태, 4까지 = 과장.
- **슬라이더 범위를 크게**: Bulge -100~600 %, Muscle Split / Groove 400 %, Ridge 600 %, 아래 굵기 500 %, Twist ±720°, Bend ±400 %, 노치 60 %, 기울기 ±75°, 부위 슬라이더 -300~600 %.
- **Bulge Shape**: 0 = 둥근 볼록, 1 = **원기둥 띠**, 2 = **네모 띠**. **Bulge Width** = 띠 길이. (팔다리 + 갈비/골반/머리)
- **위아래 노치**: Top Notch / Bottom Notch + 각각 폭.
- **구멍**: Top Hole / Bottom Hole(크기) + 깊이. 두 깊이 합이 100 %가 되면 **관통(튜브)**.
- 모든 팔다리·갈비·골반·머리가 같은 튜브 빌더 사용(닫힌 메쉬, 노멀 바깥). Whole Body(인간형)는 Chest + Pelvis로 15조각.

**라인 라쏘** — 헤더 Sketch 옆 **Line** 버튼: Lasso / Curve Lasso / Brush Stroke로 그은 **선**을 따라 **Line Width** 폭의 띠(끝 Round / Flat)로 도구 실행. Cut / Split = 홈, Base Mesh / Armor Plate / Cloth Plate = 띠. 점 찍기는 2점부터, 더블클릭 / Enter로 끝.

**Detail Stamp** — N 패널 **Detail Stamp**: 내 메쉬를 프리셋으로(**원점 = 디테일 바닥**, 선택 후 Add Selected). 프리셋은 config/mecha_lab/details/에 파일로 저장돼 모든 파일에서 사용.
Start Stamping → 마우스 아래 표면에 **붙어서 노멀 방향으로 따라다니고**, **Sink**만큼 살짝 안으로 들어감. **클릭하면 그 자리에 바로 배치**(Apply 없음)되고 계속 찍기. Ctrl+휠 회전, Shift+휠 크기, Alt+휠 Sink, 우클릭/Esc 끝. Join to Surface 옵션(켜면 찍은 표면 메쉬에 합침).

- 미리보기 `reference/robot_torso_head_v0220.png`, `reference/robot_vs_reference_side_v0220.png`. 테스트: 42개 파일 1880/1880 (`tests/test_log_bpy501_v0220.txt`). ZIP sha256 `900785f05dcdbc090e31e0945cbd636f41960ce9851cd8a8003cbe77dea30784`.

## 0.21.1 — 인간형 팔다리: 보내주신 Genesis 9 조각 기준, 슬라이더로 형태 잡기 (2026-10-14)

- 인간형 **윗팔 / 아랫팔 / 허벅지 / 종아리**를 새로 만듦: **관절 없이** 한 덩어리, 깔끔한 사각 링 + 평평한 끝면.
  기본 비율은 보내주신 조각에서 잼(1.8 m 기준): 아랫팔 팔꿈치 9.2×7.7 → 손목 5.3×5.3 / 길이 24.6, 윗팔 9.6×11.0 → 8.2×8.4 / 23.4, 허벅지 17.1×17.4 → 무릎 11.4×12.4 / 38.8, 엉덩이 쪽 비스듬한 단면.
- 팔다리 전용 슬라이더(팝업 + N 패널): **Bottom Width / Bottom Thickness**(아래쪽 굵기), **Taper Start**(어디서부터 가늘어지는지), **Bulge / Bulge Position / Bulge Front/Back**,
  **Muscle Split + Split Angle**(근육 두 덩어리, 옆/앞뒤), **Groove + Angle**(근육 사이 홈), **Ridge + Angle**(능선), **Twist**, **Bend + Direction**, **Top Notch + Width**(팔꿈치 쪽 V 홈), **Bottom Slant / Top Slant**(끝 단면 기울기).
  슬라이더가 많으면 팝업이 여러 줄(열)로 나뉨.
- 패널: 부위 버튼이 위, Whole Body는 아래 작은 버튼. Details(장갑판·피스톤) 기본 꺼짐 = 순수 베이스.
- 수정: 산업형 팔다리 노멀이 안쪽으로 뒤집혀 있던 문제.
- 비교 렌더 `reference/robot_limbs_vs_reference_v0211.png`(왼쪽 = 보내주신 조각, 오른쪽 = 생성). 테스트: 39개 파일 1749/1749 (`tests/test_log_bpy501_v0211.txt`). ZIP sha256 `28f227289134c4da7e6791060171b5335ec1538150867f21caa73b543d485d4b`.

## 0.21.0 — Robot Base Mesh 생성기 (2026-10-14)

- N 패널 Mecha Lab > **Robot Base Mesh**: 큰 분류 **Humanoid(인간형) / Industrial(산업형)** × **Sleek(세련된) / Rugged(투박한)** = 4가지.
- 부위: **머리, 몸통, 어깨, 윗팔, 아랫팔, 허벅지, 종아리, 발**. **Whole Body** = 14개 파츠를 각각 **별도 오브젝트**로(좌/우 따로, 'Robot Base' 컬렉션). 부위 버튼으로 하나씩도 추가.
- 파츠마다 Apply 전까지 실시간: **길이, 폭, 두께, 테이퍼, 볼륨(Bulge), 둥글기, 해상도, 랜덤 정도, 시드**, 디테일 켜기/끄기, **베벨 폭 / 세그먼트(1 = 챔퍼) / 각도**(베벨 모디파이어, 각도 제한).
- **끝면 모양**: 아랫면 / 윗면을 각각 **Style(둥글기 따라) / Round(원) / Square(네모) / Polygon(N각, 3~16)** 으로 — 예: 아래는 원기둥, 위는 네모나 육각형으로 자연스럽게 변형. **Shape Change** = 어디쯤에서 바뀌는지. (발은 뒤꿈치 → 발끝)
- 뷰포트 팝업: Apply, 새 랜덤, Sleek/Rugged, Humanoid/Industrial, 디테일, 아랫면/윗면 모양 버튼 + 슬라이더(길이·폭·두께·테이퍼·볼륨·둥글기·해상도·랜덤·베벨·세그먼트·각도·아랫면/윗면 변 수·Shape Change).
- 미리보기 `reference/robot_base_preview_v0210.png`, `reference/robot_end_shapes_v0210.png`. 테스트: 38개 파일 1633/1633 (`tests/test_log_bpy501_v0210.txt`). ZIP sha256 `2a5e512f90a5c25c90d186bb953a677b9631b769b8411b10d6918b10eb40f6d8`.

## 0.20.4 — 섹션 높이, 같은 값 그대로, 내 프리셋 (2026-10-14)

- Cloth Plate **Section Height** 슬라이더: 퀼팅 칸이 부푸는 높이(패널 Puff 대비 0~500 %).
- **직전 값 = 같은 숫자 그대로**: Cloth Plate / Armor Plate가 기억한 값을 크기에 비례해 바꾸지 않음(Puff 0.980이면 다음도 0.980). 슬라이더를 놓으면 바로 저장.
- **내 프리셋**: 팝업의 저장(✓) 버튼 / 프리셋 버튼, N 패널 **My Presets** — 이름 붙여 저장, 불러오기(선택한 판 + 다음 판), 삭제. Blender를 다시 켜도 남음(config/mecha_lab/last_used.json).
- 테스트: 37개 파일 1581/1581 (`tests/test_log_bpy501_v0204.txt`). ZIP sha256 `cbbb020992bbcca716dca0103a18ed4c31f90c958aeb7a3d26543c071380271e`.

## 0.20.3 — Symmetry / Mirror 버튼 (2026-10-14)

- 기존 Mirror 도구 이름을 **Symmetry**로 변경(마우스를 복사할 쪽으로 기울이기, Enter = 적용). 하단 툴바·Q 파이·목록 이름도 Symmetry.
- 뷰포트 왼쪽 버튼 묶음(Origin to 3D Cursor 아래)에 **Symmetry**, **Mirror** 버튼 추가. Mirror = 선택 메쉬에 **살아 있는 미러 모디파이어**(바로 적용 안 함, 옆 팝업에서 Apply / Remove / 축).
- 테스트: 37개 파일 1578/1578 (`tests/test_log_bpy501_v0203.txt`). ZIP sha256 `f157cdd26be6e04deb19c6b879623c190ab8434b437fe77a7aec1e3a08e0afe1`.

## 0.20.2 — 긴 주름, 섹션 회전/모양/위치, 직전 옵션 기억, 하이폴 수정 (2026-10-14)

- **Cloth Plate 주름**: 테두리에서 시작하는 **낱개 주름**(시작은 아주 가늘고 안쪽으로 넓어짐), 주름마다 각도·길이·세기 랜덤, **반대편 직전까지** 뻗고 끝에서 약해짐,
  교차하는 곳은 부드럽게 합쳐짐. 부채꼴 다발을 군데군데 섞음(Fan Mix). **Randomness** 슬라이더 하나로 랜덤 강도 조절, Fold Tilt / Tilt Random / Length Random.
- **섹션**: Section Turn(회전), 솔기 모양 **직선 / 물결 / 지그재그 / V자 / 아치**(팝업 버튼), Seam Bend, **Section Start / End / Move**(구간 위치·범위 — 모서리에만 디테일),
  칸마다 **둥근 쿠션**처럼 부풀고 솔기는 눌린 선. 패딩은 더 둥글게.
- **전체 패턴**: 테두리 쪽이 강하고 가운데로 갈수록 약해짐(Center Fade), 랜덤으로 약한 얼룩(Patchiness).
- **직전 옵션 기억**: Cloth Plate·Armor Plate는 팝업에서 마지막에 쓴 값을 다음에 그대로(크기 비례). 도구 설정은 `config/mecha_lab/last_used.json`에 저장돼 **새 파일**에서 그대로(열어 둔 기존 파일은 안 건드림).
- **Make High Poly(아머 플레이트)**: 다시 투영하던 방식(얼굴에서 울퉁불퉁·리메쉬처럼 보임) 대신 **지금 모양에 각진 곳 크리스 + 서브디비전** → 모양 그대로 면만 촘촘.
- Cut / Split 두께(엣지 마감 폭, 갭, 사이드 폭) 슬라이더 범위 10 m까지.
- 테스트: 37개 파일 1576/1576 (`tests/test_log_bpy501_v0202.txt`). 미리보기 `reference/cloth_plate_preview_v0202.png`, `cloth_plate_sections_v0202.png`, `cloth_plate_tilt_v0202.png`. ZIP sha256 `00ea99cffb7adbe49395b853ec1393eecb15654bd68589cd764819cc23339325`.

## 0.20.1 — Cloth Plate: 외곽에서 시작하는 패딩 패널 (2026-10-14)

- 도구 이름 **Cloth Plate**. 이제 모든 변형이 **그린 영역의 외곽에서 시작**: 테두리는 표면에 붙고 안쪽이 **부풀어 오름(Puff)**, 테두리에서 안쪽으로 **주름**.
- 주름: 테두리의 점에서 **부채꼴로 퍼짐**(시작은 가늘고 촘촘, 안쪽으로 넓게), 주름마다 **길이·세기 랜덤**(길게 가는 것 / 짧게 끝나는 것), 시드로 방향·분포가 바뀜(Bend).
- 종류 = 프리셋 3개: **Padding**(많이 부풀고 부드러운 주름) / **Denim**(덜 부풀고 가늘고 긴 주름 많이) / **Leather**(중간, 굵은 주름 적게).
- **Sections**: 긴 쪽을 가로지르는 박음질로 칸을 나눠 칸마다 부풀기.
- **외곽 마감재(Edge Trim) 프리셋**: Piping(둥근 끈) / Binding(감싼 띠 + 박음질) / Welt(떠 있는 띠), 폭·높이 슬라이더.
- **박음질(Stitching)**: 테두리 안쪽 박음질 선, 실 땀이 긴 대시로 보이게.
- 팝업: 종류 ◀ ▶, 새로고침, Edge Trim, **Reset**, 슬라이더 Height / Sections / Puff / Puff Width / Edge Roll / Seam Folds / Fold Spacing / Fold Length / Fold Sharp / Fan / Stitching / Trim Width / Trim Height / Pattern / Scale / Direction / Bend / Detail / Thickness. N 패널 머리에 리셋 버튼.
- 수정: 슬라이더를 움직여도 뷰포트가 안 바뀌던 문제(모디파이어 값 변경 후 다시 계산 신호), 가파른 곳에서 두께(Solidify)가 가시처럼 튀던 문제, 모서리에서 주름이 끊겨 튀던 문제(실제 직선 거리 + 모서리에서 주름 페이드).
- 미리보기 `reference/cloth_plate_preview_v0201.png`. 테스트: 37개 파일 1565/1565 (`tests/test_log_bpy501_v0201.txt`). ZIP sha256 `f5e340bd6da5c349c56537645822e8e98e09c5c26f64c40c9f82c2baaf1d4ffd`.

## 0.20.0 — Cloth Wrinkle 도구 + 판 테두리(N/E/S/W·랜덤) + 라인 두께 (2026-10-14)

- 새 도구 **Cloth Wrinkle**(옷 주름): 라쏘로 그린 영역이 **별도 천 레이어**가 되고 **지오메트리 노드**로 주름이 생김(Apply 전까지 실시간).
  - 종류: **Padding**(퀼팅 패딩) / **Denim**(청바지 잔주름) / **Leather**(두꺼운 가죽 큰 주름) — 미리보기 `reference/cloth_wrinkle_preview_v0200.png`.
  - 팝업: Apply / Remove / 종류 ◀ ▶ / 랜덤(새로고침), 슬라이더 **Height(표면에서 높이)**, **Depth(주름 깊이)**, Scale(간격), Direction(방향), Edge Soft(테두리로 갈수록 약해짐), Detail(촘촘함), Thickness(두께).
  - Sketch 모드, 우클릭 Make High Poly(주름 디테일을 올린 촘촘한 복사본) 지원.
- **아머 플레이트 테두리 솟음**: 팝업 **N / E / S / W** 토글(켠 방향 테두리만 솟음, 넷 다 = 전체), **랜덤 조각**(테두리 근처 랜덤 위치, 다시 누르면 새로), **테두리 경사 Chamfer / Bevel** 전환 + Rim Height / Width / Slope / Turn 슬라이더.
- **표면 라인**: Line Width(평평한 띠 + 양쪽 날카로운 경사), Line Move(위치), Line Turn(회전). **Crease 높이는 이제 판 크기 기준**(판 높이를 키워도 라인이 같이 커지지 않음 — 높게 부풀릴 때 크게 접히던 원인).
- 높은 판이 둥근 곳(어깨)에서 퍼지며 울퉁불퉁하던 문제: 높이가 클수록 평균 방향으로 올라가고, 점 방향(노멀)을 부드럽게 다듬음.
- 테스트: 37개 파일 1558/1558 (`tests/test_log_bpy501_v0200.txt`), 신규 `test_v0194.py`, `test_v0200.py`. ZIP sha256 `6c5b1e920f36be1fc29ecbd7c8ccf88de3904dfb32c9e9cbb4a53bdb16766ce2`.

## 0.19.3 — 모든 라쏘 도구 Sketch 모드 (2026-10-14)

- 뷰포트 위 도형 버튼 옆 **Sketch** 버튼: 켜면 Cut / Split / Armor Plate / Base Mesh 모두
  **그리기 = 스케치에 추가, Alt+그리기 = 빼기, Enter = 한 번에 적용, Alt+Enter = Alt 동작(Cut: 안쪽 남기기 / Base: 파고들기)**, Backspace = 마지막 하나 취소, Esc = 지우기.
- 스케치는 첫 윤곽의 시점 평면에 놓여 중간에 뷰를 돌려도 됨; 적용은 첫 시점 기준. 겹침·구멍은 Base Mesh 스케치와 같은 방식(정확한 합치기/빼기).
- 기본은 꺼짐(Cut/Split/Plate). Base Mesh는 원래처럼 켜짐 — 버튼을 누르면 전부 같은 상태로 맞춰짐.
- 툴바 옆 Tool Active / Reset Axis / Origin 버튼을 뷰포트 왼쪽 중간으로 옮기고 아이콘·글씨를 키움 (Icon Size > Bottom Toolbar 배율을 따름).
- 테스트: 35개 파일 1518/1518 (`tests/test_log_bpy501_v0193.txt`), 신규 `test_v0193.py` 13항목. ZIP sha256 `2b6db8b31077fbcde548ec18bdb6106961fecc272f2112ac69c8966f5b9cc72e`.

## 0.19.2 — 판 하이폴 개선, 표면 라인, 찌그러짐 수정, Tool Active 버튼 (2026-10-14)

- **아머 플레이트 Make High Poly**: 서브디비전 대신 **같은 판을 작은 면으로 다시 만듦**(Plate Detail px, 기본 10) → 모양·챔퍼·모서리 그대로, 울퉁불퉁/주름 없음.
  Apply 한 판도 윤곽을 기억해서 나중에 하이폴 가능. 일반 메쉬는 기존 방식(베벨 지지 + 서브디비전).
- **표면 라인(Surface Lines)**: 판 윗면을 가로지르는 꺾임 라인 — Center / Cross / Random. 팝업에 **Lines 버튼**(끄기→가운데→십자→랜덤),
  **새로고침**(랜덤 다시), **Crease 슬라이더**(+ 솟은 능선 / − 파인 골). 라인은 실제 날카로운 엣지(가벼운 판에서도).
  N 패널 LIVE / Face Extract 설정에도 Line Count, Seed, Rotation.
- **좁은 곳 / 뾰족한 곳 찌그러짐 수정**: 얼굴처럼 폭이 좁은 곳에 큰 베벨·챔퍼를 주면 양쪽이 겹쳐 구겨지던 문제 → 그 자리의 폭에 맞게 자동으로 좁힘.
- **표면 밖으로 나간 윤곽** 점이 멀리 튀던 문제 수정(가까운 표면 깊이에 놓음), 원기둥 모서리 투영 보강.
- 뷰포트 왼쪽 위(블렌더 툴바 옆) **Tool Active 버튼**: 고른 Mecha 도구를 켜기 / 다시 누르면 Select. 그 밑에 **Reset Axis / Origin to Geometry / Origin to 3D Cursor**.
- **팝업(Apply 등)이 처음 뜬 자리에 고정**: 미러, 아머 플레이트, 랜덤 패널, 프리미티브(구간 +/−는 도형 끝을 계속 따라감).
- **Q 파이**: Base 칸에 Plate 추가. **라쏘 설정 바로 밑**(N 패널·우클릭 Shapes 팝업)에 엣지 Bevel / Chamfer 슬라이더.
- 테스트: 34개 파일 1505/1505 (`tests/test_log_bpy501_v0192.txt`), 신규 `test_v0192.py` 30항목. ZIP sha256 `c3faa3445145ecec90b3f18bf56d405e36a8582e1802e0f1bdbc943ed723ecdd`.

## 0.19.1 — 우클릭 Make High Poly + 왼쪽 메뉴 제거 (2026-10-14)

- 오브젝트 선택 → **우클릭 → Make High Poly**: 선택한 메쉬/아머 플레이트마다 하이폴 복사본을 `HighPoly` 컬렉션에 만듦 (원본 로폴은 숨기기만, 그대로 보존).
  - 각진 모서리(기본 35° 이상)에 베벨 지지 루프 → 판 모서리·챔퍼는 날카롭게, **곡면은 Subdivision으로 실제로 둥글게** (Flat 모드에서도 매끈).
  - 모디파이어 적용된 일반 메쉬 + Smooth: FBX는 Blender File > Export > FBX로 평소처럼.
  - 누른 직후 왼쪽 아래 조정 창(F9): Smoothness 1~3, Edge Softness, Sharp Edge Angle, Support Loops, Hide Originals, Join Into One — 바꾸면 바로 다시 만들어짐.
  - 같은 원본으로 다시 만들면 이전 복사본을 교체. 300만 면이 넘을 것 같으면 Smoothness를 자동으로 낮춤.
  - N 패널 **High Poly**: Make High Poly, Show Low / Show High(로폴·하이폴 번갈아 보기).
- 0.15의 **왼쪽 떠 있는 도구 메뉴 제거** (하단 툴바, Q 파이, Quick 팝업, N 패널 도구 목록은 그대로).
- 테스트: 33개 파일 1475/1475 (`tests/test_log_bpy501_v0191.txt`), 신규 `test_v0191.py`. ZIP sha256 `bdcda494dc8c844fd7bc690530af543475b9c57af841207903e4e221b8c7587c`.

## 0.19.0 — 아머 플레이트 실시간 조정 + Apply 팝업 (2026-10-14)

- **면 크기(Face Size) 기본 120 px** (최대 400): 기본으로 면 수가 적고 깔끔한 판이 나옴 (예전 14 px는 찰흙처럼 촘촘했음).
- 판을 그린 뒤 **Apply 전까지는 살아 있음**: 그린 윤곽선과 시점이 판에 저장되어, **Face Size**를 바꾸면 그 자리에서 새 면으로 다시 만들어짐.
- 판 오른쪽 **팝업(HUD)**: Apply / Remove / 프로필 ◀ ▶ / 슬라이더 4개 (**Height, Chamfer, Bevel, Face Size**) — 드래그하는 동안 바로 반영.
  N 패널에도 같은 항목(LIVE 상자: 높이, 챔퍼 폭·각도, 베벨, Apply / Remove).
- **Apply** = 지금 모양 그대로 일반 메쉬로 확정(모디파이어 적용, 실시간 연결 해제). **Remove** = 방금 그린 판 삭제.
- **퀵 메뉴**(Quick 팝업)와 **하단 툴바**에 **Plate**(아머 플레이트) 추가. (Q 파이는 8칸이 다 차 있어 그대로)
- 테스트: 32개 파일 1459/1459 (`tests/test_log_bpy501_v0190.txt`), 신규 `test_v0190.py` 20항목. ZIP sha256 `1aba16c1a96374eb16b879fd66af7f2e888193ae7744649640178fcc29a75fb9`.

## 0.18.2 — 회전 다이얼 방향 다시 수정 (2026-10-14)

- 기본 도형 / Station Primitive 다이얼을 돌리면 도형이 반대로 돌던 문제: 0.15에서는 화면 안쪽을 향한 다이얼만 뒤집었는데, Blender 다이얼 값 자체가
  우리가 적용하는 회전과 반대 방향으로 세어지고 있었음 → 회전값을 뒤집어서 마우스 방향 그대로 돌게 함.
- 혹시 사용 환경에서 여전히 반대면: N 사이드바 > Mecha Lab > Icon Size 패널(또는 Preferences)의 **Flip Dial Turning**을 끄면 원래대로.
- 테스트: 31개 파일 1439/1439 (`tests/test_log_bpy501_v0182.txt`). ZIP sha256 `d42bf7acb06f73f9a1ecfc407cbe069f6b7d73c29cc50d1701d429138a0b315a`.

## 0.18.1 — 구간 +/− 버튼 알아보기 쉽게 (2026-10-14)

- Station Primitive(Polygon Prism 등) 위/아래 끝의 **+ / −**(같은 단면 구간 추가/삭제)를 초록색으로 바꾸고 옆에 "Add segment" /
  "Remove segment" 글씨를 붙임. 오른쪽의 더하기/빼기 모드 버튼(주황/빨강)과 헷갈리지 않게.
- 테스트: 31개 파일 1438/1438 (`tests/test_log_bpy501_v0181.txt`). ZIP sha256 `e417cde7d73a648552f71bfce2e03a1a1735abc94c23c3b900edcca0401e65ce`.

## 0.18.0 — Mirror 떠 있는 버튼(HUD) (2026-10-14)

- Mecha Mirror가 걸린 메시를 선택하면(MECHA LAB, 오브젝트 모드) 메시 오른쪽에 프리미티브 HUD처럼 버튼이 뜸(`mirror_hud.py`):
  **Apply**(굽기) / **Remove**(지우기, 메시 그대로) / **X·Y·Z**(축 켜기·끄기) / **Bisect** / **Flip side**(반대쪽으로 복사).
  누르면 라이브 Mirror가 바로 바뀜(Mirror 도구 설정). 켜진 항목은 주황색. 마지막 축은 끌 수 없음(Remove로 지움).
- 테스트: 31개 파일 1438/1438 (`tests/test_log_bpy501_v0180.txt`), 신규 `test_v0180.py` 13항목. ZIP sha256 `9fd397beacf579662cd3e784e451d42c5786bdce1fcbf3c6891bb4673364a5cf`.

## 0.17.0 — Random Panels: 무작위 장갑판 배치 (2026-10-14)

- **Random Panels**(Armor Plate 패널 안, `random_panels.py`): 메시를 선택(편집 모드면 고른 면만) → Generate.
  - 표면을 무작위 중심점 기준으로 나누고(Lloyd 2단계로 크기 고르게), **Density**만큼 판으로 만듦.
  - 각 판은 **깨끗한 새 면**: 경계를 다각형으로 단순화 → **Gap**만큼 안쪽으로 → Armor Plate와 같은 방식으로 새 면을 채워 표면에 붙임.
    로우폴리(6면 박스)도 작업용 복사본을 자동으로 잘게 나눠서 됨. 원래 메시는 그대로.
  - **Seed**(같은 값 = 같은 배치), **Panel Size**, **Height Variation**, **Mix Profiles**(판마다 다른 프로필).
  - 옵션 **Edge Pieces**(테두리 조각): 판 경계 일부에 짧은 테두리 조각(Edge Molding 엔진, Edge Density / Edge Length).
  - **Mirror**: 기존 Mirror 도구 설정(축·로컬/월드)을 그대로 써서 한쪽에만 판을 만들고 Mecha Mirror 모디파이어로 반대쪽 복사.
- **떠 있는 HUD**(메시 오른쪽, 프리미티브 HUD와 같은 방식): **Reroll**(다음 Seed) / **Apply**(유지하고 닫기) / **Cancel**(이번 배치 지우기) /
  **Edge Pieces** / **Mirror** 토글, **Density**·**Panel Size** 슬라이더. 값을 바꿀 때마다 배치가 다시 만들어짐.
- Armor Plate: 판 만드는 부분을 `create_plate`로 분리(공용).
- 테스트: 30개 파일 1425/1425 (`tests/test_log_bpy501_v0170.txt`), 신규 `test_v0170.py` 24항목. ZIP sha256 `619ec073ecd210bfebb787b059d81a8eaa51fc6abd10f471b5e117c0b9b9316a`.

## 0.16.0 — Armor Plate: 메시 위에 라쏘 → 새 면으로 된 별도 장갑판 (2026-10-14)

- 새 도구 **Armor Plate**(왼쪽 툴 목록·아래/옆 툴바·Space 메뉴에 나옴, `armor_plate.py`).
  - 메시 위에 라쏘(클릭 = 점, 드래그 = 자유선, Enter / 더블클릭 = 생성, Esc = 취소, Shift = 45°, RMB = 모양: 사각형·원 등도 됨).
  - **리토폴로지 필요 없음**: 아래 메시 면을 쓰지 않고, 그린 선 안에 **새 깨끗한 면**(고른 격자 → 삼각분할 → 사각형으로 합침)을
    만들어 표면에 붙임(시선 방향으로 투영, 법선 유지). 6면짜리 박스·스컬프트·곡면 어디든 같은 품질.
  - **테두리 = 그린 선 그대로**: 선을 촘촘히 다시 나누고 그린 꼭짓점은 모두 유지(테스트: 0.1 px 이내).
  - 판은 **별도 오브젝트**("Mechanical Parts / Armor Plates"), 그린 메시는 그대로. Face Extract 엔진을 써서 높이·두께·챔퍼·베벨·바깥 가장자리·
    Armor Sculpt 설정을 나중에 그대로 다시 바꿀 수 있음(라이브).
  - **프로필 12종**: Flat, Chamfer 45, Steep Chamfer, Soft Bevel, Round Edge, Chamfer + Bevel, Flared, Thin Shell, Heavy Armor,
    Stepped Edge, Soft Cloth, Center Ridge. **그리는 중 마우스 휠 = 다음/이전 프로필**. 패널 버튼 = 다음 판 + 선택한 판에 바로 적용.
  - **Auto Size**: 프로필 크기가 판 크기에 맞춰짐. Face Size(px)로 면 촘촘함 조절(아주 큰 판은 자동으로 가볍게).
  - 판 위에 다시 그리면 판이 아니라 아래 메시에 새 판이 붙음. 선이 메시 밖으로 조금 나가면 그 점들은 표면 평면 위에 놓고 알림.
- 테스트: 29개 파일 1401/1401 (`tests/test_log_bpy501_v0160.txt`), 신규 `test_v0160.py` 25항목. ZIP sha256 `6abd7c3046e7322f11f965f46f24eb0973abee5848a8c6c954e7d6797547475c`.

## 0.15.0 — 아이콘 복구, 왼쪽 떠 있는 툴 목록, 프리미티브 HUD, Station 위아래+좌우+비틀기, 다각기둥 (2026-10-14)

- **아이콘 깨짐 수정**: 0.14.3의 "아이콘 = 버튼"은 Blender가 버튼 안 아이콘을 키우지 않아 길쭉한 빈 버튼이 됐음 → 큰 그림 + 이름 버튼(A안)으로 복구.
- **왼쪽 떠 있는 툴 목록**: 아래 툴바와 같은 둥근 버튼으로 모든 툴을 뷰포트 왼쪽(Blender 기본 도구 막대 옆)에 세로로. 이름은 버튼 오른쪽,
  지금 툴은 주황색, 화면 높이가 모자라면 여러 줄. Icon Size의 Bottom Toolbar 크기를 따름. 기존 왼쪽 "MECHA LAB TOOLS" 목록은 접힘.
- **프리미티브 HUD**(반투명 도형과 선택한 Station Primitive): 도형 오른쪽에 따라다니는 **[+ 더하기] [− 빼기] [✓ Apply]**, Apply 밑
  **슬라이더**(좌우로 끌기: 원형 도형 = Segments, 다각기둥 = Sides 3–64, 그 밖의 Station = Profile Resolution, 베벨한 박스 = 베벨 세그먼트).
  − 모드면 도형이 빨갛게 보이고 Apply / Enter가 빼기. Station Primitive Apply: + = 겹친 메시에 합치기(안 닿으면 그냥 확정), − = 파내기.
- **겹치는 면 경고**: 반투명 도형의 면이 메시 면과 같은 자리에 있으면(같은 크기로 빼기 등, Boolean 찌꺼기 원인) 그 면 테두리가 **빨간 점선**,
  HUD에 빨간 글씨 "조금 키우거나 줄이세요". 도형 전체 색은 그대로.
- **Station Primitive 꺾기**: 지점마다 **Up / Down**과 **Left / Right**를 따로(동시에) + **Twist**. 예전 Bend + 방향은 자동으로 변환(모양 동일).
  핸들을 반투명 도형과 같은 방식으로: 다이얼 3개(위아래·좌우·비틀기), 길이 화살표, 폭·위·아래 두께 **네모**. 꺾인 곳 바깥 **점** = 접힘 모양 순환.
- **다이얼 회전 방향 수정**: 다이얼 축이 화면 안쪽을 향하면 반대로 돌던 문제 → 다이얼을 항상 보는 쪽으로 뒤집어 마우스 방향 그대로 돎(기본 도형·Station 모두).
- **새 프리미티브: Polygon Prism**(Station Primitive 프리셋): 정사각기둥으로 서서 시작, Sides 3–64(원기둥에 가까워짐), 옆 모서리·끝 모서리
  **Bevel / Chamfer**, 도형 **위/아래 끝의 + / −** = 같은 단면 구간 추가/삭제(나머지 모양은 제자리), 구간마다 위아래·좌우·비틀기·길이 핸들,
  접히는 안쪽은 합쳐지고 바깥 **점 클릭** = 직각 → 약한 밴드 → 더 둥글게 → 가장 둥글게 → 직각. 전용 정N각형 단면(NGON)이라 어떤 면 수·접힘에서도 닫힌 메시.
- 테스트: 28개 파일 1365/1365 (`tests/test_log_bpy501_v0150.txt`), 신규 `test_v0150.py` 48항목. ZIP sha256 `76313363f6015ed9231289d0e15ba829ff0037cf08d2dd9c45837529fbc6b5c5`.

## 0.14.4 — Base Mesh 빼기 선 색 (2026-10-13)

- Base Mesh에서 그리는 선: 더하기 = 주황색, **Alt(빼기) = 빨간색**. 예전에는 둘 다 같은 주황색이라 헷갈렸음.
  (Sketch First가 꺼져 있을 때 Alt = 커터 선도 빨간색.) Cut / Split / Mask 색은 그대로.
- 테스트: 27개 파일 1315/1315 (`tests/test_log_bpy501_v0144.txt`). ZIP sha256 `9d1f28552f9af14e4ab6922f6820457903589b3681a0c4127df5d07e2128ce1a`.

## 0.14.3 — 프리미티브 핸들 개편·되돌리기, 테이퍼/베벨, Base Mesh 표면 붙이기, 툴 메뉴 타일, 아이콘 크기 저장 (2026-10-13)

- **Primitive 반투명 도형**
  - 도형을 고르기 전에는 나오지 않음(Primitive 도구에 들어가기만 해서는 안 뜸). Station Primitive를 만들면 숨겨짐.
  - 핸들 새 배치: 면마다 **네모 = 크기**(그 면만), 축마다 **화살표 = 이동**(도형 자신의 축 방향), **다이얼 3개 = X/Y/Z 회전**
    (드래그 시작 때의 방향을 기준으로 돌려 다이얼이 마우스 아래에서 같이 돌지 않음), 바깥 모서리 **점 2개 = 전체 크기**(비율 유지,
    Substance 방식), 가운데 링 = 자유 이동.
  - **Ctrl+Z / Ctrl+Shift+Z = 도형 편집 되돌리기/다시**(이동·크기·회전·모양). 드래그 하나가 한 단계. 되돌릴 도형 편집이 없으면 Ctrl+Z는 Blender 실행 취소.
    Enter 뒤에는 도형 기록이 비워져서 Ctrl+Z가 합치기를 취소.
  - 예전 파라메트릭 프리미티브에 있던 기능 복원: **위/아래 크기(Top X / Top Y, 축마다)** — 박스가 사다리꼴·쐐기·피라미드, 원기둥·알약이
    원뿔대로. **모서리 Bevel / Chamfer**(폭·세그먼트, 30° 넘는 모서리만, 실제 메시에도 적용).
  - **합치기 글리치 점검**: 합친 결과 메시는 깨끗함(모든 도형·솔버에서 열린 모서리·찌그러진 면·아주 짧은 모서리 0개). 문제는 표시였음:
    Enter 직후 반투명 도형이 새로 생긴 면과 정확히 겹쳐 깜빡이고, 뒷면까지 비쳐 보였음. → Enter 직후에는 외곽선만, 움직이면 다시 채움.
    면은 앞면만 그림. 살아 있는 Base Mesh에 합칠 때 동결(나중 재생성이 합친 모양을 지우던 문제).
- **Station Primitive 핸들 Ctrl+Z**: 핸들 드래그가 실행 취소 단계를 만들지 않아 Ctrl+Z가 생성 이전까지 돌아가 파란 도형이 다시 보였음.
  드래그가 멈추면 한 단계 기록.
- **Base Mesh: Stick to Surface**(기본 켜짐): 메시 위에 그리면 그 표면 방향(그린 영역 아래 평균 법선)으로 세워지고, 바닥이 표면에
  살짝 묻혀 붙음(곡면이면 틈이 안 생길 만큼 자동으로 더 깊게). Sketch First에도 적용. 끄면 예전처럼 화면을 향함.
- **왼쪽 툴 메뉴**: 넓은 글씨 칸 대신 타일(아이콘 위, 이름 아래). 칸 수는 왼쪽 영역 폭에 맞춰짐.
  **아이콘을 눌러도 실행**(툴·모양·PNG·프로필·프리미티브 격자 전부).
- **아이콘 크기 저장**: Blender 설정을 저장하지 않아도 다시 켤 때 유지(애드온 전용 파일 `config/mecha_lab/ui_sizes.json`).
- 테스트: 27개 파일 1313/1313 (`tests/test_log_bpy501_v0143.txt`), 신규 `test_v0143.py` 53항목. ZIP sha256 `60c5632b16f86f805f8383c8d95db75b597111d1658c10362eee877c502a3858`.

## 0.14.2 — 아이콘 크기 탭 (2026-10-13)

- 오른쪽 사이드바(N) > Mecha Lab 탭에 **Icon Size** 패널 추가(Preferences > Add-ons > Mecha Lab에도 같은 항목).
  - **Panel Icons** (0.5–2.5): 패널·메뉴·팝업의 도구/도형/프로필/PNG 썸네일 크기.
  - **Bottom Toolbar** (0.5–2.5): 아래 툴바 버튼 크기 + 버튼 사이 간격 + 이름 글자 크기. 기존 S/M/L과 곱해짐.
  - **Viewport Handles** (0.3–3.0): Primitive 반투명 도형과 Station Primitive 핸들(화살표·다이얼·점) 크기.
  - 프리셋 버튼 Small / Normal / Large / Huge = 세 값을 한 번에.
  - 기본값은 모두 1.0이라 움직이기 전에는 지금과 같음. 값은 애드온 설정에 저장(사용자 .blend 파일은 바뀌지 않음).
- 테스트: 26개 파일 1260/1260 (`tests/test_log_bpy501_v0142.txt`), 신규 `test_v0142.py` 13항목. ZIP sha256 `d87a87ef336679dbe52ae6b93a0e4afbe9c3ec3e79656634f7966e4f72aeb610`.

## 0.14.1 — Base Mesh 스케치 먼저 (주황색 모양 그리기 → 확정하면 메시) (2026-10-13)

- **Sketch First** (Base Mesh, 기본 켜짐): 그린 모양이 바로 메시가 되지 않고 주황색 스케치로 남음.
  - 그리기 = 스케치에 더하기, **Alt + 그리기 = 스케치에서 빼기**. 겹치면 하나로 합쳐지고, 안쪽을 빼면 구멍, 가로지르면 두 조각이 됨. 순서대로 계산(뺀 자리에 다시 그리면 섬).
  - 합쳐진 결과 외곽선이 주황색 선과 옅은 주황색 면으로 표시됨.
  - **Enter = 메시 만들기**: 합쳐진 모양으로 라이브 Base Mesh 하나를 만듦(프로필·높이·베벨은 기존 설정, 구멍 포함, 나중에 다시 편집 가능).
  - **Alt+Enter = 아래 메시에 파기**: 예전 Alt+드래그 커터와 같은 방식. 선택한 메시, 없으면 스케치 아래 메시.
  - **Backspace = 마지막 모양 지우기**, **Esc = 스케치 지우기**(스케치가 없으면 Esc는 원래대로 도구 나가기). Ctrl+Z로도 한 획씩 되돌아감.
  - 첫 획이 그리는 평면을 정함. 뷰를 돌려도 다음 획은 같은 평면 위에 그려짐.
  - 2D 합치기/빼기는 Blender 내장 삼각분할(`delaunay_2d_cdt`)로 계산: 선이 교차하는 점까지 정확히 나눈 뒤 각 삼각형이 어느 모양 안에 있는지로 판정.
  - 패널의 **Sketch First** 버튼으로 끄면 예전처럼 그리는 즉시 메시(Alt+드래그 = 커터).
- 테스트: 25개 파일 1247/1247 (`tests/test_log_bpy501_v0141.txt`), 신규 `test_v0141.py` 28항목. ZIP sha256 `a7c73a85c561308b550d36667b2e6c51ffd4dbbcb6f294433af5daceb35f8b2c`.

## 0.14.0 — 반투명 도형 찍기(Enter 합치기 / Alt+Enter 빼기), 알약 원기둥, 스탬프 커서 위치, 툴바 이름 (2026-10-13)

- **Primitive 도구 = 반투명 도형 찍기** (Substance 3D Modeler 방식, `primitive_place.py`):
  - Primitive 도구를 켜면 고른 모양이 반투명하게 바로 나옴(처음엔 3D 커서 위치).
  - 화살표 6개 = 크기. 한쪽 면만 움직이고 반대쪽 면은 고정(비대칭). 다이얼 = 도형 자체 Z축 회전, 가운데 링 = 이동.
  - 메시를 클릭하면 그 표면으로 이동("Align to Surface"가 켜져 있으면 표면 방향으로 세움). 드래그 = 박스 선택, Shift+클릭 = 선택.
  - **Enter = 겹친 메시에 합치기**(Boolean Union, 바로 확정). 아무것도 안 닿으면 새 오브젝트. 여러 개가 닿으면 활성 오브젝트, 없으면 가장 가까운 것.
  - **Alt+Enter = 빼기**: 닿은 모든 메시에서 파냄. Alt를 누르고 있으면 도형이 빨갛게 바뀜.
  - Enter 뒤에도 도형은 그 자리에 남아 바로 다음 도형을 찍을 수 있음. Esc = 숨기고 Select로.
  - 이음새: Hard / Chamfer / Smooth. 새로 생긴 이음새 모서리만 깎음(Cut의 Edge Finish와 같은 방식).
  - 라이브 Station Primitive·파라메트릭 프리미티브는 합치기/빼기 전에 동결됨.
  - 도형 상태는 WindowManager에 저장: Ctrl+Z로 위치가 돌아가지 않고 사용자 .blend에 저장되지 않음.
  - Primitive가 Blender 도구(`mecha.primitive`)로 등록됨. 기본 선택 도구가 클릭을 먼저 가져가던 문제 때문.
- **알약 원기둥(Pill Cylinder)**: 원기둥의 둥근 면을 늘린 모양. 단면 = 알약(두 반원 + 직선). X = 긴 쪽, Y = 폭, Z = 높이. 새 아이콘 포함.
- **알파(PNG) 스탬프·내장 스탬프 미리보기 위치 수정**: Blender는 도구 커서를 창 좌표로 그리는데 영역 좌표로 한 번 더 빼서,
  뷰포트가 창 안에서 떨어진 만큼 마우스와 어긋나 있었음. 이제 마우스 위치 그대로 그림(Blender 자체 Select Circle 커서와 같은 방식).
- **Primitive 패널**: 메뉴를 열지 않아도 오른쪽 사이드바(N) Mecha Lab 탭에 도형 그리드(썸네일 위, 이름 아래)가 바로 보임.
  다른 도구일 때도 "Primitive Shapes" 패널이 있어 클릭 한 번이면 Primitive 도구와 도형이 켜짐.
  RMB 도형 메뉴도 계단식 줄 대신 고른 격자. 예전 라이브 파라메트릭 프리미티브는 아래 접힌 칸에 그대로 있음.
- **아래 툴바**: 툴팁이 설명문 대신 버튼 이름과 단축키(예: "Cut  (C)"). 아이콘 밑 이름 표시가 기본으로 켜짐(이전에 끈 설정은 유지).
- 테스트: 24개 파일 1219/1219 (`tests/test_log_bpy501_v0140.txt`), 신규 `test_v0140.py` 46항목. ZIP sha256 `d02dc9f2137be4b32d94f667342739ff348449ac86c403d5199eb3cc89b5f3e9`.

## 0.13.2 — 아머 프리셋 5종 + Curved Plate 단면 (2026-10-13)

- 새 단면 **Curved Plate (armor)**: 휘어진 판. Top = 볼록한 높이(크라운), Bottom = 판 두께, 좌/우 두께 = 가장자리 두께 배율.
  반원까지는 진짜 원호(두께가 곡면을 따라 일정, 접힘 없음), 더 높으면 타원(헬멧). 다른 단면과 같은 정점 구성이라 지점별 전환 가능.
- **아머 프리셋** (사람 크기, 미터): Shoulder / Knee(관절 위로 말리는 캡), Upper Arm / Thigh(위가 넓은 긴 쉘), Forearm / Shin
  (관절 쪽 벌어짐 + 테이퍼 + 끝 커프), Torso / Chest(허리 → 가슴, 위가 목 쪽으로 넘어감), Helmet(크레스트 릿지, 뒤쪽 둥글게 닫힘).
  Primitive 패널의 "ARMOR" 묶음. 생성 후 지점·폭·볼록함·릿지 편집 가능.
- 테스트: 23개 파일 1172/1172 (`tests/test_log_bpy501_v0132.txt`), 신규 `test_v0132.py` 15항목. ZIP sha256 `b396f81af7448e4334c39ff38f90f6a66a98a5db7f73cbadde5482ac17a625e7`.

## 0.13.1 — Station Primitive: 옆으로 꺾기, Tight 직각, 지점별 단면, 뷰포트 핸들, Mirror 연동 (2026-10-13)

- **꺾임 방향**: 위/아래/왼쪽/오른쪽 버튼 + 자유 각도(엔진은 원래 지원, 패널에 숨어 있던 것을 앞으로). 옆으로 꺾으면 판이 평평한 채로
  평면 안에서 돌아감.
- **꺾임 방식** (지점마다): Fold(날카로운 접힘, 두께 유지) / **Tight**(거의 직각: 안쪽이 겹치지 않는 가장 작은 반경을 자동 계산) /
  Band(지정 반경) / Auto(반경 0 = Fold, > 0 = Band; 기존 파일 호환).
- **지점마다 단면 종류**: 모든 단면 종류가 같은 정점 구성을 쓰도록 바꿔 구간 안에서 이전 단면 → 다음 단면으로 이어짐(Loft처럼).
- **Left = Right** 토글(좌우 대칭 단면).
- **뷰포트 핸들** (`station_gizmos.py`, Primitive 도구 또는 Select/Move에서 살아 있는 Station Primitive 선택 시): 지점 점(클릭 =
  선택), 구간 가운데 +(클릭 = 그 자리에 지점 삽입, 모양 유지), 꺾임 각도 다이얼, 꺾임 방향 다이얼, 길이·좌/우 폭·두께 화살표.
- **Mirror/Symmetry**: 라이브 Mirror(Symmetry) 모디파이어가 지점 편집·재생성 중에도 유지. Mirror Apply(패널·Enter) 시 Station
  Primitive 동결(미러된 절반이 다음 재생성에 지워지지 않게).
- Cut 후 동결은 그대로(사용자 결정).
- 테스트: 22개 파일 1152/1152 (`tests/test_log_bpy501_v0131.txt`), 신규 `test_v0131.py` 28항목. ZIP sha256 `e5d7c53df793481454502b35a5fe2c28070cd7921ca136728ce8157da2281a6e`.

## 0.13.0 — Station Primitive (Advanced Parametric Primitive, Phase 1: 생성 엔진) (2026-10-13)

- 새 엔진 `station_sweep.py`(순수 기하): 단면 7종(Round/Oval, Capsule, Box, Rounded, Chamfer, Ribbon, Polygon) ×
  지점(Station) 사슬. 지점마다 꺾임 각도·방향·반경(0 = 접힘, 마이터로 두께 유지)·길이·비틀림·Local/World 방향,
  좌/우 폭, 위/아래 높이, 좌/우 두께, 좌/우 모서리, 릿지 높이·폭·위치. 구간 보간 Linear/Smooth/Step.
  릿지 6종(Crease, Raised, Box, Round, Groove, Double). 끝 마감 Flat/Round/Point/Open. 자동 세그먼트(각도·비틀림·보간),
  반경이 단면보다 작으면 올리고 경고.
- 지점은 앞 구간 끝 방향에서 시작: 지점 1을 바꾸면 뒤 사슬이 함께 돌고, 뒤 지점들의 값은 그대로(시나리오 E 테스트).
- Blender: `station_primitive.py` — 객체별 파라미터(저장 후 재편집), 항상 실제 메시로 재생성(GN 아님, Cut/Boolean 바로 가능),
  Shell(라이브 Solidify), 프리셋 6개(Flat Panel, Multi-Bend Armor, Wrap/Tyre Cover, Helmet/Teardrop, Automotive Panel, Duct),
  지점 추가(활성 지점 뒤, 값 복사)/삭제/순서, Apply. Primitive 도구 패널 맨 위(간단 + Asymmetry/Advanced 접기).
- 살아 있는 Station Primitive를 Cut/Split/Boolean 하면 먼저 동결(자른 결과가 다음 재생성에 덮이지 않도록)하고 메시지로 알림.
- 테스트: 21개 파일 1124/1124 (`tests/test_log_bpy501_v0130.txt`), 신규 `test_v0130.py` 50항목. ZIP sha256 `a9dba3e703b9d92e5f0cbd761033fb0f663bfe871f1a857641868192b83133f9`.
- 미구현: 뷰포트 지점 핸들(Phase 4), 헬멧 쉘 전용 옵션·릿지 구간(Phase 2), 랜덤 생성기(Phase 3).

## 0.12.0 — UX 프로토타입 v2.1의 최소 Blender 버전 (2026-10-13)

기준: 0.11.3 + 브라우저 프로토타입 v2.1. Cut/Split 엔진(기하 계산)은 그대로, 입력·도구 전환만 추가.
- **자동 대상 (Auto Target, 새 기본값)** / **선택만 (Selected Only)**: Cut/Split에서 그린 도형이 덮는 메시를 바로 자름
  (선택 무시). 도구를 유지한 채 다음 장갑판을 바로 자를 수 있음. 잘린 메시가 선택됨. 도구 헤더 토글 + **T** 키.
  잠금(선택 불가)·와이어 표시(커터 등) 오브젝트는 제외. 판정: 화면 경계 사전 필터 → 외곽선·내부 샘플 레이캐스트/중심점.
  Selected Only는 기존 동작(선택한 메시만). 빈 곳에서 시작한 도형이 아무것도 덮지 않으면 아무것도 바뀌지 않음.
- **Q = 도구 파이**(8개: Select, Cut, Split, Base, Boolean, Mirror, Primitive, Radial), **Shift+Q = Select ↔ 마지막
  모델링 도구**. 둘 다 MECHA LAB에서만(밖에서는 Q = Blender Quick Favorites).
- **V 비움, N = Blender 사이드바로 복귀.** F = Select/Move, Space = 큰 도구 메뉴, B/C 그대로.
- **하단 툴바**: 뷰포트 하단 가운데 2D 버튼 기즈모(모달 아님), 현재 도구 주황 표시, 크기 S/M/L, 아이콘 아래 이름(선택).
  Preferences에서 끄기 가능.
- 마지막 도구·Select 상태는 WindowManager에 저장(Undo에 안 섞이고 파일에 저장 안 됨).
- 테스트: 20개 파일 1074/1074 (`tests/test_log_bpy501_v0120.txt`), 신규 `test_v0120.py` 27항목. ZIP sha256 `270841f19e16687320f5e91e0567a7e5b6b414dd5407e8228a1140304417c7fe`.
- 프로토타입 v2.1(별도 HTML): Box Hide Apply가 복원 기록을 버리던 버그 수정, 자동 대상/선택만, 메시별 Cap,
  아이콘 이름 표시, 옵션 카드 접기·위치·자동 흐림.

## 0.11.3 — 스탬프 도형 6종, 단축키, Ctrl+Z 도형 유지, Cable→Mesh, Curve Lasso 원래 방식, Mirror 업그레이드 (2026-10-13)

- **기본 스탬프 도형 6종** (Lasso / Stamp 도형 팔레트): 오각형, 사다리꼴, 기울어진 알약 3개(나란히, 각각 분리),
  삼각형, 둥근 홈 박스(원기둥으로 파낸 모양), 다각형 홈 박스. 애드온 안에 포함(`shapes/builtin_shapes.json`,
  `icons/shape_*.png`, 생성기 `tools_dev/make_shapes.py`) — 사용자 폴더에 쓰지 않음, 삭제 불가. 클릭 = 찍기, 드래그 = 크기/회전.
- **단축키** (MECHA LAB에서만): Tool Menu = **V**(Space도 유지), Quick Menu = **N**, Select / Move = **F**.
  MECHA LAB의 Object Mode에서는 N이 사이드바 대신 Quick Menu (다른 Workspace는 Blender 기본 그대로).
- **Ctrl+Z가 도형을 예전 것으로 되돌리던 문제**: 도형·스탬프·선택 도구가 Scene 데이터라 Undo에 포함됐음 →
  undo/redo 직전 값을 기억했다가 직후 복원(`tool_state.snapshot_ui_state / restore_ui_state`).
- **Cable: Convert to Object (Mesh)** 버튼 — 같은 이름의 메쉬 오브젝트로 굽고 커브·숨은 단면 커브 정리.
- **Curve Lasso 원래 방식 복구 (ChatGPT v0.7.2 규칙)**: 점은 처음에 직선 모서리, 점 클릭마다 약 → 중 → 강 → 직선 순환,
  파란 핸들 드래그로 둥글기 조절. (0.8.0에서 기본 곡선 스플라인으로 바뀌었던 것을 되돌림.)
- **Mirror 업그레이드 (HardOps 방식)**: Mirror 도구를 고르면 바로 라이브 미러 시작(`mch.mirror_lean`).
  마우스를 복사하고 싶은 쪽으로 기울이면 그 축/방향으로 미러(Bisect: 그 쪽이 반대쪽 복사본으로 바뀜).
  **Enter / Space = 적용(Apply)**, 클릭 = 라이브 유지, Shift+클릭 = 축 추가, X/Y/Z = 축 토글, B = Bisect, Esc/우클릭 = 취소(원상복구).
  패널: "MIRROR: LEAN MOUSE TO SIDE" 버튼, "Copy toward +X/Y/Z", "Start when Mirror is picked". Bisect 기본 ON.
- **충돌(크래시) 대비**: 단축키 편집 행이 KeyMapItem을 모듈 리스트에 붙잡고 다시 그리던 방식(해제된 메모리 접근 위험) →
  매번 새로 찾음. Ortho Lock이 카메라 뷰를 건드리지 않음. Radial Array 자체는 headless에서 충돌 재현 안 됨.
- 테스트: 19개 파일 1046/1046 (`tests/test_log_bpy501_v0113.txt`), 신규 `test_v0113.py` 35항목. ZIP sha256 `deed2943d3d8276a383cdf338455d393e508cf337c6d42e01a1f98c9604e2c37`.

## 0.11.2 — 일반 Cube Cut/Split 오류 추적용 진단 + Edit Mode Cut 수정 (2026-10-13)

사용자 보고: 0.11.1에서도 일반 Cube Cut/Split이 "whole object"로 실패. headless(실제 RegionView3D 원근/직교 포함)에서는
재현되지 않음 → 원인을 사용자 환경에서 바로 확인할 수 있게 함.
- 실패 메시지에 사실 정보 추가: 그린 도형이 오브젝트 정점 몇 개를 덮는지(화면 루프 + 깊이 범위), 도형 픽셀 범위와 뷰 크기,
  PERSP/ORTHO, Alt/반전 상태, **실행 중인 Mecha Lab 버전**. 같은 내용이 시스템 콘솔에 `[Mecha Lab] cut failed:`로 출력.
  - 도형이 정말 오브젝트 전체를 덮으면: "The drawn shape covers the whole of ..."(정상 거부, 이유 명시).
  - Alt 반전인데 겹치지 않으면: "does not intersect"(다중 대상에서는 건너뜀 목록으로).
- Self Test에 **실제 3D View 투영으로 Cut / Alt Cut / Split** 단계 추가(뷰 중심에 임시 큐브, 끝나면 삭제). 13단계.
- Edit Mode에서 Cut/Split 시 `to_mesh(): Mesh is in editmode` 오류 → Object Mode로 나간 뒤 실행.
- 테스트: 1012/1012 (`tests/test_log_bpy501_v0112.txt`). ZIP sha256 `000db2d3d84a0215dcfd1b55fcd296e59267c1e091a2be5d04af7593676c0aa5`.

## 0.11.1 — Cut/Split "whole object" 오류 수정, Alt 모드 전환 롤백, Select / Move (2026-10-13)

기준: 0.11.0. 입력·작업 상태 관리 부분만 v0.9.3 방식으로 복구, 다른 기능은 그대로. 검증은 Linux headless bpy 5.0.1뿐.

- **Alt+뷰포트 클릭 모드 전환 완전 삭제**: 빈 곳 Alt+클릭 → 선택 모드, 오브젝트 Alt+클릭 → 도구 복귀, `ALTWAIT` 단계,
  `alt_pending`/`alt_wait`, `ALT_CLICK_SEC`/`ALT_DRAG_PX`, `_alt_begin_drag`/`_modal_altwait`/`_modal_alt_pending`,
  `mch_last_tool` 저장, `MCH_OT_alt_click_return` 연산자와 Object Mode `Alt+LEFTMOUSE CLICK` 키맵, `alt_click_return` 설정 제거.
- **Cut/Split 입력 v0.9.3 복구**: 누를 때 대상 수집 후 바로 획 시작, `alt_latch`(누를 때 Alt) 또는 그리는 중 Alt = 반전(안쪽
  남기기). 그리는 중 Alt+클릭도 점 추가 + 반전. 직선 2점의 면 선택은 다시 Alt+클릭 = 그쪽 남기기. Ctrl+드래그 중심 그리기 유지.
  (0.10~0.11의 더블클릭 자체 판정, 시작점 닫기, Tab 통과, PNG R 회전, Stabilizer, 다중 대상 보고는 유지.)
- **"The result would delete the whole object" 수정**:
  - 원인(재현됨): Live Primitive(MCH_Box 등 Geometry Nodes)는 기본 메쉬가 비어 있어 Boolean 결과가 항상 빈 메쉬.
    → `core_geometry.ensure_real_mesh`가 Cut / Split / Boolean 전에 평가된 형상을 실제 메쉬로 굽힘(재질 유지, 보고에 표시).
  - 빈 결과일 때 다음 솔버(Manifold → Exact)로 재시도.
  - 그래도 실패하면 메시지에 대상 이름, 연산(Cut / Keep inside / Union), 시도한 솔버를 표시.
  - 일반 Cube에서의 같은 오류는 headless에서 재현되지 않았습니다(Alt 상태가 남는 경로를 제거한 것이 대응).
- **Select / Move** (`mch.select_move`): Mecha Lab 메뉴(왼쪽 도구 목록·Space·V 팝업·사이드바) 맨 위. Object Mode로 전환 후
  `builtin.move` 툴(Blender 선택 + 이동 기즈모, 다중 선택) + 기즈모 표시. 실행 중인 Cut/Split 모달은 툴 변경을 감지해 취소,
  다시 들어가면 새 획. 단축키: Object Mode `W`(`mch.select_move_key`, MECHA LAB Workspace에서만), Preferences와
  Workspace & Hotkeys 패널의 **키 편집 행**에서 바꿀 수 있음(Quick Menu / Tool Menu / B·C 단축키도 함께).
- 시작 시 활성화에서 `bpy.data` 제한 오류(`_RestrictData`)가 나던 Ortho 검사를 타이머로 미룸.
- 테스트: 18개 파일 1007/1007 (`tests/test_log_bpy501_v0111.txt`). `test_v0100_regression.py` 108항목(0.11.1 블록 신규).

## 0.11.0 — Mechanical Modeling Toolkit (Face Extract / Armor Sculpt / Molding / Cable / Hollow / Mesh Along Curve) (2026-10-13)

기준: 0.10.0. 기존 기능 제거 없음. 검증은 Linux headless bpy 5.0.1뿐(Windows Blender 5.0.2 GUI 미실행, Blender 5.3도 미실행).

- **Base Mesh**: 다른 상단 탭(Workspace)으로 나가면 이번 세션에 만든 미확정 Base Mesh를 자동 Apply(0.5초 간격 가벼운 타이머,
  미확정 도형이 있을 때만 동작).
- **Face Extract (Basic)** — 새 도구. Edit Mode에서 선택한 면(여러 오브젝트·여러 섬 각각)을 별도 파츠로 추출, 원본 불변.
  Bevel Modifier 조합이 아니라 **자체 단면 생성기**(`panel_gen.py`): Extract Height / Thickness(0=솔리드, >0=Solidify 쉘) /
  Surface Offset / Resolution, Bevel Width·Segments·Profile·Angle(윗면 엣지 라운드 + 외곽선 코너가 Bevel Angle보다 날카로운
  측면 세로 엣지만), Chamfer Width·Angle·Depth(세 값 중 두 개를 고르는 모드, 나머지는 계산 표시)·Direction Inward/Outward,
  Outer Edge(바닥 엣지) Bevel Width / Chamfer Width / Angle. 모든 값 실시간, 파츠를 다시 선택해도 유지.
- **Armor Sculpt** — 같은 생성기의 고급 모드. 평균 노멀 + 주축으로 로컬 N/E/S/W(회전·스케일·오프셋·미러). 방향별 Thickness /
  Slope / Roundness / Chamfer Width·Angle / Bevel Width·Segments를 부드러운 분할(cos²)로 연결. 중앙 라인 6종(Straight, Cross,
  Y, X, S, Z) + Rotation / Scale X·Y / Offset / Width / Height / Strength / Sharpness / Roundness / Angle / Invert / Symmetry,
  방향별 Length·Width, Y·X 가지 각도, S 곡률. Ridge Profile 6종(Sharp, Flat, Round, Box, Groove, Split), Surface Transition
  (Width, Smoothness, Surface Tension). 실제 메시 높이를 바꾸는 높이장, 결과는 항상 닫힌 솔리드.
- **Edge Molding** — 선택 면 외곽 / 선택 엣지 / 추출 파츠 경계 / Armor 중앙선에서 별도 오브젝트. Width, Height, Surface Offset,
  Slope Angle, Chamfer Width·Angle, Bevel Width·Segments, Profile Resolution, Smooth Boundary(기본 0 = 원래 엣지 그대로),
  Round / Square / Flat / Chamfer / Custom, 배치 Centered / Inside / Outside. 표면 노멀 기준으로 세워 휘어진 표면에서도 똑바름.
- **Hollow / Shell** — 여러 메쉬 동시. Wall Thickness, Inward/Outward/Center, Even, Rim Fill, Rim Thickness(정점별 Solidify 두께),
  Rim Bevel + Segments, 선택 면 = 개구부(GN), 자기교차/두께 초과 검사, Apply / Reset.
- **Mesh Along Curve** — Curve Deform(±X/Y/Z, Start Offset, Rotation, Scale, Stretch), Curve Array(Rigid = GN 인스턴스 / Deform =
  Array+Curve, Count / Spacing / Fit Curve, Start·End Offset, Global Scale, Rotation Offset, Follow Tangent, Align Axis, Reverse,
  Apply / Reset). 커브 배치 Free / World X / Y / Z(기준 중심선만 축에 고정, 제어점은 자유, 생성 후 변경 가능).
- **Cable Generator** — 두 메쉬 표면 클릭(서로 다른 오브젝트 가능, 노멀 방향으로 출발), Control Points 추가/삭제, Handle Angle /
  Length, Sag, Curvature, Midpoint Offset, Twist, Thickness / Start / End / Taper, Curve·Profile Resolution, Round / Square /
  Ribbon / Oval / Custom. Edge to Cable(엣지 유지, 체인별 또는 한 오브젝트, Smoothing).
- 정리용 컬렉션 `Mechanical Parts / Extracted Armor, Edge Moldings, Cable Objects, Curve Arrays`.
- 그리던 도중 **Tab** = 획 폐기 후 Blender로 전달(Edit Mode 전환). 새 도구는 모달이 아니라 패널 + 오브젝트별 설정이라
  Edit/Object 전환과 무관하게 유지.
- 자가 진단(Self Test)에 Face Extract / Armor / Molding / Hollow / Cable 추가(12항목).
- 테스트: 18개 파일 995/995 (`tests/test_log_bpy501_v0110.txt`), 신규 `test_mechanical_toolkit.py` 99항목.

## 0.10.0 — 안정화 + 입력 UX 통일 + Deform 포인트 조작 + Free Draw Stabilizer (2026-10-13)

기준: **ChatGPT v0.9.3** (= Claude 0.9.0 + ChatGPT Deform v0.9.1 + Primitive v0.9.2/0.9.3). 무수정 원본은
`reference/CHATGPT_v0_9_3/`. 검증은 Linux headless bpy 5.0.1뿐이며 **Windows 11 / Blender 5.0.2 GUI는 실행하지 못함**.

### 사용자 보고 고장(P0) — 원인 분석과 조치
| ID | 조치 | 비고 |
|---|---|---|
| B09 등록 오류 `MCH_PG_Brush already registered` | `addon_safety.py`: 등록 전 이전 실행/다른 사본의 잔여 클래스·`mch_*` 속성·핸들러·헤더 함수·`mch.*` 키맵·`mecha.*` 툴을 정리, 등록 중 예외 시 **완전 롤백**, 해제는 단계별로 계속 진행(중간 실패해도 나머지 해제) | 해제가 중간에 멈추면 다음 활성화가 이 오류로 실패하고, 그 뒤에 등록되는 Mirror/Radial/Surface 패널·키맵·툴이 통째로 빠짐 → B01 등 "여러 기능 먹통"의 유력한 공통 원인. 다른 Mecha Lab 사본이 켜져 있으면 패널 상단에 경고 |
| B01 Mirror / B02 Loft / B03 Smart Fuse | 코드는 0.9.0과 동일했고 headless에서는 모두 통과 → GUI 전용 경로를 보강: 왼쪽 도구 목록(Properties 편집기)에서 도구를 바꿀 때 `tool_set_by_id`를 **3D View 컨텍스트로 실행**, 툴바가 바뀌지 않아도 선택한 도구 패널이 표시되고 Cut이 LMB를 가로채지 않음. Mirror Apply/Remove 다중 선택. Smart Fuse: 다른 오브젝트의 미확정 미리보기가 패널을 가로채지 않음, Undo 등으로 남은 `active` 플래그 자동 복구, 확정/취소 후 고아 노드 그룹 정리 | **재현 불가 → 추정 원인 기반 수정.** 새 `Run Mecha Lab Self Test` 버튼(Workspace & Hotkeys 패널)이 사용자 Blender에서 임시 씬으로 Mirror/Loft/Fuse×3/Boolean/Cut/Base Mesh/Deform을 실행하고 결과를 클립보드에 복사 |
| B04 Lasso 더블클릭 | Blender가 두 번째 클릭을 `DOUBLE_CLICK` 대신 `PRESS`로 보내는 환경에서도 닫히도록 **자체 더블클릭 판정**(시간+거리). 시작점 닫기 반경 14px × UI Scale. 3회 클릭 토글 제거(충돌 원인) | Curve Lasso 점 편집 클릭과 충돌하지 않음(편집 클릭 뒤의 더블클릭은 닫지 않음) |
| B05 Mesh Curve 직선/점만 | 기존 점 **더블클릭이 두 번 토글되어 Smooth→Straight로 되돌아가던 버그** 수정(첫 PRESS + DOUBLE_CLICK, 또는 PRESS 두 번). 이제 한 번의 더블클릭 = 한 번 전환 | |
| B06 PNG R 회전 | 드로잉 중 `R`/`Shift+R` 15° 회전, 대기 상태에서도 `R`(PNG 모양일 때만, 아니면 Blender R), 커서에 스탬프 윤곽 미리보기(WorkSpaceTool draw_cursor) | 미리보기 = 실제 커터 윤곽(테스트) |
| B07 Split Gap 확정 | 시작점 클릭 / 아무 곳 더블클릭 / Enter 모두 확정, 열린 선(F)도 시작점 클릭으로 확정 | |
| B08 Mask | 도구 목록·Space·V·툴바·단축키에서 **숨김**. 코드·연산자·저장된 마스크 속성/Vertex Group은 그대로 | 이전 파일에서 Mask가 활성이면 Cut으로 표시 |
| B10 Bevel 폭 | Cut Edge Finish / Split Side A·B 폭 슬라이더 상한 0.5→2.0(숫자 입력 무제한), `Clamp Overlap` 옵션, 짧은 이웃 엣지 때문에 폭이 제한되면 결과 메시지에 "limited to about …" 표시 | |

### 입력 UX (docs/02)
- **Alt+짧은 좌클릭**(놓을 때 이동량/시간으로 판정): 드로잉 도구 → 선택 모드(그리던 획 폐기, 완료 작업 유지). 선택 모드에서
  오브젝트 위 Alt+클릭 → 마지막 Mecha 도구로 복귀(빈 곳이면 Blender 기본). **Alt+드래그**: Cut = 안쪽 남기기, Base Mesh = Boolean
  커터. 직선 Cut의 면 선택 단계에서 "남길 쪽"은 Alt 대신 **Ctrl+클릭**.
- 3회 클릭 → 선택 모드 기능 **제거**. Alt+MMB는 추가하지 않음.
- `V` 빠른 메뉴(Cut/Boolean/Base Mesh/SubD Plane/Split/Radial, 마우스 위치), `Shift+A > Mecha Lab`(Primitive 5종, SubD Plane,
  Base Mesh 도구, Lattice/Bend). MECHA LAB Workspace에서만, Preferences에서 끌 수 있음.

### 기능 (docs/03)
- **Boolean: 노란색 활성 = 커터, 나머지 선택 = 대상**(여러 대상 각각). 패널에 CUTTER/TARGETS 표시. 실패한 대상은 그대로 두고
  메시지에 표시, 대상이 하나라도 실패하면 커터는 삭제하지 않음. Slice도 같은 규칙.
- Cut/Split: 기본 Targets = Selected, 같은 도형으로 모든 선택 메쉬 처리, 겹치지 않는/실패한 대상은 변경 없이 메시지에 표시(1 Undo).
- **Base Mesh Bevel Sides**: Top Only / Bottom Only / Both Sides / None, Both는 위/아래 폭·세그먼트 별도(기본 연결). 이전
  `Bevel Bottom Too`는 로드 시 Both로 이전. Dome은 Bevel Sides 미사용(UI에 표시). **Alt+드래그**: 그린 입체를 Top↔Bottom
  반전(Both는 위/아래 값 교환)해 표면 안쪽으로 뒤집은 커터로 Boolean Difference(포켓 입구에 반전된 베벨). **도구를 떠날 때**
  (Alt+클릭/Esc/다른 도구) 이번 세션에 이 도구가 만든 Live Base Mesh만 Apply(Freeze), Undo 1단계.
- **Deform(Lattice Cage / Bend Curve) 포인트 직접 조작**: 점 클릭 → Move/Rotate/Scale 기즈모(Mecha 스타일) 또는 Blender 기즈모 +
  Proportional Editing(Mecha 설정과 실시간 동기화). 선택 점이 피벗, Falloff Radius/Smoothness(연속값), 단일 점 회전·스케일도
  주변을 변형, 다중 선택, Pivot(선택 중심/각 점/3D 커서), Lattice Resolution X/Y/Z(편집 중에도, 변형 유지), Bend 점의 접선 회전 =
  국소 Twist(tilt), 스케일 = 두께(radius), 점 개수 재샘플. Apply 전까지 비파괴, 언제든 재편집. v0.9.1 연산자 ID·태그·모디파이어
  이름·스택 베이크 Apply 유지, Twist/Taper 슬라이더는 점별 편집 위에 더해지는 램프로 변경.
- **Free Draw Stabilizer(Lazy Mouse)**: ON/OFF(기본 OFF), Smoothing Strength 0–100%(시간 기반 지수 추종, 이벤트 빈도 무관),
  Lazy Radius 0–80px(원 안에서는 선이 멈춤), Stroke Spacing(기존 Sample Spacing 재사용). 드로잉 중 타이머로 계속 따라오고, 놓을 때
  간격 단위로 부드럽게 따라와 끝남(긴 직선 점프·이중 점 없음). 지연 원/줄 가이드 표시 옵션. OFF/0%/0px는 기존 코드 경로 그대로.
  Cut/Split/Base Mesh 공통, Lasso·Curve Lasso·도형·PNG·Curve Tool은 변경 없음.

### 테스트
- 17개 파일 875/875 통과(`tests/test_log_bpy501_v0100.txt`). 신규: `test_v0100_regression.py`(92), `test_deform.py`(109),
  `test_registration_recovery.py`(38), `test_self_test.py`(4). `test_zip_install.py`는 비활성/재활성 3회.
- 기존 테스트 중 새 사양으로 바뀐 것: Boolean 선택 규칙(활성=커터), Alt는 드래그해야 반전, 3회 클릭 제거.

## 0.9.0 — Mesh Curve 수정, SubD Plane, Radial 회전, Gap Split, 양쪽 독립 베벨 (2026-10-13)

기준: 0.8.0. 기존 기능은 제거·대체 없이 확장. 검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 Mesh Curve (Panel / Curve 도구 → 이름 "Mesh Curve", Curve Lasso와 무관)
- **직선처럼만 생기던 원인 3가지 수정**: (1) 모든 점이 VECTOR 핸들로 생성(Free Draw 포함), (2) Edit Mode 점 더블클릭 →
  Smooth 키맵이 v0.5.9부터 `active = False`로 등록돼 한 번도 동작하지 않음, (3) Straight/Smooth 버튼이 Edit Mode 전용이라
  Object Mode에서 비활성.
- 직선(VECTOR) 그리기는 기본값 그대로. 그리는 중 기존 점 클릭/더블클릭 = Straight ↔ Smooth, `S` = 새 점 종류, Backspace가
  점 종류를 보존. Free Draw 점은 AUTO(부드러움). Edit Mode 더블클릭 키맵 활성화(Mecha 경로가 아니면 통과).
- 새 Live 설정(Object.mch_live): Curve Resolution(경로 resolution_u), Profile Segments(원형 단면), Rotation X/Y/Z(스윕: 단면 회전,
  Curve Array: 복제본 회전), Twist(시작→끝 누적 비틀림, Set Curve Tilt). `All Smooth / All Straight`(Object Mode).
- 0.9 이전에 만든 Live 오브젝트는 처음 값을 바꿀 때 노드 그룹을 한 번 재생성.

### P0 SubD Plane (새 도구)
- `Create SubD Plane`: 3D 커서에 Plane + `Simple SubD → Catmull-Clark SubD → Solidify`. 두 SubD를 **동시에** 쓰고 레벨 슬라이더
  각각(0~5). Thickness / Offset / Even Thickness / Use Creases, Edit Mode 선택 엣지 Crease, `Apply All`(스택 순서대로 데이터 적용),
  `Add SubD Stack to Selected`. 모든 모디파이어 Edit Mode 표시.

### P1 Radial Array
- Ring Rotation X/Y/Z(배열 전체 회전), Copy Rotation X/Y/Z(복제본 로컬 회전), Start Angle(이름 정리), Rotate Each Copy **기본 OFF**
  (씬 기본값과 오브젝트 모두). 원본 방향은 메쉬에 그대로, 배열 회전은 별도 노드. 이전 배열은 처음 수정 시 노드 그룹 재생성.
- 기울어짐 점검: 복제본 회전은 Rotate Each Copy가 켜져 있을 때만 Z축으로 일어나며, 기본값이 ON이던 것이 "원하지 않는 회전"의
  주원인이었음. OFF에서는 모든 복제본이 원본 축을 유지함을 테스트로 확인.

### P1 Gap Split
- Split Mode: Normal(기존) / Gap. Gap Width(모델 단위)만큼 띠를 제거: 닫힌 도형은 윤곽을 ±Gap/2 오프셋한 두 커터로
  (안쪽 = 조각, 바깥쪽 = 남는 원본), 2점 직선은 ±Gap/2 두 평면, 폴리라인/곡선도 지원. 중심선 유지, Cap 옵션, 각각 별도 오브젝트.
  Gap이 도형에 비해 너무 크면 메시지와 함께 거부, Auto Apply OFF에서는 안내 후 거부.

### P2 Split 양쪽 독립 마감
- Side A(남는 원본) / Side B(`_Split`) 각각 None/Chamfer/Bevel, Width, Segments, `Swap Sides`. Normal/Gap/직선 모두,
  새 절단 경계만 처리(원래 모서리 불변 테스트). Split은 이제 이 설정을 쓰고, Cut의 Edge Finish는 Cut 전용.

### P2 2D Corner 점검
- 0.8.0의 Sharp/Chamfer/Round, Corner Width(px, 이름 정리), Corner Segments, Lasso 그리는 중·Rectangle 드래그 중 미리보기가
  실제 상태기계에서 동작함을 테스트로 확인. 새 기능 추가 없음.

## 0.8.0 — 입력 P0 수정, Base Mesh, Loft/Surface, ZBrush Bridge (2026-10-13)

기준: ChatGPT **v0.7.2** (`reference/CHATGPT_v0_7_2/`). v0.7.1(트리플 클릭, Ortho Lock)과 v0.7.2(마스크 레이캐스트,
열린 Mask Brush Stroke, Edge Finish 엣지 수 진단)는 유지. 독립 Curve Tool(Panel/Curve, `mch.draw_path`)은 수정하지 않음.
검증은 Linux headless bpy 5.0.1뿐 (Windows 5.0.2 GUI 미실행).

### P0 입력 / UI
- **Esc → 선택 도구 복귀**: 획 중이든 대기 중이든 Esc는 미완성 획만 버리고 `builtin.select_box`로 전환. 적용된 컷 유지.
  (대기 중 Esc는 도구 키맵의 `mch.exit_tool`, 팝업 대기 중 Esc도 동일.)
- **더블클릭 자동 폐합**: Lasso/Curve Lasso는 시작점 근처가 아니어도 더블클릭 위치에서 마지막 점→시작점으로 닫고 적용.
  DOUBLE_CLICK은 점을 추가하지 않고, 같은 마우스다운에 PRESS+DOUBLE_CLICK이 함께 와도 4px 이내 중복 점은 버림,
  시작점 위의 마지막 점도 제거 → 길이 0 엣지 없음.
- **트리플 클릭 상태기계 정리**: v0.7.1 카운터 유지, 단 Curve Lasso 점 토글/드래그·핸들 클릭(편집 클릭)은 세지 않음.
  v0.7.2에서 같은 점을 세 번 누르면 도구가 꺼지던 충돌을 테스트로 재현 → 수정.
- **Curve Lasso 재설계**: 처음부터 부드러운 닫힌 스플라인(Catmull-Rom 탄젠트 → 3차 Bezier 구간). 점 클릭 = 각/부드러움 토글,
  점·Bezier 핸들 드래그(정렬된 대칭 핸들), `Curve Samples`, `Curve Smoothness`. 이전의 "각진 라쏘 + 꼭짓점 라운드 단계" 제거.
- **Free Draw**: Shape 이름을 Brush Stroke → Free Draw로. PRESS→MOUSEMOVE 연속 샘플→RELEASE, 간격/스무딩/단순화.
  Cut/Split/Base Mesh는 닫힌 외곽선, Mask는 열린 브러시(v0.7.2). Lasso에서도 LMB를 누른 채 끌면 연속으로 그려짐.
- **Outline Corners**: Lasso/Rectangle의 2D 모서리 Round/Chamfer(px) — 3D Edge Finish와 분리된 설정.
- 우클릭: Cut/Split/Mask = Shape/PNG 팝업, **Base Mesh = 단면 프로필 팝업**, 더블 = 종료.

### P1 Base Mesh from Shape (새 도구 `mecha.base_mesh`)
- 공통 Shape(Lasso/Curve Lasso/Rect/Circle/Ellipse/Free Draw/PNG)로 그린 윤곽을 뷰 평면에 투영해 **새 닫힌 솔리드** 생성.
  표면 위(윤곽 아래 메쉬가 있으면) 또는 3D 커서 평면. 원본 메쉬 무변경.
- 프로필: Flat, Chamfer(윗면 경계 1세그먼트), Bevel(윗면 경계 N세그먼트), **Rounded/Dome**(경계까지 거리 기반 높이장,
  densified 경계 + 내부 격자의 Constrained Delaunay → 오목 윤곽에서도 면 뒤집힘 없음). Roundness/Height/Edge Height/
  Resolution/Border Width/Segments/Offset/Bevel Bottom.
- 구멍(PNG 링)·여러 섬 지원. 자기교차·너무 작은 윤곽은 메시지와 함께 거부(오브젝트 생성 안 함).
- **Live**: 윤곽과 설정이 오브젝트에 저장되어 값 변경 시 재생성, RMB 프로필 선택도 선택된 Live 오브젝트에 반영. Freeze.
- 경사 뷰에서 거의 일직선인 경계 점 사이 sliver 삼각형이 잘못 분류되던 문제를 테스트로 찾아 **교차 parity 분류**로 해결.

### P2 Loft / Surface (부분)
- Loft: 2+ 커브, 호 길이 재샘플, 방향/시작점 자동 정렬, Catmull-Rom 단면 보간(Smoothness), Cap Ends, Thickness(Solidify),
  Flip, Twist, Close Loft, 섹션 순서 이동/개별 Reverse. Sweep: 단면+경로(평행 이동 프레임, 스케일, 비틀림).
- 커브 수정 시 depsgraph 핸들러로 **Live 갱신**, Apply로 확정. CAD NURBS 패치가 아닌 보간 폴리곤 표면.

### P2 ZBrush Bridge (부분)
- OBJ 파일 기반 Send / Import Back. 오브젝트마다 개별 파일(자동 Join 없음), ID(`mch_zb_id`)와 매니페스트(파일, 시각,
  내보낼 때의 world matrix), 바뀐 파일만 다시 가져와 원래 오브젝트 로컬 좌표로 변환해 메쉬 교체, 이전 메쉬 백업,
  이름 변경/삭제/파일 누락/공유 메쉬 처리, 축·스케일 설정, ZBrush 실행 파일 선택 실행. **GoZ 프로토콜은 구현하지 않음**
  (설치 경로가 있으면 정보로만 표시).

### 기타
- Ortho Lock(v0.7.1): 잠금 상태로 저장한 파일을 다시 열면 타이머가 자동 재시작(v0.7.2는 버튼을 다시 눌러야 했음).
- 새 아이콘 7개(Base Mesh, Loft, ZBrush, 프로필 4종). 매니페스트 0.8.0.

## 0.7.2 / 0.7.1 (ChatGPT)
`addon/mecha_lab/CHANGELOG_v0_7_1_KO.md`, `CHANGELOG_v0_7_2_KO.md` 참고.

## 0.7.0 — MECHA LAB Workspace MVP (2026-10-12)

기준: 배포본 v0.5.9 (`reference/RELEASE_v0_5_9`, 원본 그대로 보존). 미검증 초안 v0.6.0은 참고만 했고 코드를 가져오지
않았습니다(타이머로 Cut 모달을 재시작하는 방식은 경쟁 상태 위험 때문에 채택하지 않음). 검증 수준은 `test_report.md` 참고.

### UI / UX (P0)
- **`MECHA LAB` Workspace**: 버튼·탭 메뉴·F3에서 생성/전환. 현재 탭을 복제해 만들며 다른 탭·Startup File은 변경하지 않음.
  `Repair Layout`, 확인 창이 있는 opt-in `Save as Startup` 제공.
- **왼쪽 큰 아이콘+이름 도구 목록** (Properties 영역 Tool 탭에 표시). 순서: Cut, Split, Boolean, Smart Fuse, Mirror, Mask,
  Curve Array, Radial Array, Panel/Curve, Pose(미구현 표시), Surface Conform, Assets, Remesh, Live Result.
- **공통 Shape 팔레트** (뷰포트 Tool Header, 왼쪽 위): Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Brush Stroke,
  PNG 썸네일 + Custom + Import. 네이티브 버튼이라 GPU hit-test 없음. Shape를 쓰지 않는 도구에서는 비활성 + 안내.
- **오른쪽 Sidebar = 현재 도구 1개의 설정만** (`MCH_PT_main`). 긴 N패널 제거. Sidebar에 접힌 `Tools (fallback list)`.
- **Space** = 큰 아이콘 도구 팝업 (MECHA LAB 탭에서만; 다른 탭은 Blender 기본 Space).
- **Cut과 Split을 별개 도구로 분리.** 별도 Random Polygon / N-gon 항목 제거(Lasso가 그 역할).
- 원본 아이콘 21개(도구 14 + 도형 7) 생성 스크립트 `tools_dev/make_icons.py`.

### Cut 입력 시스템 (P0 버그 수정)
- Cut/Split/Mask를 **네이티브 WorkSpaceTool**로 재구현. LMB 한 번 = 한 획 동안만 모달(`mch.cut_stroke`),
  끝나면 FINISHED → **컷마다 독립 Undo 단계**. 획 사이에는 모달이 없어 `Ctrl+Z`/메뉴/다른 에디터가 정상 동작.
  (v0.5.9: 하나의 장기 모달이 모든 키를 가로채 Ctrl+Z 불가, 메뉴 클릭 전 Esc 필요.)
- 획 도중: 뷰포트 밖 이벤트는 pass-through(팔레트·사이드바·메뉴 클릭 시 Esc 불필요), Shape/도구 변경 시 미완성 획만 폐기,
  `Ctrl+Z`/`Backspace` = 마지막 점, `Ctrl+Shift+Z` = 점 복구, `Esc` = 획만 취소, 더블클릭 확정 시 점 중복 없음.
- **RMB 1번 = Shape 팝업, RMB 더블 = 도구 종료**: 더블클릭 간격(사용자 설정)만큼 기다린 뒤 팝업을 열어 두 번째 클릭을
  삼키지 않음. 대기 중이 아닐 때는 작은 게이트 연산자(`mch.rmb_gate`)가 같은 규칙 처리.
- `Space`는 컷 확정에 쓰지 않음(도구 메뉴). 확정은 Enter / 더블클릭.
- Curve Lasso: 점 재클릭으로 4단계 라운드 순환, 점·핸들 드래그, 핸들 표시.
- 원근(perspective) 뷰에서도 그린 실루엣과 일치하는 **frustum 커터** (v0.5.9는 정사영 가정 prism).
- 2점 직선 컷의 평면도 원근 정확(두 시선 ray를 포함하는 평면).

### 기하 안정성
- 새 `core_geometry`: 커터를 캡(구멍 포함 삼각분할)+벽이 정점을 공유하는 **닫힌 메쉬로 직접 생성**하고 manifold 검사.
- Boolean은 **베이스 메쉬에 대해서만** 평가(기존 모디파이어는 평가 중 잠시 숨김 → 그대로 유지), 결과 검증
  (전체 삭제 / 교차 없음 / 비매니폴드) 후에만 기록. 실패 시 원본 무변경 + 메시지, Undo 단계도 생기지 않음.
- Solver Auto: 닫힌 메쉬는 Manifold → Exact 폴백, 열린 메쉬는 Exact.
- **공유 메쉬(Alt+D) 지원**: 모든 적용 경로(`Cut`, `Boolean`, `Slice`, `Smart Fuse confirm`, `Remesh`, `Live result`,
  `Mirror apply`, `Radial bake/Boolean`, `Apply Live Cut`)를 `bpy.ops.object.modifier_apply` 대신 데이터 수준 적용으로 교체.
  v0.5.9 오류 "Modifiers cannot be applied to multi-user data"를 headless에서 재현 → 0.7.0에서 해결 확인.
  정책: 이 오브젝트만(기본) / 모든 링크 복제본.
- **Edge Finish (Bevel/Chamfer) — 새 절단 엣지만**: 커터 면에 `mch_cutter_face` 속성을 달아 Boolean 후
  커터 면/원래 면 경계만 bevel. 원래 실루엣 모서리는 테스트로 불변 확인. Lasso 모서리 라운드와 완전히 별개 설정.
- Split: 안쪽은 `<이름>_Split` 새 오브젝트, Cap ON/OFF.
- Depth `From Surface`(고정 깊이 포켓) 추가.

### PNG Custom Cut Shape (P1)
- v0.5.9 비매니폴드 원인 재현: **모서리만 맞닿은 픽셀**(대각선 접촉) → 윤곽선이 한 정점을 공유하는 bow-tie →
  커터가 닫히지 않음. 새 파이프라인은 마스크 정리(점 노이즈/핀홀 제거) + 2×2 saddle 해소 + 단순화 결과의
  자기/상호 교차 검증(실패 시 단순화를 줄여 재시도, 최종적으로 원본 픽셀 윤곽) + 포함 깊이 기반 외곽/구멍/섬 구분.
- PNG 도형이 공통 Shape 팔레트의 일부가 됨(Cut/Split/Mask에서 같은 커터 엔진 사용). 클릭 스탬프 / 드래그 크기.
- Smooth Steps, Remove Specks 옵션, 프리셋 schema 2. v0.5.9 프리셋 자동 업그레이드.

### Smart Fuse (P2, 부분)
- **v0.5.9 Smart Fuse 패널의 크래시 원인 확인**: Live Preview 패널이 Blender 5.0에 없는 아이콘 `MOD_NODES`를 사용 →
  패널을 그릴 때마다 TypeError(스크린샷의 잘린 traceback이 아이콘 enum 목록을 출력하는 형태와 일치). `GEOMETRY_NODES`로 수정.
  모든 소스의 아이콘 이름을 5.0 enum과 대조하는 테스트 추가.
- **두 번째 크래시**: 생성 실패 시 정리 코드가 이미 삭제된 노드 그룹에 접근(ReferenceError). 수정.
- 생성 직후 교차 seam 존재 여부 검사: 떨어져 있거나 면만 맞닿은 메쉬는 설명과 함께 거부하고 원래 상태로 복구.
- 셰이프 키가 있는 메쉬는 거부.

### 호환성
- 이전 연산자 ID 유지: `mch.draw_delete_cut`(→ Cut/Split 도구 활성화), `mch.draw_mask`, `mch.stamp_png_cut`,
  `mch.select_tool`, `mch.cut_finalize`(데이터 안전 적용으로 재작성), `MCH_MT_tool_menu`.
- 저장된 .blend의 선택 도구 enum 번호 유지.
- `mch_enabled`(v0.5.9 세션 토글)는 남겨두었지만 사용하지 않음 — 단축키는 Workspace 범위로 대체.
- manifest `blender_version_min` 4.3 → **4.5** (Manifold solver 필요).

### 제거
- v0.5.9 장기 모달 `MCH_OT_draw_delete_cut` 본체, 긴 N패널(`MCH_PT_cut/boolean/fuse/...`), MECHA LAB MODE 토글 UI.
- 오래된 애드온 내부 문서 `README_v0_5_9_KO.md`, `PNG_CUT_GUIDE_KO.md` (원본은 reference에 보존).
