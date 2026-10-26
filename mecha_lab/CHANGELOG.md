# CHANGELOG

## 0.24.34 — 모든 그리기 툴에 대상 선택(Auto / Selected Only / Active), F + 마우스 = 브러시 크기, 목도리 케이프(Scarf Cape) (2026-10-26)

- **대상 선택을 모든 그리기 툴에**: Cut 패널의 **Auto Target / Selected Only / Active** 줄이 메쉬 위에 그리는 모든 툴(Surface Draw, Base Mesh, Armor / Creature Plate, Belt, Spike, Scales, Scale Brush, Bridge, Flower, Surface Curve, Cape, Scarf Cape, Hair, Plate Detail 1/2/3, Screw, Cloth Plate, Primitive, Mesh Curve, Cable 등)의 패널 맨 위에 생김.
  - Selected Only = 선택한 메쉬에만 그려짐(앞에 다른 메쉬가 있어도 뚫고 지나감), Active = 활성 메쉬에만.
  - 그린 뒤 새 판 / 띠가 선택돼도 그 판이 붙은 메쉬는 계속 대상(다음 획도 같은 메쉬에).
  - Cut과 같은 설정 하나(바꾸면 모든 툴에 같이 적용), 기본 Auto Target = 예전과 동일. T 키 전환도 그리기 툴에서 동작.
- **F + 마우스 좌우 = 브러시 크기(모든 그리기 툴)**: Concept Move처럼 F를 누르고 마우스를 좌우로 움직이면 크기가 바뀌고 화면에 원으로 보임. 클릭 / F = 확정, 우클릭 / Esc = 원래대로.
  - 크기 = Line Width(Line 모드 · Surface Draw · Belt · Surface Curve 등), PNG 스탬프 모양이면 Stamp Radius, Mask 브러시면 Mask Brush Radius, Screw Stamp면 Size. Surface Draw는 저장된 다음 획 Width / Height도 같이.
  - 툴 안에서 F는 이제 크기 조절(툴 밖 / Select 툴에서는 F = Select / Move 그대로, 툴 ↔ Select 전환은 Q).
- **Scarf Cape(목도리 케이프, 새 툴)**: 몸 위에 **가로로 선을 그으면** 그 선이 윗단이 되어 그은 길이만큼의 폭으로 아래로 늘어짐. 주름선은 **가로로**(접힌 선은 또렷하게, 사이는 평평하게), 가장자리에서 주름이 서서히 사라져 옆선이 깔끔함.
  - **Gravity**: 올리면 가운데가 처지고 주름선이 U자로 휨. 나머지 설정은 망토와 같음(설정은 망토와 따로 저장, 기존 망토는 그대로).
- 테스트: 106개 파일 3464/3464. 새 test_v02444(대상 선택 15) · test_v02445(Scarf Cape 17) · test_v02446(F 브러시 크기 12). ZIP sha256 `86cceef084d993161d94b25600cd15a6798150a17c3d844810edffc5a333566c`.

## 0.24.33 — Path Move 방식(Extend / Separate Tube), Perforate, Surface Draw, Point Radial Symmetry, 망토 좁게 (2026-10-26)

- **Path Move 방식 선택**(패널 Method):
  - **Extend**(기본): 잡은 곳에서 메쉬를 자르고, 잘린 단면을 길 따라 쓸어서 끝을 옮김 → 원래 메쉬가 늘어난 것처럼 보이는 가벼운 한 덩어리 메쉬.
  - **Separate Tube**: 같은 단면의 관을 새 오브젝트로 만듦(가볍고 빠름), 나중에 **Merge**(Join / Union)로 합침.
  - **Stretch**: 예전 방식(무브를 여러 번 반복) 그대로 남김.
- **Perforate**(새 툴): 선택한 메쉬에 사이파이 구멍판 패턴 — **Honeycomb / Circle / Square / Diamond**. 라이브(크기 · 간격 · 가장자리 여백 · 회전 · 위치), 구멍은 표면이 있는 곳에만, Mirror 앞에 들어감(베벨은 그 앞에 그대로). Apply / Remove.
- **Surface Draw**(새 툴): VR처럼 메쉬 표면 위에 그리면 띠 모양 메쉬가 생김.
  - 가장자리 **Square(직각, 기본) / Chamfer / Bevel**(+ Round / Ridge).
  - 펜을 떼고 다시 그어도 **처음 폭 · 높이 그대로**(Keep First Size), 겹쳐 그려도 쌓이지 않고 같은 높이.
  - 같은 메쉬에 그린 선은 한 라이브 오브젝트로 합쳐지고 슬라이더로 전부 다시 계산, Remove Last Stroke / Apply.
  - **Fill Area**: 닫힌 라쏘 = 그 면적을 같은 높이로 채움.
  - **Alt + 선 / 라쏘 = 그 영역을 잘라냄**(라이브 유지, 다시 계산해도 잘린 곳 유지).
- **Point Radial Symmetry**(새 툴): 점을 하나 찍으면 그 점을 중심으로 선택한 메쉬가 돌아가며 복사(개수, 활성 메쉬의 로컬 X / Y / Z 축). 그 위에 새로 만드는 Base Mesh · 판도 같이 복사, Cut은 모든 복사본을 같이 자름. Apply / Remove.
- **Cape**: Only Drawn Width(기본 켬) = 그은 길이만큼만 가로 폭, 몸에 더 가깝게, 더 얇게, 더 촘촘한 격자.
- **Cloth Brush · Cloth Wrap 제거**(요청): 코드 · 아이콘 · 테스트 · 메뉴 모두.
- 테스트: 103개 파일 3407/3407. 새 test_v02439(Path Move 방식) · test_v02440(Perforate) · test_v02441(Surface Draw, Alt 컷 포함) · test_v02443(Radial Symmetry). ZIP sha256 `933ecbc2062186650d7e6b042df5f1313e0c13651ccf05e277967ce66b13b3bc`.

## 0.24.32 — Path Move(길 따라 무브), 무브 패널 옵션(Cut처럼), Jungle Gym 제거 (2026-10-25)

- **Path Move**(새 툴, 왼쪽 목록 · 하단 바 Path · V 파이 Primitive 칸 Move 아래): Concept Move처럼 잡고 길을 그리듯 드래그하면 잡은 **네모 / 동그라미가 모양 그대로 길을 따라가고**, 지나간 자리에 같은 굵기의 몸통이 생김(프레임 · 파이프 · 팔).
  - **Follow Turns**(기본 켬): 길이 꺾이면 잡은 단면도 같이 돌아서 단면이 길에 수직으로 유지(파이프 구부리듯). 끄면 처음 방향 그대로 이동.
  - **Taper**(기본 0 = 끝까지 같은 굵기), 손 떨림은 살짝 다듬음. 크기 · Hardness · 구 / 박스 · 미러 · Generate · Even Out은 Concept Move 설정을 같이 씀, F + 마우스 = 크기, 드래그 중 휠 = 깊이. 놓은 뒤 F9: Size · Hardness · Taper · Follow Turns.
- **Concept Move · Path Move 패널 옵션(Cut 툴과 같은 모양)**:
  - **Through All / From Surface**: From Surface = 잡은 메쉬만, Through All = 브러시 안에 들어온 대상 메쉬 모두 같이(몸통 위 판도 같이 늘어남).
  - **Auto Target / Selected Only / Active**: 마우스 아래 메쉬 / 선택한 메쉬만(앞에 다른 게 있어도 뚫고 잡음) / 활성 오브젝트만.
  - **Auto Apply**(기본 켬): 끄면 무브가 편집 가능한 상태로 남음 → 패널의 **Undo Last**(마지막 무브만 되돌림) · **Clear**(무브 전 메쉬로) · **Apply**(확정).
  - 무브는 장면 기준으로 계산해서 회전 · 크기 바뀐 오브젝트도 화면에서 본 그대로 늘어남, 여러 오브젝트도 각자 공간에서 같은 무브.
- **Concept Move Ctrl 회전 = 화면 기준**: 드래그 중 Ctrl + 마우스 좌우 = 화면에서 보이는 대로 왼쪽 / 오른쪽으로 돌림(화면 세로축), 위아래 = 앞쪽을 숙이고 젖힘(화면 가로축). 전에는 보는 방향(깊이) 축으로만 돌았음.
- **Jungle Gym 제거**(의도와 달라서): 코드 · 아이콘 · 테스트 · 메뉴 모두.
- **크래시 수정**: 길게 꺾이는 경로에서 Blender의 면 분할(grid fill)이 Blender를 꺼뜨림 → 직접 만든 grid fill로 교체. Concept Move를 크게 여러 번 늘릴 때도 같은 위험이 사라짐.
- 테스트: 99개 파일 3297/3297, `test_v02437.py`에 Path Move 검사 추가(길 끝까지 단면 폭 유지, 꺾이면 단면이 돎, 몸통). ZIP sha256 `8c367a412f7b8bd95599c4a54a4532ba9cab544ed17f66e056141f2fd45c65f1`.

## 0.24.31 — VR식 러프 탐색: Concept Move · Jungle Gym, Blender 5.2 호환, 새 천 툴은 숨김 (2026-10-25)

- **Concept Move**(새 툴, 왼쪽 목록 · 하단 바 Move · V 파이 Primitive 칸): 표면을 잡고 찰흙처럼 쭉 늘리기(Substance 3D Modeler의 Move처럼).
  - Shape 구 / 박스(화면을 향한 정육면체: 프레임 · 판), Hardness(통째로 움직이는 범위), Falloff Clay / Elastic / Sharp, Mirror X, Strength.
  - **Generate**: 놓는 순간 늘어난 만큼 실제로 메쉬를 만들어 줌(늘어난 면을 쪼개서 다시 당김 → 길쭉한 면 없음). **Even Out**: 늘린 부분 면을 표면을 따라 고르게(각진 모서리는 그대로).
  - 드래그 중: Shift = 표면 바깥 방향, **Ctrl + 좌우 = 잡은 덩어리 돌리기**, 휠 = 깊이, [ ] = 크기. 놓은 뒤 F9: Size · Pull · Turn · Hardness · Shape · Falloff.
  - **F + 마우스 = 브러시 크기**, **Real Size** = 줌해도 장면에서 같은 크기.
  - **어느 Mecha 툴에서든 D 누른 채 드래그 = Concept Move**(툴 안 바꿈, Hotkeys 박스에서 키 변경 가능).
  - 라이브 오브젝트(망토 등)는 Apply 없이 늘려도 됨: 늘린 동작을 기억해서 슬라이더로 다시 만들어도 다시 적용, Clear Moves로 지움.
  - 미러 통일: 오브젝트에 자기 미러(Mecha Mirror)가 있으면 반대쪽(복사본)을 잡아도 원본 절반이 움직임.
  - Follow View(3D 마우스): 잡은 채 시점을 돌리면 덩어리가 따라옴. Shift+클릭 = 찰흙 공 추가, Fuse = 합치기(복셀).
  - 무거운 메쉬: 드래그 중엔 브러시가 닿는 점만 계산, 화면이 그대로면 계산 안 함.
- **Jungle Gym**(새 툴, 프로토타입): 화면에만 보이는 가벼운 격자(정글짐) 위를 기어가듯 그리기.
  - 마우스 방향에 가장 맞는 막대로 한 칸씩(대각선 시점이면 깊이로도), 휠 = 앞 / 뒤 칸, 되돌아가면 지워짐. 지금 점의 X · Y · Z 막대 = 주황, **45°** 대각선 = 흐린 주황(기본 켬).
  - Magnet(1 = 막대에 딱, 낮추면 자유 곡선), Corner(꺾이는 곳 둥글기), Thickness. 평평하게 닫힌 선 = 베이스 메쉬, 나머지 = 라이브 튜브. F9로 다시 조절.
  - 방향 World / Object / View / Surface, R / Shift+R = 15° 회전, 간격 = 줌 따라 1 · 2 · 5 자동.
  - **Follow Body**(기본 켬): 몸 위에서 시작하면 격자가 몸에 그물처럼 붙고 선이 몸을 감쌈(뚫지 않음), 휠 = 몸에서 띄우기(Lift).
- **Blender 5.2 호환**: 지오메트리 노드 모디파이어 입력(`properties.inputs`), Random Value 노드 소켓, numpy 2. 5.0에서도 그대로.
- **숨김**(코드 · 저장된 오브젝트는 그대로, `tool_state.EXPERIMENTAL_CLOTH = True`로 다시 켬): Clothing, Hood, Scarf, Quad Cloth. 망토(Cape)는 그대로.
- 테스트: 99개 파일 3301/3302 (속도 검사 1개가 이 기기에서 0.547초 > 0.5초로 실패, 단독 재실행 통과, 0.24.30 코드도 여기서 0.55초), 새 `test_v02432`~`test_v02437`. ZIP sha256 `8f25ac3f67cc600ba521584ce039017efecbd568f6601ec7d39a85d3daeb1ca2`.

## 0.24.30 — Cape: Straight(망토 옆선이 일자로 떨어짐) (2026-10-23)

- **Cape Straight**(0–1): 망토가 내려가면서 옆으로 퍼지는 정도를 줄여서 양옆 선이 사선이 아니라 수직으로 떨어짐(1 = 일자, 0 = Flare만큼 퍼짐). 기본: Cloak · Ragged 0.6, Capelet 0.3, Poncho 0(퍼지는 게 모양이라).
- 테스트: 92개 파일 3099/3099, `test_v02428.py`에 Straight 검사 추가. ZIP sha256 `a46a3dfd17d1daf1afc7e2a9fe0d6078457380b23271a0c223072902c26bed43`.

## 0.24.29 — 새 툴 Creature Hair(프레데터 드레드락 등 크리쳐 헤어 제네레이터) (2026-10-23)

- **Creature Hair**(왼쪽 툴 목록, 아이콘): 머리 위에 두피 영역을 라쏘로 그리면 그 안에 뿌리가 고르게 퍼지고 가닥이 자라서 몸을 따라 흘러내림(망토처럼 몸을 뚫지 않고 어깨 · 등을 타고 내려감). 라이브, Enter = Apply. Line 모드로 그으면 선을 따라(모히칸처럼).
  - **Style**: Dreads(프레데터: 굵은 꼬인 로프 + 금속 링) / Tentacles(굵고 매끈, 끝이 뾰족, 휘어짐) / Quills(뻣뻣한 가시털, 중력 거의 없음) / Strands(가는 머리카락 많이).
  - Count, Length · Length Random, Thickness · Thickness Random, Taper(끝으로 갈수록 가늘게), Lift(두피에서 얼마나 서 있다가 꺾이는지), Gravity, Wave(흔들림 · 컬), **Straight**(떨어질 때 얼마나 일자로 곧게 내려오는지: 1 = 수직으로 쭉, 옆으로 퍼짐 · 흔들림 줄어듦, 0 = 느슨하게; Dreads · Strands 기본 0.7), Rope · Rope Twist(드레드락 꼬인 질감), Rings · Ring Size(금속 밴드 / 비즈, 머티리얼 슬롯 2), Seed, Gap, Sides · Segments.
  - 몸에 머티리얼이 없으면 "MCH Hair"(어두운 색) / "MCH Hair Rings"(금속 금색)를 만들어 줌(이미 있으면 재사용).
  - 정수리처럼 위를 향한 뿌리에서 가닥이 위로만 솟던 문제를 만들면서 잡음(중력이 방향을 각도로 꺾음, 위를 향하면 영역 가운데에서 바깥쪽으로 넘어감).
- 몸을 고를 때 라이브로 생성된 것(망토 · 헤어 · 플레이트)은 통과 → 헤어 위에 망토, 망토 위에 헤어를 그려도 몸에 붙음.
- 테스트: 92개 파일 3098/3098, 새 `test_v02429.py`. ZIP sha256 `edb0231d418004676b71c2380d468ca73b9f4ca28ecdd70c81a27738d0b58479`.

## 0.24.28 — 새 툴 Cape(망토 제네레이터) (2026-10-23)

- **Cape**(왼쪽 툴 목록, 아이콘): 몸 위에 망토가 걸릴 쪽에서 그리면(등 뒤에서 보면서 그리면 등 뒤로) 그린 것의 **윗변 = 어깨 / 목 부분**에서 망토가 걸려 아래로 떨어짐. 시뮬레이션이 아니라 계산이라 모든 슬라이더가 바로 반영(케이프 하나 약 0.1초).
  - 몸을 따라 걸침: 천의 각 세로줄이 윗변에서 아래로 떨어지다가 몸에 들어가면 Gap만큼 밖으로 밀려서 어깨를 넘어 등 뒤로 흘러내림. Flare = 내려갈수록 퍼짐.
  - **Style**(레퍼런스 참고): Capelet(어깨 망토, 짧고 둥근 끝) / Cloak(다리까지 오는 긴 망토) / Poncho(넓게 퍼지고 뾰족한 끝, 옆으로 많이 감쌈) / Ragged(너덜너덜 찢긴 끝). 누르면 아래 슬라이더가 채워짐.
  - **Shape**: Auto(낮고 넓게 그리면 Preset, 길게 그리면 Outline) / Outline(그린 실루엣 그대로 = 아랫변이 밑단) / Preset(윗변만 쓰고 길이 · 밑단은 슬라이더).
  - Length, Hem(Straight / Round / Pointed / Split), Flare, Wrap(목 둘레로 양옆 몇 도 더 감쌀지), Folds · Fold Depth · Fold Random(세로 주름, 밑으로 갈수록 깊어짐), Wind · Wind Direction(아래쪽이 옆으로 날림), Tatter · Seed(찢긴 밑단), Thickness · Gap(0 = Auto), Columns · Rows.
  - 다른 플레이트처럼 Apply 전까지 라이브, Enter = Apply. 몸을 고를 때 이미 만든 망토는 통과(망토 위에 또 걸리지 않음).
- 목도리 · 후드는 망토 의견 받은 뒤 이어서.
- 테스트: 91개 파일 3064/3064, 새 `test_v02428.py`. ZIP sha256 `f3b32b0092c35e73cd274eb76761bab9e66f4480c74bfbe9a570e665a9d7240d`.

## 0.24.27 — Split 단축키를 다른 키로 바꿔도 안 되던 문제 (2026-10-23)

- S = Split은 뭔가 선택돼 있으면 Blender Scale에 양보하는데(0.24.8), 이 규칙이 키를 바꾼 뒤에도 따라가서 D · Shift+S 등 새 키도 선택 중엔 아무 반응이 없었음 → 이제 양보는 **그냥 S일 때만**, Hotkeys 상자에서 바꾼 키는 선택과 상관없이 항상 Split.
- 테스트: 90개 파일 3026/3026, `test_v0248.py`에 바꾼 키(D, Shift+S) 검사 추가. ZIP sha256 `33754e94ef1ef6536afaf5d8b1a16260d00dae352cf353645cd2c32c36d37cee`.

## 0.24.26 — Mech Ridge 모든 다각형(5각 · 6각 · … 24각, 오목 / 별), Plate Detail Alt = 파내기 + 쉐이딩 수정 (2026-10-23)

- **Mech Ridge가 직선 라쏘로 찍은 모든 다각형에서 작동**: 오각형 · 육각형 · 팔각형 … 24각형, 불규칙한 다각형, 오목한 별 모양까지. 6개 엣지 패턴 × Sharp / Chamfer / Bevel 전부 닫힌 메쉬로 나오는 것을 576가지 조합으로 확인.
  - 찍은 꼭짓점은 전부 유지(예전엔 Straighten이 23 · 24각형의 꼭짓점을 합쳐서 15각형처럼 됐음). 프리드로우(점이 많고 촘촘함)만 직선으로 정리. 완전히 일직선인 점(1° 미만)만 빠짐.
  - 볼록 다각형은 불린 없이 정확히 계산해서 즉시(12각형 이상이 3–18초 걸리던 것 → 0.1초 이하). 오목 모양은 빠른 Manifold 불린, 안 되면 Exact.
  - 꼭짓점이 많이 모이는 곳에서 베벨이 찢어질 때는 폭을 1/2, 1/4로 줄여서 다시 하고, 그래도 안 되면 그 부분 베벨만 빼고 패널에 안내(찢어진 메쉬는 안 만듦).
- **Plate Detail 1 / 2 / 3 + Alt**: 
  - 일반 메쉬 위에서 Alt + 그리기(또는 스케치 Alt+Enter) = 그 디테일 모양을 메쉬에 파냄(트림 단 / 라이즈 / 패널이 표면 안쪽으로 뒤집힌 모양, 디테일 높이만큼만). 예전엔 "draw over one" 오류.
  - 살아있는 디테일을 Alt로 자를 때 쉐이딩이 깨지던 문제(모든 면을 강제로 smooth로 만들어서 잘린 벽에 검은 줄) → 원래 면 쉐이딩 유지, 잘린 벽만 평평 + 경계 sharp. Creature Plate의 Alt 구멍도 같음.
- 테스트: 90개 파일 3024/3024, `test_v02424.py`에 다각형 · 별 · 패턴 · Plate Detail Alt 검사 추가. ZIP sha256 `7e8e6301056efde94949aa767ea78921282cd1ab570bf5f183d9b6bc5847287a`.

## 0.24.25 — Mech Ridge: 엣지 패턴 프리셋 + Turn + 엣지별 버튼 (2026-10-23)

- **Edge Pattern**(Ends 대신): 어떤 변이 경사로 올라가고 어떤 변이 세운 벽으로 남는지 고르는 프리셋. All Edges(Hip) / Gable(긴 쪽, 자동) / Every Other Edge(한 칸씩 건너) / Half Hip(한 변만 세움) / Corner(이웃한 두 변만) / Shed(한 변만 경사 = 한쪽으로 기운 판) / Custom.
- **Turn ◀ ▶**: 패턴을 외곽을 따라 한 변씩 돌림(그린 순서 기준). Gable은 Turn으로 가로 / 세로 방향 전환.
- **엣지 번호 버튼**(라이브 플레이트): 1, 2, 3 … 변마다 켜면 경사, 끄면 세운 벽. 누르면 자동으로 Custom. 최소 한 변은 경사로 남음.
- Shed / Corner처럼 전체 폭을 따라 올라가는 패턴은 Max Height로 높이를 자를 수 있음.
- 테스트: 90개 파일 2996/2996, `test_v02424.py`에 패턴 / Turn / 엣지 버튼 검사 추가. ZIP sha256 `925cdaf045ed6813bdf434a1c057885123b848773abd7b4fc672ca6ca6448fc6`.

## 0.24.24 — Armor Plate "Mech Ridge", Cut / Split 베벨: 고른 폭 + Crisp Shading (2026-10-23)

- **Armor Plate 프로파일 Mech Ridge**(메카닉 전용, 크리쳐 플레이트 Ridge의 메카 버전): 그린 외곽의 모든 변이 같은 각도(Slope)로 올라가 날카로운 능선에서 만남. 박스 라쏘 = 지붕(hip roof) 모양 4면, 긴 박스 = 가운데 능선. 면은 완전히 평평하고 능선은 정확히 각짐(근사가 아니라 정확한 기하로 만듦). 프리드로우 외곽은 Straighten(px)만큼 직선 변으로 정리.
  - **Ends: Hip / Gable**: Hip = 끝도 경사(박스면 4면), Gable = 능선이 양 끝까지 곧게 이어지고 끝은 세운 벽(끝 삼각형 없음). Swap Axis = 능선을 짧은 쪽 방향으로.
  - Max Height(0 = 끝까지 능선, 값 = 그 높이에서 평평하게 자름), Edge Wall(옆벽), Sink, Resolution(곡면 따라가기).
  - **Ridge Lines / Outer Edge 따로**: Sharp / Chamfer / Bevel + Width(0 = Auto) + Segments.
  - Smooth Bevels(기본 켬): 평평한 면은 깨끗하게, 챔퍼 · 능선 경계는 날카롭게(정확히 표시), 둥근 베벨만 부드럽게. 곡면 위에서도 면이 얼룩 없이 보임.
  - 다른 플레이트처럼 Apply 전까지 슬라이더가 바로 반영, Enter = Apply.
- **Cut / Split 베벨 폭이 들쭉날쭉하던 문제**: 0.24.23의 짧은 조각 정리가 테두리 점을 엣지 가운데로 옮겨서 테두리가 지그재그 → 베벨 띠 폭이 고르지 않았음. 이제 정리 뒤 모든 테두리 점을 원래 잘린 평면 위로 되돌려서 테두리가 곧고 베벨 띠가 고름.
- **Crisp Shading**(Edge Finish, 기본 켬): 베벨 띠 경계를 날카롭게(챔퍼 = 평평한 띠, 베벨 = 안쪽만 부드럽게), 잘린 벽은 평평하게, FBX 등에서 가져온 커스텀 노멀은 지움(새 면에 번져서 뭉개 보이던 원인). 끄면 예전 그대로(커스텀 노멀 유지).
- 테스트: 90개 파일 2986/2986, 새 `test_v02424.py`. ZIP sha256 `46522f02ccf80b3bb8872c0c9f053fbdb358a6a32b4f2e0f64698824dbac31a5`.

## 0.24.23 — Apply Modifiers, 크리쳐 플레이트 / 크리쳐 베이스 Alt = 두께만큼 파내기, 스케치 점 변환 되돌림, [ / ] 굵기 키 수정, 스컬프트 G = 선택, 촘촘한 메쉬 Cut / Split 베벨 수정 (2026-10-23)

- 뷰포트 왼쪽 동그란 버튼 목록 맨 위(툴 버튼 위)에 **Apply Modifiers (click a mesh)** 버튼. 누른 뒤 메쉬를 클릭하면 그 메쉬의 모디파이어를 스택 순서대로(위 → 아래) 하나씩 적용. 계속 다른 메쉬를 클릭할 수 있고 Esc / 우클릭으로 끝. 회전 / 줌 / 이동은 그대로 됨.
- 뷰포트에서 꺼 둔(눈 끈) 모디파이어는 건드리지 않음. 중간에 하나가 실패하면 거기서 멈추고(앞의 것은 적용된 채) 어떤 모디파이어에서 왜 멈췄는지 알려줌. 살아있는 Mecha 도형은 먼저 고정(Live 해제)해서 결과가 덮이지 않게. 공유 메쉬(Alt+D)도 기존 안전 적용 방식 사용.
- **Creature Plate Alt + 그리기**: 살아있는 크리쳐 플레이트 위가 아니면 오류 대신 아래 메쉬를 그 모양으로 **파냄**(불린처럼). 깊이 = 그 플레이트를 만들었을 때의 두께(Height + Edge Thickness)만큼만, 관통하지 않음. 살아있는 플레이트 위에서 Alt는 예전처럼 그 플레이트에 구멍.
- **Creature Plate 스케치**: 0.24.21의 "프리드로우 → 점으로 바뀜"을 되돌림. Sketch 켜고 그리면 예전처럼 선으로 스케치에 더해지고, Alt로 그리면 스케치에서 빠짐. **Enter** = 플레이트 적용, **Alt+Enter** = 그 모양을 메쉬에서 파냄(위와 같음). 다른 툴의 Sketch + 프리드로우도 같은 방식(점 변환 없음).
- **Creature Base Mesh Alt**(그리기 / 스케치 Alt+Enter): 관통 컷 대신 그린 덩어리 모양으로 메쉬를 파냄. 덩어리가 표면 가운데 걸치므로 들어가는 깊이 = 덩어리 아래쪽 절반 두께. 일반 Base Mesh Alt는 그대로(관통).
- **[ / ] 라인 굵기 키 수정**: Mecha 툴에서 굵기가 안 바뀌던 문제(Object Mode의 Blender 기본 [ / ] = 부모 / 자식 선택이 먼저 받는 것으로 추정, 실제 GUI에서는 미검증) → Mecha 그리기 툴이 켜져 있을 때는 [ / ] = Line Width 작게 / 크게가 먼저(상태줄에 cm 표시). Mecha 툴이 아닐 때는 Blender 기본 그대로.
- **Sculpt Mode에서 G** = Object Mode + Select / Move로 돌아감(왼쪽 Select / Move 타일과 같음).
- **Cut / Split Bevel · Chamfer가 촘촘한 메쉬(FBX 등)에서 안 되던 문제**: 기본 박스는 되는데 삼각형이 촘촘한 메쉬는 안 되거나 될 때도 있고 안 될 때도 있던 원인 = 불린이 잘린 자리 옆에 0.00002 정도의 아주 짧은 조각 엣지를 만들고, Clamp Overlap가 베벨 전체 폭을 그 가장 짧은 엣지에 맞춰 줄여서(0.05 → 0.002) 안 보였음. 잘리는 위치가 기존 점과 얼마나 가까운지에 따라 조각이 생기거나 안 생겨서 "랜덤"처럼 보였음. 이제 베벨 전에 잘린 테두리 주변의 짧은 조각만 정리(평평한 잘린 벽은 큰 면으로 합침, 짧은 엣지는 접음)해서 원래 폭이 나옴. 정리 중 메쉬가 열리는 단계는 되돌림(닫힌 메쉬 유지). 그래도 폭이 줄면 예전처럼 메시지로 알려줌.
- 테스트: 89개 파일 2954/2954, 새 `test_v02422.py`(8), `test_v02423.py`(Alt 파내기, [ / ], G, 촘촘한 메쉬 베벨). ZIP sha256 `e11cb27d71cfb2387ab79ddb2679732d82346b7f342e77bba9399d1128a9bd20`.

## 0.24.22 — Creature Plate / Plate Detail: Alt + 그리기 = 그 영역 빼기, Taper / Pressure 켜기 끄기 버튼 (2026-10-23)

- **Alt + 그리기 = 빼기(불린처럼)**: Creature Plate, Plate Detail 1 / 2 / 3에서 Alt를 누른 채 그리면 그 아래 살아있는 플레이트에서 그린 영역이 빠짐(안쪽이면 구멍, 가장자리에 걸치면 홈). 여러 번 가능. 빼낸 모양은 오브젝트에 기억돼서 슬라이더로 다시 만들어도 그대로 남음, Apply하면 그 메쉬 그대로 확정. 플레이트가 없는 곳에 Alt로 그리면 아무것도 안 만들고 안내만.
- **Taper / Pressure 버튼**: 헤더(Line 켰을 때)에 **Taper**(켜면 양 끝 뾰족, 옆 슬라이더 = 양), **Pressure**(펜 필압) 둘 다 켜기 / 끄기 버튼. 끄면 Taper 양은 그대로 기억.
- 테스트: 91개 파일 2968/2968, test_v02421에 Alt 빼기(구멍, 홈, 슬라이더 후 유지, 플레이트 없음 안내, Apply, Plate Detail) / Taper 버튼 검사 추가. ZIP sha256 `3c0998153d3e1e9a093264c78fd483b892f0ba6144901f79364c4e54eff5f46c`.

## 0.24.21 — 브릿지 패치 주름 메우기, 스케치 모드 프리드로우 = 수정 가능한 라쏘, 스컬프트 브러시, 라인 Taper / 필압 / [ ] 굵기, 깨진 메쉬 Split 안내 (2026-10-23)

- **Bridge Patch: Fill Crease**(기본 0.5): 두 덩어리가 맞닿아 정면에서 틈이 안 보일 때(몸통-골반 같은 곳) 패치가 메쉬 표면 바로 아래에 숨어서 안 보이던 문제. 이제 앞면을 여러 번 부드럽게 펴면서 메쉬보다 뒤로는 안 들어가게 해서, 맞닿은 골짜기는 패치가 덮어 메우고 볼록한 곳은 메쉬가 그대로 보임. 0 = 예전처럼 표면을 그대로 따라감.
- **스케치 모드 + Free Draw**: Sketch가 켜져 있으면 프리드로우로 그리고 손을 떼도 바로 적용되지 않고, 그린 외곽이 라쏘 점으로 바뀌어 점을 끌어서 수정할 수 있음 → **Enter**로 적용(스케치에 추가). Sketch가 꺼져 있으면 예전처럼 손을 떼면 바로 적용.
- **Creature Base Mesh / Creature Plate 시작 Resolution = 15**(Base Mesh는 28 그대로). 한 번만 적용, 바꾼 값은 유지.
- **SCULPT 브러시 타일**(왼쪽 MECHA LAB TOOLS 목록 아래): Draw / Clay Strips / Inflate / Grab / Smooth / Crease. 누르면 선택한 메쉬로 바로 Sculpt Mode + 그 브러시(탭 이동 없음). 위의 **Select / Move** 또는 Back to Object = 다시 Object Mode, Mecha 툴을 고르면 자동으로 Object Mode. 기존 Sculpt Move 버튼은 5.0에 없는 'Move' 대신 Grab 브러시.
- **라인 모드 Taper / Pressure**(헤더 Line 옆): Taper = 띠가 양 끝으로 갈수록 뾰족하게 가늘어짐(크리쳐 플레이트 등 라인을 쓰는 모든 툴), Pressure(펜 아이콘) = Free Draw에서 펜 필압만큼 굵기가 변함(마우스는 항상 1). **[ / ]** = Line Width 작게 / 크게(그리는 중에도).
- **Split / Cut이 깨지는 메쉬 안내**: 메쉬가 하나의 닫힌 덩어리가 아닐 때(겹친 파츠를 그냥 합쳐서 3면 이상이 붙은 엣지가 있거나 구멍이 있을 때) 결과가 깨지거나 "would delete the whole object" 같은 오류가 났음 → 이제 원인(몇 개 엣지가 어떤지)과 해결법(먼저 Remesh)을 메시지로 알려줌. 결과가 나와도 경고를 붙임.
- 테스트: 91개 파일 2958/2958, 새 `test_v02421.py`, test_v02420_bridge에 맞닿은 덩어리 주름 검사 추가. ZIP sha256 `ae6f1687c9e7acb73ff4f96b42ddcc2ce9dce9ad57cd3f0ec55137c7ca0953d7`.

## 0.24.20 — 크리쳐 툴 세트, 브릿지 패치, 베이스 메쉬 휨 / 쿠션, 라인 모드 손 떼면 적용 (2026-10-23)

### 새 툴 (왼쪽 툴 목록, 각자 아이콘)
- **Creature Base Mesh**: 라쏘 → 둥근 덩어리. Puff(부풀림, 얇은 곳은 얇게) / Ridge(다이아몬드 단면) / Pillow(납작, 외곽만 둥글게). Height(0 = Auto), Edge Round, Soft Outline, Resolution. Base Mesh와 따로 설정.
- **Creature Plate**: 아머플레이트의 크리쳐 버전(빠름). Puff / Ridge / Pillow / Scale(뿌리 두껍고 끝 얇게 들림), Height · End Height, 엣지 두께, Through(앞뒤 관통).
- **Belt Maker**: 메쉬를 감싸는 스트랩(Wrap) 또는 그린 선을 따라가는 스트랩(Follow). 프리셋 Plain / Rail / Webbing(택티컬), 버클.
- **Creature Spike**: 프리셋 4(Fin / Horn / Hook / Notch), 고른 것끼리 랜덤 섞기, 크기 · 기울기 · 회전 + 랜덤. 라쏘 = 영역 채우기, Line 버튼 = 선 따라.
- **Creature Scales**: 비늘 프리셋 7(A–G, 스케치에서 따옴), 랜덤 섞기 · 크기 · 회전, 뿌리 두껍고 끝 들림, Resolution Low / Mid / High(Low가 High보다 약 5배 가벼움). 라쏘 = 영역 채우기, Line = 선 따라.
- **Scale Brush**: 조약돌 프리셋 12개가 바닥이 붙은 채 서로 겹치지 않고 촘촘하게 라쏘 영역을 채움(보로노이 칸마다 하나씩 맞춰 넣음). Size · Size Random · Rotate Random · Gap · Dome / Pillow · Height · Edge Round · Resolution · Seed.
- **Bridge Patch**: 두 메쉬 사이 틈 메우기(별도 오브젝트, 지브러시 DynaMesh로 합치는 용도). 기본 = 라쏘 전체가 하나의 덩어리로 두 메쉬와 겹침: 라쏘 방향으로는 앞면이 메쉬 표면을 따라가다 틈에서 완만한 곡선으로 이어지고, 폭 방향으로는 양옆이 둥글게 말림(Round), 뒷면은 메쉬 가운데 깊이 기준 대칭으로 채움(Fill). Trim to Gap = 틈만(테두리를 메쉬 속으로 묻음). Smooth · Bulge · Wrap · Thickness · Sink · Overlap · Resolution.
- **Flower Plate**: 그린 모양 그대로, 시작점 쪽은 붙고 나머지가 들려서 휨. Lift, Curl(+ 뒤로 말림 / − 바깥으로 처짐), Curl Power, Side Bend, Roll, Attach, Thickness, Tip Thin, Tip Sharp(0 = 그린 모양 그대로), Sink.
- **Surface Curve**: 메쉬 위를 따라 그리면 그 위에 Mesh Curve가 생김(이후 Mesh Curve처럼 편집).

### 기존 툴
- **Base Mesh / Creature Base Mesh: Bend**(만든 뒤 LIVE 패널): Bend Up / Down, Bend Sideways, Band(고르게) / Angle(한 곳에서 꺾임, 이음매 틈 없음), Angle의 Outer Round / Inner Round, Bend Position, Bend Direction.
- **Base Mesh 프로파일 Cushion**: 양면이 볼록하고 외곽이 솔기처럼 모이는 쿠션(Height = 전체 두께, Edge Round = 테두리 볼륨). 1차 버전.
- **Mesh Curve**: 외곽 라인(Lines / Height / Width / Rotate), 크리쳐 단면 A / B / C, Guts(내장 느낌 마디), From Object(내 오브젝트 외곽을 단면으로).
- **라인 모드(모든 툴)**: 선을 긋다가 손을 떼면 바로 적용(Enter / 더블클릭 필요 없음). Plate Detail 1 / 2 / 3에도 Line 버튼.
- **Remesh 바로 실행 단축키**: 처음엔 비어 있음 → Remesh 패널의 Run Key 또는 Hotkeys 상자에서 키 지정, Save로 유지. 어느 툴에서나 선택한 메쉬에 Remesh + Smooth 실행.
- **Mirror**: 0.24.19의 좌클릭 / 우클릭 적용을 되돌림(요청). Mirror 자체는 그대로.
- 스탬프 모양에 비늘 외곽 7개(Scale A–G) 추가. 새 툴 · 프로파일 아이콘 13개.
- 테스트: 90개 파일 2923/2923. 새 test_v02420*(bend / bridge / cushion / keys), test_v0220 라인 모드를 누르고-끌고-떼기로. ZIP sha256 `4cb9cff994f6947903c03ea04883ac55b81d1fa2ed44905b69c1676608e3badc`.

## 0.24.19 — Mirror: 좌클릭 = 오른쪽으로 복사 + 적용, 우클릭 = 왼쪽으로 복사 + 적용 (2026-10-22)

- **Mirror(Alt+X / 왼쪽 Mirror·Symmetry 버튼)**: 켠 상태에서 **좌클릭** = 화면 오른쪽으로 복사(왼쪽 반이 오른쪽에 거울로)하고 바로 적용, **우클릭** = 화면 왼쪽으로 복사하고 바로 적용. 화면에서 좌우로 놓인 축을 고름(위 / 앞 뷰 = X, 뒤 뷰면 -X 쪽이 화면 오른쪽). Mirror 버튼(살아있는 미러 모드)에서도 클릭은 적용.
- 다른 오브젝트를 가리킨 채 클릭하면 예전처럼 그 오브젝트 건너편으로 복사 + 적용. 콜렉션 인스턴스는 클릭해도 거울 인스턴스가 원본을 따라다니는 그대로.
- 바뀐 것: 예전 좌클릭 = "살아있는 미러로 끝내기", 우클릭 = 취소 → 취소는 **Esc**만. 살아있는 미러로 끝내려면 Mirror 버튼 + Enter. Shift+좌클릭(축 추가), X / Y / Z, B, Enter / Space, 마우스 기울이기 미리보기는 그대로.
- 테스트: 82개 파일 2668/2668 (`tests/test_log_bpy501_v02419.txt`), 새 `test_v02419.py`(21), test_v0113의 "클릭 = 살아있는 미러" 검사를 Enter(Mirror 버튼 모드)로 바꿈. ZIP sha256 `6e441cca809dbce5fd9d8d4f16966a9d8aeff594fd0fca5f5a5b9cde273c0bbf`.

## 0.24.18 — 라쏘는 점 찍기만, Box Hide Enter 적용 / Split Off, Line Curve 아이콘 (2026-10-22)

- **라쏘 = 클릭으로 점 하나씩**: 마우스를 누른 채 움직이면 점이 줄줄이 찍히던 동작 제거(자유롭게 그리기는 Free Draw). Cut / Split / Base Mesh / Plate 등 라쏘를 쓰는 툴 모두.
- **Box Hide + Enter**: Box Hide 툴에서는 숨긴 메쉬가 선택돼 있지 않아도(Auto Target이라 보통 선택 안 됨) Enter = Apply. 다른 툴에서는 예전처럼 선택한 것만.
- **Box Hide Split Off**: 패널의 "Split Off Hidden" - 숨긴 부분이 따로 떨어진 메쉬(이름_Hidden)가 되고 원래 메쉬는 그 자리가 뚫림(Split처럼 둘 다 닫힌 솔리드, Open이어도). 새 조각이 선택됨.
- **L 모양 메뉴**: 커스텀(PNG) 모양 칸은 처음엔 접혀 있음 - "Custom PNG Shapes" 줄을 눌러야 펼쳐짐(Blender를 새로 켜면 다시 접힘).
- **Line Curve 아이콘**: 점 줄 → 굵기가 일정한 한 줄 선(0.24.17의 바뀐 기능에 맞춤).
- 키캡용 아이콘(512 px PNG 32개, 라쏘 메뉴 L 포함)은 `tools_dev/make_icons.py` + `make_icons_v02417.py`(OUT = 512)로 다시 뽑을 수 있음.
- 테스트: 81개 파일 2647/2647 (`tests/test_log_bpy501_v02418.txt`), 새 `test_v02418.py`(19), test_v0245 +4(Box Hide Enter), test_stroke_events의 "라쏘 드래그 = 연속 점" 검사를 새 동작("누른 채 움직여도 점 1개, 클릭마다 1개")으로 바꿈; 전체 실행에서 test_zip_install의 '키맵 중복' 검사 3개가 0.24.17 툴 키 항목들(키는 비어 있고 고르는 툴만 다름)을 같은 항목으로 봐서 실패 - test_registration_recovery처럼 action / tool까지 비교하도록 고쳐 그 파일만 다시 실행 19/19. ZIP sha256 `982e1941b3a622a6698265fd3c280c3687788acad0f6f61b57c0b4537514b921`.

## 0.24.17 — L = 라쏘 모양 메뉴, 툴별 단축키 + 저장, Line Curve = 굵기 일정한 튜브, 왼쪽 메뉴 새 아이콘 (2026-10-22)

- **L = 라쏘 모양 메뉴**: MECHA LAB에서 L → 마우스 위치에 모양 고르기 창(예전 Space 메뉴처럼 큰 아이콘).
- **단축키 탭**: Workspace & Hotkeys의 Hotkeys에 "Tools (left list)" - 왼쪽 메뉴 툴 전부(처음엔 비어 있음, Cut = C / Split = S / Armor Plate = Alt+A는 그대로). 키 칸을 눌러 지정 → **Save Hotkeys**로 Mecha Lab 전용 파일(config/mecha_lab/hotkeys.json)에 저장, 다음 실행 때 그대로 적용(Blender 설정은 안 건드림). **Default Keys** = 저장 파일 삭제 + 기본 키.
- **Line Curve 다시 만듦**: 0.24.10은 오브젝트(없으면 구)를 같은 크기로 줄지어 복사해서 점처럼 보였음 → 이제 처음부터 끝까지 같은 굵기의 튜브, **Thickness** 하나로 전체 굵기. 점별 굵기 손잡이(주황 점) / Ctrl+휠은 Line Curve에서 꺼짐. 단면 / 끝막음 / 닫기 / 비틀기 / 점 편집은 Mesh Curve와 같음. 0.24.10에서 만든 Line Curve는 패널 버튼 하나로 라인으로.
- **왼쪽 메뉴 아이콘**: 같은 그림을 쓰던 툴에 각자 그림 - Box Hide(모서리가 숨겨진 큐브), Armor Plate / Plate Detail 1 / 2 / 3 / Screw(T자 나사) / Cloth Plate(옷)는 같은 룩(바닥선 위 옆모습), Mesh Curve(튜브), Line Curve(같은 굵기 선). `reference/left_list_icons_v02417.png`, 생성 스크립트 `tools_dev/make_icons_v02417.py`.
- 테스트: 80개 파일 2572/2572 (`tests/test_log_bpy501_v02417.txt`; 전체 실행에서 test_registration_recovery의 '키맵 중복' 검사 4개가 키가 비어 있는 툴 키 항목들을 같은 항목으로 봐서 실패 - 항목의 동작(action / tool)까지 비교하도록 고쳐 그 파일만 다시 실행 38/38), 새 `test_v02417.py`(18). ZIP sha256 `07d4733bd536ff4e2ebc2565e5648e5725195a5398b94344db164620df5c6291`.

## 0.24.16 — Panel Cloth Puff(부푸는 정도) 슬라이더 (2026-10-19)

- **Puff**: 천을 선택하면 Tension / Gravity 위에 있음. 1 = 프리셋 그대로(결과 동일), 0 = 안 부풂, 2 = 두 배. 바꾸면 Refresh가 빨갛게, 누르면 새 값으로 다시 굽기(새 천에도 값 유지). 원래 거의 안 부푸는 프리셋(Cloth / Silk / Canvas)도 Puff를 올리면 조금 부풂. 비교 `reference/panel_cloth_puff_v02416.png`(Padding, Puff 0 / 1 / 2.5).
- 테스트: 79개 파일 2554/2554 (`tests/test_log_bpy501_v02416.txt`), 새 `test_v02416.py`(8). ZIP sha256 `a1b3b0dd64d24375126a17ffad0ea4962c805f8e0d4f30757a6d999e7d7eba87`.

## 0.24.15 — 메쉬 Mirror 안 되던 문제(0.24.13) 수정, 다른 오브젝트를 가리켜 그 너머로 미러 (2026-10-17)

- **원인(0.24.13 회귀)**: 콜렉션 인스턴스 미러 연산자를 기존 메쉬 Mirror 연산자(`mch.mirror_lean`)에서 상속받아 만들었더니, Blender가 메쉬 Mirror의 파이썬 클래스를 잃어버려("unable to get Python class for RNA struct 'MCH_OT_mirror_lean'") Alt+X / 왼쪽 Mirror·Symmetry 버튼 / Symmetry 툴이 모두 "mirror_lean.poll() failed, context is incorrect"로 막힘(사용자: Base Mesh로 만든 메쉬). 테스트는 연산자를 목업으로 바꿔 불러서 못 잡았음. → 상속을 없애고 공통 부분을 별도 믹스인(LeanModal)으로 분리. 실제 연산자 poll을 부르는 회귀 테스트 추가.
- **다른 오브젝트를 가리켜 미러**: Alt+X / Mirror 기울이기 중 마우스를 다른 오브젝트 위에 올리면 그 오브젝트가 미러 중심이 되고, 복사본은 그 너머 반대편에 생김(축 = 선택한 것에서 그 오브젝트 쪽 월드 축, 선택한 쪽은 그대로). 예: 왼팔 선택 + 몸통 가리킴 → 오른쪽에 복사. 빈 곳으로 가면 예전 기울이기. 메쉬와 콜렉션 인스턴스 둘 다, 자기 자신(인스턴스는 자기 콜렉션 부품)은 제외. 아래 상태줄에 안내.
- **Mirror 진입점 하나로**: Alt+X와 왼쪽 Mirror / Symmetry 버튼이 같은 함수 - 메쉬가 있으면 메쉬 Mirror, 없고 콜렉션 인스턴스가 있으면 인스턴스 Mirror, 둘 다 없으면 알기 쉬운 안내(커브 등은 "먼저 메쉬로 변환").
- 테스트: 78개 파일 2546/2546 (`tests/test_log_bpy501_v02415.txt`), 새 `test_v02415.py`(10), `test_v02413.py`(21: 실제 연산자 poll, 커브만 / 커브 + 인스턴스 / 왼쪽 버튼 분기), test_v0113 / test_v0192 / test_v0232 / test_v0248의 버튼 소스 검사·목업을 새 진입점에 맞춤. ZIP sha256 `827eb58468eabb786725342811e274859dbe69d07b030cc8713853b89ffb348f`.

## 0.24.13 — 콜렉션 인스턴스도 Alt+X 미러 (2026-10-17)

- **콜렉션 인스턴스 선택 + Alt+X**: 메쉬 Mirror와 같은 기울이기 제스처(마우스를 복사할 쪽으로, X / Y / Z 키, Shift+클릭 = 축 추가, Esc = 취소). 반대편에 같은 콜렉션의 거울 인스턴스가 생기고, 원본을 움직이거나 돌리면 따라옴(콜렉션 안을 고치면 양쪽 다 바뀜). 다시 Alt+X = 거울 인스턴스를 새 축으로 바꿈. 기준면은 Mirror 설정(World 원점 / 3D 커서 / Local)을 따름. 메쉬를 선택하면 예전처럼 메쉬 Mirror.
- 테스트: 77개 파일 2529/2529 (`tests/test_log_bpy501_v02413.txt`; 전체 실행에서 test_v0232의 keep_live 검사 1개가 Python 클래스 주석을 읽다 실패 - 연산자 속성은 그대로 있음을 확인하고 등록된 RNA 속성을 보도록 고쳐 그 파일만 다시 실행 19/19), 새 `test_v02413.py`(14). ZIP sha256 `2e99a81d7cddf0273708fbc272f7b501d5e6231c936f223c26196c0e88fbed8d`.

## 0.24.12 — Smart Fuse: 여러 개 한 번에, 이어 붙이기 / 컷 문제 수정 (2026-10-16)

- **이어 붙이면 망가지던 진짜 원인**: 퓨즈를 확정해도 이음새 표시(베벨 대상 엣지)가 메쉬에 남아 있었음 → 다음 퓨즈가 ① 그 옛 표시를 새 이음새로 착각(멀리 떨어진 오브젝트도 '붙었다'고 하고 지워 버림) ② 옛 이음새에 베벨을 또 걸어 겹친 면 / 구멍이 생김(4번째쯤부터 메쉬가 안 닫힘) → 그 뒤 퓨즈 / 컷이 이상하게 됨. → 퓨즈 전과 확정 후에 옛 표시를 지움. 두 메쉬가 닫혀 있으면 합치기를 Manifold 방식으로(이음새를 못 찾으면 Exact).
- **여러 개 한 번에**: 3개 이상 선택하면 활성(노란) 오브젝트에 가까운 것부터 하나씩 붙이고 확정. 처음엔 안 닿다가 이웃이 붙은 뒤 닿는 것도 다시 시도. 끝내 안 닿는 것은 그대로 두고 알려줌. 2개는 예전처럼 미리보기.
- **미리보기 상태에서 다음 퓨즈 / 컷**: 미리보기가 남아 있으면 먼저 확정(Apply)한 뒤 진행. 예전엔 다음 퓨즈는 막히고, 컷은 원본만 잘리고 숨은 상대 오브젝트가 다시 합쳐져 이상하게 보였음.
- 테스트: 76개 파일 2515/2515 (`tests/test_log_bpy501_v02412.txt`), 새 `test_v02412.py`(16). ZIP sha256 `4cee1206061bc8027c9d0f197441ec14c4dc67a9fc8f4a8abdd70ab0034c9e9c`.

## 0.24.11 — Box Hide: Selected Only 지킴, Shift+D 복제본이 같이 잘리던 문제 (2026-10-16)

- **스케치 + Enter가 Selected Only를 무시하던 문제**: 스케치로 그린 Box Hide는 Targets 설정과 상관없이 덮인 메쉬를 전부 대상으로 했음. → Selected Only면 선택한 메쉬만, Active면 활성 메쉬만(바로 그리는 Box Hide와 같음).
- **Shift+D 복제본까지 잘리던 문제**: 숨긴 메쉬를 Shift+D로 복제하면 복제본의 Box Hide 모디파이어가 원본과 같은 "숨김 볼륨"을 가리킴 → 원본에 더 숨기면 복제본도 같이 잘림. → 볼륨을 바꾸기 전에 같은 볼륨을 쓰는 다른 메쉬에 지금 모양 그대로의 자기 볼륨을 따로 줌. Show All / Apply도 다른 메쉬가 쓰는 볼륨은 지우지 않음.
- 테스트: 75개 파일 2499/2499 (`tests/test_log_bpy501_v02411.txt`), 새 `test_v02411.py`(11). ZIP sha256 `d6a19ae92a64f7093a2d7aecf1160481066c94762ce12ebdf60b8b5b1ddd4d33`.

## 0.24.10 — 새 툴 Plate Detail 3, Line Curve (2026-10-16)

- **Plate Detail 3**(툴 목록 / 아래 버튼 줄 "Detail 3"): Plate Detail 1에서 계단 테두리(트림 층)를 뺀 버전. 그린 모양 그대로 평평한 판이 수직 벽으로 올라옴. Height(기본 크기의 2 %) / Lift 실시간, Enter = Apply, 라쏘 스케치도 됨. Plate Detail 1 / 2는 그대로.
- **Line Curve**(새 툴, 툴 목록 / 아래 버튼 줄 "Line Curve"): Mesh Curve와 별개 툴. 점을 찍으면 내 오브젝트(없으면 구)가 커브를 따라 반복되고, 복사본이 모두 같은 크기. 점마다의 반지름(주황 점 / Ctrl+휠)과 Start / End Size는 무시, Radius / Size를 바꾸면 전체가 같이 커지고 작아짐. Linked Object / Count·Distance / Align / Rotate / Twist / 점 편집 / IK / Apply는 Mesh Curve의 Repeat과 같음. Mesh Curve 툴은 그대로(Tube / Repeat), 서로의 결과는 각자 툴에서만 편집 패널 / 아래 버튼이 뜸.
- 테스트: 74개 파일 2488/2488 (`tests/test_log_bpy501_v02410.txt`; 전체 실행에서 test_v02321의 소스 문자열 검사 1개가 HUD 판정을 tool_owns로 옮긴 탓에 실패 → 실제 동작 검사로 고쳐 그 파일만 다시 실행 13/13), 새 `test_v02410.py`(31). ZIP sha256 `f94b74c3adf34f1c10149fb24573923d3e20b991840b8d8c0288eee3afc5dea5`.

## 0.24.9 — 살아있는 Mirror의 반대쪽에 그려도 Cut이 됨 (2026-10-16)

- **Mirror(살아있는 미러) 뒤 Cut이 안 먹던 문제**: 미러로 생긴 반대쪽(복사본) 위에 모양을 그리면 Auto Target은 그 메쉬를 찾지만, 실제 자르기는 미러 전 원본 반쪽만 보기 때문에 "The shape does not intersect the mesh"로 아무것도 안 바뀌었음. 월드 축으로 뒤집은 뒤(음수 스케일)에는 원본이 반대편으로 가서 늘 이렇게 됨. → 원본과 안 겹치면 그린 모양을 Mirror 축(피벗 오브젝트 포함)으로 뒤집어 원본 반쪽을 자름. 미러가 양쪽에 똑같이 보여줌. Split도 같은 경로.
- Box Hide 중 Ctrl+Z 크래시: 코드에서 원인을 찾지 못했음(Ctrl+Z 핸들러 / 스케치 / 타이머 확인). 크래시 로그가 필요.
- 테스트: 73개 파일 2439/2439 (`tests/test_log_bpy501_v0249.txt`), 새 `test_v0249.py`(15). ZIP sha256 `f8262d1b2c7b421f474ddf8a3143dc59f714f73a6c354bd0016ce56fae07b96d`.

## 0.24.8 — 단축키 Alt+X = Mirror, S = Split, Alt+A = Armor Plate (2026-10-16)

- **Alt+X = Mirror**: 왼쪽 Mirror 버튼과 같음(마우스를 복사할 쪽으로 기울이기, 결과는 살아있는 Mirror). 메쉬를 선택하지 않았으면 경고만.
- **S = Split 툴**: 아무것도 선택하지 않았을 때만. 오브젝트를 선택한 상태면 S는 그대로 Blender 크기 조절(Scale).
- **Alt+A = Armor Plate 툴**(MECHA LAB 안에서는 Blender의 Alt+A "선택 해제" 대신).
- 모두 MECHA LAB 작업 공간 + Object Mode에서만, N > Workspace & Hotkeys에서 키 바꾸기 / 환경설정의 Hotkeys 체크로 끄기 가능.
- 테스트: 72개 파일 2424/2424 (`tests/test_log_bpy501_v0248.txt`), 새 `test_v0248.py`(10). ZIP sha256 `83aadd89d98fa3014d37de1106a660b3c07ce3927e48508f31bbb36fddec3fc2`.

## 0.24.7 — 이미지 여러 개 불러온 뒤 목록 멈춤 수정, 업데이트 뒤에도 휠 = 확대 / 축소 (2026-10-16)

- **스탬프 목록이 느리고 Blender가 멈추던 문제**(JPG 여러 개 불러온 뒤): 목록이 다시 그려질 때마다 모든 모양 파일(외곽선 좌표가 든 JSON)을 다시 읽고, 큰 원본 이미지를 그대로 아이콘으로 불러왔음. → 목록은 바뀐 파일만 읽고 나머지는 기억, 라이브러리에는 192 px 작은 PNG만 저장, 예전에 불러온 큰 이미지는 처음 한 번 `_thumb.png` 작은 아이콘을 만들어 씀. 여러 파일 불러오기는 끝에 미리보기를 한 번만 새로 고침. 지우기는 작은 아이콘도 같이 지움.
- **휠이 여전히 스탬프 크기를 바꾸고 화면 확대가 안 되던 문제**: Blender는 툴을 다시 등록할 때 이미 있는 툴 키맵을 새로 만들지 않아서, 0.24.5의 "휠 = 스탬프 크기" 키맵이 업데이트 뒤에도 남을 수 있었음. → 애드온이 켜질 때 Mecha 툴 키맵을 지우고 현재 설정으로 새로 만들고, 없어진 `mch.stamp_scale` 키 항목도 지움(애드온 키맵만, 사용자 키맵 설정은 건드리지 않음). 설치 뒤 **Blender를 한 번 다시 시작**해 주세요.
- 테스트: 71개 파일 2414/2414 (`tests/test_log_bpy501_v0247.txt`), 새 `test_v0247.py`(17). ZIP sha256 `5f8b31097d584013b268ace1eb3aa575efae3626dd5b3dbcb3e7e804a170564f`.

## 0.24.6 — 스탬프 여러 파일 한 번에, Auto 전경, 휠은 다시 확대 / 축소 (2026-10-16)

- **스탬프 불러오기에서 여러 파일 한 번에**(파일 창에서 Shift / Ctrl / 드래그로 선택): 이름은 각 파일 이름, 실패한 파일은 경고로 알려주고 나머지는 들어옴.
- **Foreground: Auto**(새 기본값): 투명 배경이 있는 PNG는 불투명한 부분, 투명이 없는 JPG / PNG는 밝은 부분이 모양. White / Bright, Alpha도 그대로 고를 수 있음.
- **마우스 휠 = 스탬프 크기 제거**(0.24.5): 크기는 드래그로, 휠은 다시 화면 확대 / 축소.
- 테스트: 70개 파일 2396/2397 (`tests/test_log_bpy501_v0246.txt`) - 실패 1개는 test_v02319 시간 검사(0.514초). 같은 검사를 0.24.4 코드로 돌려도 지금은 0.52 ~ 0.61초라 이 머신이 느려진 것으로 판단(전에는 0.42 ~ 0.48초). 여러 파일 불러오기는 그 전체 실행 뒤에 넣어서 test_png_shapes / test_v0245 / test_ui_draw / test_register를 다시 돌려 통과. ZIP sha256 `f998927f74222572dd0ff0419d5806ecbf782dcca444ada21b6f9ad70b1f44ad`.

## 0.24.5 — Enter = Apply, 더블클릭으로 툴 나가기, JPEG 스탬프, 휠 = 스탬프 크기, Base Mesh 설정 유지, Alt Base Mesh = Cut (2026-10-16)

- **Enter = Apply**: 선택한 오브젝트의 라이브 결과를 적용(먼저 맞는 하나): Plate Detail → Armor Plate → Cloth Plate → Base Mesh → Mirror → Box Hide → Curve. 스케치 중이면 Enter는 예전처럼 스케치 적용.
- **더블클릭으로 툴 나가기**: 아무것도 안 그린 상태에서 더블클릭 = Select로. 빈 곳이면 선택 유지, 다른 메쉬면 그 메쉬 선택. 라쏘를 그리는 중(점 2개 이상)이면 예전처럼 닫고 적용. Screw Stamp는 첫 클릭의 나사를 되돌리고 나감.
- **스탬프 불러오기에 JPEG**(.jpg / .jpeg): 투명 없으면 밝기 기준, 라이브러리에는 PNG로 보관. 버튼 "Import PNG / JPG".
- **마우스 휠 = 스탬프 크기**(스탬프 모양일 때만, 한 칸 10 %, 아니면 화면 확대 / 축소).
- **Base Mesh**: 살아있는 모양에서 바꾼 높이 / 프로파일 / 베벨 등이 다음 모양에도 유지(매번 예전 기본값으로 돌아가던 문제).
- **Alt Base Mesh = Cut 툴처럼**(깊이 모드 / 깊이 / Edge Finish / Solver를 Cut 설정으로): 예전 커터는 Height 깊이라 얇은 판의 뒷면까지 뚫었음. 스케치 Alt + Enter도 같음.
- 테스트: 70개 파일 2396/2396 (`tests/test_log_bpy501_v0245.txt`), 새 `test_v0245.py`(21), 옛 Alt 커터 검사(test_v0100_regression) 새 동작으로 수정. ZIP sha256 `b67a52f9c48ff0a725229f0335d2696de3e215c189e98c437d91ef8fc5a64ed1`.

## 0.24.4 — Panel Cloth Refresh 버튼, Plate Detail 2 프리셋(Vertical / Slanted / Round) (2026-10-16)

- **Panel Cloth**: Tension / Gravity를 바꿔도 바로 다시 굽지 않음 - **Refresh** 버튼(바뀐 값이 있으면 빨갛게)을 눌러야 새 값으로 다시 굽기. 기본 결과는 그대로 0.23.25와 같음.
- **Plate Detail 2 프리셋 버튼**: **Vertical**(바닥은 부드럽게 붙고 직각 벽, 윗면 모서리 각짐) / **Slanted**(같은 바닥 + 70° 벽) / **Round**(기존). 새 가장자리 모양 **Foot + Wall**: 표면에 접하는 둥근 바닥(Foot Radius, 기본 높이 × 0.6) 다음 곧은 벽(Wall Angle). 마지막 값은 다음 디테일에 이어짐. Plate Detail 1은 그대로.
- 비교 `reference/plate_detail2_presets_v0244.png`. 테스트: 69개 파일 2377/2377 (`tests/test_log_bpy501_v0244.txt`). ZIP sha256 `30cbb736ab1ec444ad5c2af777e22af560757a0de6f9110a6723c9c86503af15`.

## 0.24.3 — Ctrl+Z 크래시 수정, Box Hide 스케치 (2026-10-16)

- **Ctrl+Z / 플레이트 디테일 뒤 Blender 꺼짐**(사용자 크래시 로그: `curve_tube._on_depsgraph`): 커브(Tube) / 로프트의 depsgraph 핸들러가 `depsgraph.updates`를 읽었는데, Ctrl+Z 직후나 애드온이 임시 메쉬를 지운 직후 이 목록에 이미 지워진 데이터가 남아 읽는 순간 크래시. → 목록을 아예 안 읽고 연결된 원본의 상태(위치 / 평가된 경계 / 점 수 / 좌표 합, 커브 점)를 비교. 살아 있는 커브 / 로프트가 없으면 아무것도 안 함, Ctrl+Z / 다시 실행 직후 0.3초는 쉼.
- **Box Hide + 스케치**: 그리기 = 스케치에 추가(스케치가 없을 때 Alt + 그리기도 추가 - "Draw a shape first" 오류 없음), **Enter = 숨기기, Alt + Enter = 다시 보이기**, 스케치가 있을 때 Alt + 그리기 = 빼기. 안내 문구도 맞춤. 스케치 끔은 예전과 같음.
- 대상 찾기(Auto Target)가 방금 지운 임시 오브젝트(None) 때문에 멈추던 문제 수정.
- 테스트: 69개 파일 2371/2372 (`tests/test_log_bpy501_v0243.txt`, 시간 검사 1개가 다른 실행과 겹쳐 0.599초 → 단독 재실행 통과), 새 `test_v0243.py`(9). ZIP sha256 `4d6158f3bc875127692f8b87e805932ed3f928b089eb255bdacecdfa5f63111a`.

## 0.24.2 — Plate Detail 렉 / 나사 홈 수정, Panel Cloth = 0.23.25 결과 + Tension / Gravity + Fast Start (2026-10-16)

- **Plate Detail 렉(멈춤)**: 슬라이더 한 번에 3 ~ 5초 걸리던 다시 만들기 → 0.2 ~ 0.4초. 표면 패치를 아머 플레이트처럼 큰 면(20px)으로, 외곽선까지 거리는 처음 한 번만 계산(자를 때 다시 안 함), 드래그 중엔 쉬었다가 손을 멈추면 한 번만 다시 만듦. Ctrl+Z 때 대기 중인 다시 만들기는 버림.
- **나사 홈이 가장자리에 닿을 때** 옆면에 구멍(열린 엣지)이 생기던 문제 수정.
- **Panel Cloth**: 시뮬 코드는 0.23.25 그대로 - 기본 결과가 0.23.25와 **비트 단위까지 같음**(Padding / Cloth로 확인). 그 위에 **Tension / Gravity** 슬라이더(구운 천 선택 시 N 패널): 기본값(1 / 프리셋)에서는 결과 그대로, 바꾸면 손을 멈춘 뒤 다시 굽기. Tension을 내리면 느슨함은 프리셋의 최대 2.5배까지.
- **Fast Start**(체크박스, 기본 꺼짐): 천을 표면에서 띄우는 준비가 9초 → 0.02초(9천 점 기준). 시작이 아주 미세하게 달라서 주름 자리가 조금 다름.
- 테스트: 68개 파일 2363/2363 (`tests/test_log_bpy501_v0242.txt`). ZIP sha256 `ed26f08ab74b146d4acbc855b987ec8d04a719283e873fac47e30b4ea82eb78a`.

## 0.24.1 — Plate Detail: 스케치, Lift, Round / Chamfer, 면 수 대폭 줄임 (2026-10-15)

- **스케치**가 Plate Detail 1 / 2와 Box Hide에서도 다른 라쏘 툴처럼 됨(여러 번 그리기 / Alt 빼기 → Enter 한 번 적용, Backspace, Esc). 스케치가 안 되는 툴에서는 Sketch 버튼이 회색.
- **Lift** 슬라이더(Detail 1 / 2): 표면 방향으로 올리기 / 내리기(- = 박힘) - 면에 딱 붙게.
- **Detail 2 가장자리: Round / Chamfer**(+ Round Top, Soft Foot). Round = 표면에서 자라나듯 바닥은 완만한 필렛, 위는 둥근 어깨(8링). 바닥 아래 테두리와 매끈한 면이 섞여 생기던 어두운 끊김 선을 없앰(샤프 엣지).
- **면 수 줄임**: 평평한 부분은 큰 면 하나로 합침(평평한 판 예: 15081 → 44면, Detail 2 16240 → 221면). 휜 면에서는 실제 표면에서 크기의 0.12 % 안으로만 합쳐서(휜 정도로 칸을 나눔) 큰 판이 표면 아래로 꺼지지 않음(반지름 3 원통 위 예: 600 ~ 1100면). 비교 `reference/plate_detail_v0241.png`.
- 테스트: 68개 파일 2361/2361 (`tests/test_log_bpy501_v0241.txt`), 새 `test_v0241.py`(12). ZIP sha256 `9201b09a7ab74818472980db0561aa4c3fccdde51e3fe5d539243ce57b5f9521`.

## 0.24.0 — Plate Detail / Plate Detail 2 / Screw Stamp, Panel Cloth 텐션·중력 실시간 (2026-10-15)

- **Plate Detail**(하단 툴바 **Detail**, 새 도구): 플레이트(아머 플레이트 포함) 위에 닫힌 외곽선을 그리면 낮은 서페이스 트림. 그린 테두리 그대로, 안쪽은 평평한 판, 테두리를 따라 **1 / 2 / 3겹** 계단(프리셋 버튼 = 크기에 맞춘 넓이·높이, 이후 겹마다 **넓이 / 높이** 직접 조절), **Edge High**(테두리가 높음) / **Inside High**(안쪽이 높음, Inside Height), Base Thickness, **나사 0 / 1 / 2**(볼록한 모서리 쪽 트림 가운데에 둥근 홈, Size / Depth). 그린 메쉬에 붙어(부모) 같이 움직임. Apply / Remove.
- **Plate Detail 2**(하단 툴바 **Detail 2**): 외곽선 안이 표면에서 **자연스럽게 올라와** 평평한 윗면. **Height**, **Slope Width**(넓을수록 위가 좁아짐), **Slope** 모양(Smooth / Straight / Round Top / Soft Foot).
- 다음 디테일은 마지막에 고친 값을 크기 비율로 기억(큰 외곽선 = 큰 트림).
- **Screw Stamp**(하단 툴바 **Screw**): 클릭할 때마다 표면에 나사 머리(표면 방향에 맞춤, 그 메쉬에 붙음, 살짝 박힘). **Dome / Post / Socket / Cross**(사용자 그림). 선택한 나사 Size / Height / Hole Depth 실시간, Alt + 클릭 = 지우기, **Join Screws to Surface**.
- **Panel Cloth Tension / Gravity**(N 패널 › Cloth Plate › PANEL CLOTH, 구운 천을 선택하면): 값을 바꾸면 잠깐 뒤 자동으로 다시 구움(드래그 중에는 한 번만). Tension 1 = 프리셋, 높이면 팽팽(여유 천 줄고 뻣뻣), 낮추면 주름 많음. 다른 프리셋으로 다시 구우면 Gravity는 그 프리셋 값, Tension은 유지.
- 테스트: 67개 파일 2349/2349 (`tests/test_log_bpy501_v0240.txt`), 새 `test_v0240.py`(Plate Detail 23), `test_v0240b.py`(Screw 17), `test_v02328.py`(Panel Cloth 슬라이더 9). ZIP sha256 `d6fa728a865c38c3a7a8c1b8965faccb92fe5314c371d3aca70ba24024191f7c`.

## 0.23.27 — 공통 Lasso Settings 패널, Alt는 모든 도구에서 빨간 선 (2026-10-15)

- N 사이드바에 **Lasso Settings** 패널 하나를 따로 두고 **모든 도구**(Select 포함)에서 보이게 함: 모양별 설정(Free Draw 손떨림 보정 / 간격 / 스무스 / 단순화, 원 세그먼트, Curve Lasso 해상도, Line, 프리셋 모양, 바깥 모서리 둥글게 / 각지게, Cut 라쏘의 Edge Finish). 전에는 Cut / Split / Mask / Base Mesh / Box Hide 패널 안에만 있고 Armor Plate / Cloth Plate 등에는 없었음 → 각 도구 패널 안의 사본은 지움.
- 뷰포트 위 모양 버튼 줄(Lasso / Curve Lasso / Sketch / Line ...)도 모든 도구에서 눌림(전에는 라쏘 도구가 아니면 회색).
- Alt를 누르고 그릴 때(반대 동작) 선 색이 **모든 도구에서 빨간색**(전에는 Base Mesh만 빨강, Cut 하늘색, Armor / Cloth / Box Hide는 색이 안 바뀜).
- 테스트: 64개 파일 2270/2270 (`tests/test_log_bpy501_v02327.txt`), 새 `test_v02327.py`. ZIP sha256 `4a414b288d585b594f853e0b7e35f7f5484df0276ddf4bfa0d4d6b84cf8512ad`.

## 0.23.26 — Fold Patch: 팔꿈치 / 무릎 X·Y 주름 패치 (2026-10-15)

- N 사이드바에 따로 **Fold Patch** 패널(Cloth Plate 도구 / Select / 패치 핸들 선택 시). 메쉬 선택 + 3D 커서 → **+ Add Fold Patch**: 표면에 핸들(G / R / S로 이동·회전·크기) + 라이브 GN 모디파이어(Cloth Plate면 두께 Solidify 앞).
- 패치마다: Size, Depth(- = 안으로), Thickness, **Taper "<"**(한쪽으로 좁아짐, - = 반대), Fade(가장자리), **Wrap**(팔 / 다리 둘레 반지름 - 추가할 때 자동 측정), **Mirror X**, ◀ ▶ 패턴(감싸는 주름 / X·Y 주름 / 별, 각각 좌우 반전). 여러 개 배치, 목록에서 선택 / 삭제, Apply로 메쉬에 확정.
- 주름 선은 사용자가 그린 그림을 따라 만든 높이 이미지(패턴 / 두께가 바뀔 때만 다시 굽기, 파일 열 때 다시 만듦). Overall Scale과 무관.
- 비교 `reference/fold_patch_v02326.png`. 테스트: 63개 파일 2232/2232 (`tests/test_log_bpy501_v02326.txt`), 새 `test_v02326.py`. ZIP sha256 `e3ea3d9bb5298b6b806988eeeab6027f3bc9df0d1a9515dde75a6e8c37d4ed72`.

## 0.23.25 — Cloth Plate 팝업 버튼 복구 (2026-10-15)

- 0.23.23의 "빠진 슬라이더 손잡이 만들기" 수정이 팝업 **버튼(아이콘)이 안 보이게** 만들었음 → 팝업 코드를 0.23.22와 똑같이 되돌림. 0.23.24의 "슬라이더 글자 목록 없음"만 유지(버튼만 보임), Overall Scale은 N 사이드바 LIVE 상자에.
- 테스트: 62개 파일 2218/2218 (`tests/test_log_bpy501_v02325.txt`). ZIP sha256 `baa0c9a383320fda16771485a1a32ff206f3541edccdcd3ce67705111990c6cb`.

## 0.23.24 — Cloth Plate 팝업은 버튼만, N 사이드바는 고른 도구만 (2026-10-15)

- **Cloth Plate 팝업 밑 슬라이더 글자 목록 제거**(Overall Scale 포함): 팝업에는 Apply / Remove / 종류 / Trim / Creature Skin 버튼만. 값은 N 사이드바(LIVE 상자 맨 위 Overall Scale + 모든 값)에서.
- **N 사이드바는 고른 도구 것만**: 도구를 고르면 Mecha Lab 메인 패널(그 도구 설정)과 그 도구 전용 패널만(Base Mesh → Robot Base Mesh, Armor Plate → Creature Shell, Mesh Curve → Tube / Curve; Mirror / Radial / Surface는 원래 그랬음). Primitive Shapes, Detail Stamp, High Poly, Icon Size, Tools 목록, Workspace & Hotkeys는 **Select 상태에서만**.
- 테스트: 62개 파일 2218/2218 (`tests/test_log_bpy501_v02324.txt`), 새 `test_v02324.py`. ZIP sha256 `2478d031dfe78ad37a70bed8b54cd6198b3241635df0514e6ce98d3146b020b6`.

## 0.23.23 — Overall Scale 조정 안 되던 문제 (2026-10-15)

- 뷰포트 HUD의 Overall Scale 글자는 보이는데 드래그가 안 됨: HUD가 업데이트 전에 만들어져 있으면 새 슬라이더의 손잡이가 없었음 → HUD가 빠진 손잡이를 스스로 만듦.
- **N 사이드바에도 Overall Scale**: Cloth Plate 패널의 LIVE 상자 맨 위(입력 / 드래그 가능한 일반 필드). HUD 슬라이더와 같은 값.
- 테스트: 61개 파일 2207/2207 (`tests/test_log_bpy501_v02323.txt`), 새 `test_v02323.py`. ZIP sha256 `4f1008d348a16c1a8236fe3c0fe1f3dccd5e7aa76c6b9cc6dd261172fa4ec024`.

## 0.23.22 — Low Poly: 스컬핑(ZBrush) → 로봇 베이스 메쉬 (2026-10-15)

- Remesh / ZBrush Bridge 패널의 **LOW POLY**: 스컬핑을 선택하고 **Make Low Poly** → 사본이 Voxel Remesh(구멍 닫기, 고른 밀도) → 면 줄이기 → **면 평평하게 밀기**(비슷한 방향의 면을 한 덩어리로 묶고, 면적으로 가중한 주 노말 평면 위로 점을 밀기. 두 면이 만나는 점은 두 평면의 교선, 세 면은 교점으로 → 곧은 모서리) → **면마다 엔곤 하나**. 원본은 숨겨서 그대로 둠(Show Original).
- 실시간: **Bevel / Chamfer**(Width, Segments 1 = 챔퍼, Profile, 이 각도보다 날카로운 모서리만) + Weighted Normals. **Re-make**(Detail / Faces / Flatten Sides 각도 / Flat Merge), **Apply**.
- ZBrush FBX에 흔한 적용 안 된 배율(0.01)도 처리(Remesh 크기를 오브젝트 공간으로).
- 사용자 PM3D_Cube3D_1(6.8만 면) → 23면(엔곤 21), 닫힘, 약 1초. 비교 `reference/lowpoly_v02322.png`. 테스트: 60개 파일 2204/2204 (`tests/test_log_bpy501_v02322.txt`), 새 `test_v02322.py`. ZIP sha256 `dd59e6b0a7823258f0e14f74544371b1c1806d9454f99fa16f7789ebbbe39b24`.

## 0.23.21 — 도구 HUD는 그 도구에서만 (2026-10-15)

- Mirror 버튼처럼, 결과물 옆에 뜨는 버튼 / 슬라이더(HUD)가 **자기 도구를 고른 동안에만** 보임 - 다른 도구로 가면 숨김(결과물은 그대로, 다시 그 도구를 고르면 다시 보임).
  - Cloth Plate HUD → Cloth Plate, Armor Plate HUD / Random Panels / Creature Shell → Armor Plate, Mesh Curve 점 / 바 → Mesh Curve, Robot 파트 → Base Mesh. (Primitive / Station과 Mirror는 이미 그랬음.)
- 테스트: 59개 파일 2194/2194 (`tests/test_log_bpy501_v02321.txt`), 새 `test_v02321.py`(HUD poll이 실제로 도는지도 확인 - 처음에 Cloth Plate / Armor Plate / Robot 모듈에 import가 빠져 Blender에서 HUD가 오류 날 뻔한 것을 이 테스트로 발견해 고침). ZIP sha256 `57f7e2575a0aaa62473d5ba48b8bed04d7110bcf2b321ae9ecd6377c89afa755`.

## 0.23.20 — Overall Scale 실시간 (2026-10-15)

- Overall Scale을 드래그해도 화면이 바로 안 바뀌던 문제: 값은 바뀌었지만 다른 슬라이더처럼 뷰포트 다시 그리기 신호를 보내지 않았음 → 같은 새로고침 사용. 한 단계 약 0.4초(헤드리스, Fold Length 슬라이더와 같은 정도).
- 테스트: 58개 파일 2183/2183 (`tests/test_log_bpy501_v02320.txt`). ZIP sha256 `adcb019e14fbdbd4d251393c29b89fec6f501fa0fcb33b29c2fc47e1f4c7778f`.

## 0.23.19 — Cloth Plate Overall Scale (2026-10-15)

- 주름 모양은 그대로 두고, HUD 맨 위에 **Overall Scale** 슬라이더(100 % 기준, 10 ~ 400 %): 길이 값 전부(주름 간격 / 길이 / 깊이, Puff, Roll, Stitch, 패턴, Center Fade, 두께 등)를 한꺼번에 같은 비율로. **Trim은 제외**. 각도 / 날카로움 / Fan 같은 비율 값은 그대로. Reset이면 100 %로.
- 테스트: 58개 파일 2182/2182 (`tests/test_log_bpy501_v02319.txt`), 새 `test_v02319.py`. ZIP sha256 `bde23129b6fea46dba6fd79bdba9e9a438b263145dc5349c37be3e2824175660`.

## 0.23.18 — Base Mesh 베벨 / 챔퍼 폭, 미러 Apply 버튼은 Mirror에서만 (2026-10-15)

- **Base Mesh Bevel / Chamfer**: Width가 두께의 95 %로 몰래 잘리던 문제(6 cm 판에 Width 2 m → 5.7 cm, 큰 판에선 거의 안 보임). 이제 Width는 윗면(또는 아랫면)을 가로질러 들어가고, 내려가는 높이만 두께에 맞춤(얇은 판 = 넓고 완만한 챔퍼 / 라운드). 모양보다 넓으면 모양에 맞게 줄이고 LIVE 패널에 "width limited to …"로 표시. 
- **Mirror Apply / Remove 버튼**: Mirror(Symmetry) 도구와 Select에서만 보임 - Cut, Base Mesh 등에서는 숨김.
- (0.23.17 포함: Box Hide 빠르게 / Cut과 같은 대상 메뉴 / 주황 선)
- 테스트: 57개 파일 2176/2176 (`tests/test_log_bpy501_v02318.txt`), 새 `test_v02318.py`. ZIP sha256 `fd99be01744a2b71174a89970e024e15d9cc35105df475ba4664ff78400fb629`.

## 0.23.17 — Box Hide 빠르게, Cut과 같은 대상 메뉴, 주황 선 (2026-10-15)

- **속도**: 0.23.16은 Exact 불리언이라 10만 면 메쉬에서 한 번 계산에 46초 → **Manifold 솔버**(닫힌 메쉬, 0.26초) / **Float 솔버**(열린 메쉬, 약 0.9초)로 바꿈. Open도 같은 컷 후 막은 면만 지움(0.25초). 숨김 볼륨은 그릴 때마다 하나의 닫힌 덩어리로 합침(작아서 빠름).
- **대상 / 깊이 메뉴**: Cut과 같은 Through All / From Surface(+ 깊이), Auto Target / Selected Only / Active (Cut과 같은 설정을 공유).
- **선 색**: 그리는 선이 Cut처럼 주황(Alt도 주황).
- 테스트: 56개 파일 2158/2158 (`tests/test_log_bpy501_v02317.txt`), 새 `test_v02317.py`(10만 면 속도, Selected Only / Auto, 주황). ZIP sha256 `7e0ab8c89ab2c1a7d876e2a390614457577eb27c13d2b5be38a43c8b0e05ca09`.

## 0.23.16 — Box Hide (프로토타입에서 애드온으로) (2026-10-15)

- 새 도구 **Box Hide**(Split 옆): 공용 모양(사각형 / 라쏘 / 원 …)을 메쉬 위에 그리면 그 안이 숨겨짐. 그린 곳이 덮는 메쉬가 자동으로 대상.
  - **Alt + 그리기** = 그 부분 다시 보이기. 겹쳐 그리면 숨김이 합쳐짐.
  - **Cap / Open**: Cap = 잘린 곳을 면으로 막음(속이 찬 덩어리), Open = 뚫린 구멍. 메쉬마다, 나중에 바꿀 수 있음.
  - **Mirror X**: 메쉬의 로컬 X 반대편도 같이 숨김.
  - **Show All**(모두 다시 보이기) / **Apply**(숨긴 부분을 실제로 삭제해 확정).
  - 비파괴: 메쉬마다 Geometry Nodes 모디파이어 `MCH_BoxHide` + 숨겨진 볼륨 오브젝트(`MCH_BoxHide` 컬렉션). Apply 전까지 원래 메쉬 데이터는 그대로.
- 테스트: 55개 파일 2151/2151 (`tests/test_log_bpy501_v02316.txt`), 새 `test_v02316.py` 12항목. ZIP sha256 `a0e1deb11dddf65768c9996238e07ca8decb8b28847e074bae635f0e8e33fa02`.

## 0.23.15 — Cloth Plate / Panel Cloth를 0.23.9로 되돌림 (2026-10-15)

- 요청대로 **Cloth Plate**(`cloth_wrinkle.py`)와 **Panel Cloth 시뮬**(`cloth_sim.py`)을 0.23.9 코드로 되돌림. 0.23.10~0.23.13의 클로스 변경(Panel Cloth 슬라이더 / Draft·Detail / 뒤집힘 수정, Pinch 1·2 분리, Surface Detail, Fold In, Center Calm, V핀치, 막 Puff)은 빠짐. `cloth_sim.py`는 0.23.9와 똑같음.
- 남긴 것(클로스 모양과 무관): **Space로 외곽선 이동**(0.23.13), **지난번 값이 판 크기를 따름**(0.23.14 - 작은 판이 파편 덩어리로 터지던 원인; Crumple / Billow도 포함), 새 판의 길이 값을 슬라이더 범위 안으로 제한, **Billow 기본값 낮춤**(Drape 0.09 → 0.02, Cotton 0.012 → 0.005, Puffer 0.004 → 0.002).
- 테스트: 54개 파일 2129/2129 (`tests/test_log_bpy501_v02315.txt`). ZIP sha256 `a7a7cac6be32384cafdc42573e6012adf22c5a8606bf25bd790c740b052b6e11`.

## 0.23.14 — 작은 Cloth Plate가 파편 덩어리로 터지던 문제 (2026-10-15)

- **원인**: 새 Cloth Plate는 지난번 값(Last used)으로 시작하는데, 길이 값(주름 길이·간격, Puff, 두께 등)을 절대값으로 기억했음. 큰 판(예: 30배)에서 만진 값이 작은 판에 그대로 들어가 Fold Length 9 m, Puff 0.27 m가 0.34 m 판에 걸려 깨진 파편 덩어리가 됨. 사용자 FBX(cloth.fbx)로 똑같이 재현함.
- **수정**: 길이 값은 그 값을 만진 판의 크기와 함께 기억. 새 판이 0.5~2배 크기면 지난번과 똑같은 숫자, 그보다 크거나 작으면 크기 비율만큼 조정. 크기 없이 저장된 예전 길이 값은 버림(그 판은 프리셋 기본값으로 시작). 사용자 프리셋도 같은 방식(새로 저장하는 프리셋은 판 크기 포함, 예전 프리셋은 선택된 판에 그대로 적용).
- 비교 `reference/cloth_last_used_scale_v02314.png`(왼쪽 수정 전, 오른쪽 수정 후). 테스트: 57개 파일 2155/2155 (`tests/test_log_bpy501_v02314.txt`). ZIP sha256 `61f3abe51220749d0c33ceab7e2d181a0188986dce8fbccd571e380333b5501f`.

## 0.23.13 — 패딩 V핀치, 얇은 주름, X자 능선 제거, Space로 라쏘 이동 (2026-10-15)

- **패딩 핀치 = 날카로운 V 단면**: Fold In(패딩/퍼퍼)일 때 메인 주름이 가운데로 갈수록 뾰족하게 파고드는 V 모양(폭 절반, 지수 1.6). 부채꼴 잔주름도 Fold In에서 더 날카롭게.
- **주름 더 얇게**: 메인 주름 폭 ×0.75, 최소 폭 = 엣지 길이 1.5배, 블러 1회. Center Calm 기본값 90 %.
- **X자 능선 제거**: 볼륨(Puff)을 테두리 직선 거리 대신 막(membrane, 푸아송) 높이로 계산 - 모서리로 가는 대각선 능선 없이 둥근 돔.
- **Space**: 큰 툴 메뉴를 더 이상 열지 않음. 라쏘 등 모양을 그리는 중에 Space를 누른 채 마우스를 움직이면 지금까지 그린 외곽선 전체가 따라 움직임(놓으면 계속 그리기).
- 비교 `reference/cloth_padding_vpinch_v02313.png`. 테스트: 57개 파일 2148/2148 (`tests/test_log_bpy501_v02313.txt`). ZIP sha256 `9d4796a89b028d766f5d8444d703730f70693fadc7f454b6515e7e5808560d63`.

## 0.23.12 — Center Calm: 가운데는 평평하게, 주름은 테두리 쪽에 (2026-10-15)

- **Center Calm**(HUD 슬라이더, 기본 80 %): 주름(메인 + Surface Detail + 잔주름)이 판 가운데로 갈수록 사라짐. 테두리에서 가장 먼 거리 대비 20 % 지점부터 줄어들어 60 %에서 최대. 0 = 예전처럼 가운데까지, 100 % = 가운데 완전히 평평.
- 측정: Center Calm 1에서 가운데 높이 편차 0.028 → 0.0, 테두리 쪽 주름은 거의 그대로(0.035 → 0.033).
- 비교 `reference/cloth_center_calm_v02312.png`(위 0.23.11 / 아래 0.23.12). 테스트: 56개 파일 2112/2112 (`tests/test_log_bpy501_v02312.txt`). ZIP sha256 `19abf17cf9b7671f6d020caed29f3ad42ff5283990ec5ebf5b8d3c476dd64bf4`.

## 0.23.11 — 옷주름 정리: 0.23.2식 메인 주름 + Surface Detail, 패딩은 핀치(안으로) (2026-10-15)

- **원인**: 0.23.3 비대칭 단면이 완만한 쪽 폭을 1.9배, 계산 범위를 2.2배로 넓히고 접힘 홈을 넣어서 주름이 판 중앙까지 번짐.
- **메인 주름 = 0.23.2**: 테두리에서 들어오는 뚜렷한 둥근 주름(예전 단면 / 폭)으로 되돌림. Fold Asymmetry / Thinness는 이제 메인에 영향 없음.
- **Surface Detail**(새 슬라이더, 기본 0 = 꺼짐): 0.23.3 이후 비대칭 / 얇은 주름 레이어를 통째로 조절 → 표면 디테일로 위에 얹어서 사용.
- **패딩 = 핀치 / 옷 = 튀어나옴**: 새 입력 **Fold In**(HUD "Folds In (pinch)") - Padding / Puffer는 1(주름이 안으로 파고듦, 부푼 쿠션), 나머지 옷은 0(주름이 튀어나옴).
- **지저분한 것 정리**: 주름 높이를 세분 후 Blur로 다듬음(삼각형을 가로지르는 주름이 구슬처럼 끊기던 것), 최소 폭 1.3 → 2.2 엣지, 테두리 부채 주름 줄임(Fan Mix 0.6 → 0.3, Pinch 2 = Pinch 1의 절반).
- 비교 `reference/cloth_cleanup_v02311.png`(위 0.23.2 / 가운데 0.23.11 / 아래 0.23.11 + Surface Detail, 각각 Padding / Denim / Leather). 테스트: 55개 파일 2109/2109 (`tests/test_log_bpy501_v02311.txt`). ZIP sha256 `5c19278bbc55bb633a6edc6bbe51ed5f9a1a93efbd1655e776d8568a3dbd33ef`.

## 0.23.10 — Panel Cloth: 슬라이더(Puff / Gravity / …), 가볍게(Draft → Detail), 뒤집힘 수정 (2026-10-15)

- **슬라이더**(N 패널 › Cloth Plate › PANEL CLOTH): **Puff**(0 = 납작, 1 = 프리셋, 2 = 두 배 - 압력과 여유 천을 같이), **Gravity (sag)**(처짐 - 너무 처지면 낮추기), **Shrink (slack)**, **Pressure (puff)**, **Bend (stiffness)**, **Frames**. 프리셋을 고르면 값이 채워지고, 라쏘 직후 시뮬과 **Re-bake (sliders / Detail)** 버튼이 이 값을 씀.
  - 테스트로 확인: 부풀기는 Pressure만이 아니라 Shrink(여유 천)도 같이 만듦(Pressure 0이어도 Shrink -0.05면 볼록) → Puff 하나로 둘 다 줄이게 함.
- **덜 빵빵하게**: 패딩 계열 기본 압력 낮춤(Padding 9 → 6, Puffer 16 → 11, Pillow 7 → 5, Quilt 10 → 7).
- **가볍게(멈춤 방지)**: Sim을 켜면 판을 **큰 면**으로 만듦(**Sim Face Size** 기본 24px - 일반 Face Size 8px 대신) → 천과 충돌체 모두 가벼움. **Detail 1~4**(1 Draft ≈ 1500면, 품질 낮춤 / 4 ≈ 16000면): 처음엔 1로 뽑고 모양이 정해지면 Detail 올려서 Re-bake. 너무 촘촘한 원본은 Decimate로 줄임. 굽는 동안 진행 표시.
- **뒤집힘 수정**: 열린 판(큰 판 / 휜 판)에서 면 방향 재계산이 안쪽을 고르면 압력이 천을 몸 안쪽으로 밀어서 뒤집혀 보였음 → 원본 면의 바깥 방향(버텍스 노말)과 비교해 조각마다 맞춤.
- 테스트: 54개 파일 2101/2101 (`tests/test_log_bpy501_v02310.txt`). ZIP sha256 `99a8b15ffd1a3e5b204abbd9e945b1d6d43f3bf7f1ca4481f806a4756f6c6b84`.

## 0.23.9 — Panel Cloth: 라쏘 영역 충돌체, 라쏘 직후 시뮬, 프리셋 9개, 조각별 랜덤 (2026-10-15)

- **RandomFlow 방식 정리**(공식 문서 사이트는 이 환경에서 접속 불가 → 검색 결과 + 보내주신 화면 기준): 블렌더 내장 클로스 + Pressure / Shrink / Pin / 충돌을 짧게 굴리고 베이크, Mark Sharp / Seam으로 나뉜 조각마다 다른 값(Individual Seed, Random), Collide To Source, Remove Faces. 이 구조대로 맞춤.
- **충돌체 = 우리가 만든 면(Region, 기본)**: 라쏘로 생성된 면(패널 원래 표면)을 임시 충돌체로 만들어 시뮬 → 몸 전체보다 가볍고, 천이 그 면 밑으로 꺼지지 않음. Body(몸 전체) / None도 선택. 천은 표면에서 살짝 띄워 시작(겹친 채 시작하면 충돌이 불안정해서 천이 뚫림), 접촉 두께는 판 크기에 맞춰 자동.
- **라쏘 직후 시뮬**: Cloth Plate 헤더 **Sim** 토글 + 프리셋 → 라쏘를 끝내면 바로 시뮬 + 베이크(`_PCloth`), 원래 판은 숨김. Through(앞 + 뒤)도 하나로 합쳐서.
- **프리셋 9개**: 패딩 계열 **Padding**(0.23.8보다 진하게: Pressure 4 → 9) / **Puffer** / **Pillow** / **Quilt**(조각마다 따로 부풀기), 천 계열 **Cloth** / **Silk**(가는 주름 많이) / **Canvas**(큰 주름 몇 개) / **Leather**(뻣뻣) / **Crumple**(구겨진 천). Bend(휨 강성) 추가.
- **다른 프리셋으로 다시**: 만든 `_PCloth`를 선택 → 패널의 프리셋 버튼 → 숨겨 둔 원본에서 다시 시뮬(오브젝트는 하나로 교체).
- **Split Seam**(표시된 Seam / Sharp에서 나눔), **Random per piece**(조각마다 Shrink ~ Shrink Max, Pressure Variation), **Remove Faces**(Edit Mode에서 원본 면 삭제).
- 미리보기 `reference/panel_cloth_presets_v0239.png`(윗줄 Padding / Puffer / Pillow / Quilt / Cloth, 아랫줄 Silk / Canvas / Leather / Crumple). 테스트: 53개 파일 2089/2089 (`tests/test_log_bpy501_v0239.txt`). ZIP sha256 `d8bc94d28360811a49ee54ff09ac0f01cb78fcc6a639ec10766b288ca19d35b3`.

## 0.23.8 — Pinch 1 / Pinch 2, Panel Cloth(짧은 실제 클로스 시뮬 + 베이크) (2026-10-15)

- **Pinch 1 / Pinch 2**: 큰 주름(테두리에서 길게 들어오는 주름)과 작은 주름(부채꼴 잔주름)을 따로 조절. HUD 슬라이더 2개. 새 판은 Pinch 2 = Pinch 1로 시작해서 예전과 같은 모양.
- **Panel Cloth**(Cloth Plate 패널 버튼 / F3 "Panel Cloth"): 선택한 판(또는 Edit Mode에서 선택한 면)을 별도 `_PCloth` 오브젝트로 복사 → 세분(Subdivision) → 테두리 고정(Pin) → **블렌더 내장 클로스**로 몇 프레임 시뮬(Pressure = 부풀림, Shrink 음수 = 천이 커져서 주름, Gravity, Mass, Quality, Seed, Noise) → 마지막 프레임을 메쉬로 굳힘(베이크) + Subsurf. 그린 몸이 충돌체(Collide To Source, 임시 Collision 모디파이어는 끝나면 제거). Split: None / Angle(꺾인 곳에서 나눠서 칸마다 따로 부풀기). Pin: Border / Corners / None. Through 앞판 + 뒷판은 하나로 합쳐 솔기를 붙임(Join Panels) → 소매. 원본은 숨기기만 함.
  - 처음엔 지오메트리 노드로 직접 시뮬을 짜 봤는데(simulation zone, 위치 기반) 천이 고무처럼 늘어나기만 하고 주름이 잘 안 생겨서, 보내주신 RandomFlow 방식대로 블렌더 내장 클로스로 바꿈 - 판 하나 약 6초.
  - 너무 무거워지지 않게 시뮬 면 수 약 1만 5천 개 이하로 자동 조절.
- 미리보기 `reference/panel_cloth_v0238.png`(왼쪽 판 위 Panel Cloth, 오른쪽 Through 소매 → 하나의 링). 테스트: 52개 파일 2075/2075 (`tests/test_log_bpy501_v0238.txt`). ZIP sha256 `2121b1849032f253eaa58ee4e8536b6b416735c2b4ccd3a645af64a024c900f6`.

## 0.23.7 — Through(관통) 플레이트, 레퍼런스 옷주름: Puffer / Cotton / Drape (2026-10-15)

- **Through**(헤더 토글, Armor Plate / Cloth Plate): 앞에서 그린 라쏘가 메쉬를 관통해서 **뒷면까지** 같이 만들어짐. 화면 기준으로 라쏘 안에 들어오는 대상 메쉬의 면을 직접 잘라냄(앞뒤, 안쪽 레이어 모두). 영역은 **실루엣(앞/뒤가 바뀌는 곳)** 과 **급하게 꺾이는 곳(Crease, 기본 50°)** 에서 패널로 나뉘고, 패널마다 기존 플레이트/옷 파이프라인을 그대로 탐 → 팔에 띠를 그으면 앞판 + 뒷판이 옆선에서 만나는 소매/브레이서. Crease 180 = 실루엣에서만 나눔.
  - Armor Plate Through 판도 Face Size 실시간 변경(아웃라인 + 패널 번호 저장).
  - 제안해 주신 "급하게 꺾이는 곳 감지" = Crease 분할로 들어감(그 선이 솔기가 됨).
- **옷주름(레퍼런스 3장)**: 새 레이어 **Crumple** — 여러 방향으로 교차하는 가늘고 날카로운 구김(늘인 ridged 노이즈 4겹, 낮은 노이즈로 휘어짐) + **Billow** 큰 부드러운 굴곡. 가장자리는 표면에 붙어 있음.
  - 새 타입 **Puffer**(패딩 점퍼: 박음질 사이 둥근 채널 5칸, 가장자리 접힘 / 부채 주름 없음, 솔기 근처 잔주름), **Cotton**(구겨진 얇은 천: 가는 구김이 교차), **Drape**(무거운 천: 큰 굴곡 + 그 위 잔구김). Padding / Denim / Leather는 그대로(Crumple 0).
- 미리보기 `reference/through_plates_v0237.png`(왼쪽 Cloth Through - Drape, 오른쪽 Armor Through: 앞판 + 뒷판), `reference/cloth_types_v0237.png`(Padding / Puffer / Cotton / Drape). 테스트: 51개 파일 2059/2059 (`tests/test_log_bpy501_v0237.txt`). ZIP sha256 `f9a37f70be4f3ff7e19b44e7e39de3bdb9f80fcf030927c398053be246019886`.

## 0.23.6 — 레퍼런스대로 오가닉한 비늘: 악어 / 턱수염도마뱀 / 악어 등판 (2026-10-14)

- **Crocodile**(악어 옆구리 사진): 통통하게 부푼 둥근 비늘 + 좁고 깊은 홈, 큰 비늘이 모인 곳 사이를 작은 비늘이 채움, 비늘 위 미세한 오돌토돌 결. 예전엔 가운데가 뾰족한 피라미드 모양이었음.
- **Dragon**(턱수염도마뱀 사진): 작고 둥근 자갈 비늘 + 군데군데 솟은 뾰족한 가시(약 30 % 셀).
- **Croc Back**(악어 등 사진, 새 6번째 스킨): 줄지어 늘어선 사각 비늘판, 대부분 가운데에 솟은 용골(keel). Organic이 줄을 살짝 휘게 함. 줄 방향은 판의 로컬 X/Y.
- 둥근 비늘 모양: 셀 중심에서의 거리로 만든 반구 + 가장자리 좁은 홈. 가장자리 거리 / F1·F2 비율 방식은 비늘 가운데에 능선(주름)이 생겨서 버림.
- 미리보기 `reference/creature_skins_reference_v0236.png`(악어 / 도마뱀 / 악어 등). 테스트: 50개 파일 2040/2040 (`tests/test_log_bpy501_v0236.txt`). ZIP sha256 `33b9ca16680a13a214137287b000b6defd8868158563617a0027eafc631566e6`.

## 0.23.5 — 오가닉한 갑각 / 비늘 경계, 불규칙하게 작아지는 외곽 (2026-10-14)

- **Organic**(Creature Shell) / **Skin Organic**(Creature Skin): 셀 경계가 직선 대신 휘어진 선. 노이즈로 좌표를 셀 하나 크기만큼 휘게 해서 만듦. 0이면 예전 직선.
- **외곽 쪼개짐(Shell)**: 안쪽은 넓은 판, 바깥으로 갈수록 판이 3단계로 좁아짐. 기준은 판 옆면까지의 거리. **Edge Shrink**(강도), **Shrink Width**(폭), **Edge Irregular**(경계선이 들쭉날쭉). 안쪽 판은 Edge Shrink를 바꿔도 그대로인 것을 테스트로 확인.
- **Skin Irregular**(Skin): 비늘이 작아지는 경계선도 불규칙하게. 가장자리 마무리(피부 결)는 원래 경계를 그대로 따름.
- Shell 기본 Detail 5(작은 판을 표현하려면 해상도가 필요). 한계: 판 하나의 메쉬 해상도보다 작은 조각은 뭉개져 보임 → Detail을 올리거나 Shrink Width / Facet Size를 키우세요.
- 미리보기 `reference/creature_shell_organic_v0235.png`(왼쪽 예전, 가운데 새 기본, 오른쪽 Facets ↑), `reference/creature_skin_organic_v0235.png`(위 예전, 아래 새 기본: 고질라 / 코끼리 / 악어). 테스트: 49개 파일 2035/2035 (`tests/test_log_bpy501_v0235.txt`). ZIP sha256 `bc7f813a15d7d35a6b6c834bfcd84699dfa5cca97bc8ff1b60b7aee15bc3626b`.

## 0.23.4 — 주름 방향(위쪽이 가파름), Creature Skin, Creature Shell (2026-10-14)

- **주름 방향**(그려주신 방향대로): 서 있는 면에서는 각 주름의 **가파른 접힘 벽이 위쪽**, **완만한 긴 경사가 아래쪽**(월드 위 기준). **Fold Direction** 입력 Up(기본) / Down / Random. 면이 위를 향해 누워 있으면(월드 위가 패널 안에 거의 안 보이면) 예전처럼 랜덤.
- **Creature Skin**(하단 툴바 **Skin** = Cloth Plate + 크리처 레이어): 프리셋 **Crocodile**(둥근 비늘) / **Dragon**(뾰족 비늘) / **Godzilla**(넓적한 판 비늘) / **Toad**(두꺼비 오돌토돌) / **Elephant**(갈라진 코끼리 피부). 옷 기능(퍼프·솔기·스티치·트림)은 꺼지고, 가장자리 마무리가 **Skin Edge**(없음 / 피부 결 / 피부 주름 / 자갈)로 바뀜. **Edge Shrink**: 가장자리로 갈수록 비늘이 작아짐(폭 Shrink Width). 슬라이더 Skin Scale / Depth / Random, Gravity. HUD 버튼: 스킨 종류, 가장자리 마무리.
- **Creature Shell**(하단 툴바 **Shell** = Armor Plate + 갑각 레이어): 판마다 **딱딱한 갑각판**(셀마다 다른 기울기 + 사이 홈), **Bulge**(울룩불룩), **Lift N/E/S/W**(그 방향 가장자리가 몸에서 들림, 높이·폭), **Gravity**, 새 랜덤(Reroll), Add/Remove Shell. HUD는 판 왼쪽.
- 수정: Skin/Shell 버튼이 툴 전환 순서 때문에 크리처 레이어를 다시 끄던 문제(헤드리스 테스트에서 발견).
- IK는 0.23.3에서 이미 들어감(Mesh Curve 버튼 줄 **IK**).
- 미리보기 `reference/creature_skin_shell_v0234.png`(위: 악어 / 용 / 고질라 / 두꺼비 / 코끼리, 아래: 갑각 Lift S+E). 테스트: 48개 파일 2024/2024 (`tests/test_log_bpy501_v0234.txt`). ZIP sha256 `0bc194542d646eb45460b6dcb1b27fe835240bfc886af3fd6e82689e178ef46a`.

## 0.23.3 — 비대칭 옷주름, 더 얇은 주름, Mesh Curve IK (2026-10-14)

- **옷주름 단면 비대칭**(보내주신 그림 O): 주름마다 한쪽은 **가파르게 접힌 벽 + 아래 접힘 홈**, 반대쪽은 **길고 완만한 경사**. 어느 쪽이 접히는지는 주름마다 랜덤. **Fold Asymmetry** 슬라이더(0 = 예전 둥근 대칭, 기본 75 %).
- **Fold Thinness**: 주름 시작 부분과 전체 폭을 훨씬 얇게. 메쉬 해상도보다 얇아지면 구슬처럼 끊어지므로 해상도 한계에서 멈춤 — 더 얇게 하려면 N 패널 Spacing(면 크기)을 줄이세요. **Fold Sharp** 범위 30까지.
- **Mesh Curve IK**: 버튼 줄 **IK** / N 패널. 점을 끌면 마디 길이를 유지하며 사슬이 따라옴, **Pin Start**(첫 점 고정, 기본 켬) / 끄면 사슬 전체가 따라옴. 드래그 기즈모와 점 편집 모드 모두 적용.
- 미리보기 `reference/cloth_folds_asym_v0233.png`(왼쪽 대칭, 가운데 비대칭, 오른쪽 비대칭 + 얇게). 테스트: 47개 파일 1995/1995 (`tests/test_log_bpy501_v0233.txt`). ZIP sha256 `a4f865c0cc84c7151dfae8e731397b7c2ee08dc916b4122482e16f6d7511b8f1`.

## 0.23.2 — 미러 제스처, V 파이, 클로스 중력, Mesh Curve 교체 + 링크 어레이, 노마드식 기즈모 (2026-10-14)

- **미러 버튼**(왼쪽): Symmetry처럼 **마우스 기울이기 제스처**로 방향을 고르고, 결과는 **살아 있는 Mirror**(Enter/클릭 = 유지, 적용 안 함).
  Symmetry / Mirror 모두 **방향 표시가 화면 아래쪽 가운데**에 나오고 그 위치 기준으로 기울이기 → 오리진이 화면 밖(아래)이어도 보임.
- **도구 파이 = V**(Q = Select ↔ 마지막 도구는 그대로).
- **Cloth Plate Gravity** 슬라이더(팝업, N 패널): 주름·부푼 부분이 **아래(월드 -Z)로 처짐**, 테두리는 붙어 있음.
- **Mesh Curve = 새 커브 도구**(예전 Mesh Curve는 목록에서 숨김, 코드는 남김). 하단 툴바 이름 Curve.
  Repeat: **Linked Object**(내 오브젝트를 고르면 그 오브젝트를 고칠 때 커브도 같이 바뀜, 모디파이어 포함), **Spacing: Count / Distance**(간격 거리).
- **노마드식 기즈모**: 커브를 선택하면 언제든 **흰 점 드래그 = 이동**, **주황 점 드래그 = 그 점 굵기**(헤더에 Radius 표시).
  화면 아래 가운데 **버튼 줄**: Apply, 점 추가(Points), Tube/Repeat, Closed, Smooth/B-Spline/Linear, Profile, Cap, Count/Distance + 슬라이더 Radius, Twist, Rotate, Sides, Hole, Count / Spacing, Resolution.
- 미리보기 `reference/cloth_gravity_v0232.png`(왼쪽 Gravity 0, 오른쪽 Gravity 2.5). 테스트: 46개 파일 1983/1983 (`tests/test_log_bpy501_v0232.txt`). ZIP sha256 `abdbb6bf35336f396f825390793aea17e11df35405cf0878626e6ec74376b937`.

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
