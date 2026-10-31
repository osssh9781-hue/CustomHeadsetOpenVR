# CHANGELOG

## 0.24.95 — 엣지 기억(Edge Memory) · Bake High Poly(베이크용 하이폴리) (2026-10-30)

- **엣지 기억**(사용자: "우리가 자르는 오브젝트나 Box Hide Split 할 때 엣지 정보를 남겨 놓게 만들 수는 없나"): 자르기 계열 도구가 **만든 엣지**를 메시에 남깁니다(`edge_memory`: 엣지 속성 `mch_hard` + Sharp + 크리즈 1.0). 모든 자르기(Cut · Line Cut · Base Mesh 빼기 · Boolean · Plate Detail · 프리미티브 빼기)는 마지막에 `remove_cutter_attribute` 를 지나므로 그 자리에서 커터 면 플래그가 엣지 표시로 바뀝니다(커터 / 원본 경계 + 커터 면끼리 30° 넘게 꺾이는 선). 마무리(챔퍼 · 베벨) 없음이어도 남습니다(예전엔 마무리를 켰을 때만 Sharp 를 찍었음). **Box Hide Apply · Split Off** 는 볼륨 면에 커터 플래그를 실어 보내고 결과에서 표시를 받습니다(예전엔 아무 표시 없음).
- **표시를 읽는 곳**: Hard Edges Find Edges 는 기억된 엣지를 각도와 상관없이 하드로 넣습니다(2° 얕은 단차도 잡힘; 각도 검출은 그 밖의 영역만). Bake High Poly 가 고정선으로 씁니다. ZBrush 내보내기의 "Creases as Polygroups" 는 크리즈 1.0 을 읽으므로 그대로 폴리그룹이 됩니다(포켓 큐브: 5 영역).
- **Fast Decimate 가 기억된 엣지를 지킵니다**: C 엔진의 feat(테두리처럼 지키는 변)에 넘기고, 결과 메시에 다시 찍습니다(`hard_feat` · `transfer_segments`; 2,048 삼각형 포켓 큐브 → 10 %: 153 엣지 유지, 전부 포켓 윤곽 위). 메시지에 "N remembered edges kept".
- **리메시 뒤 되찾기**: 메시를 통째로 바꾸는 `swap_mesh`(Quad Remesh · Re-Fix · Hard Edges · 영역 컷 · 백그라운드 작업)와 복셀 리메시 네 곳(ZBrush DynaMesh · Mesh Tools DynaMesh · Re-Fix · Concept Move)에서 옛 표시 선에 가장 가까운 새 엣지(양 끝이 선에서 크기의 1.5 % 안, 방향 일치)에 표시를 옮깁니다(`transfer`). 복셀 격자라 100 % 는 아닙니다(포켓 큐브 DynaMesh: 96 → 20 엣지).
- **Bake High Poly**(회사: "리토포해서 베이크할 때 면이 각지면 보일 것 같다"): ZBrush 왼쪽 선반(Hard Edges 아래) 과 Mecha Lab 탭 Mesh Tools 의 새 버튼(`bake_highpoly`, 액션 BAKE_HP, 안전 저장 대상). 하드 엣지(엣지 기억 ∪ 각도 30° ∪ 테두리)는 **그대로 고정**, 그 사이 면은 중점 분할 N단계 + Taubin 스무딩(수축 없음; 선 위의 점은 선을 따라서만, 꺾이는 점(3선 이상 · 선 끝 · 25° 넘게 꺾임)은 고정, 원래 평평한 면의 점은 그 평면 안에서만). 설정(공용 `mch_zb`): **Target**(천 면, 기본 1000 → 단계 자동 `levels_for`), **Rounding**(100 = 완전 둥글게, 0 = 원본 모양 그대로 더 조밀, 사이 = 섞음), **Fillet %**(하드 엣지에 작은 둥근 베벨, 띠는 자유롭게 둥글어지고 되살리기 단계는 빼서 평면 밖으로 안 부풂). 결과는 `BakeHP` 컬렉션의 `<이름>_BakeHP`, 원본은 숨김(변경 없음). 사용자 부품 MCH_Base.009: 17,401 → 2,301,780 면(필렛 0.3 %), 48 s, 모서리 점 이동 0; 렌더 `dist/bake_highpoly_proto_MCH_Base009.png`(프로토타입) · `dist/bake_highpoly_addon_MCH_Base009_0.24.95.png`(애드온, 모서리 확대 포함). 원통 16각: 반지름 편차 0.0072 → 0.0006.
- 테스트: 새 test_v02495_edge_memory 24(표시 · 컷 · 2° 단차 Hard Edges · Box Hide Apply/Split · transfer · Decimate · DynaMesh · swap · ZBrush 영역), test_v02495_bake_highpoly 25(levels · hard_mask · taubin 격자/모서리/꺾임 · 큐브 · 원통 · 필렛 · 기억 선 · build · Mesh Tools · 오퍼레이터 · 선반), test_v02495 10(배선). 실제 창: `tests/gui/bake_highpoly_real_window_0.24.95.txt`(ZBrush 선반 BAKE_HP → Part_BakeHP 2,562 면, 원본 숨김, 포켓 윤곽 점 34개 x = ±0.5 · z = 1 그대로, 최대 |좌표| 1.0; Mesh Tools 경로 Cyl_BakeHP). 전체 테스트: 215개 파일 PASS 5,395 / FAIL 0(세 번째 실행이 최종; 두 번째는 cutquad 1 FAIL → 번짐 수정), 실제 창 13/13(이 zip). ZIP sha256 `f106531039e2766a6f639ea010dab9d17143520411c8763d08ed576dd178750b` (`mecha_lab-0.24.95_20261030-1441.zip`).
- **부품을 만드는 도구도 전부**(사용자: "내가 자르는 행위를 하는 모든 거는 다 남아야 돼 - 디테일 플레이트니 이런 거"): Armor Plate(모든 프로필 · Mech Ridge) · Plate Detail · Creature Plate · Scale Brush · Flower Plate · Mech Ridge · Surface Draw · Bridge Patch · Screw · Edge Molding · Face Extract · Base Mesh(새 솔리드 · 커터) · Surface Lasso 조각이 만들 때와 슬라이더로 다시 만들 때마다 자기 선(테두리 + 30° 넘는 꺾임, 깨끗한 생성 지오메트리라 정확)을 표시합니다(`edge_memory.mark_generated`). 라이브 Solidify 를 지나도 표시가 따라갑니다(평판 16 → 두께 준 뒤 32+). 손으로 만든 커터로 `boolean_result` 를 불러도 커터 플래그가 붙어(`flag_cutter`) 결과에 표시가 남습니다. 테스트 test_v02495_edge_memory_tools 28(도구 13개 + Solidify + 커터 플래그).
- 블렌더 자체 복셀 리메시(Preserve Attributes 기본 켜짐)는 엣지 속성을 새 메시의 거의 모든 엣지에 번지게 합니다(12엣지 큐브 → 20,172엣지 전부 표시; Decimate 가 아무것도 못 접음 - 전체 테스트에서 test_v02478_cutquad 로 발견). 그래서 표시를 쓸 때마다 도장(표시 수 · 엣지 수, 메시 속성 `mch_hard_n` / `mch_hard_e`)과 맞춰 보고, 엣지 수가 달라졌는데 표시가 3배 넘게 불어 절반 넘는 엣지에 붙어 있으면 번진 것으로 보고 버립니다(분할로 늘어난 표시는 그대로). 우리 DynaMesh 경로는 리메시 전에 표시를 떼어 두었다가(`remember`) 새 엣지에 다시 찍습니다(`restore`). 속성 이름은 내부용 `.mch_hard`. Decimate 는 조밀한 메시의 절반 넘는 엣지가 표시돼 있으면 표시를 안 믿습니다.
- **Bake High Poly 가 베벨 있는 부품을 일그러뜨리던 것**(사용자 스크린샷: 포켓 있는 블록의 모서리가 안으로 휘고 윗면 테두리가 부풀고 끝면이 둥글어짐): 원인 세 가지. (1) 모서리에 라이브 베벨(Hard Edges 베벨 · Bevel 모디파이어 2단)이 있으면 그 띠의 면들이 이웃과 정확히 30° 라 하드 선 판정 경계에 걸리고, 띠 옆 평면의 테두리 점들이 자유로워져 스무딩이 점을 **표면을 따라 끌고 가** 띠 속으로 밀어 넣었음(모서리가 휨). (2) 좁은 모서리 패치는 Taubin 의 되살리기 단계(|μ| > λ)가 고정선 사이에서 바깥으로 달아남(부풂). (3) Boolean 이 남긴 긴 슬리버 엣지가 하드 선이 되면 그 선 위의 점이 두 이웃의 **중점**으로 미끄러져 부품의 절반을 건너뜀(끝면 점이 x 1.0 → 1.06). 고침: 자유 점은 **자기 법선 방향으로만** 움직임(표면 위 드리프트 없음, `taubin(corners=)`); 평면 판정을 '코플래너 영역의 크기' 기준으로(`flag_flats`: 소프트 이웃 영역보다 3배 이상 크면 평면, 그 옆의 작은 영역(베벨 줄 · 모서리 패치 · 필렛 줄)은 띠) 바꾸고 평면과 띠가 만나는 테두리 점은 평면 안에서만 움직임; 띠의 점은 자기 평면들을 절대 넘지 못함(`clamp_strips`, 영역 id `.mch_bk_region` 이 분할을 따라감); Taubin 두 단계 크기를 같게(λ = |μ| = 0.5: 어떤 주파수도 증폭 안 됨); 선 위의 점은 두 이웃을 잇는 현(弦) 위의 **가장 가까운 자리**로(중점 아님); 각도 판정은 '엄격히 초과'(30.0° 베벨 줄은 소프트). 결과: 2단 베벨 큐브(폭 0.06)에서 평면의 점 578개가 x = ±1 그대로, 큐브 밖으로 나간 점 0, 모서리 띠 단면이 길이 방향으로 0.0008 안에서 같음; 포켓 6개 + 홈 + 베벨 블록(437 → 110,852 면, 4.5 s) 경계 상자가 원본과 같음(앞서는 x 가 1.096 까지 부풂). 렌더 `dist/bake_highpoly_bevel_block_0.24.95.png`. 원통 16각 둥글림은 유지(반지름 편차 0.0008).
- **Bake High Poly, 사용자 FBX(Base Mesh + 3단 베벨 + 포켓)에서 또 터짐**(사용자: "이런 건 잘 되는데 베벨이 문제인가 봐", "연속적인 각도가 나오면 베벨로 인지할 수 없나?"): 베벨 줄의 면이 길이 0.9 × 폭 0.005 라, (a) 이웃 평균이 줄의 먼 끝에 끌려 Taubin 쌍이 상쇄 못 하는 일정한 당김이 생겨 모서리 점이 단계마다 0.09 씩 기어가고, (b) 반복마다 다시 잰 법선이 점의 0.008 이동에 60° 돌아 줄의 긴 방향으로 기울어 한 단계에 0.5 달아남. 고침: 이웃을 **엣지 길이 역수로 가중**(가까운 점이 지배), 법선은 **단계 시작 때 한 번만** 측정, 그리고 사용자 제안대로 **베벨 인식**(`bevel_rows`): 양쪽 긴 변이 모두 2° ~ 70° 꺾인 가는 사각형(짧은 변 < 긴 변의 25 %)들이 긴 변을 공유하며 이어진 줄에서 총 꺾임이 100° 이하면 모델링한 베벨 → 그 줄의 변을 선으로 고정(단면 그대로); 100° 넘으면 곡면(16각 원통 · 반원 홈) → 둥글림. 그로우 단계는 다시 |μ| = 0.53(같게 하면 곡면이 1.2 % 줄어듦). 사용자 부품: 872 → 208,187 면, 경계 상자 원본과 동일, 최대 이동 0.001, 베벨 줄 변 128개 고정(렌더 `dist/bake_highpoly_user_part_0.24.95.png`). 테스트: Base Mesh BEVEL 3단 + 포켓 → 경계 상자 오차 0, 줄 16개 고정(test_v02495_bake_highpoly 28).
- **Cloth Drape · Wrinkle Lines: 천이 바닥을 뚫던 것**(사용자: "클로스 드레이프 바닥을 종종 뚫어" + 스크린샷: 주름 사이로 몸체의 평평한 바닥이 비침): 충돌체 격자가 몸체의 **점**만 담고 있었습니다(점마다 2칸 띠). 메카 부품처럼 큰 평면 한 장에 점이 네 귀퉁이뿐이면 그 사이가 격자의 구멍이라 천이 그대로 떨어졌습니다. 이제 몸체의 **면**도 샘플링합니다(`cloth_pbd.surface_samples`: 루프 삼각형 위에 2칸 간격의 무게중심 격자점 + 삼각형 법선, 60만 점 상한을 넘으면 간격을 넓힘; 천 영역을 가로지르는 큰 면은 귀퉁이가 멀어도 포함). 8점짜리 박스 위 드레이프: 전엔 벽을 뚫고 지나감, 지금은 모든 점이 면 바깥(y ≤ -0.25 + 0.3 %). 구처럼 조밀한 몸체는 샘플이 안 늘어 속도 그대로(1.8 s). Wrinkle Lines 의 프록시 충돌체도 같은 샘플링.
- **Gravity 마이너스**(사용자: "그래비티도 마이너스 값도 줘"): Cloth Drape -600 ~ 600, Wrinkle Lines -300 ~ 300. 0 아래면 천이 위로 뜹니다(테스트: -200 에서 자유 점들의 평균 높이 +0.198, +200 에서 -0.185).
- **Cloth Drape Padding · Trim**(사용자: "클로스 드레이프 좋네, 그 패딩도 넣어줘", "트림도 넣어줘"): **Padding** - 올가미 패치의 화면 좌표(`.mch_pad_uv`)에 퀼팅 선 격자(Square / **Diamond** 45°, Cell = 윤곽 크기의 %)를 깔고 선 위의 점을 몸체에 고정, 그 사이 칸은 Puff 압력으로 부풀림(Looseness 가 여분 천). Sew Copy 의 pillow 압력을 재사용. **Trim** - Keep 할 때 천의 열린 테두리를 따라 8각 파이핑 튜브를 별도 오브젝트 "Cloth Trim"(천의 자식)으로 만듦, 폭 = 윤곽 크기의 %. 패널에 Padding 토글 · 패턴 · Cell · Puff, Trim 토글 · Trim Width. 테스트 test_v02492_cloth_drape 35 → 89(스케치 4 · 잡아 끌기 9 · Surface 4 · Drape Mask 15 · 충돌 프록시 12 · quilt_lines 순수 · 핀 수 908 > 테두리 408 · 칸이 솔기보다 높음 · 트림 면 = 테두리 변 × 8 · 트림 점이 테두리 반지름 안). 렌더 `dist/cloth_drape_padding_trim_0.24.95.png`(구 위 다이아몬드 14 % · Puff 120 · Looseness 35 · Trim 2 %).
- Padding 패턴 **Whole**(사용자: "다이아몬드랑 네모 퀼팅 없는, 걍 내가 그린 칸 채로 부푸는 것도"): 솔기 없이 테두리만 잡고 그린 영역 전체가 쿠션 하나로 부풂(테스트: 핀 = 테두리 408개뿐, 가운데가 테두리보다 0.15 높음).
- Bake High Poly **사전 정리**(사용자 스크린샷: 베이크 뒤 평판 위에 검은 슬리버 줄): 베이크 전에 겹친 점 합치기(크기의 1e-6) · 면적 0 면 제거 · 떠 있는 점/변 제거 · 뒤집힌 면 법선 정렬(`preclean`). Boolean 이 남긴 자기 점을 따로 가진 슬리버(평판 위에 겹친 삼각형)가 베이크에서 따로 움직여 검게 비치던 경우가 이에 해당(합성 재현: 겹친 슬리버의 점 2개 합쳐짐 · 떠 있는 점 1 제거 · 큐브 밖으로 나간 점 0). 메시지에 "cleaned first: …". 길게 부채꼴로 쪼개진 평판(슬리버 삼각형 7개)은 수정 전에도 정상(윗면 법선 전부 +z)이라, 사용자 부품 파일이 있어야 확정.
- **Cloth Drape 스케치 모드**(사용자: "클로스 드레이프에는 스케치 모드가 없어?"): 다른 라쏘 도구와 같은 **Sketch** 버튼(뷰포트 헤더)이 Cloth Drape 에서도 켜집니다(`lasso_sketch.MODES` + CDRAPE). 켜면 그린 윤곽이 천이 되지 않고 스케치에 더해지고(Alt + 그리기 = 빼기, Backspace = 마지막 윤곽 취소, Esc = 스케치 지움), **Enter** 가 합쳐진 윤곽 하나로 천을 깝니다(이후 Space · Enter · Esc 는 그대로). 두 사각형을 겹쳐 그린 테스트: 한 장의 천이 두 모양을 다 덮음(x -0.4 ~ +0.8). 시뮬이 돌고 있는 동안(Space 뒤)의 Enter / Esc 는 시뮬 모달이 먼저 받으므로 천 남기기 / 버리기 그대로.
- **Cloth Drape 잡아 끌기**(사용자: "중간중간 메시에 들어갈 때가 있어서 내가 잡아서 뗄 수 있게, 재생하는 중에"): 드레이프 모달(Space 뒤) 동안 **천 위를 왼쪽 마우스로 누르고 끌면** 그 점과 주변(패치 간격 4배 안, 가운데 1 → 가장자리 0 의 부드러운 가중치)이 손을 따라옵니다(화면 평면, 누른 점의 깊이). 재생 중이면 매 제약 패스마다 그 자리에 붙잡아 두므로(`Cloth.hold`) 중력 · 충돌에도 손을 따라오고 이웃이 같이 당겨지며, 일시정지 상태면 바로 옮겨집니다. 놓으면 그 자리에 남고(속도 0), 고정된 테두리 점은 안 잡힙니다. 천에서 40 px 넘게 떨어진 클릭은 전처럼 도구에 넘어갑니다. 헤더에 "drag the cloth to pull it" / "holding N points". 테스트 10(선택 · 빈 클릭 · 테두리 제외 · 재생 중 8프레임 뒤 0.4 위 그대로 · 이웃 가중치 · 놓기 · 일시정지 즉시 이동 · Esc).
- **Cloth Drape Surface 모드**(사용자: "그냥 표면에 그리는 모드도 만들어 주라"): 헤더의 **Surface** 버튼이 Cloth Drape 에서도 켜집니다(`surface_lasso.MODES/PATCH_MODES` + CDRAPE). 켜면 Cut / Armor Plate 의 Surface 처럼 몸체 **표면에 점을 찍어**(회전 · 줌 사이에도 점은 메시에 붙어 있음) 윤곽을 만들고, 점 끌기로 옮기고, Enter 가 그 윤곽(그린 영역의 평균 법선에서 본 시점)으로 천을 깝니다. 구 위에 앞 · 옆 두 시점에서 5점을 찍은 테스트: 천이 구 표면 바로 위(r 0.99 ~ 1.1), 그린 쪽(앞-오른쪽)에 깔림. 테스트 4.
- **Offset · 실제 시작 모양 미리보기**(사용자: "마스크 영역을 몸보다 조금 크게 만드는 게 안정적이지 않나?"): Drape Mask · 망토 · 목 천에 **Offset**(천 크기의 %, 기본 2): 천을 몸에서 그만큼 띄워 시작하고 원래 길이도 띄운 모양 기준(몸보다 조금 큰 천, 몸을 조이지 않음); Gap + 칸 절반이 더 크면 그쪽(`start_lift`). Space 전 미리보기는 이제 **띄운 실제 시작 모양**(전에는 몸 표면에 붙은 모양이라 몸과 겹쳐 보였음 - 직전 렌더의 흰 얼룩), Offset 슬라이더는 다시 짜지 않고 바로 띄움(`show_start`). 세분화한 사람(21.4만 점) 어깨 · 등 마스크, Points 5,000 · Gravity 60 · 120프레임: Offset 0 → 시작 9.7 mm, 3 % → 21.3 mm, 둘 다 시작 · 10프레임 · 120프레임에 몸 안 점 0(이 장면은 원래도 안정적; 차이는 미리보기와 천의 여유) `dist/drape_mask_offset0_vs_3_0.24.95.png`. 테스트 3 추가(미리보기 거리 · 슬라이더 즉시 · Space 시작 = 화면).
- **라쏘 천에도 Offset · Cloth Detail 즉시 반영**(사용자: "라쏘로 뽑아서 붙일 수 있지? ... 그래 넣어줘"): 라쏘(Area) 천도 Drape Mask · 망토처럼 Space 전 미리보기가 **Offset 만큼 띄운 실제 시작 모양**이고(`build(offset_lift=True)`), Offset 슬라이더는 바로 띄우며, **Cloth Detail** 슬라이더를 움직이면 같은 라쏘 · 같은 뷰(고정해 둔 프로젝터)로 천을 바로 다시 짭니다(`rebuild_area`; 대기 중인 천은 숨기고 광선을 쏘므로 새 천은 몸 위에 깔림, Front + Back 도 그대로). 재생 중에는 건드리지 않고 Space / Restart 때 반영. Offset 슬라이더는 모드마다 따로 있던 것을 Gap 아래 하나로 합침. "Cloth Detail 은 다음 라쏘부터" 안내는 이제 내 메시 / 감싸기 모드에서만. 테스트 6 추가(띄운 미리보기 = 시작 모양 · Offset 8 % 즉시 · Detail 절반 → 다시 짜고 새 라쏘와 같은 점 수 · 몸 위 · Space 시작 · 재생 중 무시). 기존 "Lines as Tubes" 테스트는 앞 단계에서 남긴 천(이제 2 % 떠 있음) 위에 새 라쏘가 깔리던 것이라 남긴 천을 지우고 진행하도록 고침(새 라쏘가 남긴 천 위에 겹쳐 깔리는 건 정상 동작).
- **로컬 충돌 프록시 · Points 즉시 반영**(사용자: "마스크한 영역은 콜리전으로 로우 메시 뽑고 그 위에 시뮬용 천 뽑는 건가? 그게 더 이득이지 않나? 천 디테일 조정도"): 영역 천(라쏘 · Drape Mask · 망토 · 목 천)은 원래 천 주변만 충돌체로 쓰는데, 프록시는 **몸 전체**를 Proxy Faces 로 줄인 것이라 무거운 몸에서는 그 영역이 거칠었음 → `collider_proxy.local_proxy_mesh`: 천 둘레(천 크기의 40 % 여유) 안의 면만 잘라 예산을 그 영역에 다 씀("<이름>_proxy_local", 숨김 컬렉션, 몸 · 영역이 바뀔 때만 다시), 영역이 예산보다 가벼우면 프록시 없이 그대로. Drape This Mesh · Wrap · Sew Copy · 다른 메시(Targets)는 그대로 몸 전체 프록시. Drape Mask 의 **Points** 슬라이더는 천을 깐 뒤 Space 전에 움직이면 바로 다시 짜임(`rebuild_mask`), 시뮬 전에는 깨끗한 천을 보여 줌. 세분화한 사람 메시(21.4만 점) · 어깨와 등 윗부분 마스크 · 예산 2만 삼각형: 그 영역의 충돌체 점 5,675(몸 전체 프록시) → 10,092(로컬, 1.8배), Points 1,500 → 슬라이더 5,000 → 5,001점, Gravity 60 · 120프레임 15 s: `dist/drape_mask_local_proxy_points_0.24.95.png`. 새 테스트 test_v02495_cloth_local_proxy 7; test_v02492_cloth_drape 의 몸 프록시 검사를 로컬 동작에 맞춤.
- **Cloth Drape Panel + Tack Pins**(마블러스 디자이너의 압정; 사용자: "다각형으로 그은 플랜을 핀으로 천 하나 사람 하나 찍고, 반대도 천 하나 사람 하나 찍으면 그게 붙어서 시뮬, 핀도 여러 개"): Mode **Panel** - 다각형을 그으면 화면을 향한 **평평한 천 판**("Cloth Panel", Cloth Detail 간격)이 그 아래 몸 바로 앞에 생김(몸이 없으면 3D 커서 깊이). 직접 만든 평면도 됨. **Tack Pins** 버튼(모달): 천 위 점 클릭 → 몸 위 점 클릭 = 한 쌍, 원하는 만큼 반복(같은 천 점을 다시 찍으면 교체), Backspace 마지막 취소, Enter · 오른쪽 클릭 끝; 몸을 찍을 때는 앞의 천을 뚫고 그 뒤 몸을 찍음, 쌍마다 천 점(주황) · 몸 점(파랑) · 선을 그림. 핀은 천 오브젝트에 저장(`mch_tacks`), 지우기 버튼. **Drape This Mesh**: 몸을 따로 선택 안 해도 핀이 있는 몸을 씀, 테두리 고정 대신 핀이 붙잡음. 핀 점은 **걸어가는 고정점** - 매 단계 목표 쪽으로 조금씩, 바로 뒤의 충돌 처리가 밖으로 밀어 몸을 타고 돌아감, 나머지 천은 그 고정점에 매달려 늘어짐, 처음 25 % 프레임 동안 서서히 세짐; 핀에서 천을 따라 잰 거리로 **테더**. 처음 시도에서 배운 것: 핀 점을 목표로 곧장 당기면 어깨 속을 관통해 천 윗부분이 몸 안에 숨고, 한 번에 조금만 당기면 천 무게에 져서 흘러내리고, 고정점으로 바꿔도 몇 점만 잡으면 천 무게로 핀 옆 삼각형이 길게 늘어나 천 전체가 허리 아래로 떨어졌음(핀 4점만 위에 남음) → 테더로 해결. 사람 메시: 등 뒤 사다리꼴 판(6,189점) + 핀 4개(양 어깨 · 허리 양쪽), Gravity 100 · 120프레임 12 s, 핀 오차 최대 9 mm, 몸 안 42점(최대 1 mm): `dist/cloth_panel_tack4_0.24.95.png`(왼쪽 3장 드레이프 전, 오른쪽 3장 후). 새 테스트 test_v02495_cloth_tack 16.
- **Cloth Drape 망토(Cape) · 목 천(Neck Cloth)**(사용자: "점을 딱딱 찍어 엔터를 누르면 천이 생겨, 시뮬 돌리면 망토 … 원을 그려 엔터 … 길이 조절 슬라이더 … 망토랑 목도리 제네레이터", "당연히 찍은 만큼만 나와야지", "목 위에 얹어 놓는 천, 사이파이 식으로"): Cloth Drape 패널에 **Mode** - Area(기존) / **Cape** / **Neck Cloth**. **Cape**: 어깨 · 등을 가로지르는 선을 그리거나(Line 모드면 그은 경로 자체) Surface 를 켜고 점을 찍고 Enter → 그 선에 매달린 천("Cloth Cape", 선이 고정). 시작 모양은 찍은 선에서 **수직으로 내려 건 평평한 천**: 점은 몸에서 바깥으로만(옆으로는 절대 안) 밀려나고 아래로 가며 다시 안으로 들어오지 않아, 천이 **찍은 폭 그대로**(Flare 0 기본) 가장 튀어나온 곳(견갑골)에서 늘어짐. 처음 버전(몸 표면을 따라 미끄러지는 시작 모양)은 양 끝 기둥이 팔을 타고 퍼져 기둥 간격이 최대 1 m 로 벌어졌음(렌더 v5) → 지금 2.3 cm. **Neck Cloth**(사용자: "세로로 원기둥 지른 거처럼 생겨야 돼"): **Neck Style** - **Tube**(기본): 그린 원에서 위로 Length 만큼 세운 **세로 원기둥**, 둘레 방향마다 튜브 높이 전체에서 몸(턱 · 얼굴)이 가장 튀어나온 만큼 반지름을 잡아 모든 고리가 같은 단면(점마다 따로 밀면 얼굴 앞에서 구겨졌음), **Pin Top**(기본 켬) 이면 위아래 고리 고정 → Looseness 만큼 남는 천이 주름으로 모임, 끄면 튜브가 목 둘레로 흘러내려 어깨 위에 카울처럼 얹힘. **Bottom Size · Top Size**(목 반지름 대비 여유 %, -50 ~ 300, 기본 0; 사용자: "위 고리랑 아래 고리 사이즈를 다르게 슬라이더로"): 다르면 원뿔, 몸 안으로는 절대 안 줄어듦(높이마다 몸을 비키는 반지름이 하한). 가장 넓은 고리 기준으로 둘레 점 수를 늘려 칸이 고름(원뿔 위쪽 칸이 넓어 어깨가 천을 뚫던 것). (이전 이름 Tube Size: "핀탑 끄고, 튜브 크기 좀만 키우고" Pin Top 끔 · 30 · Gravity 60 `dist/neck_tube_pinoff_size30_g60_0.24.95.png`.) **모양 먼저, 시뮬은 나중에**(사용자: "원기둥 사이즈랑 위아래 고리를 먼저 정하고 그다음에 시뮬, 망토도"): 천을 깐 뒤 Space 전에는 Length · Flare · Neck Style · Pin Top · Bottom/Top Size 슬라이더가 움직이는 즉시 모양을 다시 만듦(`_hang_live_update` → `rebuild_hang`), 패널에 "set the shape with the sliders, then Space" 안내; 시뮬 전에는 시작 지터 없는 깨끗한 모양을 보여 줌. 원뿔(Bottom 30 · Top 100 · Pin Top 끔 · Gravity 60) 시뮬 전 / 120프레임: `dist/neck_cone_bottom30_top100_0.24.95.png`(3,339점, 5.2 s)(사람 메시 Length 8 % · Gravity 20 · 120프레임 `dist/neck_tube_len8_g20_frame120_0.24.95.png`, 1,029점, 1.8 s). **Ring**: 목 둘레에 원을 그리고 Enter → 목 높이의 **평평한 고리(도넛)** 천, 바깥 고리로 갈수록 점이 늘어 칸이 고름(최장 변 < 2.5 × 중앙값), 중력으로 어깨 위에 둥근 숄처럼 내려앉음(처음 버전: 목에서 수직 기둥 → 어깨 · 팔에 밀려 칸이 가로로 크게 벌어지고 팔이 천을 뚫음 → 고리 방식으로 바꿈). **Length**(몸 크기의 %, 기본 50) · **Flare**(망토만): 천을 깐 뒤 Space 전에 바꾸면 같은 선에서 다시 만듦(`rebuild_hang`, Cloth Detail · Gap 도). 한쪽 변만 매달린 천이 고무처럼 늘어나던 것(150프레임에 0.98 m 천이 2.4 m) → 솔버에 **long-range tether**(`cloth_pbd.tethers`: 고정점에서 천을 따라 잰 거리 × Looseness 이상 못 멀어짐, 망토 · 목 천에서 켬). 직선 획은 넓이가 0이라 라쏘의 표면 선택을 못 써서 점마다 레이로 가장 많이 맞은 메시를 몸으로(`line_from_screen`). 사람 메시(1.75 m) 렌더: 망토 상체 · Gravity 20 · 120프레임 `dist/cape_v9_upper_g20_frame120_0.24.95.png`(9,324점, 20 s), 목 천 Length 25 % · Gravity 20 · 120프레임 `dist/neck_cloth_g20_frame120_0.24.95.png`(15,812점, 54 s). 새 테스트 test_v02495_cloth_cape 28(Tube 5 · 슬라이더 즉시 반영 / 원뿔 4 포함).
- **충돌 프록시 · Collide With**(사용자: "충돌용 바디 별도의 저해상도 프록시 메쉬 생성 할 수 있어? 셀렉트 모드 전체 ... 모든 메쉬를 프록시화, 지금 만드는 천 제외"): Cloth Drape 패널에 **Collide With** - Body(지금처럼 몸체만) / **Targets**(공용 Targets 설정(T)을 따름: Auto = 보이는 모든 메시, Selected = 선택한 메시, Active = 몸체만). 지금 만드는 천과 그 자식(트림)은 항상 제외. **Proxy**(기본 켬) + **Faces**(기본 4만 삼각형): 예산보다 무거운 메시마다 저해상도 사본 "<이름>_proxy" 를 숨김 컬렉션 "MCH Cloth Proxies" 에 만들어(Fast Decimate, 모디파이어 결과 기준, 선택 · 렌더 안 됨) 그걸로 충돌; 원본이 바뀔 때(점 · 면 수, 좌표 합)만 다시 만들고 아니면 재사용. 눈 아이콘으로 와이어 표시. 가벼운 메시는 그대로 씀. 새 모듈 `collider_proxy`. 65만 점 몸체 Drape Mask: 10.2 s → 5.9 s(첫 실행, 프록시 생성 포함) → 2.7 s(재사용), 충돌 샘플 28.5만 → 8,600. 테스트 12(meshes_for: Body / Targets + Auto / Active · 천 제외 · Body 면 다른 메시는 충돌 격자에서 멂 · Targets 면 그 표면 거리 ~0 · 프록시 이름 · 숨김 · 약 5천 삼각형 · 몸체도 예산 넘으면 프록시, 가벼우면 그대로 · 두 번째 재사용 · 원본 바뀌면 다시 · Show · Proxy 끔 · 스냅샷 · clear).
- **Drape Mask**(사용자: "지브러시 탭에서 하는 것처럼 마스크 씌워서는 못해?"): 몸체에 **마스크**를 칠한 뒤(Sculpt Mode / ZBrush 탭 마스크 브러시 · Ctrl 드래그) **Drape Mask** 버튼 - 마스크된 면(꼭짓점 마스크 평균 ≥ 0.5)을 그대로 복사해 천으로 띄우고(`masked_faces` · `faces_mesh`, 몸체의 자식 "Cloth Drape"), 열린 테두리를 고정, 몸체가 충돌체. 시점이 필요 없으니 팔을 감싸는 영역처럼 한 방향에서 안 보이는 영역도 됩니다. 천은 **더 가볍고 고른 메시로 다시 짜서** 돌립니다(사용자: "마스크로 뽑은 면을 좀 더 낮은 면으로 바꾸고 그다음 클로스를 돌리는 게 낫겠는데"): **Points**(기본 0 = Cloth Detail 에서, 1.5 % → 약 3,500점) 만큼 — 테두리에 목표 간격마다 점을 잠그고 Fast Decimate 로 그 수까지 줄인 뒤, 새 `iso_remesh`(긴 변 쪼개기 · 짧은 변 합치기 · 변 뒤집기 · 표면 위 고르기, 5패스, 안쪽 점은 마스크 영역 위로 되돌림)로 삼각형을 고르게. 몸체 패치가 목표보다 가벼우면 그대로 씀. 구 윗부분 3.5만 점 패치: 1,000점 목표 → 1,001점 0.8 s, 3,500 → 3,482점 1.4 s, 10,000 → 9,867점 3.9 s, 변 길이 최대/중앙 1.5 ~ 1.7(그냥 데시메이트는 5.7 ~ 59), 최소/중앙 0.5. 처음 시도에서 배운 것: 데시메이트의 keep_borders 는 테두리 점을 전부 잠가 조밀한 테두리가 그대로 남고(2,747점 / 20 s), 안 잠그면 테두리가 3점까지 먹히며, even 모드는 조밀한 패치에서 목표 전에 멈춤(1,000 → 4,000점); 파이썬 합치기는 변마다 bmesh 연산을 부르면 한 패스 5 s 라 한 번의 weld 로 묶음. 몸체 BVH 대신 마스크 영역으로 투영(수백만 점 몸체를 파이썬 리스트로 BVH 만들면 몇 분). 65만 점 아이코 구 · 12.7만 점 마스크: Drape Mask 전체 10 s(충돌체 격자 2.8 s 는 라쏘와 같은 몫, 새 천 짜기 2.4 s) → 3,541점 천, 10프레임 0.9 s. 버튼은 Cloth Drape 패널(Drape This Mesh 아래)과 ZBrush 탭 Cloth 상자("Cloth Drape from the mask"); 누르면 Object Mode 로 나와 바로 드레이프가 시작됩니다(Space 일시정지 · Enter 남김 · Esc 지움, 잡아 끌기 가능). 전체가 마스크면(매달릴 테두리 없음) · 마스크 없음 · 닫힌 껍질이면 안내 메시지. 테스트 15(faces_mesh 큐브 2면 · 마스크 없음 · 구 윗부분 마스크 → 면 수 · 오브젝트 · 테두리 고정 · 15프레임 드레이프가 몸 밖 · Enter · Points 500 → 515점 · 표면 위 · 변 최대 < 2 × 중앙 · 최소 > 0.4 × · 드레이프 · Points 0 = Cloth Detail · 전체 마스크 거부 · 배선). build 의 테두리 고정: nb = 0 인 라쏘식 세션도 열린 변을 고정(전엔 아무 점도 안 잡힘).
- **Cloth Detail 안내**(사용자: "메쉬 디테일 수치 조정하게 해줘, 지금은 적용이 안 되는 듯" → "숫자가 작아야 디테일해지는구나"): 슬라이더 이름을 **Cloth Detail (less = finer)** 로 바꾸고, 천이 깔린 뒤에 값을 바꾸면 패널에 "다음 라쏘부터 적용(이 천은 메시 그대로)" 안내가 뜹니다(세션이 라쏘 때의 값을 기억). 잔주름의 세밀함은 이 값(패치 간격) 과 Wrinkles · Looseness 가 같이 정합니다.
- **거친 곡면 위의 Cloth Drape**(사용자: "이건 곡선이라 이렇게 붙는 거야?" + 스크린샷: 천에 동심원 자국, 몸체의 면 능선이 비침): 몸체가 큰 삼각형으로 된 곡면이면 충돌체가 그 **facet** 그대로라 천이 각진 면과 능선을 따라 붙었습니다. 이제 면 샘플을 **Phong 패치**(세 꼭짓점의 접평면에 투영해 섞음, 0.75)로 곡면 위에 올리고 법선도 꼭짓점 법선을 섞어 씁니다(꼭짓점 법선이 면과 35° 넘게 다른 박스 모서리는 면 법선 그대로: 평면은 평면). 320면 ico 돔: 전엔 천의 최소 반지름 0.935(facet 위) · 능선이 천을 뚫고 보임, 지금은 0.962 · 편차 0.0355 → 0.0256, 능선 안 보임(렌더 `dist/cloth_drape_coarse_dome_phong_0.24.95.png` 왼쪽 전 / 오른쪽 후). 그래도 몸체가 아주 거칠면 자국이 남으니 드레이프 전에 Bake High Poly / Remesh 로 몸체를 조밀하게 하는 게 가장 깨끗함.
- **우클릭 메뉴**(사용자: "우클릭 팝업에 메뉴 넣어 놨어?", "우클릭 패널에는 왜 안 넣어 줘"): Mecha Lab 이 직접 그리는 우클릭 패널(Mecha Menu)의 Resolution 칸에 **Bake HP**(새 글리프: 테두리 안 촘촘한 격자), ZBrush 화면의 우클릭 팝업 맨 아래에 DynaMesh · Decimate · Bake High Poly 줄, 사이드바 Actions 팝업 Resolution 에 Bake High Poly 버튼, 블렌더 기본 오브젝트 우클릭 메뉴에 Make High Poly 옆 Bake High Poly. (ZIP 1441 의 전체 테스트 뒤에 더한 메뉴 세 줄: test_v02495 14/14 로 확인, 전체 재실행은 안 함.)
- 아직 안 한 것: Fold Patch(지오메트리 노드 결과)와 Hollow/Shell 은 표시하지 않음(적용하면 각도로 잡힘). 끊긴 하드 선 메우기 없음.

## 0.24.94 — Safe DynaMesh · 크리즈 → ZBrush 폴리그룹 · 천에 주름이 생김: 넓은 굽힘 + Wrinkles 슬라이더 (2026-10-30)

- **크리즈를 ZBrush 로**(사용자: "우리 블렌더 파일에 크리즈가 잡혀 있잖아 그 값을 ZBrush 에 못 불러와?", "난 FBX 로 내보내"): ZBrush 의 FBX ExportImport 플러그인과 OBJ 가져오기는 **크리즈 값을 읽지 않습니다**(Maxon 문서: 지원 항목은 폴리그룹뿐; 폴리그룹은 FBX 에서 **머티리얼**로 — "Import Mats as Polygroups"). 그래서 내보낼 때 **Creases as Polygroups**(기본 켜짐, 보내기 · Export 둘 다): 크리즈(≥ 0.5) 또는 Sharp 로 표시된 엣지를 경계로 면을 영역으로 나누고(`zbrush_bridge.crease_regions`, 면 그래프 flood fill) 영역마다 임시 머티리얼 PG_001 … (ZBrush 폴리그룹처럼 색 하나씩)을 **내보내기 복사본**에 붙입니다(`crease_materials`; 원본 메시는 그대로, 임시 머티리얼은 끝나면 삭제). FBX 는 머티리얼이 그대로 실리고, OBJ 는 `usemtl` + 머티리얼 그룹(`g`)으로. **ZBrush 에서**: FBX 가져오기 옵션 "Mats as Polygroups" 켜고 가져온 뒤 **Tool > Geometry > Crease > CreasePG** 를 누르면 폴리그룹 경계 = Blender 의 크리즈 선이 그대로 크리즈가 됩니다(Blender 크리즈는 0 ~ 1 값, ZBrush 는 있음 / 없음이라 0.5 이상만). 첫 시도(OBJ 정점 그룹 `g`)는 Blender 내보내기가 면의 다수 그룹을 고를 때 모서리를 공유하는 면이 동률이라 한 그룹으로 뭉쳐 버림 → 머티리얼로. Hard Edges 가 만든 크리즈 · Sharp 가 그대로 넘어갑니다.

- **Safe DynaMesh**(사용자: "ZBrush 에서는 DynaMesh 가 되는데 Blender ZBrush 탭에서 DynaMesh 하면 메시가 뚫리면서 파편화"): ZBrush 는 어떤 메시든 먼저 닫힌 부피로 만들지만 Blender 복셀 리메시(OpenVDB)는 닫힌 부피를 요구합니다 — **열린 가장자리**(시트 · 구멍 · 뽑은 판)는 부피가 새어 구멍 / 빈 결과, **뒤집힌 면**(일관되지 않은 와인딩)은 그 자리가 안팎이 바뀌어 구멍, **비매니폴드 · 떨어진 조각**은 파편으로 남습니다. 이제 DynaMesh 마다 `dynamesh_fix.prepare` 가 먼저 돕니다: 겹친 점 합치기, 법선 일관화(`recalc_face_normals`), **모든 경계 루프 덮기**(덮개 면적이 메시 면적의 절반을 넘으면 시트의 바깥 윤곽이므로 덮지 않음), 그래도 열려 있으면(시트) **복셀 3개 두께로 Solidify**, 떨어진 점 · 선 제거; 리메시 뒤 `cleanup` 이 메시의 2 % 미만인 떨어진 조각(가장 큰 조각의 절반 미만일 때만)을 버립니다. 메시지에 한 일이 붙습니다("safe: 1 hole filled, 48 flipped edges fixed, 1 sliver dropped"). 잰 것: 열린 20×20 격자 → 닫힌 한 덩어리(예전엔 빈 결과), 윗부분을 잘라 낸 구 → 구멍 메워진 구, 절반 뒤집힌 구 → 멀쩡한 구, 구 + 작은 사면체 → 사면체 버려짐. 얇은 벽 보정(`cap_voxel`, 가장 얇은 벽의 1/3 로 복셀 제한)은 재 보니 Blender 리메시가 0.02 벽을 0.12 복셀에서도 멀쩡히 유지해 기본 꺼짐(점만 늘림). DynaMesh 는 이제 항상 오브젝트 모드에서 돌고 스컬프트로 돌아옴(`_mode` 가 되돌리기 단계를 남김).

사용자: "너가 만든 거 너무 주름이 안 생기는 거 아니여?" — 맞았습니다. 잰 결과 두 가지였습니다.

- 솔버가 제약 패스마다 천을 이웃 평균 쪽으로 펴는 **스무딩**(Cotton 0.5)을 걸어 잔주름을 전부 지웠고, 그걸 빼면 주름 대신 **셀 크기의 노이즈**(구겨진 알루미늄 호일)만 남았습니다. 주름의 폭은 "굽힘이 얼마나 멀리까지 버티느냐"가 정하는데, 이웃 한 칸 건너(2링)까지만 버텨 몇 칸 폭의 접힘이 만들어질 수 없었습니다.
- **넓은 굽힘**(`cloth_pbd.Cloth.set_far` · `ring_pairs`): 2 · 3 · 4칸 떨어진 점끼리도 쉬는 거리를 지키는 제약(세기 1 / 0.8 / 0.6)을 패스마다 걸어 셀 노이즈는 눌리고 몇 칸 폭의 접힘이 살아납니다. 쌍은 점마다 엣지 그래프 BFS 로(6.7천 점 0.13초, 2.5만 점 0.5초), 쉬는 거리는 Looseness 배율의 평균으로. 제약이 3배라 시간이 늘었습니다(2.5만 점 소매 30프레임 8 → 21초; C 로 옮길 후보).
- **Wrinkles 슬라이더**(Wrinkle Lines · Cloth Drape, 기본 **50**): `wrinkle_params` — 100 = 굽힘 0.5 · 스무딩 0.1 · 넓은 굽힘 전부 · 시작 지터 엣지의 0.3(조밀한 주름), 0 = 예전 솔버 그대로(원단의 굽힘 · 스무딩, 넓은 굽힘 없음). 팔 실험에서 넓은 굽힘이 켜진 채 스무딩 0.1 = 조밀, 0.3 ~ 0.4 = 조금 부드럽게, 0.5 + 넓은 굽힘 없음 = 예전의 매끈한 모습이라, 스무딩은 슬라이더 제곱으로 0.5 → 0.1(70 = 0.3, 50 = 0.4), 넓은 굽힘 세기는 슬라이더 그대로. 사용자가 2번(100) → "좀만 줄이면" 70 → "한 30 % 줄여봐" 50 으로 정함: `dist/wrinkle_lines_wrinkles50_0.24.94.png`(50 · 와이어 · 70), `dist/wrinkle_lines_smoothing_steps_0.24.94.png`(스무딩 0.1 / 0.2 / 0.3 / 0.4 / 예전). 조끼(Front + Back)는 윗변에 매달려 팽팽해 여분 천이 없으므로 여전히 매끈 — 주름을 원하면 헐렁함을 올리고 중력을 내리거나 Wrap Pressure 로 누르면 됨. Sew Copy 에서 압력 150 · 헐렁 40 이면 정맥처럼 갈라진 눌린 주름.
- 봉제 틈: 넓은 굽힘이 옆선을 조금 열어 둠(구 테스트 1 → 7 cm, 허용 10 cm 로).
- 테스트: Blender 5.2.3 bpy 전체 210개 파일 PASS 5,303 / FAIL 0(`tests/test_log_bpy523_v02494.txt`; Traceback 27개 = test_registration_recovery 26 + test_v02494_crease_groups 1 — 그 파일은 마지막 검사 직전에 테스트 쪽 버그(지운 오브젝트가 view_layer.objects 에 None 으로 남음)로 멈춤, 6/10 까지 PASS; 고친 뒤 단독 실행 10/10 PASS(MAX_REGIONS 검사 포함) — 전체 재실행은 아직 안 함). 새 테스트 test_v02494_dynamesh 14(시트 · 구멍 · 뒤집힘 · 얇은 벽 측정 · 조각 · 메시지), test_v02494_crease_groups 10(영역 나누기 · Sharp · 머티리얼 · FBX 에 PG_ 머티리얼 · OBJ usemtl / g · 끄면 없음 · 임시 머티리얼 정리 · 영역 400 초과(30×30 격자 전부 크리즈 = 900)면 머티리얼 없이 메시지 안내), test_v02492_wrinkle_lines 42 → 46(wrinkle_params 매핑 · 기본 50 · 5×5 격자의 2링 쌍 · Wrinkles 100 이 0 보다 접힘 2배 이상 · 몸 밖), test_v02494 버전. 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.94.txt`, zip 0918 로 실행; 최종 zip 0941 은 거기에 MAX_REGIONS 400 상한만 더한 것 — 창 테스트 재실행은 안 함). ZIP sha256 `de5c2cbe2728643e95323d4d9664a72c2611e470f46642d76f64c52bb9169da8` (`mecha_lab-0.24.94_20261030-0941.zip`).

## 0.24.93 — Paint Lab(세 번째 화면) · 앞판 + 뒷판 봉제 · Sew Copy · Stop at Pins · 실제 창 클로스 브러시 · 패딩 (2026-10-30)

- **Paint Lab**(사용자: "페인트 랩도 만들어주라 따로"): MECHA LAB 탭의 **세 번째 화면**(오른쪽 위 카드 MECHA | ZBRUSH | **PAINT**; 스컬프트 모드 + 페인트 플래그, ZBrush 화면의 키 · 탐색 · 팝업 · 서브툴 선택은 그대로, 색은 **청록**). 들어가면 메시에 컬러 속성이 없으면 만들고(흰색), Paint 브러시를 잡고, **Paint 보기**를 켭니다.
  - **브러시 선반**: Paint · PaintSoft · PaintSquare · PaintBlend · Smear · Blur(Blender Essentials 의 색 브러시; B 키 글자 PA PF PQ PD SR BU, 아이콘은 Essentials 미리보기) + MaskPen · Smooth · Standard · Polygroupit. ZBrush 탭의 알파 · 텍스처 · 스트로크 · 머티리얼 선반(오른쪽 B 선반)이 그대로 쓰이므로 내 알파 · 텍스처 폴더도 그대로.
  - **사진 → 스텐실 / 브러시 텍스처**(`paint_lab.py`): Load Photo 로 가져온 사진이 **Hue · Saturation · Contrast · Brightness · Flip · Rotation** 슬라이더로 보정되어(순수 numpy, 색상 회전은 YIQ 행렬 한 번 — 2k 사진 1초 안; 슬라이더를 끄는 동안은 0.15초 뒤 한 번만 다시 굽기) 브러시 텍스처가 됩니다. **Q** = 스텐실 켜고 끄기(켜면 사진이 화면 위에 떠서 그 모양대로 칠해지고, **오른쪽 드래그로 옮기고 Shift: 크기, Ctrl: 회전**; 끄면 같은 사진이 보통 브러시 텍스처(뷰 평면)로). Essentials 브러시는 **링크된 텍스처만** 받으므로(알파와 같은 이유) 보정된 사진은 애드온 폴더의 PNG 로 써서 작은 .blend 에서 링크한 텍스처의 이미지로 다시 읽습니다(`stencil_texture`).
  - **스포이드**(사용자: "화면에 보이는 색 말고 폴리페인트로 칠한 색 기준으로"): **Alt + 모델 클릭** = 마우스 아래 면의 가장 가까운 점 / 코너의 **컬러 속성 값**을 그대로 브러시 색으로(조명 · 그림자 무관). Alt + 다른 메시 클릭은 ZBrush 탭처럼 그 메시 선택.
  - **마스크**: **By Brightness**(폴리페인트 밝기 Rec.601, Black ~ White 범위의 직선 램프, Invert — ZBrush Mask By Intensity), **By Edges**(점을 지나는 가장 날카로운 접힘 각도 ≥ Edge Angle 이면 1, Soft 만큼 아래에서 서서히 0, Grow 로 띠 넓힘 — 순수 numpy `paint_lab_core.edge_angles`), **By Cavity**(Blender 의 cavity 마스크, 세기 · 블러), Invert · Clear. 마스크는 `.sculpt_mask` 속성에 직접 쓰고 모드를 한 번 왕복해 보이게 함.
  - **보기(Look)** — 색이 그대로 읽히는 세팅을 5.2 색 관리에서 확인해 넣음: **Paint**(기본) = Solid, Blender 의 페인팅용 스튜디오 라이트 `paint.sl`(부드러운 키, 색 없는 필, 약한 스펙큘러), 색 = 컬러 속성, 스펙큘러 · 캐비티 · 그림자 · 외곽선 끔, 뷰 변환 **Standard**(AgX / Filmic 은 밝은 색을 눌러 탁하게 보임 — 순빨강 폴리페인트가 벽돌색으로). **Exact** = 위와 같되 Flat(픽셀 = 칠한 값). **Material** = Material Preview + Blender 내장 중성 스튜디오 HDRI `studio.exr`(색 쏠림 없음, 배경 불투명도 0) + 컬러 속성을 Base Color 로 쓰는 Principled(거칠기 0.6, 스펙큘러 0.3) + 뷰 변환 **Khronos PBR Neutral**(제품 색 재현용 변환). 노출 0 · 감마 1 · Look None.
  - 실제 블렌더 창(`tests/gui/paint_lab_real_window.py`, 로그 `tests/gui/paint_lab_real_window_0.24.93.txt`): PAINT 전환(스컬프트 · Paint 브러시 · paint.sl · Standard) → 줄무늬 사진 로드(링크 텍스처) → Hue 120 으로 빨강 줄이 초록 → **진짜 Q 키** 로 스텐실 켜짐(STENCIL 매핑, 화면 가운데 623×312) · 다시 꺼짐 → **진짜 마우스 드래그** 로 65 점이 빨강으로 칠해짐 → **Alt + 클릭** 으로 브러시 색이 그 빨강(1, 0.1, 0.1)으로 → By Brightness 마스크. 렌더 `dist/paint_lab_real_window_0.24.93.png`.
- **Cloth Drape Front + Back**(마블러스의 앞판 · 뒷판 패턴처럼): 라쏘 하나로 몸의 **앞면과 뒷면(같은 시선의 반대쪽)** 에 같은 조각을 두 장 깔고, 외곽선 중 **위아래로 달리는 구간(옆선)을 봉제**, 위쪽 · 아래쪽 변은 열어 둡니다(`patch_two_sides` · `rim_classes`). 봉제는 두 점을 잇는 직선이 몸을 관통하므로 **몸을 따라 미끄러지는 당김**으로 — 콜리전 격자의 안쪽 방향 성분을 빼고 옆으로 걸어가 만나게(`seam_pull`, 제약 패스마다, 한 패스 이동은 천 스텝의 절반까지 — 처음 버전은 제약으로 바로 당겨 점이 몸 안으로 뚫고 들어갔음(구 r 0.33), 그 다음 힘으로만 주니 60프레임에 1.7 → 1.2 밖에 안 닫혀 패스마다로 옮김). 처음 30 % 프레임 동안 세기를 올림. Pin Rim 은 이 모드에서 **윗변만**(봉제선 옆 2점은 제외 — 아니면 모서리에 V 홈). Enter 가 봉제 쌍을 한 점으로 합침(`weld_seams`). 조각 폭이 옆선까지 못 미치면(라쏘가 좁으면) 마블러스처럼 봉제가 다 못 닫힘: 구(r 1) 에 폭 0.45 라쏘 → 틈 0.79, 폭 0.85 → 0.01. 원통 몸통(6.4천 점, 60프레임 4.6초, 봉제 258쌍, 틈 평균 0.9 cm): `dist/cloth_drape_front_back_0.24.93.png`.
- **Sew Copy**(사용자가 뜻한 봉제: "플레이트처럼 한 면을 뽑았어? 그 메시랑 똑같은 면을 복사해 … 각 변들을 꿰매 … 처음 뽑은 면은 콜리전이 되고 그 이후에 생성된 천이 시뮬"): Cloth Drape 패널의 **Sew Copy** 버튼 — 활성 판(뽑아 둔 한 장)을 복사해 "Cloth Sew" 오브젝트로, 복사본의 가장자리 점을 판의 가장자리 점에 그대로 꿰매고(같은 변 ↔ 같은 변, 고정), **콜리전은 그 판 하나**(가벼움), 복사본만 시뮬. **Puff**(판에서 떨어지는 압력: 베개 · 패딩, 부푸는 높이는 Looseness 양에서 멈춤 — 처음엔 끝없이 부풀어 풍선이 됨) · Looseness · Gravity · **Wrap Pressure**(판 쪽으로 눌러 여분 천이 주름으로). 구에서 뽑은 조각: Puff 50 · 헐렁 15 · 중력 20 이면 패딩, 헐렁 25 · 중력 100 이면 처진 주머니. 아직 사용자 확인 중(주름 설정).
- **Stop at Pins**(Wrinkle Lines · Cloth Drape, 기본 꺼짐): 천의 어떤 점도 **가장 낮은 고정 점보다 아래(월드 아래)** 로 못 내려감(`cloth_pbd.Cloth.floor`, 프레임 끝마다 클램프, 엣지 길이의 절반만 여유). ㄴ자 원통에서 발끝 고리 아래로 처지던 천이 사라지고 그 천이 옆으로 밀려 팔꿈치 주름이 더 뭉침: `dist/wrinkle_lines_stop_at_pins_0.24.93.png`(끔 / 켬 / 와이어).
- **실제 블렌더 창의 클로스 브러시 · 패딩**(`tests/gui/zb_cloth_real_window.py`, 로그 `tests/gui/zb_cloth_real_window_0.24.93.txt`): ZBrush 화면에서 선반 연산자로 ClothDrag 를 고르고 **진짜 마우스 드래그** → 475 점 이동(최대 4.2 cm; 파이썬 `sculpt.brush_stroke` 는 클로스 브러시에 0 — 실제 이벤트가 필요). **패딩**(사용자: "마스크하고 클로스 필터 쓰면 패딩처럼 될 수 있지?") — 96×96 평면에 0.5 m 격자 누빔선을 마스크(2,353 / 9,409 점)하고 선반의 **Cloth Filter Inflate** 를 호출해 마우스를 끈 뒤 클릭: **마스크 선은 0 이동, 칸은 최대 8.5 cm 부풀어** 누빔 패딩: `dist/zb_cloth_filter_padding_0.24.93.png`, `dist/zb_cloth_drag_real_window_0.24.93.png`. (창 스크린샷은 llvmpipe 에서 검게 나와 워크벤치 렌더로 대신.)
- 테스트: Blender 5.2.3 bpy 전체 209개 파일 PASS 5,256 / FAIL 2(`tests/test_log_bpy523_v02493.txt`, FAILED FILES: test_v02487_wiresolo · test_v02492 — 둘 다 코너 카드 글자가 MECHA LAB | ZBRUSH 에서 MECHA | ZBRUSH | PAINT 로 바뀐 것을 기대값이 모르던 것; 기대값을 고친 뒤 혼자 다시 12/12 · 80/80; Traceback 28개 = test_registration_recovery 24 + 그 FAIL 과 관련 4). 새 테스트 test_v02493_paint_lab 29(사진 보정 · 밝기 마스크 · 엣지 마스크의 순수 계산, PAINT 전환 · 보기 · 브러시 표 · 아이콘 · 스포이드 · 마스크 · 링크 스텐실 · Q · 코너 카드 · 선반 · 범례 · 키 처리 · 복귀 · Look), test_v02492_cloth_drape 23 → 33(Front + Back · Stop at Pins), test_v02492_wrinkle_lines 39 → 42, test_v02494 버전. 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.93.txt`, 이 zip). ZIP sha256 `c4ab9ebd95729d5221cb6aa0fd732114fb76c99d6b0012beb05998082d974e4e` (`mecha_lab-0.24.93_20261030-0543.zip`).

## 0.24.92 — Wrinkle Lines: 선을 그으면 튜브 + 덮은 천 시뮬로 주름 (2026-10-29)

X 의 "CL Sculpt Assistant"(Calappa Lab) 주름 시뮬을 우리 식으로: 메시에 가이드 선을 긋고 Space 두 번이면 선 자리에 주름이 잡힙니다. 관찰(참고 영상 · 사용자 지적)대로 **두 단계**입니다.

- **1단계 튜브(Space)**: 그은 선마다 **얇은 둥근 튜브**(Wrinkle Size 5 % × 1/3 = 부품 크기의 1.7 %)를 표면에 올립니다. Fold Strength = 튜브 높이, **Tube Lift** = 튜브를 표면에서 들어올림(0 = 반쯤 묻힘, 100 % = 같은 굵기의 파이프가 통째로 올라앉음), End Fade = 선 끝에서 사라지는 길이(선 길이의 %), Line Strength = 마지막 선의 세기(선마다 기억). 슬라이더가 **실시간**으로 모양에 반영되고, Enter 로 튜브만 확정할 수도 있습니다. Crease 모드는 튜브 대신 홈.
- **2단계 천(Space 한 번 더)**: 마블러스 디자이너처럼 — **메시 복사본을 표면 조금 위에 천으로 깔고**, 열린 가장자리(소매 끝)만 고정(Pin Mesh Boundary / Pin Selected), **원래 표면 + 튜브는 안쪽 콜리전**. 천은 Looseness 만큼 표면보다 크고(기본 20 % — 헐렁한 소매), Shrink 로 조이고(기본 0), 중력(기본 100 %) 에 처지며, 콜리전에 닿으면 마찰로 붙습니다. 천이 튜브에 걸려 그 아래로 접히고 선 사이 천이 구겨집니다. Silhouette Keep 은 시작 모양으로 약하게 당기는 스프링. 원단 프리셋(Cotton 기본 · Denim · Silk · Leather · Knit)은 굽힘 · 마찰 · 감쇠 · 펴짐. 프레임은 타이머로 돌아 접히는 것이 보이고(Space 멈춤 / 계속), Enter 는 천을 메시에 씀(점 수 같음 — UV · 다른 데이터 그대로), Esc 는 백업으로 되돌림. 설정은 Tool Presets(사이드 패널 Presets) 에 저장됩니다(`scene.mch_wlines`).
- 어떤 메시든 됩니다: 콜리전은 "천의 점이 가장 가까운 콜리전 점의 접평면 위에 머문다"(점이 미끄러지면 KD 트리로 다시 고름)라 원기둥 전용이 아닙니다. 솔버는 0.24.92 의 `cloth_pbd`(numpy 위치 기반 천; 길이 · 굽힘 제약, 라플라시안 펴짐, 콜리전 콜백). 2.5만 점 30프레임 약 5 ~ 8초(프레임당 0.2초), 6천 점 20프레임 0.5초. 2만 면 미만 메시는 Add Detail 로 먼저 세분(접힘엔 점이 필요).
- **콜리전이 가벼워짐**(사용자: "콜리전은 기존 메쉬 쓰면 개무거우니까"): 콜리전 표면을 **거리 격자**(`cloth_pbd.GridCollider`, 표면 둘레 2칸 띠에 가장 가까운 점의 접평면 거리, 점에서 격자로 뿌려 굽기 — 파이썬 루프 없음)로 한 번 구워 두고 프레임마다 격자 조회만 합니다. 2.5만 점 소매: 프레임 203 → 129 ms, 격자 굽기 0.7 ~ 1.4초. **Sim Points**(기본 4만): 점이 그보다 많은 메시는 **데시메이트한 가벼운 사본**에서 천과 콜리전을 돌리고 변위만 원래 메시에 입힙니다(가까운 사본 점 8개 가우시안 가중 + 메시 엣지로 3번 펴기, 메시의 고정 점은 그대로). 9.9만 점 소매 30프레임: 전체 35초 → 사본 2.5만 점 16초. 사본 결과는 전체보다 거칠고(접힘 크기가 격자 크기를 따라감) 0 으로 끄면 항상 메시 그대로.
- **Cloth Drape(영역 천, 새 도구 · Cloth 그룹)**: 마블러스처럼 — 메시 위에 **라쏘**를 그으면 그 영역에 Armor Plate 와 같은 **고른 패치**를 깔고(Cloth Detail = 외곽 크기의 %), 그 패치를 몸에서 조금 띄운 **헐렁한 천**(Looseness)으로 만들어 **가장자리만 고정**(Pin Rim = 봉제선), 중력에 떨어뜨립니다. **콜리전은 라쏘 아래의 몸 점만** 격자로 구움(등판 샘플: 1.2만 점 중 7.5천, 0.65초). 천은 라쏘 직후 "Cloth Drape" 오브젝트(몸에 부모)로 생기고 Space 로 프레임이 흐르며(타이머), Enter 는 남기고 Esc 는 지웁니다. 슬라이더: 원단 · Looseness · Shrink · Gravity · **Stickiness**(마찰) · Silhouette Keep · Gap · Cloth Detail · Pin Rim · Frames — 전부 Presets 저장. 바꾸고 Space 를 누르면 깔린 패치에서 다시 돕니다(Cloth Detail 만 새 라쏘). 등판 샘플(3.3천 점, 60프레임 0.9초): `dist/cloth_drape_0.24.92.png`. **Drape This Mesh**(사용자: "라쏘 말고도 내가 리메쉬한 메쉬 자체 위에"): 패널 버튼 — 활성 메시 **자체**가 천이 되어 같이 선택한 다른 메시(없으면 부모) 위로 떨어집니다. 열린 가장자리가 봉제선(Pin Rim), 일부 점을 선택해 두면 그 점도 고정(전부 선택은 무시), 콜리전은 그 몸 전체(40만 점까지; 넘으면 천 둘레 2배 상자), 월드 좌표로 맞춤. Enter 는 메시를 바뀐 채로, Esc 는 저장해 둔 복사본으로 되돌림. 위에 던진 6.5천 점 쿼드 조각이 90프레임 2.5초에 걸쳐 내려앉음(`dist/cloth_drape_mesh_0.24.92.png`); 달라붙음이 낮으면(20 %) 매끈한 몸에서는 미끄러져 떨어짐.
- **Wrap This Mesh**(사용자: "똑같은 형태의 천이 둘러싸야… 보자기로 싼 것처럼"): 몸을 복사한 천(닫힌 메시는 복셀 리메시 복사 — 극점 · 바늘면 없음, Wrap Points 로 점 수; 열린 원통은 그대로 복사해 **위아래 열린 끝을 고정**)을 Gap 만큼 띄우고 Looseness 만큼 크게 만든 뒤 **Wrap Pressure**(진공 포장처럼 몸 쪽으로 누르는 힘)로 몸에 붙입니다. 남는 천이 뭉쳐 보자기 주름이 됩니다. 처음 시도(천을 몸보다 작게 조이기)는 팽팽해질 뿐 주름이 없어 버림. 새 "Cloth Wrap" 오브젝트. 반으로 꺾은 원통(팔꿈치) 샘플: `dist/cloth_drape_wrap_elbow_0.24.92.png`.
- **Thickness**: Enter 로 남길 때 천 오브젝트에 Solidify(바깥쪽, Even Offset 끔 — 구겨진 자리에서 가시가 터짐, Quality Normals). 내 메시 자체 모드에는 안 붙임.
- **Lines as Tubes · Draw Lines**(사용자: "라쏘 모드랑 리메쉬 그리고 튜브 내가 그을 수 있게"): 세 모드 모두에서 몸에 그어 둔 Wrinkle Lines 의 선이 콜리전 위의 튜브가 되어 천이 거기 걸려 접힙니다(튜브 크기 · 높이 · 들어올림 · 끝 페이드는 Wrinkle Lines 슬라이더, Cloth Drape 패널에도 표시). Draw Lines 버튼이 Wrinkle Lines 도구로 보내고, 선은 몸에 남으니 Cloth Drape 로 돌아오면 됩니다. ㄴ자 원통 + 선 4개: `dist/cloth_drape_wrap_lines_0.24.92.png`(Wrap), `dist/wrinkle_lines_elbow_0.24.92.png`(Wrinkle Lines 자체).
- **선 없이 Space = 스컬핑한 능선이 콜리전**(사용자: "튜브를 손으로 스컬핑하고 그 위에 시뮬하면 어떠냐", "졸라 좋은데 이거지"): Wrinkle Lines 에서 선을 하나도 안 긋고 Space 를 누르면 튜브 단계를 건너뛰고 **지금 메시 그대로**(클레이 스트립 등 아무 브러시로 직접 올린 능선 포함)를 콜리전으로 삼아 같은 천을 떨어뜨립니다. 선 튜브 · 손 스컬핑 · 둘 다, 어느 쪽이든 됩니다. ㄴ자 원통에 넓고 울퉁불퉁한 능선 4줄을 올리고 선 없이 돌린 샘플(2.5만 점, 30프레임 5초): `dist/wrinkle_lines_sculpted_0.24.92.png`(능선 → 천 → 와이어).
- 안정화: 고정된 봉제선 옆 4줄은 Looseness 를 서서히(고정 링 바로 옆이 40 % 늘어나 튀던 것), 제약 한 번에 점이 변 길이의 절반 이상 못 움직임(`cloth_pbd._project` 클램프), 프레임당 이동 상한(`Cloth.max_step`). 앞판·뒷판 봉제는 다음.
- **ZBrush 선반**(왼쪽, Hard Edges 아래)에 Wrinkle Lines 상자: "Draw Lines (MECHA LAB)" 이 오브젝트 모드의 도구로 보내고, 주요 슬라이더(Size · Fold · Looseness · Gravity · 원단) 도 거기서.
- **ZBrush 선반에 Blender 클로스 브러시**(사용자: "원래 블렌더 클로스 브러쉬를 지브러시 탭에 넣어줘"): 브러시 표에 **ClothDrag · ClothFolds · ClothPinch · ClothPush · ClothGrab · ClothInflate · ClothExpand · ClothRandom**(Blender Essentials 의 Drag / Pinch Folds / Pinch Point / Push / Grab / Inflate / Expand-Contract / Grab Random Cloth; B 키 글자 CD CF CP CU CG CI CE CR; 아이콘은 Essentials 미리보기) — 아래 브러시 선반에는 그중 4개(Drag · Folds · Push · Grab) 그룹, 8개 전부는 B 팝업에서, 왼쪽 선반에 **Cloth Brush** 상자(브러시 자체의 값: 변형 종류, 시뮬 영역 Local / Global / Dynamic, 힘 감쇠, Sim Limit · Falloff, Mass, Damping, Silhouette Keep(softbody), Pin Boundary, Collision)와 **Cloth Filter**(Gravity · Inflate · Expand · Pinch · Scale: 누르고 끌기) 버튼. 클로스 브러시는 펜 압력이 크기 · 세기에 안 걸림(압력이 바뀌면 시뮬이 다시 시작되므로). Stretch/Move · Bend/Twist · Boundary 계열은 Pose / Boundary 브러시라 뺌.
- 결과 비교 그림: `dist/wrinkle_lines_0.24.92_looseness.png`(참고 영상 프레임 vs Looseness 10 ~ 20 %), `dist/wrinkle_lines_0.24.92_tube_lift.png`(Tube Lift 0 / 50 / 100 %), `dist/wrinkle_lines_0.24.92_gui_kept.png`(실제 창에서 Space · Space · Enter 로 남긴 메시).
- 중간에 버린 방식(기록): 블렌더 Cloth 모디파이어의 shrink 그룹(움푹 + 자갈 노이즈), 스컬프트 Cloth 브러시를 파이썬으로 긋기(`sculpt.brush_stroke` 는 되나 Cloth Filter 는 파이썬에서 호출 불가, 선이 통째로 튀어나옴), 선을 홀드하고 전체를 줄이는 PBD(선 둘레만 튀어나옴), 튜브 능선 + 약한 Drag Cloth(변화 거의 없음).
- 테스트: Blender 5.2.3 bpy 전체 208개 파일 PASS 5,234 / FAIL 0(`tests/test_log_bpy523_v02492.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery. 첫 실행에서는 아래 브러시 선반이 클로스 8타일로 넓어져 2560 px 에서 왼쪽 키 안내 카드와 겹쳐 test_v02492 가 2개 FAIL — 선반을 4타일(ClothDrag · Folds · Push · Grab, 나머지는 B)로 줄이고 그룹 간격 12 → 10 으로 고친 뒤의 최종 실행이 위 수치). 새 테스트 test_v02492_wrinkle_lines 39(격자 콜리전 · 가벼운 사본 · 선 없이 스컬핑 콜리전 포함; tube_field 의 단면 · 끝 페이드 · 닫힌 선 · 여러 선 · Tube Lift, 튜브 단계의 높이 · 반지름 · 실시간 갱신 · Crease, 천 단계의 콜리전 밖 유지 · 고정 링 · 마찰 · 중력 방향 · 속도 · NaN 없음, simulate · start / run / step / confirm / cancel 흐름 · 백업 정리, 패널 · 키맵 · ZBrush 선반 · 프리셋), test_v02492_cloth_brush 11, test_v02492_cloth_drape 23(패치 · 구 위에 머무름 · 가장자리 봉제 · perform / step / restart / confirm / cancel · 두 번째 라쏘 거부 · 도구 연결 · 패널 · 프리셋 · Drape This Mesh: 몸 고르기 · 열린 가장자리 고정 · 월드 좌표 콜리전 · Esc 되돌림 · Enter 유지 · Lines as Tubes: 선 위에서 천이 튜브 반지름만큼 높음). 고친 기존 테스트 test_workspace_data(Space 는 Wrinkle Lines / Cloth Drape 의 시뮬 키만 허용). 실제 블렌더 창: 도구 활성 → Space(튜브) → Space(천 30프레임, 타이머) → Enter 가 끝까지 돌고 메시가 남음(2.5만 점 소매 23.5초, `dist/wrinkle_lines_0.24.92_gui_kept.png`); Cloth Drape 도 실제 창에서 도구 활성 → 라쏘(perform) → Space(60프레임) → Enter 21.5초; 자동 GUI 테스트 13/13(`tests/gui/gui_result_0.24.92.txt`, 최종 zip). ZIP sha256 `a4fd3ebe4d1ec5fcc3e2e26bac7626bf8d444988b014092e2614862fb037dbb2` (`mecha_lab-0.24.92_20261030-0445.zip`).

## 0.24.91 — 컷 Edge Finish(베벨 · 챔퍼) 가 들쭉날쭉한 부품에서 멈추지 않음 · 컷 정리 빠르게 (2026-10-29)

퍼즈(시드 1205)가 찾은 "15k 면 DynaMesh 손잡이에 베벨 컷 90초"(KNOWN_LIMITATIONS 0.24.88) 를 잰 결과, 두 군데였습니다.

- **Edge Finish 가 꼬인 밴드에서 포기함**(`rim_sweep`): 테두리가 들쭉날쭉하면(DynaMesh 노이즈 · 거친 컷) 챔퍼 폭이 테두리의 잔 굴곡보다 넓어 스윕 밴드가 자기 자신과 수천 번 교차하고(938 테두리 엣지에 8,290 교차), 그 밴드의 Exact 자기합집합이 15초 ~ **7분**(457초, 결과 0면) 걸렸습니다. 이제 교차 수를 테두리 엣지 수의 4배까지만 세고, 넘으면 폭을 반으로(두 번까지: 8,290 → 5,922 → 4,762) 줄여 다시 스윕합니다. 그래도 꼬인 밴드가 5,000면을 넘으면 **1초 안에 포기**하고 컷 경고줄에 이유를 씁니다("Edge Finish skipped: the rim is too jagged … Fix Mesh / DynaMesh it, or a narrower width"). 꼬인 밴드의 빠른 결과가 깨끗하지 않을 때 전체 Exact 로 가던 63초 경로도 끊었습니다(꼬이지 않은 밴드는 그대로). 열린 엣지 몇 개짜리 빠른 결과는 작은 구멍을 메운 뒤 다시 판정(`_settle`).
- **컷 정리(tidy)의 "하나씩 고치기" 단계**(`core_geometry._one_by_one`, 바늘면 · 0면적면 · 스파이크): 시도마다 **부품 전체를 복사하고 전체 엣지를 다시 셌습니다**(10k 면 부품에 1,700번 시도 = 68초). 이제 (1) 후보 12 ~ 48개와 그 둘레 두 링을 작은 메시로 잘라 내어 거기서 고치고 되돌려 넣음(`SUB_FACES` 2,000면 넘는 메시; 테두리 점이 그대로이고 엣지가 열리지 않을 때만, 아니면 예전 방식) — 손대지 않은 면의 UV · 색은 그대로, (2) 판정은 그 면 둘레 엣지만 셈(`_guarded_local`), (3) 한 번 찾은 후보는 면에 표시해 두고 다시 확인만 함(시도마다 전체를 다시 훑지 않음), (4) 스파이크는 호출마다 한 번만 찾음(전엔 하나 고칠 때마다 전체 점을 다시 훑음: 24초). 시도 한도는 256 → 4,096(한 번에 ~2 ms 라서; 256 에서는 거친 테두리의 0면적면 1,024개 중 760개가 남았음), 호출당 2초 예산(`CHUNK_BUDGET`) 을 넘으면 나머지는 그대로(전엔 전부 그대로였음).
- 잰 것(시드 1205, 같은 컷 단계; 이 시나리오는 실행마다 결과가 조금씩 달라 범위로): **90초(최악 7분) → 24 ~ 34초(두 번 측정 24.2 · 33.7초; Edge Finish 는 꼬인 밴드에서 1초 안에 포기)**. 20k 면 부품에 바늘면 80개 정리: 3.5초 → 0.4초.
- 테스트: Blender 5.2.3 bpy 전체 205개 파일 PASS 5,144 / FAIL 0(`tests/test_log_bpy523_v02491.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트 test_v02518_tidy_sub 11(작은 부품에서 고른 면만 바뀜 · 20k 면 잘라내기 정리 0.4초 · UV 보존 · 예전 방식도 같은 결과 · 교차 수 · `_skip` · 경고 문구 · 상수). 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.91.txt`). ZIP sha256 `5b01f2459bdce591ef3bc6eac53e89fedb61632369ac0f8b35161fdc474f34b5` (`mecha_lab-0.24.91_20261029-1537.zip`).

## 0.24.90 — Cloth Plate 의 라이브 값(Trim Width 등)이 패널에 돌아옴 (2026-10-29)

"클로스 플레이트 트림 폭 설정이 사라졌어" — 원인: 블렌더 **5.2** 가 지오메트리 노드 모디파이어 입력을 `mod["Socket_x"]` 에서 `mod.properties.inputs` 로 옮겼는데(0.24.5x 의 5.2 호환 작업에서 읽기 · 쓰기는 고쳤지만), 사이드바의 **LIVE 상자가 그 옛 경로로 입력 62개를 그리고 있어** 5.2 에서는 아무것도 안 그려졌습니다(그려진 사이드 패널도 같은 그림을 쓰므로 둘 다 비었음). Trim Width · Trim Height · Puff · Fold … 전부.

- **`Object.mch_cloth_live`**: HUD 슬라이더 표(SLIDERS)의 항목마다 RNA 속성 하나(길이는 **부품 크기의 %**, 각도는 도, 나머지는 %). 읽고 쓰면 노드 입력에 바로 반영되고(기존 `set_input` 경로: 다음 플레이트에 기억 · 주름선 갱신), Apply 뒤엔 0 으로 읽히고 쓰기는 무시.
- LIVE 상자에 **그룹별로**: Edge Trim(Trim Width · Trim Height) → Shape(Height · Puff · Puff Width · Edge Roll · Gravity · Center Fade) → Folds → Sections → Stitch / Pattern. 크리처 스킨이면 Skin · Edge · Shape. 그려진 사이드 패널에도 같은 바들.
- 테스트: Blender 5.2.3 bpy 전체 204개 파일 PASS 5,132 / FAIL 0(`tests/test_log_bpy523_v02490.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트 test_v02517_cloth_live 10(Trim Width 가 부품 크기의 % 로 읽히고 쓰면 노드 입력 · 기억 · 각도 · 정수 · 네이티브 패널 · 그려진 패널 · Apply 뒤). 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.90.txt`). ZIP sha256 `27e2fa1ac0a67384a49def5f09fa0f8ce5446e06c77264236b14efc4906cff7c` (`mecha_lab-0.24.90_20261029-1355.zip`).

## 0.24.89 — Belt Maker: 큰 몸통에서 8배 빠르게 · 슬라이더 즉시 · 폭을 비율로 (2026-10-29)

"벨트가 예전같지 않아 작고, 엄청 느려" — 잰 것(`tools_dev/bench/`: `probe_belt3`): 벨트 코드는 10월 26일 이후 안 바뀌었고, 작아 보이는 것은 **폭이 절대 길이(0.15)** 라 큰 하이폴리 몸통에선 가늘게 나오는 것, 느린 것은 **몸통 전체를 bmesh 로 복사해 평면으로 자르고 파이썬 리스트 BVH 를 짓는 구조**라 면 수에 비례했기 때문입니다(130만 면 몸통: 첫 벨트 6.4초, **슬라이더 한 칸마다 3.4초**).

- **Relative Width(기본 켜짐)**: 폭을 벨트 루프 크기의 % 로(기본 7.5 % — 2 m 몸통에서 예전 기본 0.15 와 같음). 어떤 크기의 부품에도 같은 비율. 끄면 예전처럼 길이로. 보고 메시지와 LIVE 상자에 "loop 1.99, width 0.149 = 7 %" 가 나와 가늘면 왜인지 보임.
- **Defaults 버튼**("Settings for the next belt" 옆 · Apply 옆): 다음 벨트는 마지막 벨트의 설정을 이어받으므로, 작게 만든 적이 있으면 계속 작게 시작하던 것을 되돌림.
- **속도**: 대상 메시를 한 번 읽어 두고(내장 속성으로, 바뀌면 다시) BVH 는 C 로 짓고(`BVHTree.FromObject`), 감기 루프는 bmesh bisect 대신 **numpy 평면 단면**(교차하는 면마다 선분 하나, 공유 변으로 연결), 루프는 폭 · 밀도 · 부드럽기와 따로 캐시. **130만 면: 첫 벨트 6.4 → 0.8초, 슬라이더 3.4 → 0.01초**; 8만 면: 0.41 → 0.15초, 슬라이더 0.16 → 0.00초.
- 테스트: Blender 5.2.3 bpy 전체 203개 파일 PASS 5,122 / FAIL 0(`tests/test_log_bpy523_v02489.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트 test_v02516_belt 10(상대 폭 기본값 · 보고의 루프 크기 · Defaults · 플레이트 / 적용된 벨트 / 미러 반쪽 몸통 위에서도 루프는 부품 크기). 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.89.txt`). 퍼즈는 0.24.88 것(벨트는 퍼즈 시나리오에 없음). ZIP sha256 `cd75bdd56185cf6363f24e9c0571ae9b70c0338c3fa0a544dff5661ec3a99929` (`mecha_lab-0.24.89_20261029-1123.zip`).

## 0.24.88 — Panel Cloth(클로스 시뮬) 빠르게 · 품질 (2026-10-29)

클로스 시뮬("클로스 시뮬쪽 효율화랑 퀄리티")은 블렌더 자체 Cloth 솔버를 프레임마다 돌려 마지막 프레임을 굽는 구조입니다. 먼저 잰 것(2,362면 Cloth Plate → 9,448면 천, 4코어 리눅스; 로그 `tests/bench_cloth_0.24.88.txt`, 스크립트 `tools_dev/bench/bench_cloth.py`): 프리셋마다 **10 ~ 28초**, 그중 프레임 계산이 0.25 ~ 0.6초 × 31 ~ 46프레임, **시작 준비 루프 2.9초**(점마다 노멀을 다시 읽던 것), 장면에 Mirror 가 붙은 130만 면 부품이 있으면 **+3초**. 품질: 천 계열 프리셋(Cloth · Silk · Canvas · Crumple)의 결과에 **서로를 뚫고 지나간 면 쌍 44 ~ 646개**와 면적이 평균의 0.05 % 인 바늘 면. 고친 것:

- **백그라운드 베이크**: Background 토글(ZBrush 선반 · Mesh Tools 의 것과 같은 값, 기본 켜짐)이 켜져 있으면 Panel Cloth(버튼 · 라쏘 뒤 Sim · Refresh · 프리셋 redo)가 **두 번째 블렌더**에서 프레임을 돌립니다. 천 오브젝트는 바로 생기고(평평한 시작 상태) 끝나면 주름이 얹힙니다(언두 한 단계). Panel Cloth 상자에 진행 줄 + Cancel. 도는 동안 그 천의 Refresh 는 거부. 콜라이더(생성 면 또는 Body)와 설정을 같이 보내고, 결과는 창 안 베이크와 **같은 값**(테스트에서 높이 0.5857 = 0.5857).
- **임시 장면에서 베이크**: 프레임은 천과 콜라이더만 있는 임시 장면에서 돌립니다. 사용자 장면의 프레임 · 캐시는 그대로이고 무거운 부품의 재평가가 없음(Mirror 붙은 1.3M 부품: 14.4 → 8.5초).
- **Fast Start 기본 켜짐**: 2.9초 절약. 꺼짐 = 0.24.1 ~ 0.24.87 의 시작 상태(점마다 노멀 재계산).
- **자기 충돌 기본 켜짐**(충돌 품질 2, 자기 거리 = 접촉 두께): 측정에서 교차 쌍 **Cloth 485 → 0, Silk 641 → 0, Canvas 162 → 0, Crumple 10 → 0**, 바늘 면 없어짐(최소 면적 0.05 % → 13 %), 베이크 시간은 같음(20 → 20초, 26 → 26초). Padding 계열은 원래 0이고 시간 차이 ±5 %. (주름 폭이 조금 커짐 — 천이 자기를 뚫지 못하고 겹치는 것이 맞는 모습.) 다른 변형들도 재봤음: 자기 충돌 거리 3배 + 품질 5 는 교차 12 지만 7 ~ 10배 느림(140 ~ 250초), shrink 를 프레임에 걸쳐 올리는 것은 Silk 만 도움(646 → 240) · Cloth 는 그대로, 시작 노이즈는 교차 20 ~ 100.
- **Padding 계열 솔버 단계 줄임**(Padding · Quilt 5 → 3, Puffer · Pillow · Leather 6 → 4): 같은 부풂(편차 2 % 안)에 **35 ~ 45 % 빨라짐**(Padding 9.5 → 6.2초, Puffer 12.9 → 8.8, Pillow 13.1 → 8.8, Quilt 10.4 → 6.2, Leather 15.1 → 9.9). 천 계열은 단계 수를 줄이면 교차가 다시 생겨(Cloth 4단계: 13) 그대로.
- 측정 중 찾은 버그: `run_preset` 이 `self_collision` 을 버려 프리셋 경로에서는 자기 충돌을 켤 수 없었음(이제 전달).
- 테스트: Blender 5.2.3 bpy 전체 202개 파일 PASS 5,112 / FAIL 0(`tests/test_log_bpy523_v02488.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트 test_v02515_cloth_bg 21(임시 장면 베이크 · 백그라운드 베이크가 창 안과 같은 높이 · 도중 Refresh 거부 · 임시 콜라이더 정리 · 자기 충돌 기본값 · Cloth 프리셋 교차 0 · 바늘 면 없음). 고친 기존 테스트 test_v02328(Fast Start 기본 켜짐). 파이프라인 무작위 테스트 20 × 12(seed 1201~): 20 OK · 크래시 0(품질 메모는 KNOWN 부류; seed 1205 의 베벨 컷 90초는 0.24.87 과 같음 — KNOWN). 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.88.txt`). ZIP sha256 `0035142150fb236c30e5fa6055960319f842517597a18dda1efb99f63b72c8e3` (`mecha_lab-0.24.88_20261029-1013.zip`).

## 0.24.87 — 그룹 박스선 전체 끄기, 컷 엔진 검토 문서 + 빠른 경로 프로토타입(플래그) (2026-10-29)

- **그룹 박스선 일괄 끄기**("박스 라인은 일괄로 안보이게"): 장면 설정 **Group Box Lines**(기본 켜짐). 끄면 **모든 그룹**의 상자 선이 안 그려집니다(선택한 그룹도). 스위치 두 곳: **Layers 패널 머리**의 상자 버튼(최소화 `–` 왼쪽), **Groups 카드** 맨 위 "Box Lines (all groups)" 토글. 그룹마다 있는 눈(0.24.85)은 그대로 — 전체를 다시 켜면 그룹별 설정이 다시 적용됩니다. 파일에 저장됨. 새 테스트 test_v02514_boxes_all 10.
- **컷 엔진 최적화 검토** `CUT_ENGINE_REVIEW_KO.md`: 국소 Boolean 과 국소 SDF 를 측정으로 비교(SDF 는 블렌더 OpenVDB 로 리샘플링: 복셀 = 변 길이에서 벽 평면 오차 최대 변 길이 1.5배 · 모서리 띠 11 % 둥글어짐 · 면 수 9배; 1/4 복셀이면 228만 면 · 8초), 단계별 병목(1.3M: 불리언 0.36초, 꿰매기 1.14초, 얹기 0.70초, 정리 0.66초), 다음 단계 제안(국소 Boolean v2, 미룬 꿰매기 "Instant Cut"). 판단: 국소 Boolean 유지, SDF 보류.
- **빠른 경로 프로토타입(환경변수 `MECH_REGION_FAST=1`, 기본 꺼짐, 동작 변화 없음)**: High Poly 결과를 bmesh 왕복 대신 datablock 교체로 얹고, 꿰매기 안에서 정리한 결과는 뒤에서 다시 검사하지 않음. 측정 1.3M 라쏘 컷 3.29 → 2.31초, 2.1M 8.85 → 5.44초(`tests/bench_region_fast_proto.txt`). 측정 스크립트 `tools_dev/bench/`.
- 테스트: Blender 5.2.3 bpy 전체 201개 파일 PASS 5,091 / FAIL 0(`tests/test_log_bpy523_v02487.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트 test_v02514_boxes_all 10. 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.87.txt`). 퍼즈는 0.24.86 것(코드 변경이 UI 토글뿐). ZIP sha256 `68eae9184d305127774768cf13a611777993bccdc7d1ed5f219411115e30db94` (`mecha_lab-0.24.87_20261029-0742.zip`).

## 0.24.86 — 하이폴리 컷(실험 기능): 획 주변만 불리언 · 정리 · 구멍 메움도 영역만 · Quad Remesh / Re-Fix 는 백그라운드 블렌더에서 (2026-10-29)

"가벼우면서 안정적"을 위해 세 가지를 넣었고, 하이폴리 컷은 **실험 기능(기본 꺼짐)** 으로 두었습니다. 요청하신 검증 순서(동일성 → 안정성 → 속도)대로 측정했습니다.

- **High Poly(실험)** — 컷 설정 Advanced 의 토글(기본 꺼짐). 켜면 10만 면 이상 부품의 Cut · Split 에서 **불리언이 획 주변 면만** 상대합니다. 순서: 커터 축에 맞춘 상자 + 두 겹 둘레로 영역을 뽑고(`region`), 그 면들을 작은 패치로 꺼내(속성 함께, 쿼드는 한 번 삼각분할) Exact 불리언으로 **패치−커터**(남는 면)를 얻고, 커터는 Edit 모드 Knife(Intersect)로 패치를 따라 **자르기만** 한 뒤 커터 축 방향 광선으로 **부품 안쪽 조각(벽)** 을 고릅니다. (블렌더 Exact 솔버는 열린 패치를 상대로 커터 조각의 안·밖을 판정하지 못합니다 — 가는 기둥이 관통하면 안쪽 조각이 Intersect · Union · Difference 모두에서 사라지는 것을 확인했습니다. 그래서 자르기와 판정을 분리했습니다.) 벽 삼각형은 같은 평면끼리 합치고(접합선 점은 유지), 남는 면 + 벽을 **하나의 작은 메시**로 만들어 bmesh 로 이음새를 꿰매고(10만분의 1 거리, 열린 변 위 점만) 솔버가 남긴 0-길이 변 · 8변 이하 구멍을 정리한 뒤, 원본의 손대지 않은 면 위에 **테두리 점을 좌표로 맞춰** 붙입니다. 점 · 면 · 코너 · 엣지 속성(마스크 · 폴리그룹 · 재질 인덱스 · UV · 색 · sharp_edge · 스무스)과 재질 슬롯이 따라갑니다. 결과의 열린 변이 늘면(허용: 4개 또는 5만 면당 1개) **전체 불리언으로 자동 전환**, 어떤 단계가 실패해도 마찬가지. 보고 메시지에 `(Region)`.
  - 동일성(전체 불리언과 비교, `tests/…` 밖 측정 스크립트): 세 부품(ico 327k · ico 1.3M · 복셀 쿼드 2.1M) × 두 커터(관통 기둥, 얕은 포켓) × Cut / Split 조각 전부 **부피 차이 1e-6 이하(대부분 1e-9), 결과 닫힘(열린 변 0), 컷 바깥 면 전부 비트 동일, 면 속성 · 재질 인덱스 동일**. 면 수는 벽 삼각형 구성이 달라 ±2 % 안.
  - 측정(4코어 리눅스, 20 px 라쏘 관통 컷; 하이폴리 머신에선 더 빠름):

  | 부품 | 커터 · 연산 | 전체 Manifold | 전체 Exact | **영역(High Poly)** | 영역 단계(초): 영역 · 꺼내기 · 불리언 · Knife · 정렬 · 꿰매기 | 부피 차이 | 결과 |
  |---|---|---|---|---|---|---|---|
  | ico 327k | 기둥 Cut | 0.82 | 2.30 | **0.62** | 0.06 · 0.02 · 0.15 · 0.08 · 0.02 · 0.30 | 6e-10 | 닫힘 |
  | ico 327k | 기둥 Split 조각 | 0.47 | 1.82 | **0.40** | 0.05 · 0.01 · 0.15 · 0.07 · 0.02 · 0.09 | 4e-9 | 닫힘 |
  | ico 327k | 포켓 Cut | 1.19 | 2.17 | **0.57** | 0.05 · 0.01 · 0.13 · 0.05 · 0.01 · 0.31 | 4e-12 | 닫힘 |
  | ico 327k | 포켓 Split 조각 | 0.41 | 1.62 | **0.36** | 0.06 · 0.01 · 0.12 · 0.06 · 0.01 · 0.09 | 1e-9 | 닫힘 |
  | ico 1.3M | 기둥 Cut | 4.51 | 13.3 | **1.96** | 0.19 · 0.05 · 0.46 · 0.15 · 0.04 · 1.07 | 1e-9 | 닫힘 |
  | ico 1.3M | 기둥 Split 조각 | 2.97 | 8.91 | **1.17** | 0.20 · 0.04 · 0.34 · 0.16 · 0.04 · 0.39 | 2e-8 | 닫힘 |
  | ico 1.3M | 포켓 Cut | 5.61 | 11.1 | **2.07** | 0.18 · 0.04 · 0.40 · 0.15 · 0.04 · 1.26 | 4e-12 | 닫힘 |
  | ico 1.3M | 포켓 Split 조각 | 3.39 | 7.24 | **1.18** | 0.20 · 0.05 · 0.33 · 0.14 · 0.03 · 0.43 | 5e-10 | 닫힘 |
  | 복셀 쿼드 2.1M | 기둥 Cut | 16.3 | 72.4 | **6.25** | 0.39 · 0.63 · 1.12 · 0.34 · 0.11 · 3.66 | 4e-9 | 닫힘 |
  | 복셀 쿼드 2.1M | 기둥 Split 조각 | 10.6 | 43.8 | **3.68** | 0.51 · 0.19 · 0.82 · 0.35 · 0.15 · 1.65 | 1.5e-6 | 닫힘(T-접합 수정 전엔 열린 변 3) |
  | 복셀 쿼드 2.1M | 포켓 Cut | 14.5 | 58.7 | **5.24** | 0.41 · 0.18 · 1.12 · 0.37 · 0.09 · 3.07 | 3e-8 | 닫힘 |
  | 복셀 쿼드 2.1M | 포켓 Split 조각 | 7.49 | 45.4 | **3.08** | 0.63 · 0.26 · 0.75 · 0.34 · 0.07 · 1.03 | 9e-7 | 닫힘 |

  컷 도구 전체(20 px 라쏘 관통 Cut, 불리언 + 결과 얹기 + 정리 + 검사 모두; 같은 머신 · 같은 실행에서 High Poly 끄고 / 켜고):

  | 부품 | High Poly 끄고(Manifold) | **High Poly 켜고(Region)** | 켜고의 단계(초): 불리언 · 얹기(bmesh 왕복) · 정리 · 열린 변 세기 |
  |---|---|---|---|
  | ico 327k | 1.50 | **0.88** | 0.55 · 0.16 · 0.19 · 0.02 |
  | ico 1.3M | 5.47 | **3.29** | 1.95 · 0.70 · 0.66 · 0.11 |
  | 복셀 쿼드 2.1M | 24.3 | **8.85** | 5.23 · 1.90 · 1.41 · 0.34 |

  (0.24.85 의 같은 라쏘 컷: 1.3M 10.4초, 2.1M 24초. 복셀 줄은 T-접합 수정 뒤 다시 잰 것. 영역 경로의 남은 비용은 꿰매기 — 손대지 않은 면 + 영역을 새 메시로 쓰고 속성을 옮기는 것 — 와 결과 얹기의 bmesh 왕복입니다. 측정 로그 `tests/bench_region_0.24.86.txt`.)
- **메시 배열 읽기 · 쓰기가 100배 빨라짐**(측정 중 발견): 애드온의 numpy 검사들은 `loops.foreach_get('vertex_index')` 처럼 RNA 컬렉션을 항목마다 훑는 호출로 메시를 읽었습니다 — 130만 면 부품의 코너 390만 개에 205 ms, 변 196만 개에 90 ms, 점 좌표에 20 ~ 90 ms. 같은 숫자가 메시의 내장 속성(`position` · `.corner_vert` · `.corner_edge` · `.edge_verts`)에 있고 그 `foreach_get` / `foreach_set` 은 memcpy 한 번(1 ~ 4 ms)입니다. 새 `mesh_io` 모듈이 속성이 있으면 그걸 읽고 없으면 예전 경로로 돌아갑니다. 컷 경로의 모든 numpy 읽기(열린 변 세기 · 바뀐 면 찾기 · 접힌 면 · 뒤집힌 면 · 떨어진 점 · 메시 크기 · 영역 뽑기 · 되돌려 넣기), 결과 메시 만들기(Decimate · Quad Remesh · 영역 컷)가 이 경로입니다. **130만 면 라쏘 컷(High Poly 꺼짐): 11.1 → 8.3초**(열린 변 세기 1.8 → 0.15초, 정리 1.6 → 0.9초). 남은 시간은 불리언 자체(Manifold 6초)와 결과 얹기(bmesh 왕복 1.2초).
- **이음새 T-접합**(측정 중 발견): 라쏘 컷의 영역 결과에 열린 변 3개가 남아 구멍 메움 · 정리가 4 ~ 5초를 더 쓰고 있었습니다. 솔버와 Knife 가 같은 교차점을 4e-5 떨어진 두 점으로 놓아(용접 허용 2.4e-5 밖) 한쪽에만 점이 있는 T-접합. 용접 뒤 남은 열린 변에 대해 **다른 쪽 열린 점이 변 위에 놓이면(10만분의 1 거리) 그 자리에서 변을 쪼개고 용접**하는 단계를 넣었습니다(열린 기하만, 구멍 메움 앞뒤로 세 번씩; 허용치보다 짧은 열린 변도 — 복셀 쿼드 부품의 Split 조각에 남던 열린 변 3개가 그것이었고, 138 → 0). 단위 테스트 test_v02513_tees 6. 그리고 컷의 결과 정리를 **영역이 아직 작은 메시일 때** 꿰매기 안에서 먼저 돌려, 컷 뒤 정리가 영역을 다시 꺼내 · 되돌려 넣지 않게(1.4초). 
- **결과 정리(tidy)가 영역만** (3번 과제): 컷 결과의 정리가 바뀐 면(+한 겹)을 **작은 메시로 꺼내 정리하고 되돌려 넣습니다**(`extract_faces` / `replace_faces`, 속성 포함, 테두리 점은 양쪽 면이 함께 쓰는 점으로 정의). 5만 면 이상 부품에서만; 테두리 점이 사라지면 전체 정리로. 이번 측정에서 130만 면 라쏘 컷의 정리 0.9초(0.24.85: 7.2초), 210만 면 6.1초(34초; 영역 경로에선 1.5초).
- **구멍 메움도 영역만**: 컷 결과에 열린 변이 남으면 그 둘레 면만 꺼내 메우고 되돌려 넣음(130만 면에서 14초 → 1초 미만).
- **Quad Remesh · Re-Fix 를 백그라운드 블렌더에서** (2번 과제): ZBrush 선반 · Mesh Tools 의 **Background** 토글(기본 켜짐). 2만 면 이상 부품이면 메시를 작은 .blend 로 내보내 **두 번째 블렌더(백그라운드)** 가 같은 코드를 돌리고, 결과 .blend 를 받아 부품에 얹습니다(언두 한 단계). 창은 그대로 움직이고, 상태 줄 "Quad Remesh running in the background … 12 s" + **Cancel**. 돌아가는 동안 그 부품을 바꾸면 결과는 버리고 메시지로 알림. 같은 부품에 두 번 시작은 거부. 9950X3D 처럼 코어가 많은 머신에서 남는 코어를 씁니다. 헤드리스 블렌더(창 없음)에서는 그대로 인라인.
- 컷의 Auto Target 이 오브젝트 목록을 훑기 전에 뷰 레이어를 갱신(방금 지운 임시 커터의 잔재로 **드물게 세그폴트** — 0.24.85 전체 테스트 1차와 이번 작업 중 test_v02509 두 번째 라쏘에서 두 번 봄, 원인 추정).
- 멀티스레딩 · C++ 에 대해(물어보신 것): 블렌더 Exact 불리언은 교차 검사 등에 이미 `parallel_for` 가 있고 Manifold 솔버도 내부 병렬입니다. 실측(130만 면 컷 10.4초: 불리언 3.8초, 나머지는 애드온의 전체 메시 훑기)으로 병목은 블렌더가 아니라 제 파이프라인이었고, 그걸 이번에 줄였습니다. 블렌더 소스를 고칠 근거는 아직 없습니다.
- 테스트: Blender 5.2.3 bpy 전체 200개 파일 PASS 5,081 / FAIL 0(`tests/test_log_bpy523_v02486.txt`, FAILED FILES: none; Traceback 24개는 test_registration_recovery). 새 테스트: test_v02510_hipoly 11(영역 불리언 vs 전체: 면 수 2 % · 닫힘 · 속성 · 재질; 빗나간 커터 → None; 작은 부품 → None; 얇은 판 관통; 라쏘 Cut/Split 이 "Region"; 끄면 전과 같음), test_v02511_tidy_sub 10(꺼내기 / 되돌리기 왕복 · 테두리 점 이동 시 거부 · 327k 컷의 정리가 영역만), test_v02512_bg 13(백그라운드 시작 · 중복 거부 · 결과 적용 · 취소 · 바뀐 부품은 버림 · 작은 부품 인라인 · 끄기 · Re-Fix), test_v02513_tees 6(이음새 T-접합). 영역 경로를 모든 컷에 강제한(`MECH_REGION_MIN=300`) 컷 기하 테스트 93/93, 파이프라인 무작위 테스트 20 × 12: 영역 강제(seed 1001~) **20 OK · 크래시 0**(품질 메모 20줄: GN Edge · 컷 베벨 뒤 부스러기 · 스파이크 — KNOWN 0.24.83 부류; 134면 Thin7 에서 Fix Mesh 가 126변을 연 것 1건은 134면 부품에까지 영역 경로를 강제한 조건), 보통 설정(seed 1101~, High Poly 꺼짐) **20 OK · 크래시 0 · 컷이 부품을 연 것 0**(품질 메모: GN Edge 뒤 0-면적 면 31 · 부스러기, Quad Remesh 가 134면 Block 에서 면을 못 낸 것 2 — KNOWN; `tests/fuzz/pipe_scenario_report.md` 는 보통 설정 실행). 실제 블렌더 창 자동 테스트 **13/13**(`tests/gui/gui_result_0.24.86.txt`). ZIP sha256 `4914a19135c1a3f70f4b18fd0324219e7d51251d056de1703573ecd53d4488c7` (`mecha_lab-0.24.86_20261029-0649.zip`).

## 0.24.85 — 하이폴리 컷 · 스플릿 3 ~ 4배 빠르게, 데시메이트 속도 원복, 결과 음영(내보내기용) 옵션, Re-Fix 면 정리, 연결된 그룹 복사, 그룹 박스선 눈, 미러 평면 끄기 · 투명도 (2026-10-29)

- **하이폴리 컷 · 스플릿 속도("하이폴리 모드처럼 안 되나")**: 잰 결과 컷 시간의 대부분이 불리언이 아니라 **0.24.82부터 붙은 결과 정리(tidy)의 파이썬 검사**였습니다 — 82k면 몸통에 컷 2.8초 중 2.4초(불리언은 0.23초), 327k면 몸통은 컷 8.8초 · 스플릿 10.1초. 새 면 몇 개를 찾느라 몸통 전체를 점마다 · 면마다 파이썬으로 훑던 것. 이제 정리는 **컷이 바꾼 면(컷 전 메시에 없던 점을 가진 면 + 그 한 겹 둘레)만** 봅니다(`tidy_result(..., before=컷 전 메시)` — 바늘 · 0-면적 · 스파이크 · 조각 · 핀 검사 모두). 접힌 면 · 뒤집힌 면 · 짧은 변 · 떨어진 점은 numpy 로 먼저 보고 없으면 그 단계를 건너뜀. 같은 몸통: **82k면 컷 2.8 → 0.6초, 327k면 컷 8.8 → 2.4초 · 스플릿 10.1 → 3.4초**(남은 시간의 대부분이 불리언 자체 0.6 ~ 1초). 안정성은 그대로(보호된 정리 · Edge Finish 보호 · 자기 교차 경고 전부 유지; 파이프라인 무작위 테스트 20장면 다시 돌림 — 아래).
- **데시메이트가 느려진 것**(물어보신 것): 0.24.82 부터 데시메이트 뒤에도 같은 결과 정리가 돌았고, 0.24.83 에서 단계마다 메시 복사본을 만들며 **결과 면 수에 비례해 느려졌습니다** — 33k면 결과 +0.2초, 100k면 +0.6초, 200k면 +1.5초(데시메이트 자체는 0.7초). 이제 깨끗한 결과는 numpy 사전 검사만 하고 끝(200k면 정리 2.2 → 0.7초, 82k면 1 → 0.07초). 데시메이트 메시지의 시간이 이전(0.24.81)과 같은 수준으로 돌아옵니다.
- **결과 음영 — "데시메이트 뒤 면이 각져 보이는데 내보낼 때 클라이언트 스무스 설정을 모른다"**: Decimate 줄에 **Shading: Smooth / Flat / Keep**(ZBrush N 패널 Decimation 상자 · Mesh Tools 의 Decimate 아래; 기본 **Smooth**). Smooth = Decimate · Quad Remesh · Re-Fix 결과의 **모든 면을 스무스로 하고, 면이 Hard Edges 각도(기본 30°)보다 꺾이는 변은 샤프로 표시** — Shade Auto Smooth 가 보여 주는 것과 같지만 모디파이어가 아니라 **메시 데이터**라서 FBX · OBJ · glTF 로 내보낼 때 그 법선이 파일에 들어가고, 받는 쪽 뷰어에 아무 설정이 없어도 같은 모양으로 보입니다. Flat = 전부 플랫, Keep = 전처럼 결과가 가져온 대로. (Hard Edges Find 는 자기 샤프 표시를 새로 하므로 영향 없음.)
- **Re-Fix 결과의 면이 지저분하던 것**: DynaMesh 복셀 결에 Decimate 삼각형이 그대로 따라가 평면이 울퉁불퉁했음. 이제 DynaMesh 뒤 **가벼운 스무딩 2회**(Re-Fix 상자의 **Smooth** 0 ~ 6, 기본 2; 0 = 안 함) → Decimate 는 **Quads 로**(평면이 삼각형 결 대신 깨끗한 사각형) · Quad Remesh. 다섯 가지 조합을 렌더해 본 것 중 가장 깨끗한 둘. 벽이 얇아 두 면이 뚫고 나오는 경우의 재시도 문턱은 면 수의 1/2000(최소 2).
- **연결된 그룹 복사(Linked Copy)** — "복사한 그룹도 원본 바꾸면 같이 바뀌게": Groups 카드의 **Linked Copy** 버튼 · 메카 메뉴 Groups > Linked Copy. 복사본의 부품이 **원본과 한 메시를 공유**하므로(둘 다 "linked" 표시) 어느 쪽에서 Cut · Split · Decimate · Quad Remesh · Re-Fix · Fix Mesh 를 해도 모두에 보임 — Cut 의 Shared Mesh 설정(This Object Only)과 상관없이 연결된 복사끼리는 항상 한 메시("shared mesh: 2 users updated"), 메시를 통째로 바꾸는 Decimate · Re-Fix 는 복사본도 새 메시로 옮김. 모디파이어로 붙는 것(Box Hide · Armor Shell · Hard Edges 베벨 · Mirror)은 **오브젝트마다**라서 전파되지 않음(KNOWN_LIMITATIONS). 전처럼 **Duplicate** 는 독립 복사.
- **그룹 박스선 눈**: Layers 패널의 그룹 줄 enter 버튼 옆 · Groups 카드에 **박스선 눈**(카드 모양 아이콘). 끄면 그 그룹의 상자 선이 안 그려지고(선택하면 보임), 그룹마다 따로.
- **미러 평면 끄기 · 투명도**: Mirror 가 켜진 부품의 Symmetry 카드 Mirror 절에 **Plane** 토글 · **−5 % / +5 %** · 현재 % — 색깔 평면을 끄거나 투명도를 0 ~ 100 %(기본 10 %)로. Preferences > **Show Mirror Planes** / **Mirror Plane Opacity** 와 같은 값. 0 % 또는 끔이면 평면 · 테두리 모두 안 그림.
- 테스트: Blender 5.2.3 bpy 전체 196개 파일 PASS 5,041 / FAIL 0(`tests/test_log_bpy523_v02485.txt`, FAILED FILES: none; 로그 안 Traceback 24개는 전부 test_registration_recovery가 일부러 내는 것). 새 테스트: test_v02508_linked 26(연결 복사 · 컷 전파 · swap_mesh 재연결 · 박스 눈 · 미러 평면 카드 · 결과 음영 · 정리 사전 검사), test_v02509_cut_speed 9(쌍둥이 해시 충돌 · 바뀐 영역 · 핀 제거 · 82k면 컷 1.6초 미만 · 스플릿). 파이프라인 무작위 테스트 20 × 12: 20 OK · 크래시 0 · 부품이 열린 것 0(남은 품질 메모: GN Edge · 컷 베벨의 스파이크 1 · 부스러기 1 — KNOWN 0.24.83). 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.85.txt`). ZIP sha256 `17479aedfdd403d0762d38200275b3a5d310cb33c15ce66f50a50e041d3b7089` (`mecha_lab-0.24.85_20261029-0434.zip`).

## 0.24.84 — Re-Fix 버튼: DynaMesh 를 알맞은 해상도로 돌리고 깨끗한 Decimate / Quad Remesh 로 되돌려 다시 쓰기 좋게 (2026-10-29)

- **Re-Fix**(사이드바 N > Mecha Lab > Mesh Tools 의 Fix Mesh 아래, ZBrush 화면 N 패널 Geometry 의 Re-Fix 상자, ZBrush 액션 `REFIX` — 단축키 지정 가능): 작업하다 지저분해진 부품(얇은 판을 반대쪽까지 밀어 조각한 것, 깨진 컷, 라이브 단계가 잔뜩 붙은 것)을 한 번에 **깨끗한 가벼운 솔리드**로 되돌립니다. 손으로 하시던 DynaMesh → Decimate / Quad Remesh 그대로이고, 숫자는 제가 고릅니다.
  - 순서: 라이브 단계(Box Hide · Armor Shell · Hard Edges 베벨 · Mirror …) 먼저 굳힘 → 작은 구멍 메움 → **DynaMesh**(면 수 × 8 점, 12만 ~ 50만; Quad Remesh 마감이면 25만까지 — 쿼드 솔버가 느린 부분) → **Decimate**(고르게, C 엔진) 또는 **Quad Remesh**(Mostly Quads, 선반의 Hard Edges 각도)로 **Faces** 만큼 → 남은 구멍 메움.
  - **Faces** 0 = Auto(지금 그 부품의 면 수, 2,000 ~ 40,000). **Finish**: Decimate(빠름, 삼각형; Decimate 의 Quads 토글 따름) / Quad Remesh.
  - Decimate 마감에서 **벽이 삼각형보다 얇아 두 면이 서로 뚫고 나오면** 면 수를 2배씩(2번까지) 올려 다시 함 — 메시지에 "faces raised to 8,000: a wall thinner than the triangles".
  - 메시지: "Re-Fix (Decimate): 790 > 7,982 faces (DynaMesh 121,676 points, asked 2,000 …) | open edges 0 > 0 | self-crossings 337 > 0 | 1 live step(s) applied first".
  - DynaMesh 는 Fix Poles · Preserve Volume 둘 다 끄고 돌림: Preserve Volume 은 눌린 주름의 두 벽을 서로 뚫게 했고(교차 1,115), Fix Poles 는 변 4개를 열어 놓았음. 그냥 복셀 리메시가 깨끗함(교차 0 · 열린 변 0).
- **자기 교차 세기(`self_overlaps`)가 닿기만 한 면도 세던 것**: 불리언 이음새 · T 자 이음 · 같은 평면 이웃 · 복셀 리메시가 남긴 눌린 주름의 두 벽을 교차로 셌음(깨끗한 DynaMesh 결과에서 177). 이제 **서로의 평면을 양쪽으로 확실히(면 크기의 1/1000 넘게) 지나는 쌍만** 셉니다 — 0.24.83 의 "crosses itself" 경고도 이 기준.
- 테스트: Blender 5.2.3 bpy 전체 194개 파일 PASS 5,006 / FAIL 0(`tests/test_log_bpy523_v02484.txt`, FAILED FILES: none; 로그 안 Traceback 24개는 전부 test_registration_recovery가 일부러 내는 것). 새 테스트: test_v02507_refix 11(교차 세기 · Auto 면 수 · 점 수 규칙 · 뚫린 판 Re-Fix(Decimate) → 닫힘 · 교차 0 · 라이브 Box Hide 있는 몸통 Re-Fix(Quad) → 굳힌 뒤 닫힌 쿼드 · Mesh Tools 버튼). 보내주신 장면의 판(4만 면 · 교차 418): Decimate 2.8초 → 교차 0 · 닫힘, Quad 23초 → 교차 1. 전후 그림 `dist/refix_before_after_0.24.84.png`. 실제 블렌더 창 자동 테스트 13/13(`tests/gui/gui_result_0.24.84.txt`, 최종 zip 설치 포함). ZIP sha256 `6d4570693f9b3eee5b52d55a854cae33cbcf63384df938f07614b1fa508cffca` (`mecha_lab-0.24.84_20261029-0318.zip`).

## 0.24.83 — 컷 · 컷 베벨 · GN Edge · 컷 램프 · Box Hide · ZBrush 파이프라인(DynaMesh → Decimate → Quad Remesh → 다시 컷) 무작위 테스트로 찾은 깨짐 수정 (2026-10-28)

"특히 오류가 많은 컷, 컷 베벨, 컷 램프가 제대로 들어갔는지, 복스하이드가 가끔 안 되는 것, DynaMesh → Decimate → Quad Remesh 뒤 다시 작업하면 메시가 깨지는 것"을 그대로 돌리는 무작위 테스트(`tests/fuzz/pipe_scenario.py`)를 만들어 세 번 돌리고(각 40 ~ 60 장면 × 12 단계, 장면마다 블렌더 프로세스 하나), 나온 것을 고쳤습니다. 테스트가 보는 것: 단계마다 NaN · 열린 변 · 면 3개 이상 붙은 변 · 0-면적 면 · 바늘 면 · 같은 점 위 겹친 면 · 뒤집힌 면 · 부스러기 조각(BAD), **도구가 "됐다"고 했는데 그 부품의 평가 메시가 그대로인 것(NOOP — 모양 안 점 중 그 부품 위에 있는 점이 있을 때만)**, **Cut Ramp 가 평평한 윗면에서 첫 변 쪽이 Cut Depth 만큼 깊고 반대쪽은 표면으로 올라오며 어디서도 요청보다 깊지 않은지(RAMP)**, 도구가 거부한 것(FAIL)과 20초 넘게 걸린 단계(SLOW). 첫 실행(40 × 12): BAD 90줄 · 거부 60줄.

- **0.24.82의 결과 정리(tidy)가 닫힌 컷을 열어 버리던 것**(가장 큰 것 — 0.24.82 자체 버그): 불리언 결과는 닫혀 있는데(296면, 열린 변 0) 뒤이은 `dissolve_degenerate`(짧은 변 합치기, 중간 변 길이의 5 %까지)가 27면을 없애며 **열린 변 35개**를 만들었음. 이제 정리의 **모든 단계가 복사본에서 먼저 돌고, 열린 변이나 3면 변이 늘면 그 단계는 버림**(`_guarded`), 짧은 변 합치기는 부품의 100만분의 1 이하만(5 % 규칙은 실제 베벨 단(0.01)도 뭉개던 것), **0-면적 면 · 바늘 면은 통째로 안 되면 하나씩**(가장 짧은 변 접기 → 안 되면 가장 긴 변 녹이기, 각각 열리지 않을 때만). GN Edge 결과 4,180면(0-면적 24 · 바늘 19) → 4,120면 깨끗, 컷 베벨 Knob(0-면적 66 · 바늘 31) → 0-면적 1 · 바늘 0. 회귀 테스트: 베벨 + 리메시 + 데시메이트한 몸통에 무작위 컷 12번 모두 닫힘(0.24.82는 35 변 열림).
- **From Surface(깊이 모드)로 두 부품 위에 그리면 첫 표면 하나만 잘리던 것**: 깊이 범위를 모양 가운데의 첫 표면 하나로 잡아 모두에 썼음 → 몸통 위에 떠 있는 판은 "not touched (no overlap)"로 안 잘리고(seed 5), **Box Hide 도 같은 범위를 써서 "Hidden on Body, PlateA" 라면서 PlateA는 그대로였음(NOOP, seed 37 — "복스하이드가 가끔 안 되는" 것 중 하나)**. 이제 부품마다 **자기 표면 아래**에서 포켓 범위를 따로 잡음(`own_pocket`; Cut · Split · Box Hide, Gap Split 제외). 테스트: 밑 상자 + 위 판 한 번에 0.05 포켓 → 둘 다 자기 표면에서 0.05.
- **Box Hide 를 같은 부품에 두 번 하거나 가려진 부품 위에 띠를 그리면 "EXACT: result has 34 non-manifold edges" 로 실패하던 것**(seed 22 — "복스하이드 가끔 안 됨"의 다른 하나): 두 번째 모양이 첫 모양과 **같은 앞·뒤 캡 면**(같은 부품 범위)이라 Exact 합집합이 깨짐. 이제 들어가는 모양마다 앞뒤를 0.4 % × n 만큼 더 늘리고(캡이 겹치지 않음), 합집합은 AUTO(두 닫힌 기둥엔 Manifold 가 정확) · 실패하면 모양을 0.3 % 키워 한 번 더. 테스트: 같은 부품에 겹치는 가리기 2번 + 띠 → 셋 다 가려지고 볼륨은 닫힌 하나.
- **Hard Edges(Find Edges) 베벨이 촘촘한 몸통에서 깨진 결과를 주던 것**(seed 35: DynaMesh 뒤 데시메이트한 3,563면 몸통, 하드 엣지 2,035개, 폭 0.04 → Clamp 켜도 열린 변 44 · 3면 변 48 · 0-면적 150): 베벨 모디파이어 결과를 검사해 깨졌으면 폭을 절반씩 3번까지 줄이고, 그래도 깨지면 **베벨 없이**(깨끗한 메시가 깨진 베벨보다 낫다) — Find Edges 메시지에 "bevel width 0.04 overlapped …, 0.01 used" / "no bevel (Decimate / Quad Remesh lower first)" 로 알림. 베벨이 만나는 곳의 어쩌다 한두 개(8개 또는 0.1 %)는 전처럼 그냥 둠(Edge Mesh 테스트의 6개).
- **GN Edge Chamfer / Bevel 결과에 남던 작은 조각(네면체)**: 폭이 큰 챔퍼가 모서리를 깎아 낸 3 ~ 4면 조각(부품의 8 % 크기)이 별도 조각으로 남았음 → 부피가 부품 크기³의 1만분의 1 아래인 8면 미만 조각은 부스러기로 버림.
- **컷이 깨진 이유 알려 주기**: 닫힌 부품의 컷 결과가 열려 나오면 부품이 **자기 자신을 가로지르는지**(얇은 판을 반대쪽까지 밀어 조각한 것 — seed 122: 40k면 판, 교차 428쌍 → 컷 뒤 열린 변 217) 세어 "Thin1 crosses itself in 428 places - the cut is broken there; DynaMesh or Fix Mesh it first" 경고. (자동으로 고치지는 않음 — KNOWN_LIMITATIONS.)
- **크래시(세그폴트) 하나 잡음 — 컷 설정을 바꾸면 마지막 컷이 다시 잘리는 기능(0.24.56 Live Last Cut)이 설정의 업데이트 콜백 안에서 바로 다시 잘랐음**: 무작위 테스트 seed 353 에서 GN Edge 스윕(지오메트리 노드 평가)을 그 콜백 안에서 돌리다 블렌더가 죽음(같은 재컷을 콜백 밖에서 돌리면 멀쩡 — 둘로 나눠 확인). 이제 Cut Depth · GN Edge · Ramp 슬라이더의 재컷은 **0초 타이머로 미뤄 콜백 밖에서** 돌아감(`ramp_edit.refresh_later` / `flush`; Base Mesh 램프 슬라이더도 같이). 실제 창 테스트에 "라이브 컷 뒤 GN Edge 켜기 → 타이머 재컷으로 면이 늘고 → 끄면 원래 컷" 단계 추가. 헤드리스 테스트는 `ramp_edit.flush()` 를 부름(test_v02466 · 02467 · 02473 · 02476).
- **Edge Finish(컷 베벨 · 챔퍼) / GN Edge 가 메시를 깨뜨리면 버리고 평범한 컷을 남김**: 폭이 표면에 비해 너무 큰 베벨이 평면 컷 몸통을 열고(열린 변 150), 구(Knob)를 열고(187), 자기 교차 부품에서 GN 스윕이 찢었음. 이제 마감 전후를 비교해(열린 · 3면 변이 8개 또는 0.1 % 넘게 늘면) 마감만 되돌리고 "Edge Finish skipped on Body: it broke the mesh there (too wide for the surface) - the plain cut kept" 라고 알림(Cut · Split 양쪽 · 라인 컷 모두).
- 라인 컷을 아무 메시도 없는 곳(또는 Box Hide 로 가려진 곳)에 그리면 "Targets are outside the view" 대신 "The line does not cross any mesh".
- **Cut Ramp 가 제대로 들어갔는지**(물어보신 것): 테스트로 잼 — 평평한 블록에 깊이 0.3 램프: 첫 변 쪽 0.26 · 가운데 0.14 · 반대쪽 0.03, 어디서도 0.3 보다 깊지 않음, 블록은 닫힘(`test_v02506_pipe`). 무작위 테스트의 RAMP 검사도 같은 것을 봄(구멍 · 터널 위, 깊이보다 얇은 판은 제외).
- 무작위 테스트 기반: `tests/fuzz/fuzz_common.py`(두 시나리오 공용 — 가짜 뷰 드라이버 · 몸통 · 품질 측정 · 획), `mech_scenario.py`는 그것을 씀. 라인 컷은 Enter 뒤 **버릴 쪽을 클릭**하는 단계까지(전에는 RUNNING_MODAL 에서 멈춤), 시작이 안 된 획(invoke 가 RUNNING_MODAL 이 아님)은 블렌더처럼 modal 을 안 부름, `MECH_LOG_PTS=1` 로 획 점 · 컷 설정 · ZBrush 설정을 로그에 남겨 저장된 장면에서 그대로 재생(`$S/rt/replay.py`), 리포트에 거부 · 느린 단계 섹션.
- 테스트: Blender 5.2.3 bpy 전체 193개 파일 PASS 4,995 / FAIL 0(`tests/test_log_bpy523_v02483.txt`, FAILED FILES: none; 로그 안 Traceback 24개는 전부 test_registration_recovery가 일부러 내는 것; zip 설치 test_zip_install 은 최종 zip `mecha_lab-0.24.83_20261028-2306.zip` 로). 새 테스트: test_v02506_pipe 27(보호된 정리 · 무작위 컷 12번 닫힘 · 두 부품 From Surface · Box Hide 두 번 + 띠 · 라인 빈 곳 · Cut Ramp 측정 · Hard Edges 베벨 보호 · 조각 부피 규칙 · 자기 교차 · 타이머 재컷 · Edge Finish 보호). 고친 기존 테스트: test_v02505_tidy(핀 삭제는 FACES 로 — 남는 선 변을 열린 변으로 세지 않음), test_v02494(버전). ZBrush 파이프라인 무작위 테스트 다섯 번(`tests/fuzz/pipe_scenario.py`, 장면마다 블렌더 프로세스 하나, 매번 다른 seed): 1차 40 × 12 → BAD 90줄 · 거부 60줄(여기서 위의 것들을 찾음), 2차 60 × 12 → 60 OK, 3차 60 × 12 → 59 OK + **CRASH 1**(seed 353, 위 타이머 수정), 4차 60 × 12 → 60 OK · 크래시 0 · BAD 32줄(열린 변은 자기 교차 부품 3건 + 평면 컷 베벨 1건 → Edge Finish 보호), 5차 40 × 12 → **40 OK · 크래시 0 · BAD 11줄**(컷이 부품을 연 것 0건; 남은 것: 부스러기 1개 · 스파이크 · 데시메이트 3면 변 — KNOWN_LIMITATIONS), `tests/fuzz/pipe_scenario_report.md` 는 5차. 메카 빌드 무작위 테스트(`mech_scenario.py`): 3차 80 × 16 → 80 OK · BAD 39줄, 4차 40 × 14 → 40 OK · BAD 7줄, **5차 40 × 14 → 40 OK · BAD 4줄**(`mech_scenario_report.md`). 실제 블렌더 창 자동 테스트: **13/13**(`tests/gui/gui_result_0.24.83.txt`, 화면 `dist/gui_smoke_0.24.83_*.png`: zip 설치 · MECHA LAB · 막대 픽셀 · 진짜 마우스 Cut · Ctrl+Z / Ctrl+Shift+Z · Box Hide + Ctrl+Z · **라이브 컷 뒤 GN Edge 켜기 → 타이머 재컷(챔퍼 25면) → 끄기 → 평범한 재컷(13면), 블렌더 살아 있음** · Tab → ZBrush · 단축키 충돌 26개 · 타이머). 실행기(`run_gui.sh`)는 X 가 뜰 때까지 기다리고 짧은 런타임 폴더를 씀(긴 소켓 경로로 Wayland 에 가서 죽던 것), 테스트는 시작 파일의 기본 Cube 를 먼저 지움(우리 큐브와 겹쳐 두 대상이라 라이브 컷이 안 됐음). ZIP sha256 `67e963b1fe0f6854238fc00a6298d745b30d6473702ee4c01f5445705fd87062`.

## 0.24.82 — Redo Last(마지막 작업을 지금 설정으로 다시) · zip 이름에 빌드 시각 · 내보내기 정리(빈 오브젝트 · 작은 부품 과밀 쿼드) · Quad Remesh 수율 재시도 + 단계별 측정표 (2026-10-28)

- **Redo Last**(Actions 카드 · 메카 메뉴 Actions > Redo Last · N > Mecha Lab 맨 위 "Last: …" 줄): 부품을 만드는 그리기 도구(Armor Plate · Base Mesh · Creature Plate · Plate Detail · Flower · Scale Brush · Belt · Surface Draw · Cape / Hood / Scarf / Garment · Hair · Spikes / Scales · Bridge …)가 끝나면 그 획(화면 라쏘 / 선), 그린 시점(고정), 대상, 만든 부품이 기억됨. 설정(위 막대 · Quick HUD · 패널)을 바꾸고 **Redo with current settings**를 누르면 만든 부품이 없어지고 같은 획이 같은 시점에서 지금 설정으로 다시 그려짐 — 그리기 전에 설정해 둔 것처럼. 메시를 바꾸는 도구(Cut · Split · Box Hide · Mask)는 여기 안 들어감(Cut은 이미 슬라이더로 다시 잘림). 기록은 세션 안에서만(파일에 저장 안 됨), 다른 도구로 그리면 바뀜, Ctrl+Z 한 단계.
- **zip 파일 이름에 빌드 시각**: `mecha_lab-0.24.82_20261028-1830.zip`처럼 — 같은 버전을 다시 만들어도 어느 것인지 구분됨. zip 안 `build_stamp.txt`에 같은 도장이 들어가고 **Preferences 맨 위에 "Mecha Lab 0.24.82 build 20261028-1830"** 으로 보임(설치된 게 어느 빌드인지 바로 확인).
- **Export: 빈 메시 오브젝트는 내보내지 않음**(MCH_Base.009.fbx에 3개 있었음 — 파일에 빈 오브젝트로 들어갔다 나오던 것).
- **Export Quad Mesh: 단순한 작은 부품이 쿼드를 너무 많이 받던 것**(86면 베벨 상자 → 5,494 쿼드, Client Look까지 하면 4배 → 45개 부품 파일이 85만 면 / 31 MB): 모양 맞춤 검사(0.5 %)가 둥근 모서리에서 조금 벗어나면 세 배씩 촘촘하게 재시도한 탓. 이제 **1 % 넘게 틀어질 때만**(진짜 손실) 두 배로 재시도, 2 % 넘게 남으면 원본대로, 그리고 **부품 자기 면 수의 8배를 넘지 않음**. 같은 부품들: 86 → 647, 386 → 708, 216 → 1,676, 50 → 420, 172 → 45.
- **Quad Remesh 수율(All Quads가 요청의 1/6만 주던 것)**: 얇은 벽 많은 조각 부품(MCH_Base 합친 것, 11만 면)에서 **All Quads가 요청의 15 ~ 20 %만** 돌려줌(4천 → 790, 8천 → 1,273, 12천 → 1,924, 16천 → 2,277; Mostly도 16천에서 3,173). 원인: All Quads는 4배 거친 눈금으로 풀고 면을 4등분하는데, 그 눈금에서 얇은 벽이 대부분 사라짐 — 입력이 결과를 제한하는 경우(GPT 지적대로 "요청 면 수가 목표치일 뿐"이 아니라 입력 때문). 먼저 해 본 "모자란 만큼 키워 재시도"는 틀렸음: 2배 키우면 같은 비율(14 %), 4배 키우면 **8배(8천 요청에 66,642면)** — 비례가 아니라 절벽. 그래서 **요청의 절반에 못 미치면 All Quads는 같은 목표의 Mostly Quads 결과로 대체**(Mostly 자체가 모자라면 2배 한 번), 둘 중 요청에 가까운 쪽을 쓰고 메시지에 "All Quads kept only 1,056 faces - thin walls: Mostly Quads at the same count instead"로 적힘. 수치(같은 부품, 대체 뒤): All 4천 → 2,134(Mostly도 2,134: 이 부품은 4천에서 둘 다 53 %), **8천 → 8,390**(전 1,273), **12천 → 12,667**(전 1,924), 16천 → 2,920(Mostly 2배는 67,204라 가까운 쪽인 첫 결과 유지 — 이 부품의 16천은 어느 모드로도 안 나옴), 24천 → 47,370(홈 재시도 2배, 전과 같음). 대체는 시간이 두 배(8천: 19 → 39초)지만 요청한 면 수가 나옴. 8천 → 1,076 사례는 이렇게 닫힘("입력 때문" 확정 + 대체).
- **Quad Remesh 단계별 측정표**(GPT가 요구한 표; `tests` 밖 스크립트로 잰 것, 4코어 리눅스):

  | 부품 | 모드 · 목표 | 결과 면 | 열린 변 | 전체 | C 솔버(레벨 포함) | 고른 삼각형(파이썬) | Fix Mesh | 구멍 메우기 등 | 최대 RAM 증가 |
  |---|---|---|---|---|---|---|---|---|---|
  | 00001 (7,480면 · 깨진 71) | Mostly 1,870 | 1,969 (86 % 쿼드) | 0 | 1.5 s | 0.9 s | 0.5 s | 0.1 s | 0.1 s | +20 MB |
  | | All 1,870 | 974 (96 %) | 112 | 2.6 s | 1.3 s | 1.1 s | 0.1 s | | +13 MB |
  | | Mostly 8,000 | 8,104 (89 %) | 13 | 11.3 s | 8.6 s(2배 재시도 포함) | 2.4 s | 0.1 s | 0.1 s | +273 MB |
  | | All 8,000 | 8,095 (99 %) | 0 | 2.2 s | 1.1 s | 1.0 s | 0.1 s | | 0 |
  | MCH_Base 합침 (162,949면 · 깨진 5,880) | Mostly 8,000 | 8,379 (76 %) | 223 | 30.2 s | 17.8 s | 7.5 s | 4.1 s | 0.6 s | +613 MB (프로세스 961 MB) |
  | | All 8,000 | 1,076 (85 %) | 1 | 18.7 s | 6.7 s | 7.5 s | 3.9 s | 0.6 s | 0 |
  | | Mostly 40,000 | 84,151 (89 %) | 282 | 73.7 s | 47.9 s(2배 재시도 포함) | 19.4 s | 4.0 s | 1.6 s | +929 MB (1.9 GB) |
  | | All 40,000 | 37,588 (97 %) | 288 | 40.6 s | 15.7 s | 19.2 s | 3.9 s | 1.0 s | 0 |

  읽는 법: 시간의 절반은 C 솔버(다단계 레벨 만들기 포함), 1/4은 **고른 삼각형 만들기(파이썬 — 다음 C 이식 후보, 16만 면에서 19초)**, Fix Mesh 4초; 검증(is_cut_mesh · needs_fix)은 0.1초 미만. 메모리는 4만 면 목표에서 +0.9 GB(16만 면 부품). 요청보다 2배로 나오는 것(84,151)은 "홈이 쿼드보다 좁아 2배 촘촘히" 재시도의 결과(메시지에 적힘).
- **Live Stack 카드**(Layers 패널의 LIVE STACK 섹션 — 처음부터 펼쳐짐, N > Mecha Lab): 선택한 부품에 붙어 있는 라이브 단계(Mirror / Radial(대칭 카드) · Box Hide · Armor Shell · Hard Edges 베벨 / Subdivide · Cloth Plate · High Poly Subdivide · GN Edge … 그리고 블렌더 모디파이어 전부)를 **적용 순서대로 쉬운 이름**으로 보여줌. 줄마다 눈(뷰포트 숨김 / 표시) · ▲▼(순서) · ✓ **Apply**(Mecha 도구의 것이면 그 도구의 Apply — 기록도 같이 정리) · × 제거, 아래에 **Apply All**(순서대로 전부 굽기). 순서 메모: "Mirror 앞에 Box Hide: 양쪽 다 가려짐", "Subdivide 뒤 Boolean: 촘촘한 메시에 불린(느림)", "Armor Shell이 마지막이 아님: 뒤의 것이 껍데기를 바꿈". GPT 조언대로 **전용 스택 엔진 없이 블렌더 모디파이어가 그대로 진실** — Undo도 블렌더 것.
- **단축키 충돌 검사**(Preferences > Hotkeys 상자 맨 아래 **Check Conflicts**, 옆에 "n on Blender keys"): Mecha 단축키가 같은 키맵(Object Mode · 3D View · Sculpt …)에서 블렌더의 어떤 키 위에 앉아 있는지 목록(예: `Object Mode: Shift+D  mch.duplicate  shadows  object.duplicate_move`) — 클립보드와 콘솔에. Mecha 키는 그 도구 / MECHA LAB 워크스페이스에서만 이기고(poll) 나머지 때는 블렌더 키가 그대로라는 설명 포함. 창 없는 bpy에는 블렌더 키맵이 비어 있어서 실제 창 테스트(7단계)가 진짜 키맵으로 확인(Shift+D → object.duplicate_move가 잡히는지).
- **토스트 알림**: 도구가 실패하거나(안 잘림 · 선이 자신과 교차 · 너무 작음 · 예외) 결과가 요청과 다를 때("kept as it was", "could not …", "not one clean solid …"), Redo Last / Live Stack Apply 실패 때 **뷰포트 아래 툴바 위에 짧은 줄**이 4초 그려짐(빨강 = 오류, 노랑 = 경고, 파랑 = 알림; 같은 줄은 한 번만, 최대 3줄, 마지막 0.6초 페이드). 블렌더 상태줄 메시지는 그대로 — 큰 화면에서 놓치는 걸 보완하는 것.
- 테스트: Blender 5.2.3 bpy 전체 191개 파일 PASS 4,959 / FAIL 0(`tests/test_log_bpy523_v02482.txt`, FAILED FILES: none; 로그 안 Traceback 24개는 전부 test_registration_recovery가 일부러 내는 것). 새 테스트: test_v02501_lastop 10(Armor Plate 기억 · Redo로 면 수 변화 · 삭제 뒤 · Cut 제외 · Base Mesh · 버튼), test_v02502_livestack 12(네 단계 이름 · 순서 메모 · 눈 · 위/아래 · 도구 Apply · 제거 · Apply All · 이름 규칙), test_v02503_keycheck 7(같은 키 판정 · 표기 · 만든 키맵 상대 충돌 · 줄 · 연산자), test_v02504_toast 8(큐 · 중복 · 3줄 · 만료 · 긴 줄 · report · 타이머 없음 · 배선). 고친 기존 테스트: test_zip_install(+1 빌드 도장, 이름 규칙), test_v02486(+4: Client Look 왕복 · 빈 오브젝트 · 8배 상한 · 맞춤 규칙), test_v02498(+3: 빈 결과 · 수율 대체 · 규칙), test_v02494(버전), test_v02490(Live Stack 섹션), test_v02479(쿼드 내보내기 규칙). 실제 창 테스트 10/10(새 7단계: 진짜 키맵 상대 단축키 충돌 26개 목록, `tests/gui/hotkey_conflicts_0.24.82.txt`; 화면 `dist/gui_smoke_0.24.82_*.png`). 메카 빌드 무작위 테스트(`tests/fuzz/mech_scenario.py`, 얇은 벽 · 조각 노이즈 · 라쏘 도구 · Redo Last · 스택 · 내보내기 왕복 + 메시 품질 검사)는 첫 40개 실행 중 — 결과와 수정은 다음 항목. ZIP `dist/mecha_lab-0.24.82_20261028-1839.zip` sha256 `24f80c99fd4d5d4d8e199ba42af3bbecc30651860ad3380b4cbbf3768f56bfa1`.

## 0.24.81 — 그룹 Shift+D 통째 복사 · 그룹 Origin to Geometry · Quad Remesh 속도(2 ~ 4배) · 브러시 원 안 알파 끔 (2026-10-28)

- **그룹 Shift+D**: 그룹을 고르고 Shift+D를 누르면 **핸들(상자)만 복사되던 것** 수정 — 블렌더 기본 복사는 선택된 것(핸들 Empty)만 복사하고 그 자식인 부품은 두고 갔음. 이제 Shift+D / Alt+D / 메카 메뉴 · Actions 카드의 Duplicate가 **Mecha 복사**: 그룹 핸들이면 그룹 **통째**(부품 전부, 안의 그룹, 대칭 중심, 반복(Mirror / Radial / Grid)까지)가 자기 컬렉션으로 복사되고 새 핸들이 선택된 채 바로 이동(grab). Alt+D는 메시를 공유하는 복사. 일반 오브젝트는 예전처럼 하나만; 그룹과 오브젝트를 같이 고르면 둘 다. 그룹 안에 들어가 부품 하나를 복사하면 그 그룹 안에 남음. 다른 워크스페이스에서도 같은 키(일반 오브젝트는 블렌더 복사 + 이동 그대로라 달라지는 것 없음; 에디트 모드는 블렌더 기본).
- **그룹 Origin to Geometry**(사이드바 N > Mecha Lab > Groups 카드의 **Origin to Geometry**, 메카 메뉴 Groups > **Group Origin**): 핸들(원점)을 부품들 상자의 가운데로 — 부품은 그대로, 반복이 핸들 기준이면 따라옴. Groups 카드에 **Duplicate** 버튼도.
- **Quad Remesh(ZBrush 선반 / Mesh Tools의 C 엔진) 속도** — 보내주신 00001.fbx(7,480면, 깨진 엣지 71개)로 다시 측정하니 "애매"가 맞았음: Mostly 1/4 10.4초, 1/2 **31.4초**, 8천 19.8초; All Quads 1/2가 요청의 **4배(15,242면)**. 원인 둘:
  - 코어스 레벨을 만드는 **고른 데시메이션이 하드 엣지 많은 부품에서 일찍 멈춤**(레벨 3: 935면 요청 → 8,906면) → 가장 거친 레벨이 가장 촘촘한 레벨만 하고, 거기에 200번 스윕. 이제 레벨이 목표만큼 못 줄면 그 크기만큼 스윕 수를 줄임(촘촘한 레벨의 스윕 수보다는 안 내려감). (코어스 레벨을 일반 데시메이션으로 바꾸는 방법도 시험 — 더 빠르지만 열린 엣지가 늘어 버림.)
  - **더 촘촘하게 재시도**: 4배 재시도는 시간을 3배로 늘리고 면 수를 4배로 주면서 결과는 2배 때와 같았음 → 최대 2배까지만. 또 열린 변이 몇 개(1 % 이하, 최소 16)면 재시도 없이 구멍 메우기로(어차피 그렇게 함).
  - 결과(같은 부품): Mostly 1/4 **1.6초**, 1/2 **8.3초**(7,445면 — 이 부품은 1/2 크기가 하필 홈 폭과 비슷해 2배 재시도가 필요), 8천 **5초**; All Quads 1/2 **3.6초 · 7,450면**(15,242면이던 것), 8천 5.8초. 쿼드 비율 · 열린 엣지 · 원래 면과의 거리(최대 0.05 %)는 전과 같음. 기존 쿼드 테스트 5개 파일 모두 통과.
  - MCH_Base.009(16만 면 · 깨진 엣지 5,880개, ZBrush 부품)는 Fix Mesh 속도 개선까지 합쳐: Mostly 8천 **92초 → 26초**, 4만 133초 → 71초, 8만 198초 → 125초; All Quads 8천 71초 → 19초, 4만 94초 → 41초, 8만 112초 → 66초. 아직 느린 몫은 고른 삼각형 만들기(파이썬, 4만에서 19초 × 2회)와 C 솔버 자체 — 다음 차례.
  - 남은 한계(KNOWN_LIMITATIONS): 깨진 부품(이 FBX처럼 얇은 벽)에서 All Quads 1/4는 요청의 절반(974면)에 열린 변 112개 — 얇은 벽이 쿼드 하나보다 얇으면 닫지 못함. Fix Mesh 후에도 같음(벽 자체가 얇음).
- **"자르고 싶은 곳에서 manifold 노란 경고가 뜨며 안 잘리던 것"(Cut · Split · 라인 컷 · Box Hide)**: 깨진 부품(열린 변, 면 3개 이상이 붙은 엣지 — ZBrush / FBX 부품 대부분)에서 불린이 실패하면 "not one clean solid … Fix Mesh it first" 경고만 나오고 손으로 Fix Mesh를 해야 했음. 이제 그런 부품은 **자르기 전에 Fix Mesh가 자동으로** 돌고(Preferences > **Auto Fix Mesh before Cut**, 기본 켜짐) 결과 메시지에 "Fix Mesh first: Body 20 → 0 broken edges"처럼 적힘. 끄면 예전처럼 경고. Fix Mesh는 Ctrl+Z 한 단계에 같이 들어감.
- **Fix Mesh 12배 빨라짐**(MCH_Base.009 16만 면 · 깨진 엣지 5,880개: **51초 → 4초**, 같은 결과): 안쪽 벽을 찾을 때 조각(270개)마다 나머지 메시 전체의 BVH 트리를 새로 만들었음 → 트리 하나를 만들고 조각 자신에 맞은 광선은 건너뜀. Quad Remesh(깨진 부품은 먼저 Fix Mesh)와 새 Auto Fix Mesh 컷이 같이 빨라짐.
- **Mirror + Box Hide 같이 쓰면 부품이 통째로 사라지던 것**(물어보셔서 돌려 보니 재현): 라이브 Mirror(대칭 카드)가 있는 부품에 Box Hide(Follow Symmetry: 가리기가 Mirror 뒤에 옴)를 하면 평가 결과가 빈 메시. Box Hide 모디파이어의 Manifold 플래그를 원본 메시(닫힘)에서 읽었는데, 실제로 모디파이어에 들어오는 건 미러된 메시(이음새에 겹친 엣지)라 Manifold 솔버가 아무것도 안 돌려줬음. 이제 모디파이어 앞의 것들을 평가한 메시로 판단. Box Hide 먼저 → Mirror 나중은 전부터 됐고 그대로.
- **ZBrush 브러시 원 안의 알파 무늬**(검게 보이던 것): 블렌더가 알파 그림을 커서 안에 그릴 때 검은 부분을 불투명하게 칠해서 얼룩처럼 보였음. 이제 **기본 꺼짐**(ZBrush처럼 — 알파는 왼쪽 선반 Alpha 칸에 보임). 보고 싶으면 Preferences > **Alpha in Brush Circle**(연하게).
- **실제 블렌더 창 자동 테스트**(`tests/gui/run_gui.sh`, 새로 됨 — download.blender.org 허용 덕분): 가상 화면(Xvfb 1920×1080)에 **진짜 Blender 5.2.3 창**을 띄우고 zip 설치 → MECHA LAB 워크스페이스 열기 → 위 막대 · 패널이 **실제로 그려졌는지 화면 캡처 픽셀로** 확인 → **진짜 마우스 클릭(xdotool)** 으로 Cut 라쏘를 그려 큐브가 잘리는지 → **Tab** 키로 ZBrush 화면 전환 → 타이머 동작, 9/9 통과(`tests/gui/gui_result_0.24.81.txt`, 화면 `dist/gui_smoke_0.24.81_*.png`). 지금까지 "창 없는 bpy라 미검증"이던 그리기 · 키 · 마우스가 처음으로 자동 검증됨(리눅스 소프트웨어 GL — Windows 창은 여전히 사용자 확인). 캡처에서 본 것: 1920 폭에서 뷰포트가 1,300px쯤이면 오른쪽 위 STYLE / NAV 카드가 위 막대 둘째 줄(CORNERS · DEPTH)과 겹침 — 다음에 손볼 것.
- **Export Quad Mesh + Client Look에서 열린 엣지가 남던 것**(00001.fbx로 내보내고 다시 불러와 확인): 쿼드 메시는 닫혀 있는데 Client Look 베벨이 아주 작은 모서리 하나(길이 0.0004)를 자기 위로 접어 면 4개가 붙은 엣지를 만들고 Subdivide가 그걸 2배로 → 파일에 열린 엣지 2개. 이제 Client Look 뒤에 깨졌으면 Fix Mesh(작은 것만)로 용접 — 같은 파일 subdiv 0 / 1 / 2 모두 0개.
- **Quad Remesh 엔진이 빈 메시를 돌려주면 내보내기 전체가 취소되던 것**(MCH_Base.009.fbx 45개 부품 내보내기에서 한 번 남): 빈 결과가 그대로 바꿔치기되고 0/0 나누기 → 이제 그 부품은 원래대로 두고 'nothing came back - the part is kept as it is' 메시지. 남은 것(KNOWN_LIMITATIONS): 단순한 작은 부품이 Export Quad Mesh에서 쿼드를 너무 많이 받음(86면 상자 → 5,494 쿼드; Client Look까지 하면 4배) — 맞춤 재시도가 둥근 모서리 때문에 세 배씩 촘촘하게 가는 탓, 다음에 손봄.
- 테스트: Blender 5.2.3 bpy 전체 187개 파일 PASS 4,917 / FAIL 0(`tests/test_log_bpy523_v02481.txt`, FAILED FILES: none; 로그 안 Traceback 18개는 test_registration_recovery가 일부러 내는 것). 새 테스트: test_v02497_groupdup 18(그룹 통째 복사 · 중첩 그룹 · 반복 · Alt+D 링크 · 일반 오브젝트 · 섞어서 · 그룹 안 부품 · Origin to Geometry · 키 · 메뉴 · 에디트 모드 제외), test_v02498_quadspeed 7(레벨별 스윕 수 · 재시도 상한 · 하드 엣지 부품 Mostly / All 20초 안 · 알파 설정), test_v02499_mirrorhide 5(Mirror → Box Hide · 반대 순서 · Manifold 판정), test_v02500_autofix 6(Cut / Split / 라인 컷 / Box Hide 자동 Fix Mesh · 끄기 · 메시지). 고친 기존 테스트: test_v02469 · test_v02497(Duplicate가 어디서나), test_v02488(자동 Fix Mesh 끄고), test_v02494(버전), test_v02486(+3: Client Look 왕복). 전체 실행 중간(140번째 파일쯤)에 Export Client Look 정리 수정이 들어가서 그 뒤 파일들은 새 코드로 돌았고, 수정에 걸리는 test_v02486 9/9 · 새 zip으로 test_zip_install 19/19는 따로 다시 돌림. 실제 창 테스트 9/9(위). 사용자 파일 왕복: 00001.fbx Export Quad Mesh → OBJ → 다시 불러옴 1,424면 · 열린 엣지 0 · 크기 같음 · 노멀 바깥 · 원본 표면과 95% 지점 0.24%; Client Look FBX 10,380면 · 열린 엣지 0(수정 전 2). ZIP sha256 `8b15049d9a3ba04d1f665ff66d22697f4a2d591ade5ba1b50cad31784532376a`.

## 0.24.80 — 전체면 익스트랙트(Armor Shell): 부품 겉면 전체를 껍데기로 떠서 잘라 외장 갑옷 만들기 (2026-10-28)

- **Armor Shell**(Face Extract 도구 오른쪽 패널 맨 위 **Whole Surface: Armor Shell** → **Extract Whole Surface**, 오브젝트 모드에서 고른 부품): 부품 겉면 전체를 감싸는 닫힌 껍데기를 새 오브젝트 `<부품>_Shell`로 만듦(선택 · 활성). 부품 자체는 안 바뀜.
  - 슬라이더(바로 반영): **Gap**(몸에서 띄우는 거리, 기본 부품 크기의 1%) · **Thickness**(바깥으로 두께, 기본 2%) · **Smooth**(근육 · 작은 디테일 사이 홈 메우기 — 그래도 Gap보다 가까이는 안 옴) · **Detail**(촘촘함: 부품 크기의 1/60 ~ 1/260) · **Fewer Faces**(기본 켜짐: 평평한 곳은 큰 면 — 면 수 약 1/20, 컷이 훨씬 빠름; 복셀 3개보다 얇은 껍데기에서는 안쪽 / 바깥 면이 닿을 수 있어 자동으로 꺼짐).
  - 만드는 방법: 부품의 거리장(Blender 5.2 SDF 지오메트리 노드 — Mesh to SDF Grid → SDF Grid Mean(Smooth) + 원래 거리장과 합침 → Grid to Mesh 두 번)에서 Gap 위치 면(안쪽, 뒤집음)과 Gap + Thickness 위치 면(바깥)을 떠서 합침. 한 거리장의 두 면이라 서로 안 겹침 → 깊은 홈 · 겹쳐 붙은 부품이 있어도 항상 닫힌 하나의 솔리드. (먼저 해 본 Remesh + Solidify 모디파이어 방식은 Remesh가 껍데기 안을 메워 덩어리가 되고 한 번 계산에 20초씩 걸려서 버림)
  - **Update from Part**: 부품을 더 조각한 뒤 다시 감싸기(슬라이더 유지). **Apply Shell**: 일반 메시로.
  - 바로 **Cut / Split** 하면 됨: 자르기 전에 셸이 알아서 일반 메시로 굳음(Cut · Split · Boolean · Base Mesh 커터 등 라이브 프리미티브를 먼저 굳히는 모든 곳, Mesh Tools, 조각 / 에디트 모드로 들어갈 때). 굳히지 않으면 모디파이어 밑의 "부품 복사본"이 잘리기 때문. 자르는 대상은 선택된 셸뿐 — 안의 부품은 안 잘림.
  - 아무것도 안 나오는 부품(감쌀 부피가 없음)은 취소 + 경고, 빈 오브젝트를 남기지 않음.
- 미리보기: `dist/armor_shell_preview_0.24.80.png`(겹쳐 붙인 기본 도형 로봇 9,232면 → 셸 15,263면 1.6초 → Split 14번, 판마다 0.4 ~ 2.8초, 모두 닫힌 조각).
- **ZBrush 탭**: N 패널 SubTool의 Extract 옆 **Shell**, 오른쪽 SubTool 카드 맨 아래 **Extract | Armor Shell** — 바로 일반 메시 SubTool `<이름>_Shell`(두께 = Thick)로 만들고 조각하던 SubTool은 그대로. 무거운 동작이라 저장 지점 먼저.
- 테스트: Blender 5.2.3 bpy 전체 183개 파일 PASS 4,878 / FAIL 0(`tests/test_log_bpy523_v02480.txt`, FAILED FILES: none; 로그 안 Traceback 18개는 test_registration_recovery가 일부러 내는 것; zip 설치 test_zip_install 19/19 포함). 새 test_v02496_shell 31: 새 오브젝트 · 모디파이어 맨 끝 · 부품 그대로 · 기본 Gap 1% / Thickness 2% · 닫힌 솔리드(Fewer Faces 3만 면 미만) · 안쪽 = Gap / 바깥 = Gap + Thickness(반 복셀 안) · 부피 방향, 슬라이더(Gap · Thickness · Smooth: 홈 메우되 Gap보다 안 가까움 · Detail · Fewer Faces 끄기 · 3복셀 미만 두께는 고른 면), Update from Part, 크기 2배 오브젝트(장면 단위 거리), Apply, 라이브 셸에 Split(셸로 잘림 · 닫힌 두 조각 · 안 부품 안 잘림), 라이브 프리미티브 굽기 경로 · Mesh Tools 굽기, 조각 / 에디트 모드 굽기(타이머 함수 직접 호출), 셸에서 다시 Extract 안 됨, 감쌀 게 없는 부품은 취소, ZBrush Armor Shell(일반 메시 · 조각 SubTool 유지 · Thick = 두께 · 저장 지점), Face Extract 패널 · 그려진 오른쪽 패널(버튼 / 셸 슬라이더) · ZBrush SubTool 카드 · N 패널. 고친 기존 테스트: test_v02494(버전). 블렌더 창에서 패널 모습 · 슬라이더 드래그 속도 · 손으로 조각 / 에디트 모드에 들어갔을 때 0.25초 타이머는 창 없는 bpy라 미검증. ZIP sha256 `4c80ee631fe25a7f8f05175c7813fd0739caddc35eda4891b32c3defc2705d7e`.

## 0.24.79 — 컨셉 무브 계열 설정은 Mecha 위 막대에, 화면 이동 NAV(ZBrush / Blender) 따로 고르기, ZBrush 이동에서도 선택 도구 (2026-10-28)

- **컨셉 무브 · Path Move · Silhouette Move 설정이 Mecha 위 막대에**(0.24.78에서 블렌더 위 막대에서 뺀 뒤 어디에도 안 보이던 것): **METHOD**(Path Move: Extend 등 + Brush / Whole), **BRUSH**(Size · Real Size · Hardness · Taper · Follow Turns · Back Mask · 모양, Concept Move는 Hardness(Clay) · Falloff · Strength), Mirror X · Generate · Even Out · Follow View. 오른쪽 패널에는 나머지(Cuts · Knife Mesh · Auto Apply · 기록된 움직임)만.
- **NAV ZBrush | Blender**(오른쪽 위 카드 STYLE 밑, Preferences > View Navigation): 화면 이동 방식을 STYLE과 따로.
  - **ZBrush**(예전 그대로): 빈 곳 드래그 = 회전(Shift 각도 맞춤), Alt = 이동, 오른쪽 드래그 = 회전.
  - **Blender**: 블렌더 기본(가운데 버튼 회전 · Shift 이동 · Ctrl / 휠 확대, 내비게이션 기즈모). **ZBrush 탭의 ZBrush 화면 · 키는 그대로** — 빈 곳 드래그 / 오른쪽 드래그로는 안 돌고(오른쪽 클릭 = 메뉴), MECHA LAB 탭에서는 선택 도구가 빈 곳 드래그로 박스 선택. ZBrush 선반의 Move / Zoom3D / Rotate 버튼은 둘 다에서 됨. ZBrush 키 안내도 바뀜.
  - STYLE이 Blender(블렌더 조각)일 때는 이동도 블렌더라 NAV 줄이 안 나옴.
- **ZBrush 이동일 때 선택 도구**:
  - MECHA LAB: 빈 곳 클릭 = 전체 선택 해제(전에는 아무것도 안 됨), 드래그 = 회전(예전처럼), Ctrl + 드래그 = 박스 선택, Shift + 빈 곳 클릭은 선택 유지.
  - ZBrush 화면 선택 모드(Q): 다른 SubTool을 **클릭하면 그것으로 바뀜**(Alt + 클릭도). 전에는 선택 모드에서 Alt + 클릭 검사가 "브러시가 아니면 블렌더 도구로 넘김" 뒤에 있어서 아무것도 안 됐음. 선택 모드에서 빈 곳 드래그 = 회전(NAV ZBrush).
- 테스트: Blender 5.2.3 bpy 전체 182개 파일 PASS 4,847 / FAIL 0(`tests/test_log_bpy523_v02479.txt`, FAILED FILES: none; 로그 안 Traceback 18개는 test_registration_recovery가 일부러 내는 것; zip 설치 test_zip_install 포함). 새 test_v02491_nav 21: 카드 NAV 줄(STYLE 밑 · 카드 안 · ZBrush 켜짐), NAV Blender(설정에 저장 · 빈 곳 회전 꺼짐 · MECHA LAB 선택 도구가 클릭을 받음 · 선반 버튼은 됨 · 오른쪽 드래그 회전 꺼짐 · 키 안내 · ZBrush 마우스 코드), STYLE Blender에는 NAV 줄 없음, ZBrush 이동의 빈 곳 클릭 = 선택 해제(Shift는 유지) · 드래그 = 회전, 선택 모드 SubTool 클릭(순서 확인), Path / Silhouette / Concept Move 위 막대 내용 · Real Size · 오른쪽 패널이 반복 안 함(3개 도구). 고친 기존 테스트: test_v02492(코너 카드 검사에서 NAV 줄 버튼 제외), test_v02490_lassobar(컨셉 무브는 이제 BRUSH 묶음), test_v02494(버전). 실제 마우스 드래그 · 화면 회전 · 마우스 밑 SubTool 클릭은 창 없는 bpy라 미검증. ZIP sha256 `3e799defb1f97b0ac7223e3819a7c3167ecfc23f79868e0d3a32d4beda5b4399`.

## 0.24.78 — 라쏘 설정은 모든 도구의 위 막대 같은 자리에, 잘린 엣지 베벨도 위 막대로, 라쏘 설정 도구별 기억, 컨셉 무브 계열 위 막대 정리 (2026-10-28)

- **컨셉 무브 계열(Concept Move · Path Move · Silhouette Move)**: 블렌더의 위 막대(Tool Header)에 도구 설정을 한 줄 가득 그리던 것(Extend · Brush / Whole · Size · Hardness · Taper ...)을 없앰 — 다른 Mecha 도구처럼 설정은 오른쪽 패널(사이드바를 열면 사이드바)에. 블렌더 위 막대의 Custom PNG 고르기도 모양을 그리는 도구에서만 나옴.
- **라쏘 설정은 모든 그리기 도구(26개)의 위 막대 같은 자리에**: SHAPE 바로 옆에 **LASSO**(고른 모양의 옵션 — Circle / Ellipse: Segments, Curve Lasso: Samples, Free Draw: Spacing · Smooth · Simplify(Mask는 Radius도), Lasso: Open Line, Custom: Size · Rotation · Rotate With Drag)와 **CORNERS**(Lasso / Rectangle 2D 모서리: Sharp · Round · Chamfer + Width, Round는 Segments). 전에는 오른쪽 패널 맨 아래 접힌 Lasso 칸 안에 있었음.
- **잘린 엣지 베벨도 위 막대로**(Ortho 앞):
  - Cut: **GN EDGE** Off · Chamfer · Bevel + Width(Bevel은 Segments), GN Edge가 꺼져 있으면 **EDGE FINISH** Off · Chamfer · Bevel + Width · Segments · Profile · Clamp · Crisp.
  - Split: **GN EDGE**(+ 어느 쪽: Both / Side A / Side B), GN Edge가 꺼져 있으면 **SIDE A** · **SIDE B** 각각 Off · Chamfer · Bevel + Width · Segments, ⇄ Swap, Clamp · Crisp.
  - Base Mesh: **EDGE** Flat · Chamfer · Bevel + 베벨 위치(Top Only 등) · Width · Segments. (Creature Base Mesh는 Puff / Ridge / Pillow라 없음)
  - 오른쪽 패널은 위 막대에 있는 것을 반복하지 않고, 설정이 다 위 막대로 가서 제목만 남는 칸은 아예 안 보임(Cut의 GN Edge 칸은 Ramp 때문에 남음). 사이드바(N)는 전부 그대로.
- **라쏘 설정 도구별 기억**(Preferences > Lasso Settings per Tool, 기본 켜짐): 한 도구에서 바꾼 모양 · 모양 옵션 · 모서리 · Line(폭 · 끝 · Taper · Pressure) · Slow Line이 그 도구에 남고, 다른 도구로 가면 그 도구의 것이 돌아옴(처음 쓰는 도구는 지금 설정으로 시작). 파일에 저장되고, Ctrl+Z로는 바뀌지 않음. 끄면 예전처럼 모든 도구가 한 벌.
- 테스트: Blender 5.2.3 bpy 전체 181개 파일 PASS 4,826 / FAIL 0(`tests/test_log_bpy523_v02478.txt`, FAILED FILES: none; 로그 안 Traceback 18개는 test_registration_recovery가 일부러 내는 것; zip 설치 test_zip_install 포함). 새 test_v02490_lassobar 38: 그리기 도구 26개 모두 SHAPE 다음 LASSO / CORNERS, 모양마다 옵션, Corners 클릭, Cut GN Edge / Edge Finish(Off일 때만) · Split GN Edge + 쪽 / Side A · B · Base Mesh Edge(클릭으로 Flat) · Creature / Box Hide / Plate에는 없음, 오른쪽 패널이 반복 안 함(4개 도구) · 빈 칸 안 보임 · Cut GN Edge 칸은 남음 · Base Mesh 자기 프로필 줄은 그대로, 컨셉 무브 3개 도구 블렌더 위 막대 비움(사이드바에는 그려짐), 도구별 기억(처음 도구 · 돌아가기 · 다른 도구 거쳐서 · 파일에 저장 · 다시 읽기 · 끄면 한 벌 · 설정 있음). 고친 기존 테스트: test_v02489(오른쪽 패널 Lasso 칸 검사는 Lasso 모양으로 — Rectangle은 이제 그 칸이 비어서 없음), test_v02494(버전). 실제 블렌더 화면(GUI)의 위 막대 모습 · 0.2초 감시 타이머(블렌더 자체 도구 목록으로 바꿨을 때)는 미검증. ZIP sha256 `34a07229ac04c85354b0ba33cfc6e1a81fbdc6bec6d6d9671435aaa8ffe0533e`.

## 0.24.77 — 지브러시 화면 각진 모양, 컷 챔퍼 / 베벨 끝 뾰족함 · 깨진 부품에서 속도, 쿼드 내보내기 모양 유지, VIEW Wire · Solo 버튼, Path Move Extend (2026-10-28)

- **지브러시 화면에서 각진 부품이 매끈하게(얼룩지게)보이던 것**: 블렌더의 조각 모드는 Sharp로 표시한 엣지를 화면에 그리지 않음(블렌더 자체 제약 — 오브젝트 모드만 반영). 그래서 면은 스무스 + 컷 엣지는 Sharp인 부품(Make Quad · Quad Remesh 결과 등)이 지브러시 화면에 들어가면 매끈하게 보였음(High Poly Mode와는 무관 — 0.24.76의 Deform Only 수정으로는 안 고쳐졌던 경우). 이제 지브러시 화면으로 들어갈 때 Sharp 엣지에 붙은 스무스 면만 평면(flat)으로 바꿔서 오브젝트 모드처럼 각지게 보이고, MECHA LAB으로 돌아오면 **정확히 그 면만 다시 스무스**(메시는 원래대로). 바꾼 면 목록은 오브젝트에 기록해 둬서 저장 · 다시 열기 · Ctrl+Z 뒤에도 오브젝트 모드에서 원래대로 돌려놓음. 그 사이 면이 바뀌었으면(DynaMesh · Remesh 등) 돌려놓을 것이 없음. 블렌더 스타일에서는 바꾸지 않음.
- **Alt가 안 되던 원인**: 블렌더의 Emulate 3 Button Mouse가 켜져 있었음(사용자 확인). 0.24.76부터 이 설정이 켜져 있으면 패널 · 지브러시 키 안내에 빨간 경고가 나옴. 껐는데 다시 켜져 있으면 Preferences의 ☰ > Save Preferences(또는 Auto-Save Preferences)로 저장해야 함.
- **컷 GN Chamfer / Bevel 끝에 뾰족한 이빨이 남던 것**(보내주신 스크린샷, 컷 선이 판 바깥 테두리와 만나는 양 끝): 컷 테두리가 판의 윗면에서 옆면으로 꺾이는 모서리에서 바로 앞뒤 점들의 단면이 모서리 단면보다 "뒤"에 놓여서, 깎아 낼 띠가 거기서 접혀(뒤집힌 조각) 불린이 얇은 조각을 남겼음. 이제 그런 점들의 단면을 모서리 단면에 맞춤(액자 모서리를 45°로 맞추듯). 구멍 모서리처럼 반대로 꺾이는 곳은 단면이 벌어지므로 그대로.
  - 판(두께 0.1) 관통 라인 컷: 고치기 전 끝에 바늘 같은 점 2개 → 0, 띠가 더 이상 자기와 겹치지 않아 빠른 길(Manifold)로 감. 무작위 판 30개 × 관통 / 표면 라인 컷 · 직선 컷 × Chamfer / Bevel 180건: 바늘 점이 줄어든 곳 16 · 늘어난 곳 4(그림으로 비교 — 옆면 삼각형 나뉨만 다르고 모양은 같음) · 같음 160, 열린 엣지 늘어난 곳 0, 전체 시간 22.3초 → 16.9초.
- **깨진 부품에서 라인 컷 Chamfer / Bevel이 느리던 것**(보내주신 00001.fbx: 7,480면, 열린 엣지 35 · 면 3개 붙은 엣지 36): 닫히지 않은 부품은 테두리 띠를 Exact의 Self Intersection(부품 전체 면끼리의 교차까지 계산)으로 뺐음 — 시간의 대부분. 이제 띠끼리만 먼저 합치고 부품은 그대로 Exact로 빼기 — 결과가 무너졌을 때만(면 절반 넘게 사라짐 · 깨진 엣지가 크게 늘어남) 예전 방식도 해 보고 나은 쪽.
  - 판을 가로지르는 관통 라인 컷: Chamfer 4.6초 → 1.5초, Bevel 4.4초 → 2.0초(깨진 엣지 수도 예전 119 / 199 → 70 / 118, 원래 부품 71).
  - 휜 판 위 From Surface 라인 컷(바닥이 휜 면을 빠져나감): 4.6초 → 2.0초 · 6.1초 → 3.1초, 단 두 방식 모두 결과가 깨짐(깨진 엣지 수백 개) — 깨진 부품은 먼저 **Fix Mesh**: 고친 같은 부품에서는 0.6 ~ 1.8초, 닫힌 결과.
  - 깨진 부품 경고 문구가 Fix Mesh를 안내("… slow to finish; Fix Mesh (or Remesh) it first", 자를 수 없을 때 "Fix Mesh it (Mesh Tools tab / Remesh tool / ZBrush shelf) or Remesh it first").
- **쿼드로 내보내기(Export Quad Mesh)가 작은 · 디테일 많은 부품을 깨진 조각으로 만들던 것**(보내주신 스크린샷 — 13,114면 부품이 5면): 내보내는 전체 크기의 1% 하나로 모든 부품을 쿼드로 만들어서 작은 부품은 면 몇 개가 됐음. 이제 부품마다 쿼드 크기를 그 부품 대각선의 1/20 이하로, 그리고 결과가 원래 모양에서 벗어나면(부품 표면의 95%가 부품 크기의 0.5% 안에 있어야 함, 깨진 원본은 Fix Mesh한 모양과 비교) 3배 촘촘하게 다시(최대 4번). 그래도 안 맞으면 그 부품은 쿼드 대신 고친 원래 모양 그대로 내보내고 알려 줌.
  - 보내주신 FBX(오브젝트 71개): 모양 벗어난 부품 0개(모두 0.5% 안), 전체 344초(오브젝트당 약 5초).
  - 리메시 결과에 같은 점들로 된 면이 두 겹 생기면(FBX로 나갔다 들어오면 구멍) 하나만 남김.
- **VIEW Wire · Solo 버튼**(MECHA LAB 화면 오른쪽 위 MECHA LAB | ZBRUSH 카드의 세 번째 줄): **Wire** = 고른 부품(없으면 화면의 모든 부품)의 와이어프레임 켜기 / 끄기 — Make Quad · Quad Remesh 결과에 켜지던 와이어프레임을 오브젝트 속성 없이 끔. **Solo** = 고른 부품만 보기(블렌더 Local View, 다시 누르면 전부). 지브러시 화면은 원래 있던 PolyF · Solo 그대로. 오른쪽 도구 설정 패널은 카드와 겹치는 경우 카드 아래에서 시작.
- **Path Move(Whole) · Silhouette Move의 Extend가 Separate Tube로 빠지던 것**: 잡은 곳에서 단면을 자른 뒤 "뒤에 남는 면"을 셀 때, 엣지를 나눈 뒤 자른 엣지가 끝쪽 면에만 붙어 남으면 "뒤에 아무것도 없음"으로 잘못 판단했음(메쉬의 면 순서에 따라 — 쿼드 리메시한 부품에서 보였지만 평범한 원통에서도 재현). 이제 나누기 전에 둘레 면을 기억해서 셈.
- 테스트: Blender 5.2.3 bpy 전체 180개 파일 PASS 4,788 / FAIL 0(`tests/test_log_bpy523_v02477.txt`, FAILED FILES: none; 로그 안 Traceback 18개는 test_registration_recovery가 일부러 내는 것). 마지막 주석 한 줄 수정 뒤 다시 만든 zip으로 test_zip_install 19/19. 무작위 기능 조합 크래시 테스트 40개(시드 321~360): 40/40 정상(`tests/fuzz/fuzz_report.md`). 새 test_v02485_zbshading 10: 스무스 + Sharp 상자 → 지브러시 화면에서 Sharp 옆 48면 평면 · 가운데 6면 스무스 → 돌아오면 원래대로(속성도 안 남음), MECHA LAB ↔ ZBRUSH 버튼(사용자가 직접 평면으로 한 면은 그대로), 다른 방법으로 나가도 감시 타이머가 되돌림, 그 사이 면이 바뀌면 아무것도 안 함, 블렌더 스타일은 그대로, Sharp 없는 메쉬는 그대로. 새 test_v02486_exportfit 6: 큰 판 + 작은 베벨 원통을 내보내기 전체 1%로 → 둘 다 모양 유지(0.5% 안), 맞출 수 없으면 원래 모양(고친 것)으로. 새 test_v02487_wiresolo 12: 카드의 VIEW Wire / Solo 줄 · 켜짐 표시 · 아무것도 안 골랐을 때 모두 끄기 · 고른 부품만 · Solo는 고른 게 없으면 안내 · 창 없는 bpy에서 오류 없음 · 오른쪽 패널이 카드 아래 · 지브러시 화면은 그대로. 새 test_v02488_rimcorner 11: 판 관통 라인 컷 Chamfer / Bevel(고치기 전 바늘 점 있음 → 없음 · 닫힘 · 빠른 길), 모서리 맞춤 자체(가까운 점만 · 반대로 꺾이면 그대로), 깨진 부품(새 길 · Fix Mesh 안내 · 무너지면 예전 방식도), 경고 문구. 새 test_v02489_extendtip 7: 원통(분할 없음 / 3번 분할)을 옆에서 잡으면 끝이 잘려 나감 · Extend가 실제로 늘림(닫힘), 쿼드 리메시한 부품 세 높이, 열린 판은 예전처럼. 고친 기존 테스트: test_v02494(버전), test_v02479_fixmesh(내보내기 쿼드 크기 — 작은 나사도 부품 크기에 맞춰 200면 이상). 실제 블렌더 화면(GUI)에서 보이는 모습 · Solo(Local View) · 카드 모양은 미검증. ZIP sha256 `3e6835e7cb89ae80700832c03ffddfc3eb5b60d1335b7caa7baa7601fc9ae211`.

## 0.24.76 — Fix Mesh, 깨진 부품도 Make Quad / Quad Remesh, 쿼드로 내보내기, 꺾인 면 자르기(Steep Edges), 지브러시 Tab · X · 셰이딩 · 펜 우클릭 · 고른 SubTool 표시 · Re-make Quad가 컷 유지 · Alt / Emulate 3 Button · Silhouette Move · Select Box (2026-10-28)

- **Fix Mesh**(새 버튼: Mesh Tools 탭 · Remesh 도구 패널, 지브러시 Fix Mesh처럼): 겹쳐만 있고 안 붙은 점(틈)을 붙이고, 넓이 0인 찌그러진 면(불린 · n각형 쪼개기 찌꺼기)을 없애고, 같은 점에 겹친 면 · 합치면서 안에 남은 벽(면 3개가 붙은 엣지)을 지우고, 작은 구멍과 넓이 0인 실틈(T자 이음새)을 메우고, 노멀 방향을 맞춤. 큰 구멍은 Close All Holes로.
  - 보내주신 FBX(오브젝트 72개 중 깨진 것 22개: 겹친 점 수백 개 · 넓이 0인 면 수백 개 · 안쪽 벽): 16개 완전히 닫힘, 4개는 엣지 1개 남음, 2개는 큰 구멍(Close All Holes 필요).
- **Make Quad**(Remesh 도구의 예전 Flow / Patch): 열린 · 깨진 부품을 거절하던 것("open / non-manifold edges") 대신 먼저 Fix Mesh로 고치고 만듦. QuadriFlow(Flow)가 포기하면 Patch로 대신 하고 알려줌. 결과는 와이어프레임으로 보임. Faces가 1부터.
  - 보내주신 FBX 69개: 예전 Flow 27개 · Patch 20개 실패 → 지금 2개씩만 실패(큰 구멍 부품 등). 단, 예전 Patch는 목표 면 수를 크게 넘기고(4,000 → 16,000 ~ 27,000) 결과에 열린 엣지가 남는 경우가 있어 **새 Quad Remesh를 권장** — Remesh 도구 패널 맨 위에 새 Quad Remesh(Target · Mostly / All Quads · Fix Mesh) 상자를 넣음.
- **Silhouette Move**(새 도구, Move 그룹 · 아래 막대 Silhouette · V 파이 Move / Path 밑): Path Move인데 항상 Whole — 잡은 곳에서 부품 단면 전체를 끄는 길 따라 늘리고 휨(실루엣이 바뀜). 0.24.54에서 Path Move 기본이 Brush(브러시 크기만)로 바뀌기 전의 동작을 Tab 없이 바로. Method / Area / Back Mask는 고를 것이 없어서 패널 · Quick HUD에서 뺌. 새 아이콘.
- **Select = Select Box**: F · 아래 막대 Select · Q로 들어가는 선택이 블렌더 Select Box 도구(클릭 · 박스 선택, G / R / S로 이동 · 회전 · 크기). 전에는 Move 도구(기즈모). 지브러시 화면 Q 선택 모드는 그대로 Move 기즈모(조각 모드에는 오브젝트 박스 선택 도구가 없음).
- **Make Quad → Cut → Re-make Quad**에서 컷이 사라지던 것: Re-make가 숨겨 둔 원본(컷 전)으로 다시 만들어서 "아무것도 안 됨"처럼 보였음(0.24.75에서도 같은 순서로 재현 — 홈이 없어짐). 이제 쿼드 결과를 만든 뒤 바뀌었으면(컷 · 조각 등) 지금 메시로 다시 만들고, 바뀐 메시는 새 원본으로 숨겨 둠(이름 `…_Changed`, 처음 원본도 그대로). 안 바뀌었으면 예전처럼 원본에서. 0.24.75 이전에 만든 쿼드 결과는 바뀐 것으로 봄(잃는 것 없게). 새 엔진 Quad Remesh → Cut → Quad Remesh는 원래 제자리에서 되고 있었음(같은 순서로 확인).
- **Path Move Extend(Brush)가 부품을 통째로 뒤집던 것**: 쿼드 리메시한 부품 등에서 끌어낸 뒤 면 방향을 다시 맞출 때 블렌더가 가끔 전체를 안쪽으로 맞춤(부피가 음수 — 검게 보이고 다음 컷 · 불린이 깨짐). 이제 원래 부품의 방향(바깥)을 그대로 지킴. 0.24.71 · 0.24.75 · 지금을 같은 조건으로 비교: Whole(전체 단면) · Brush 모양은 세 버전이 똑같고, 뒤집힘만 쿼드 부품에서 나왔음.
- **Quad Remesh**(새 엔진): 깨진 입력은 복사본을 Fix Mesh로 고쳐서 리메쉬(열린 판의 원래 경계는 그대로). 결과는 와이어프레임으로 보임. Target이 0.001(= 면 1개)부터(전에는 50부터). 2배 촘촘하게 해도 구멍이 줄지 않으면 4배는 건너뜀(시간 절약).
- **내보내기(Export)**에 **Quad Mesh** 옵션: 내보내는 모든 오브젝트를 먼저 Fix Mesh + Quad Remesh(각진 엣지 유지)로 바꿔서 내보냄. **Quad Size**(내보내는 전체 크기의 %, 기본 1%)로 모든 부품이 같은 쿼드 크기(작은 나사는 면이 적게). **Client Look**을 켜면 각진 엣지에 좁은 베벨 + Subdivide까지 메쉬에 구워서 어느 프로그램에서도 똑같이 보임. 블렌더의 원래 메쉬는 그대로.
  - 보내주신 FBX 앞 20개: 58초(오브젝트당 약 3초), 원래 메쉬 그대로, 다시 불러오면 네모 87%, 20개 중 4개에 얇은 벽이 붙은 엣지 남음.
- **꺾인 면 자르기**(Base Mesh Alt Height / Ramp, Cut Ramp): 꺾인 표면 위에서는 평평한 면마다 그 면과 나란한 바닥을 만들고 만나는 곳은 날카롭게 — 촘촘한 격자 + 부드럽게 섞인 노멀 대신(바닥이 지저분하고 면이 수백 ~ 수천 개). 안 맞는 경우(곡면 · 조각 48개 넘음 · Chamfer / Bevel 테두리 · Through · 불린 실패)는 예전 방식으로 자동 전환.
  - **Steep Edges** 옵션(Base Mesh Alt 패널 · Cut의 GN Edge > Ramp): **Even**(기본) = 모든 면에 같은 깊이(가파른 옆면으로 홈이 더 내려감), **Limit** = 보는 방향으로 같은 깊이(정면으로 보이는 면 기준, 돌아간 가파른 면은 얕게 — 예전처럼).
  - 시험본과 같은 결과(꺾인 모서리 40건 똑같음), 가장 느린 경우(둥근 모서리 41조각 + Soft) 3.3초 → 0.9초.
  - Ramp Soft: 둥글게 올라가는 옆 띠를 따라 벽과 나란한 선을 넣음(전에는 가로줄 위에만 점이 있어서 긴 삼각형이 띠를 가로질러 옆면에 톱니가 생기고 가운데가 얕았음 — 전체 테스트에서 걸림). 긴 경사에서 예전 방식만큼 매끄럽고(굴곡 0.0001) 면은 19,942 → 1,177개.
- **지브러시 화면**:
  - **X 대칭**이 실제로 켜짐: 블렌더 5에서 조각 대칭은 메쉬의 Mirror X인데 예전 설정을 바꾸고 있어서 버튼만 켜지고 대칭은 안 됐음. 텍스처 스탬프 대칭도 같이.
  - **Tab**: MECHA LAB 탭에서 MECHA LAB(오브젝트 모드) ↔ ZBRUSH(조각 모드). 다른 탭은 블렌더의 Tab(편집 모드) 그대로.
  - **Q** = 브러시 ↔ 선택 모드(블렌더 Move 기즈모, Alt+클릭으로 다른 SubTool 선택), 선택 모드에서 **G / R / S** = 이동 / 회전 / 크기 기즈모(브러시일 때 S는 예전처럼 Draw Size).
  - **펜 우클릭**: 펜 옆 버튼을 누르는 순간 펜촉이 흔들려(14px 넘게) 클릭이 화면 회전으로 바뀌고 메뉴가 안 나오던 것 — 누르고 0.25초 안에 60px 안쪽으로 움직인 건 클릭으로 봄(오래 누르고 끌면 예전처럼 회전, 마우스는 그대로). 지브러시와 MECHA LAB 우클릭 메뉴 둘 다.
  - **고른 SubTool이 눈에 띄게**: 지브러시 화면에서는 블렌더의 Fade Inactive Geometry(다른 오브젝트를 배경색 쪽으로 반쯤 흐리게)를 켜서 지금 조각 중인 오브젝트만 밝게 보임. 지브러시 화면을 나가면 원래대로.
  - **Alt 빼기가 안 되고 우클릭 같은 팝업이 뜨는 문제**(Base Mesh Alt 빼기 · 지브러시 Alt = Zsub · 스케치 Alt 구멍): **원인 아직 못 찾음**(화면 없는 시험에서는 0.24.71 · 0.24.75 · 지금 모두 정상, 사용자 확인: Emulate 3 Button Mouse 꺼짐 · 블렌더 5.2만). 대신 넣은 것:
    - 메뉴가 열리면 **무엇이 열었는지** 화면 아래 상태 줄과 System Console에 표시("Mecha Menu (Ctrl + Alt held)" / "middle click" / "right click in the tool" / "right click (Select)" + 그때 키 상태) — 다음에 팝업이 뜨면 이 글자로 원인을 바로 알 수 있음.
    - Ctrl + Alt 홀드 메뉴: Ctrl과 Alt가 **둘 다 실제로 눌려 있는지** 마우스가 움직일 때마다 확인(전에는 한 번 시작되면 두 키를 다 누른 것으로 여겨서, 한쪽 떼기를 놓치면 Alt만 누르고 있어도 0.35초 뒤 메뉴가 떴음).
    - 블렌더의 Emulate 3 Button Mouse가 켜져 있으면(Alt+클릭이 가운데 클릭으로 바뀜) 가운데 클릭 메뉴를 열지 않고 패널 · 지브러시 키 안내에 경고(블렌더 설정은 읽기만).
  - 지브러시 화면으로 가면 셰이딩이 부드럽게 바뀌던 것: High Poly Mode가 블렌더의 Deform Only를 켜서 Smooth by Angle(자동 스무스)이 꺼졌던 것 — 이제 Deform Only는 건드리지 않음(Delay Viewport Updates 등은 그대로).
- 테스트: Blender 5.2.3 bpy 전체 175개 파일 PASS 4,742 / FAIL 0(`tests/test_log_bpy523_v02476.txt`, FAILED FILES: none). 새 test_v02479_fixmesh 34: Fix Mesh(틈 · 넓이 0인 면 · 안쪽 벽 · 빠진 면 · 열린 판 경계 유지 · Close All Holes · 깨끗한 상자 그대로 · 버튼 2곳), Make Quad(깨진 부품 → 만들어짐 · 닫힘 · 와이어프레임 · 수리 알림 · Flow 실패 → Patch), Quad Remesh(깨진 부품 고친 복사본 · 닫힘 · 와이어프레임 · 복사본 안 남음 · 깨끗하면 수리 없음), Export(파일 · 원래 메쉬 그대로 · 임시 오브젝트 없음 · 세 부품 · 네모 · 닫힘 · 같은 쿼드 크기 · Client Look 면 수 · 모두 스무스). 새 test_v02480_facetcarve 20: 지붕(조각 2개 · 닫힘 · 바닥 깊이 1% 안 · 능선 날카로움 · 부피), Ramp · Ramp Soft, Steep Edges(Limit이 덜 깎음 · 같은 두 면이면 같음 · 평면 하나면 같음), 예전 방식 전환(곡면 · Chamfer · 꺼짐), Base Mesh Alt · Cut Ramp 실제 경로, 패널 표시 2곳. 새 test_v02481_keys 17: X 대칭(메쉬 Mirror X · 스탬프), Tab(키맵 2곳 · 다른 탭은 블렌더 · 오브젝트 ↔ 조각), High Poly가 Deform Only 안 건드림, 면 1개부터(Faces · Target · 12 / 37면 상자). 새 test_v02484_silhouette 15 (Silhouette Move는 아래 막대 대신 도구 목록 · V 파이 · 메뉴에 — 아래 막대가 넓어지지 않게): 도구(이름 · 아이콘 · 블렌더 도구 · Move 그룹 · 저장 번호 56 · 아래 막대 · V 파이 · 키 안내 · Quick HUD · 패널), 항상 Whole + Extend(Path Move 설정과 무관 · Tab 무시 · Path Move 자체는 그대로), 실제 동작(부품이 길어지고 휨 · 닫힘 · 바깥 방향), Select = Select Box(코드 · 실제 전환). 새 test_v02483_quadcut_alt 19: Path Move Brush를 쿼드 부품에서(닫힘 · 바깥 방향 유지 — 고치기 전 부피 -0.598), Make Quad → Cut → Re-make(홈 그대로 · 닫힘 · 바뀐 메시가 새 원본 · 처음 원본 그대로 · 쿼드 Bevel 안 구움 · 그 뒤 설정만 바꿔 Re-make해도 홈 그대로 · 안 바뀐 결과는 원본에서 · 지문 없는 옛 결과는 바뀐 것 · Apply로 지문 지움 · 패널), 새 엔진 Quad Remesh → Cut → Quad Remesh(홈 그대로 · 닫힘), Emulate 3 Button Mouse(꺼짐: 가운데 클릭 메뉴 · 키 안내 그대로 / 켜짐: 메뉴 안 열림 · 키 안내 · 패널 경고 · 설정 안 바꿈). 새 test_v02482_penfade 15: 펜 우클릭(빨리 42px 흔들림 = 클릭 · 놓으면 메뉴 · 잠깐 누른 뒤 42px = 회전 · 80px = 회전 · 10px = 클릭 · 마우스 그대로), 고른 SubTool(지브러시 화면에서 흐리게 켜짐 · 한 번만 · 나가면 원래대로 · 원래 켜 둔 사람은 그대로 · 애드온 끄면 원래대로 · 감시 타이머), Ramp Soft 긴 경사(옆 띠 · 가운데 매끄러움 0.0008 미만 · 닫힘 · 면 4,000 미만 — 고치기 전 0.0098). 테스트 도구: run_all이 파일 안의 FAIL 줄도 실패로 셈(전에는 끝 코드만 봐서 test_v02467의 FAIL이 "FAILED FILES"에 안 나왔음). 고친 기존 테스트(Silhouette Move 추가로): test_v02437(V 파이 Primitive 밑 맨 앞 두 개), test_v02474 · test_v02463(드래그의 Brush / Whole을 도구에서 읽음), test_v02489(도구 줄이 아래 툴바를 피하는 검사는 툴바가 켜진 상태로 — 도구가 하나 늘어 우연히 맞던 높이를 넘음). 고친 기존 테스트: test_v02473(Live Ramp 레이아웃 재사용은 예전 방식에서 확인 — 평평한 윗면은 이제 꺾인 면 자르기라 레이아웃 자체가 없음), test_v02494(High Poly Mode: Deform Only 대신 Delay Updates로 확인, 버전), test_v02492(S 키 = Draw Size / Scale 기즈모). 무작위 기능 조합 크래시 테스트 40개(시드 281~320): 정상 38 · 크래시 1 · 시간 초과 1 — 둘 다 0.24.75 코드로도 똑같이 재현되는 예전 문제(시드 282: High Poly 34만 면 → Hard Edges 설정 → Ctrl+Z에서 창 없는 bpy가 죽음; 시드 291: 10만 면 부품 Find Edges가 혼자 703초 — 0.24.75 717초, 제한 600초 초과)(`tests/fuzz/fuzz_report.md`). 실제 블렌더 화면(GUI) · 실제 펜 우클릭 · 흐리게 보이는 모습은 미검증. ZIP sha256 `b2c5318632879d334a970204a7c3d1b9b9715c89447b2d8ea0980c6c39e32229`.

## 0.24.75 — Quad Remesh: 컷 / Base Mesh로 만든 가벼운 부품을 그 엣지 그대로 쿼드로 (2026-10-28)

- **Quad Remesh**(지브러시 선반 · Mesh Tools 탭, 버튼 · 설정 그대로): 가벼운 입력(원하는 면 수의 20배 이하 삼각형 — Base Mesh + Cut으로 만든 n각형 부품, 데시메이트한 부품)은 자동으로 새 방식.
  - 먼저 **고른 삼각형**으로 깔기: 부품의 점과 엣지는 정확히 그대로, 긴 엣지에는 쿼드 크기 간격으로 점, 각 면은 자기 평면 위에서 그 간격의 점으로 채움(이미 작은 면은 원래 삼각형 그대로). 전에는 n각형을 부채꼴로 자른 길고 얇은 삼각형을 그대로 써서 엣지를 놓치고 이음새가 열렸음.
  - 부품 자신의 각진 엣지가 쿼드 줄의 고정선(Hard Edges 각도 이상).
  - 쿼드 한 칸보다 좁은 홈 때문에 구멍이 남으면 2배 · 4배 촘촘하게 다시(가장 구멍 적은 것). 그래도 남은 틈은 메움: 겹친 틈은 점을 붙이고, 매달린 면 · 3면 엣지(핀)는 지우고 다시 채움. 열린 판의 원래 경계는 그대로(메우지 않음).
  - 재질 · 폴리그룹(면) · 마스크 · 점 색(점)이 따라옴. 메시지에 "(low-poly part: its own edges kept …)".
- 무작위 컷 부품 99개(Base Mesh + Cut · Line Cut · Boolean · Ramp, DynaMesh 없음), 목표 1,500면: 새 방식 98개 — 닫힘 93개(나머지 5개: 입력부터 열린 부품 2개 · 0.02 크기 조각 1개 · 얇은 벽이 붙은 엣지 1~3개 2개), 네모 평균 94.6%(최저 84%), 표면 오차 중간값 부품 크기의 0.14%(최대 4.1% 한 부품), 시간 중간값 0.8초(최대 약 10초, 테스트와 동시 실행), 2배 촘촘 12개 · 4배 4개 · 틈 메움 7개.
  - 같은 12개 부품에서 예전 방식: 열린 엣지 77~713개 · 네모 61~93% · 1~8초 → 새 방식: 열린 엣지 0 · 네모 92~99% · 표면 오차 0.65% 이하 · 0.6~2.1초.
  - 데시메이트한 부품(DynaMesh → Decimate 6%)은 예전과 비슷(네모 같거나 조금 많음, 0.1~0.3초 더 걸림). 3만 삼각형 DynaMesh → 5,000면: 1.8초 → 2.2초.
- **엣지 선이 중간에 끊기는 이유**(주황 하드 엣지, 12개 부품 측정): 컷 엣지 길이의 평균 94%가 하드 엣지로 이어짐. 끊기는 곳은 ① 두 엣지가 쿼드 한 칸보다 가까운 좁은 띠(평균 2.4%, 부품에 따라 최대 14%) — 한 줄의 쿼드는 두 선 중 하나만 따라갈 수 있음 ② 여러 엣지가 만나는 모서리(1.6%) — 쿼드 격자의 특이점(엣지 3개 · 5개 점)이 그 근처에 생김 ③ 30~40°로 얕게 꺾인 엣지(1.4%, 램프 바닥 등) ④ 쿼드 1.5칸보다 짧은 엣지는 일부러 뺌(1.2%, 잡음 방지). Target을 올리면 ①이, Hard Edges 각도를 낮추면 ③이 줄어듦. 좁은 곳만 작은 쿼드(적응형)는 다음 단계 후보.
- 테스트: Blender 5.2.3 bpy 전체 169개 파일 PASS 4,619 / FAIL 0(`tests/test_log_bpy523_v02475.txt`). 새 test_v02478_cutquad 16: 컷 부품이 새 방식 · 메시지 · 닫힘(같은 부품에서 예전 방식은 열린 엣지 330 — 검사가 구별함) · 네모 98%(예전 65%) · 표면 오차 0.07% · 면 수 · 컷 엣지 100% 하드 엣지 · 0.7초 · 같은 메쉬 같은 결과 · 재질(입력 면과 100% 일치) · 마스크 · 쿼드보다 좁은 홈(2배로 다시, 닫힘) · All Quads 100% · 열린 판 경계 유지 · 데시메이트 부품 · 촘촘한 DynaMesh는 예전 방식. 고친 기존 테스트: test_v02494(버전). 무작위 기능 조합 크래시 테스트 40개(시드 241~280): 40/40 정상(`tests/fuzz/fuzz_report.md`). 새 0.24.75 zip을 Extensions 설치(Install from Disk와 같은 경로) 19/19(전체 테스트 안의 test_zip_install). 실제 블렌더 화면(GUI)은 미검증. ZIP sha256 `a67e9204eb3732c2cfa38cbe2ebd1e745fc7c7542659f81ee5f1f97c53bc85f5`.

## 0.24.74 — Edge Mesh: Auto Detail(크기 · 복잡도에 맞춰 자동), Match Original(원본 둥글기에 맞춘 엣지별 베벨), 엔진 접힘 수정 (2026-10-28)

- **Auto Detail**(Edge Mesh 상자 · Mesh Tools, 기본 켜짐) + **Tolerance**(기본 부품 크기의 0.006%): Detail을 직접 고르지 않아도 줄인 메쉬가 원본에서 Tolerance보다 벗어나기 직전까지 줄임 → 단순한 부품은 가볍게, 디테일 많은 부품은 촘촘하게. 찾은 수는 Detail 칸에 적힘.
  - 재는 법: 원본 점 2만 개에서 줄인 메쉬까지 거리의 99% 값(각진 엣지에 닿지 않는 평면 · 곡면 점은 0.3배 — Fit to Original이 원본 모양으로 다시 붙이니까). 3만 삼각형 아래부터 단계마다 잼.
  - 두 번 줄이지 않음: 보통 단계로 내려가며 수를 찾고, 그 수의 8배 이상이던 단계부터 마지막 단계(Adaptive · 고른 삼각형)만 다시 → 결과는 그 수를 Detail에 직접 넣었을 때와 똑같음(테스트로 확인).
  - 사용자 FBX(1,358,168 삼각형) → **2,098**(전에 눈으로 고른 2,000과 거의 같음, 15초). 로봇 부품 5개: 허벅지 788 · 머리 5,660 · 골반 2,432 · 몸통 4,832 · 위팔 588.
  - Half / Double: 찾은 수의 절반 / 두 배로 Auto를 끄고 직접.
- **Match Original**(Fit to Original 옆, 기본 켜짐): 엣지마다 원본이 얼마나 둥근지 재서 그만큼의 베벨 — 원본에서 날카로운 엣지는 Width 그대로, 둥글게 깎인 엣지는 넓게(최대 부품 크기의 5%). Width는 "가장 얇은 베벨", 수정자 Width는 가장 넓은 엣지에 맞추고 나머지는 가중치로. 끄면 예전처럼 Width 하나.
  - 재는 법: 엣지 양옆 원본의 평평한 곳(원본 법선이 그 면과 25° 안인 가장 먼 곳)에서 두 평면을 읽고 → 두 평면이 만나는 "날카로운 모서리"와 원본 표면 사이 거리 d → 둥근 반지름이 남기는 거리 공식으로 베벨 폭 = d · cot(꺾임각/4). 엣지 위 세 곳의 가운데 값, 같은 선의 앞뒤 엣지와 가운데 값(한 선은 한 폭). 시험 블록(반지름 0 / 0.006 / 0.015): 0 / 약 0.004 / 약 0.008~0.011.
- **데시메이트 엔진: 얇은 삼각형 옆 면 접힘**: 한 줄 위의 세 점(n각형을 단순 분할한 메쉬에 많음)으로 된 삼각형은 법선이 잡음이라 뒤집힘 검사를 그냥 통과했음 → 그런 면은 주변 면들의 평균 방향과 비교. 로봇 몸통(4만 삼각형 → 3,000): 접힌 엣지 6 → 0, 같은 몸통 65만 삼각형 → 3,000: 31 → 6. 속도 차이 5~10%. AddressSanitizer + UBSan(1 · 4스레드, 고른 삼각형 켬 / 끔) 오류 · 누수 없음.
- 고른 삼각형 단계가 얇은 삼각형 많은 메쉬에서 막히면(예: 86k → 목표 18k인데 27k에서 멈춤) 그 단계만 보통 데시메이트로.
- 베벨 없이(크리즈만 / 크리즈도 없이) 비교 렌더: 크리즈만 쓰면 모서리 옆 면이 살짝 울퉁불퉁, 크리즈 없이는 FBX가 많이 뭉개짐 → 얇은 보조 베벨이 기본 그대로.
- 테스트: Blender 5.2.3 bpy 전체 168개 파일 PASS 4,603 / FAIL 0(`tests/test_log_bpy523_v02474.txt`). 새 test_v02477_edgematch 13: 원본에서 날카로운 모서리 ~0 · 둥근 모서리(반지름 0.006 / 0.015)는 Width보다 넓고 둥근 쪽이 더 넓음 · 위 날카로운 엣지 ~0 · 수정자 Width = 가장 넓은 엣지, 날카로운 엣지 가중치 = Width / 그것 · Match 끄면 Width 하나 · Apply로 측정값 정리 · Auto: 평범한 상자는 바로 바닥까지, 둥근 블록은 더 남김 · Tolerance 4배면 더 적게 · 8배 이상 단계에서 이어받음 · 오브젝트에서 Detail 칸에 기록 + "(Auto)" · 같은 수로 직접 한 것과 똑같음 · Double = 두 배 + Auto 꺼짐 · 엔진: 로봇 몸통 접힘 0(이전 엔진 6, 같은 테스트 실패 확인). 고친 기존 테스트: test_v02474(Auto · Match 끄고 기존 검사, Half가 Auto를 끄는지), test_v02475(Auto 끔), test_v02494(버전). 무작위 기능 조합 크래시 테스트 40개(시드 201~240, Edge Mesh에 Auto · Match 무작위 켜기 추가): 40/40 정상(`tests/fuzz/fuzz_report.md`). 새 zip을 Extensions 설치(Install from Disk와 같은 경로) 19/19 + 엔진 로드 · 새 설정 · Mesh Tools 패널 확인. 실제 블렌더 화면(GUI)과 Windows DLL 실행(이번엔 Wine 없음 — 빌드 · 내보내기 함수 · KERNEL32 + msvcrt만 확인)은 미검증. ZIP sha256 `d62f893a3f0214f76314c666f967731d4691155e15e082e4b8e9209bf0167c4a`.

## 0.24.73 — Edge Mesh(데시메이트로 엣지 추적 → 클라이언트 룩), Mesh Tools 탭, 크래시 대비 (2026-10-28)

- **새 Edge Mesh**(지브러시 왼쪽 선반, Hard Edges 위 상자 + Mecha Lab 탭 Mesh Tools): 촘촘한 메쉬(DynaMesh · 조각 · FBX)를 **데시메이트를 여러 번 누르듯 단계적으로 줄여서**(매 단계 오차를 새로 계산 → 평면부터 비고 엣지가 드러남) Detail(기본 2,000) 삼각형까지 → 각진 엣지 찾기 → 평면은 쿼드로 잇기(어려운 곳은 삼각형) → 라이브 **보조 베벨 + Subdivide + Fit to Original**.
  - **Adaptive**: 마지막 단계에서 엣지 선이 꺾이는 점(둥근 끝 · 모서리)은 덜 지움 — 둥근 끝이 V자로 뾰족해지지 않음. **Straighten**: 엣지 선의 작은 지그재그를 폄(급한 꺾임은 그대로). 마지막 단계는 삼각형을 둥글게(가는 삼각형이 엣지 옆을 막지 않게).
  - **Fit to Original**: 섭디 표면을 원래 촘촘한 메쉬에 다시 붙임(엣지는 그대로). 원본은 씬 밖에 보관(어느 씬에도 없음 → 화면에 안 보이고 FBX로 안 나감), Apply / Clear 하면 지워짐. 다시 Edge Mesh를 누르면 보관한 원본에서 다시 만듦(Detail을 바꿔 다시 하기).
  - 사용자 FBX(679,100점): 2,000 삼각형까지 30단계 10~15초, 클라이언트 메쉬 커스텀 노멀 · 샤프 없음(마야 · 맥스 · 지브러시에서 같게 보임).
- **베벨이 원하는 두께로**: 블렌더 베벨의 Clamp Overlap은 부품에서 가장 좁은 곳 하나에 맞춰 **모든** 베벨을 줄였음(1.2% 요청 → 실제 0.1%). 이제 블렌더와 같은 겹침 계산을 엣지마다 해서 좁은 곳만 얇게, 나머지는 Width 그대로. 시험 실행으로 겹침이 없을 때만 Clamp를 끄고, 남은 곳은 주변 베벨만 반씩 줄여 다시 시험. 안쪽 모서리는 Width의 40%(넓으면 접혀서 금이 감). 짧게 끊긴 엣지 조각(데시메이트 흔적)은 엣지에서 뺌.
- **Bevel Style Round / Chamfer**: Chamfer = 평평하게 깎은 면 + 양쪽 보조선(섭디 뒤에도 각이 살아 있음).
- **Mecha Lab 탭 Mesh Tools**(사이드바, Select 모드): DynaMesh · Decimate · Quad Remesh · Edge Mesh · Find Edges · Apply · Clear를 오브젝트 모드에서 **선택한 메쉬 전부**에 한 번에(지브러시 선반과 같은 설정). 안 되는 메쉬는 이유와 함께 건너뜀.
- **크래시 테스트 100개(무작위 기능 조합, 하나씩 따로)**: 처음 10개 크래시 중 8개는 시험 스크립트 실수(Ctrl+Z 뒤 지난 설정 참조), 2개는 블렌더 되돌리기 버그 — add-on이 피하도록 수정:
  - 조각 모드에서는 add-on이 되돌리기 단계를 만들지 않음(빈 조각 단계가 다른 조각 단계 바로 뒤에 오면 이후 Ctrl+Z에서 블렌더가 죽음 — add-on 없이도 재현).
  - 선반 버튼이 아무것도 바꾸지 않았으면 두 번째 같은 단계를 만들지 않음(같은 단계 3개 연속 → Ctrl+Z에서 죽음). Ctrl+Z 한 번에 조각 모드 그대로 이전 메쉬(0.24.69)는 유지.
  - Divide 메모리 예측을 실측(Multires 단계 면당 약 45KB 상주)에 맞춤 — 58k DynaMesh를 두 번 Divide하면 메모리가 넘쳤음.
  - 수정 후 시드 101~200: 100/100 정상, 크래시 0.
- **왼쪽 선반 스크롤**: 휠이 끝을 지나서도 값이 계속 늘어 위로 올릴 때 한동안 안 움직이던 것(가끔 안 되던 원인), 빈 곳을 드래그하면 스크롤(사이드 패널 · Layers 패널도).
- **코드 리뷰 2단계(속도)**: 라이브 슬라이더 재구성을 자기 비용에 맞춘 간격으로(Base Mesh · Face Extract, 드래그 중 매 픽셀마다 전체 재구성하던 것), Curve Repeat 원본 변경 감지(점 하나 위 · 하나 아래로 움직이면 놓치던 것), 쿼드 Patch 거리 계산을 나눠서(메모리 폭증), 하드 엣지가 전부 사라지면 손실 0으로 재던 것, Find Edges + Merge Flats 19만 삼각형 29초 → 0.6초(같은 결과).
- **코드 리뷰 3단계(측정)**: Cut 39만 면 4.6초 중 블렌더 불리언(C) 2.4초 — 파이썬 쪽 느린 부분(면마다 도는 검사)만 고쳐 3.6초(-21%). Concept Move 16만 점 한 프레임: 계산 13ms, 메쉬 쓰기 · 갱신(블렌더) 28ms → C로 옮겨도 체감 이득 적음(안 옮김).
- Hard Edges 슬라이더(Width · Segments …)도 같은 간격 조절(드래그마다 겹침 시험이 돌아 큰 메쉬가 버벅일 수 있었음), 겹침 시험은 3만 면 이하에서만.
- 테스트: Blender 5.2.3 bpy 전체 167개 파일 4,588 통과 + 1 실패(test_v02471의 소스 문자열 검사가 바뀐 되돌리기 함수 이름을 못 찾음 → 검사 수정 후 19/19, `tests/test_log_bpy523_v02473.txt`), 마지막 수정(Hard Edges 슬라이더 간격) 뒤 관련 7개 파일 재실행 모두 통과(`tests/test_log_bpy523_v02473_after.txt`). 새 테스트: test_v02474_edgemesh 25 · test_v02475_meshtools 14 · test_v02476_speed 12. 무작위 기능 조합 크래시 테스트 200개(시드 1~200, `tests/fuzz/`): 수정 후 200/200 정상. zip을 Extensions 설치(Install from Disk와 같은 경로)로 설치 · 켜기 · 엔진 로드 · Mesh Tools 패널 등록 확인. 실제 블렌더 화면(GUI)은 미검증. ZIP sha256 `8156539df88ce0cc6f07c47861df15f4ec1eca90ba8570c507d485cfa8aec54a`.

## 0.24.72 — 지브러시 Hard Edges: 엣지 찾기 → 크리즈 → 조절되는 베벨 (2026-10-27)

- **새 Hard Edges 상자**(지브러시 화면 왼쪽 선반, Quad Remesh 아래 따로).
  - **Find Edges** + **Angle**(기본 30°): 면이 이 각도보다 꺾인 엣지(와 열린 경계)를 찾아 Sharp + **Crease** + 베벨 가중치. 혼자 떨어진 짧은 엣지 하나(잡음)는 뺌.
  - **Merge Flats**: 삼각형 메쉬(데시메이트 결과)면 각진 엣지 사이의 평평한 삼각형을 큰 면으로 합쳐서 베벨이 깨끗하게 — 쿼드(Quad Remesh 결과)는 그대로 둠.
  - 라이브로 계속 조절: **Bevel**(켜기 / 끄기) · **Width** · **Segments**(1 = 챔퍼) · **Shape**(0.5 둥글게, 크면 각지게, 작으면 오목하게) · **Outer Only**(바깥쪽으로 꺾인 엣지만, 안쪽 모서리는 날카롭게) · **Crease** · **Subdivide**(Catmull-Clark 단계: 크리즈 엣지는 날카롭게, 평면은 면이 늘어남) · **Weighted Normals**(베벨 옆 평면이 평평하게 보이게).
  - **Apply**: 라이브 베벨 / 섭디를 메쉬에 굽기. **Clear**: 표시와 라이브 수정자 지우기.
- 흐름: DynaMesh → Decimate(또는 Quad Remesh) → Find Edges → 슬라이더로 베벨 조절 → Apply. 30만 면 넘는 메쉬는 먼저 줄이라고 안내(그대로 베벨하면 블렌더가 오래 멈춤).
- 측정(헤드리스): 사용자 FBX 679,100점 → Decimate 2%(27,162면) → Find Edges 0.2초: 각진 엣지 3,358개, 평면 합치기로 4,480면, 라이브 베벨 13,010면. Quad Remesh 10k → Find Edges 0.04초(쿼드 그대로) → 베벨 + Subdivide 1 → 56,342면.
- Find Edges / Apply 직전 Safety Save 사본, Ctrl+Z 한 번에 원래대로(조각 모드 그대로).
- 테스트: Blender 5.2.3 bpy 전체 163개 파일 4,508/4,508 통과(`tests/test_log_bpy523_v02472.txt`). 새 test_v02472_hardedges 32개(상자 12엣지 · 크리즈 / 베벨 가중치 · 챔퍼 26면 · 슬라이더 즉시 반영 · Subdivide에서 크리즈 유지 / 끄면 둥글게 · Outer Only(L자 안쪽 모서리) · 데시메이트 부품: 평면 합치기 · 닫힘 · 원래 크리즈 위 · 쿼드 메쉬는 쿼드 유지 · Apply · Clear · 선반 상자 · 실제 Ctrl+Z · 30만 면 안내). 실제 블렌더 화면(슬라이더 손맛 · 셰이딩)은 미검증. ZIP sha256 `8759fb511e9f91abaf05b9df1574e4cd5e11e14c611153f54566b98231fe11ac`.

## 0.24.71 — 지브러시 Quad Remesh: 우리 엔진으로 만든 쿼드 리메쉬 (2026-10-27)

- **새 Quad Remesh 상자**(지브러시 화면 왼쪽 선반, Decimation 아래 따로): Quad Remesh 버튼 + Target(천 단위), **Mostly Quads**(네모 + 줄이 끝나는 곳에 삼각형 조금) / **All Quads**(전부 네모: 1/4 개수로 만든 뒤 모든 면을 한 번 나눔), **Hard Edges**(면이 이 각도보다 꺾이면 각진 엣지 — 네모 줄이 그 엣지를 따라가고 날카롭게 남음, 기본 30°), Half / Same / Double(지금 면 수 기준으로 Target 맞추기). 블렌더 Quadriflow(기존 ZRemesher 버튼)와는 별개.
- 방식: 블렌더 쿼드 기능을 쓰지 않음 — 우리 데시메이트 엔진의 "고른 간격" 모드로 부품을 여러 해상도로 고르게 샘플링 → 방향 · 격자 위치 계산(Instant Meshes 논문 공식, 각진 엣지와 열린 경계는 제약) → 같은 격자점끼리 합치고 한 칸 떨어진 것은 엣지 → 면 만들기(네모 먼저) → 원래 표면에 다시 붙임. 전부 C 엔진(같은 DLL, 멀티스레드): 파이썬 시제품보다 약 10배 빠름.
- 결과(헤드리스 측정): 하드서피스 시험 부품 158k 삼각형 → 2,963면 1.7초, 네모 98%, 점의 97%가 엣지 4개, 구멍 · 3면 엣지 0, 원래 각진 엣지의 94%가 쿼드의 각진 엣지 위. 사용자 FBX(679,100점) → 2,620면 5초(네모 93%) / 10,202면 8.7초(96%) / All Quads 10,294면 5.4초(100%), 모두 구멍 · 3면 엣지 0(4코어 기준, 대부분은 데시메이트 단계).
- 폴리그룹 · 재질 · 마스크 · 점 색이 따라옴(UV는 새 토폴로지라 없어짐). 12면 상자처럼 거친 메쉬는 먼저 나눠서 처리, 열린 판은 경계를 그대로 둠(메우지 않음). Ctrl+Z 한 번에 원래 메쉬(조각 모드), 실행 직전 Safety Save 사본.
- 알려진 한계: 쿼드 한 칸보다 좁은 챔퍼 · 얕게 솟은 패널은 Target이 작으면 뭉개짐(Target을 올리면 살아남) — 좁은 곳에서 쿼드가 작아지는 적응형은 다음 단계 후보.
- 데시메이트 엔진 4: 고른 간격 모드(짧은 엣지부터 + 가운데 배치, 기본 꺼짐 — 기존 Decimate 동작 그대로).
- 테스트: Blender 5.2.3 bpy 전체 162개 파일 4,476/4,476 통과(`tests/test_log_bpy523_v02471.txt`). 새 test_v02471_quad 27개(엔진 / Windows DLL 내보내기 · 목표 면 수 · 네모 비율 · 닫힘 · 표면 오차 · 각진 엣지 유지 · 속도 · 같은 결과 · All Quads · 폴리그룹 / 재질 / 마스크 · 거친 상자 · 열린 판 · 선반 상자 / 버튼 · Half · 선반에서 실행 + 실제 Ctrl+Z · Shape Key / Multires 안내), test_v02498 26/26(새: 고른 간격). C 엔진은 AddressSanitizer + UBSan에서 오류 / 메모리 누수 없음, 1 · 4스레드 같은 결과, Windows DLL은 Wine 9.0에서 같은 점 / 면 수. 실제 블렌더 화면(선반 버튼 클릭 · 걸리는 시간 · Windows 16코어 속도)은 미검증. ZIP sha256 `abb4d8d9e51a5419db176bcbfdaeed7c02b09e01a2b1f61c20db4932a4479821`.

## 0.24.70 — 데시메이트: 한 번에 많이 줄여도 무너지지 않음, 평평한 부품 12배 빠르게 (2026-10-27)

- **한 번에 아주 많이 줄이면 모양이 무너지던 것**(사용자 FBX 679,100점 → 281점을 한 번에: 부피 -29 ~ -49%): 코어마다 나눈 블록을 거의 0까지 줄이며 블록 경계 근처가 가늘고 긴 삼각형으로 망가졌음 — 블록 단계는 5%까지만, 나머지는 전체를 한 번에 → 부피 -0.1 ~ -0.2%, 속도 그대로(1.8 ~ 2.8초). 86%로 여러 번 누르는 방식(52번 → 281점: 오차 평균 0.009%)과 같은 품질.
- **평평한 면이 많은 부품이 느리던 것**(복셀 부품 357k 삼각형: 7초): 평면에서는 모든 줄이기의 오차가 0이라 순서가 없어 가는 삼각형이 쌓이고 헛돌았음 — 삼각형 모양에 작은 가중치를 둬서 0.6초(12배), 오차 거의 같음(곡면 기준 +1.6%), 가는 삼각형 46% → 10%.
- (준비 중, 아직 버튼 없음) Hard Edges: 데시메이트 결과에서 각진 엣지 찾기 → 크리즈 / 샤프 / 베벨 가중치, 라이브 베벨 · 섭디 · Weighted Normals. 쿼드 리메쉬는 데시메이트 엔진 기반으로 새로 만드는 중.
- 테스트: Blender 5.2.3 bpy — test_v02498 25/25(새: 327,680 → 300 한 번에 4코어, 부피 3% 안; 0.24.69 엔진은 0.929로 실패), test_v02492 80/80, test_v02494 34/34, test_v02469_zbfix 14/14(`tests/test_log_v02470_decimate.txt`). Windows DLL은 Wine에서 극단 비율 · 보통 비율 확인. ZIP sha256 `a3be1182b4aab482207c0a7693d12aa6c46ef57dc6722a01c3dd305db505796d`.

## 0.24.69 — 구멍 챔퍼 렉, 지브러시 Extract · Clip / Trim, 외곽 스트로크, 데시메이트 후 Ctrl+Z (2026-10-27)

- **구멍 하나 뚫는데 렉(GN Edge Chamfer)**: 깎아낼 띠를 먼저 검사해서 스스로 겹치지 않으면 정밀(Exact) 합치기를 건너뜀 — 구멍 하나 0.45~0.95초 → 0.05~0.06초(같은 모양). 챔퍼 폭이 작은 구멍의 반지름보다 크면 반지름의 약 0.8배까지만(양쪽 띠가 구멍 한가운데서 엉켜 찌그러진 깔때기가 됐음), 작은 구멍 · 짧은 슬롯은 둘레 전체 같은 폭(모서리 쪽만 좁아지던 것).
- **지브러시 Extract가 안 되던 것**: 블렌더 Mask Extract에는 두께 설정이 없는데 넘기고 있어서 매번 오류 — 이제 새 SubTool로 나오고 Thick은 그 Solidify에, 작업하던 SubTool에서 계속 조각. add-on 전체의 블렌더 명령 호출을 실제 명령 설정과 대조하는 테스트 추가(같은 종류의 실수를 미리 잡음).
- **ClipCurve / TrimCurve / TrimLasso가 안 되던 것**: 지브러시 화면의 왼쪽 클릭이 항상 브러시 획으로 가로챘음 — 이제 브러시가 아닌 도구(Clip / Trim / Move / Scale / Rotate …)는 블렌더 도구가 클릭을 받음.
- **외곽에서 그었는데 화면이 돌던 것**: 커서 한 점만 봤음 — 이제 브러시 원의 절반 안쪽이 모델에 걸치면 획(Alt Zsub · Shift Smooth도). 빈 화면 클릭은 화면상의 상자 검사로 바로 회전(추가 계산 없음).
- **데시메이트 뒤 Ctrl+Z**: 첫 번째는 아무 변화가 없고 두 번째에 오브젝트 모드로 빠졌음 — 이제 한 번에 데시메이트 전 메쉬, 조각 모드 그대로(Ctrl+Shift+Z도 조각 모드). 조각 모드를 잠시 나가는 다른 버튼(Duplicate · Merge …)도 같음. 지브러시 화면에서 Ctrl+Z / Ctrl+Shift+Z가 조각 모드를 빠져나가면 다시 들어감.
- 되돌리기 설정 유지(undo_keep)가 브러시 텍스쳐가 없을 때 Area Plane을 넣다가 멈추던 것(오류 출력) 수정.
- 테스트: Blender 5.2.3 bpy에서 관련 테스트 16개 파일 통과(`tests/test_log_v02469_fix.txt`; 새 test_v02469_zbfix 14개, test_v02468_holes 5개). 이제 5.2만 시험(요청). ZIP sha256 `d4cd1f82daeacd685567e299d430421c0ddf71daf670b58374cb068934d871fc`.

## 0.24.68 — 블렌더를 켤 때 add-on이 안 켜지던 것 (2026-10-27)

- **0.24.66 · 0.24.67이 실제 블렌더에서 켜지지 않던 것**("'_RestrictData' object has no attribute 'filepath'"): 크래쉬 대비 저장이 블렌더가 add-on을 불러오는 순간(아직 파일 정보를 읽을 수 없는 때)에 표시 파일을 쓰며 파일 경로를 읽어서 add-on 등록이 멈췄음. 이제 그 순간에는 아무것도 읽지 않고, 표시 파일은 0.5초 뒤 첫 타이머가 씀(실패해도 add-on은 멈추지 않음). 자동 테스트가 창 없이 돌아 그 부분을 건너뛰었던 것을 막으려고, 블렌더가 시작할 때와 같은 제한 상태에서 add-on 전체 등록 + 저장 시작을 시험하는 항목 추가(예전 코드로는 같은 오류가 재현됨).
- 테스트: test_v02499 36/36 · test_v02483 · test_v02494 · test_v02498을 Blender 5.2.3 / 5.0.1 bpy에서 통과(`tests/test_log_v02468_start.txt`). ZIP sha256 `59b459dc95a34d784db0c121cc616a32bf5e1c5c09ee002f2a99424cfcc453f6`.

## 0.24.67 — 화면 회전: Z축이 위로, 회전 중 Alt = 이동, Shift 스냅이 멈추지 않음 (2026-10-27)

- **Z축이 이상하던 것**: 빈 곳 드래그 / 오른쪽 드래그 회전이 화면 기준 자유 회전(트랙볼)이라 돌릴수록 모델이 기울었음. 이제 기본 **Z Up**: 좌우 = 월드 Z축 기준(블렌더 Turntable · 지브러시 Rotate Y처럼 모델이 똑바로 서 있음), 위아래 = 화면 가로축. 오른쪽 보기 막대 **Z Up** 버튼을 끄면 예전 자유 회전(지브러시 XYZ). 속도는 블렌더 Preferences > Navigation > Orbit Sensitivity를 따름.
- **회전 중 Alt가 안 먹던 것**: 회전하는 도중 Alt를 누르면 회전이 멈추고 이동, 떼면 다시 회전. Alt로 시작한 드래그는 예전처럼 Alt를 떼면 확대 / 축소.
- **Shift 스냅이 붙어 버리던 것**: Shift를 누른 채 돌리면 정면 / 옆 / 위로 한 칸씩 넘어감(전에는 작은 움직임이 매번 같은 각도로 되돌아가 멈춤), Shift를 떼면 그 각도에서 이어서 회전.
- **지브러시 Z 회전**: Shift를 누른 채 빈 곳을 클릭하고 Shift를 뗀 뒤 드래그 = 화면 축으로 돌리기.
- 테스트: 지브러시 테스트(v02492 · v02493 · v02494 · v02496 · v02498 · v02499)를 Blender 5.2.3 / 5.0.1 bpy에서 모두 통과, 5.2.3에서 Extensions 설치(Install from Disk와 같은 경로)로 zip 설치 · 켜기 · 엔진 로드 확인. ZIP sha256 `e6e8ec3b7e711c094c8c5463b9025a86cd4977d5ba29328460e9d144565bb8fe`.

## 0.24.66 — 내 데시메이트 엔진(멀티코어, 블렌더보다 빠름), 조각 중 크래쉬 대비 저장 (2026-10-27)

- **Fast Decimate**: 지브러시 화면 Geometry 아래 **Decimation > Decimate Current**가 Mecha Lab 자체 엔진으로(C로 새로 짬, 여러 코어 동시). 블렌더 Decimate와 같은 원리(면을 줄여도 모양이 필요한 곳에 디테일이 남는 QEM 방식)인데, 메쉬를 코어 수만큼 나눠 동시에 줄이고 마지막에 전체를 한 번 더 다듬음. 이 환경(4코어)에서 잰 값: 327,680면 → 5%: **0.6초 vs 블렌더 4.8초(약 8배)**, 평균 오차 같음(0.000242 / 0.000245), 닫힌 메쉬는 닫힌 채(구멍 · 겹친 모서리 없음). 1,310,720면 → 2%: 2코어 3.6초 vs 블렌더 12.8초. 16코어에서는 더 빨라질 것으로 보지만 그 컴퓨터에서는 아직 안 잼.
- 옵션(지브러시 Decimation Master 이름): **Even Tris**(삼각형을 둥글게 — 가는 삼각형 8.5% → 0.3%, 대신 오차가 약 25% 늘어남), **Allow Quads**(삼각형 두 개 → 사각형), **Keep Mask**(마스크된 곳에 디테일 약 2배, 기본 켜짐), **Keep Groups**(폴리그룹 경계가 그 자리에, 기본 켜짐), **Keep Borders**(열린 가장자리 고정).
- 점과 면이 원래 자기 것을 유지 → 마스크 · 폴리그룹 · 재질 · 색(폴리페인트) · 숨김 · UV(이음새는 대략)가 그대로 따라옴. 모서리 데이터(크리스 · 심)는 사라짐. Shape Key나 Multires가 있으면 먼저 지우라고 알림(아무것도 안 바뀜).
- 엔진 파일: Windows x64 DLL + Linux x64(add-on의 `bin/`, 다른 DLL 필요 없음). 다른 시스템은 블렌더 Decimate로 자동. 소스: `tools_dev/native/mdecim.c`(+ `build_mdecim.sh`). Windows DLL은 Wine에서 리눅스판과 같은 결과를 확인(실제 Windows 블렌더에서는 미검증).
- **Safety Save — 조각 중 크래쉬 대비**: (1) 조각 · 페인트 모드에서도 **잠깐 손을 멈추면**(기본 3초 동안 획 · 화면 드래그 없음) 복구 사본 저장 — 간격(기본 3분)이 됐고 그 뒤 바뀐 게 있을 때만, 압축 없이(큰 메쉬도 빨리). (2) **크래쉬가 잘 나는 작업 직전**(DynaMesh · Decimate · Divide · ZRemesher · Mirror And Weld · Close Holes · Extract · Split · Merge · Del Hidden …): 바뀐 게 있으면 사본(15초에 한 번까지). (3) **크래쉬 감지**: 블렌더마다 작은 표시 파일(1분마다 갱신, 정상 종료하면 지움) → 다음에 켤 때 그 블렌더가 사라졌으면 크래쉬로 보고 마지막 사본을 `이름_crash_날짜_시간.blend`로 보관(새 세션 저장에 덮이지 않게, 3개까지) + 창으로 **Open Recovery Copy / Open Folder** 제안. 크래쉬 "그 순간"의 저장은 불가능(프로세스가 이미 깨져 있음) — 대신 자주, 싸게.
- Preferences > Safety Save: **Rest (s)**, **Offer Recovery After a Crash**. 마지막 사본에 걸린 시간 표시.
- **알파를 켠 뒤 S / 우클릭에 알파 창이 뜨던 것**: 알파 칸 버튼이 같은 메뉴 명령을 '알파'로 부르는데, 블렌더가 단축키에서 비워 둔 값을 마지막 값으로 채워서 S · 우클릭(그리고 우클릭 드래그 회전)까지 알파 창이 됨. 이 값은 기억하지 않게 고치고, add-on의 모든 단축키를 같은 문제로 검사하는 테스트 추가.
- 테스트: Blender 5.2.3 bpy 163개 파일 4,445/4,445, Blender 5.0.1 bpy 163개 파일 4,444/4,444 통과(실패 0, 커밋 828f473); 단축키 수정(4470fab) 뒤 test_v02499 28/28과 지브러시 테스트 v02492 · v02493 · v02494 · v02496을 두 버전에서 다시 돌려 모두 통과. ZIP sha256 `72f3eb3df2b857373ef1fff098b7a8a959b0d86eab7675d0aa891bc261ff95b0`.

## 0.24.65 — Ctrl+Z는 한 일만 되돌림(설정은 그대로), 지브러시 빨간 커서 · Accu · 압력 곡선 · 알파 기억, 도구 검색 · 프리셋 (2026-10-27)

- **Ctrl+Z가 설정까지 되돌리던 것**: 화면 버튼으로 설정을 바꿀 때마다 되돌리기 단계가 생기던 것을 없앰(설정 = 장면의 도구 설정 · 브러시 · 크기/세기 · 화면 설정, 지금 고치고 있는 라이브 부품 값은 예전처럼 단계). 화면 버튼으로 실행한 작업(DynaMesh · Mirror 등)은 Blender 버튼처럼 자기 단계를 가짐(전에는 클릭 처리 안에서 빠져서 Ctrl+Z가 더 앞으로 가며 설정까지 되돌림). 되돌리기 / 다시 하기 직전의 설정(모든 도구 설정의 숫자 · 스위치 · 선택, 지브러시 브러시 크기 · 세기 · 대칭 · 캐비티 · 브러시 자체 설정)을 그대로 다시 넣음(업데이트 없이 저장값만 — 다시 만들지 않음).
- **지브러시**: 빨간 브러시 원(Zadd / Zsub, 브러시마다 한 번 — 나중에 바꾼 색은 유지), **Accu**(한 획이 자기 위에 쌓이는지 = Blender Accumulate, 처음엔 꺼짐), **Pressure**(펜 압력 → 세기 곡선: ZBrush 살살 시작 / Linear / Soft / Firm), 왼쪽 Stroke 칸.
- **알파가 획 방향을 따라감(Directional, 기본 켜짐)**: 지브러시처럼 세로 알파로 가로로 그어도 알파가 획 방향으로 돌아서 매끈한 줄(전에는 고정이라 오돌토돌한 줄무늬). Flh / Flv / Rot / Invr 아래 **Directional** 버튼으로 끄면 화면에 고정. 알파와 함께 기억, Ctrl+Z에도 유지.
- **메카닉 랩에서 펜 오른쪽 버튼**(지브러시 화면에서만 되던 것): 버튼을 누른 채 펜이 조금 떨려도(14px까지, 마우스 6px) 클릭으로 봄, 그리기 도구에서 태블릿 드라이버가 누름을 두 번 보내도 '오른쪽 두 번 = 도구 나가기'로 보지 않음, Mecha Menu가 펜의 반복된 여는 누름에 바로 닫히지 않음.
- **알파 기억**: 브러시마다 알파와 Flh / Flv / Rot / Invr를 이 파일에 기억 — 그 브러시를 다시 고르면, 획을 시작할 때, 파일을 다시 열면 돌아옴. Alpha Off는 잊음.
- **예전 브러시 복사본 정리**: 0.24.60 ~ 0.24.62가 남긴 "… (ZB)" 브러시가 있으면 알파 창에 **Clean N old** 버튼(그 복사본과 그것만 쓰던 알파 텍스쳐 / 이미지 삭제, 지금 브러시는 그대로).
- **DynaMesh + 마스크**: 마스크된 부분이 자기 폴리그룹이 되고(리메시를 거쳐도 유지), 마스크는 지워짐(지브러시처럼). 메시의 Preserve Attributes 설정은 원래대로.
- **도구 검색**: 오브젝트 모드에서 **Ctrl+F** 또는 동작 줄의 **Search Tools** — 이름 일부를 치고 Enter.
- **도구 프리셋**: 오른쪽 패널 맨 아래 접힌 **Presets** — Save(이름) / Load(목록) / Delete. 그 도구의 설정을 add-on 사용자 폴더에 저장(모든 파일에서, .blend 안에는 안 들어감). Load는 되돌리기 단계(라이브 부품이 바뀔 수 있어서).
- **방사 배열(Radial) 보강**: 큰 Size(1e25)와 라이브 불리언에서 Blender 5.2가 죽던 것, 겹치는 이빨 2048개에서 메모리가 바닥나던 것을 막음: 너무 크거나 무거운 배열은 라이브 불리언 / 굽기 전에 멈추고 이유를 알림. 굽기 · 불리언 한도는 이 컴퓨터 메모리에 맞춰 늘어남(64GB면 더 큰 배열 허용)
- 이미 들어 있던 것 확인(목록에 남아 있던 옛 항목): Cloth Plate 접힘 방향(위 / 아래 / 랜덤), 크리처 스킨(악어 · 용 · 고질라 · 두꺼비 · 코끼리 · 악어 등) · 크리처 쉘(무작위 면 · 혹 · 가장자리 들림 · 중력), 판 · 나사 스탬프의 미러 따라가기.
- 테스트: Blender 5.2.3 bpy 161개 파일 4,394/4,394, Blender 5.0.1 bpy 161개 파일 4,393/4,393 통과(실패 0). ZIP sha256 `1185379e92e53b1dbe97eaad10f0110a09e5f29d85d458e4c390ff0c8de533b2`.

## 0.24.64 — 알파를 지금 브러시에 바로 (2026-10-27)

- 실제 블렌더 창에서 알파가 "Alpha Off"로 남던 것: 알파용 브러시 복사본으로 블렌더가 바꿔 주지 않았음. 블렌더 기본 브러시는 다른 .blend에서 링크한 텍스쳐는 받으므로, 알파마다 작은 .blend(일반 + 반전)를 add-on 사용자 폴더에 한 번 만들고 링크해서 **지금 쓰는 브러시에 바로**. 복사본 · 재시도 없음, 작업 파일에 새로 저장되는 것 없음. Invr = 반전 짝으로 바꿈.

## 0.24.63 — 지브러시 화면에서 오른쪽 드래그 = 화면 회전 (2026-10-27)

- 지브러시처럼 오른쪽 버튼 드래그(펜 옆 버튼을 띄운 채로)로 모델 위에서도 화면 회전, Alt = 이동(드래그 중 Alt 떼면 확대 / 축소), 그냥 오른쪽 클릭 = 브러시 메뉴. 키 안내에 표시.

## 0.24.62 — 알파 브러시 복사본 전환 재시도 (2026-10-27)

- (0.24.64에서 링크 텍스쳐 방식으로 바뀜) 블렌더가 복사본을 바로 못 찾을 때 0.25초마다 4초 동안 다시 시도, 끝내 안 되면 알파 칸 아래에 표시.

## 0.24.61 — 하이폴 모드, Focal Shift 곡선, LazyStep 간격, Shift+D 복사 (2026-10-27)

- **하이폴 모드**(Preferences / 오른쪽 세로 막대 **HiPoly**): 지브러시 화면에 있는 동안 Blender Sculpt Deform Only + Delay Viewport Updates, 무거운 화면 표시(와이어 · 통계 · 면 방향 · 캐비티 · 그림자 · X-Ray · 외곽선) 끔 — 나가거나 끄면 모두 원래대로(저장값은 화면에, 되돌리기 기록에는 안 남음; 창 두 개가 같은 장면이면 마지막 창이 나갈 때 되돌림). SubTool 칸에 무거운 것(Shape Key · 켜진 모디파이어 …) 표시. Blender Preferences는 안내만.
- **Focal Shift**: 5단계 프리셋 대신 지브러시 모양 그대로의 곡선(마이너스 = 윗면 평평, 플러스 = 뾰족, 모든 값마다).
- **LazyMouse**: LazyStep = 점 간격(지브러시), LazySmooth = 따라오는 부드러움.
- 알파는 화면 기준 투영 + 브러시 원 안에 보임. **Shift+D = Duplicate**(D는 SDiv 올리기). **G**는 지브러시 화면에서 오브젝트 모드로 나가지 않음.

## 0.24.60 — 지브러시식 조각 화면 (2026-10-27)

- MECHA LAB 탭의 Sculpt Mode = 지브러시 이름 · 키 · 선반(주황): 왼쪽 SubTool / Geometry / Masking / Stroke …, 브러시 칸(브러시 · 알파 · 텍스쳐 · 스트로크 · 메테리얼 · 색 · 대칭 · Clip / Trim · Initialize, 화면이 낮으면 스크롤), 위쪽 막대(Edit / Draw / Move …, Mat, Zadd / Zsub, Z Intensity / Focal Shift / Draw Size, Dynamic …), 오른쪽 보기 막대 + SubTool 목록, 아래 브러시 줄, 키 안내. 오른쪽 위 **MECHA LAB | ZBRUSH** 전환 + **STYLE ZBrush | Blender**.
- 마우스: 모델 위 = 조각(Alt Zsub, Shift Smooth, Ctrl MaskPen), 빈 곳 드래그 = 회전(Shift 스냅) / Alt 이동 / Alt 떼면 확대, Ctrl+클릭 = 마스크 반전, Ctrl+올가미 = 마스크, Ctrl+빈 곳 드래그 = 마스크 지우기 / 마스크 없으면 DynaMesh(버튼이 켜진 SubTool), Ctrl+Shift = 보이기 / 숨기기, Alt+다른 SubTool 클릭 = 선택. 키: Space / S / U / O 메뉴(밖으로 나가면 닫힘), B 브러시(B S T …), X 대칭, D SDiv, Ctrl+D Divide, Ctrl+W 폴리그룹. 오브젝트 모드에서도 빈 곳 드래그 = 회전.
- DynaMesh = 점 개수로 복셀 리메시(버튼이 켜져 있는 동안 Ctrl+드래그로 다시), ZRemesher = Quadriflow, SDiv / Divide / Del Higher / Del Lower = Multires, Mask By Cavity(Intensity · Blur · Inv), CavityMask, Split / Extract / Groups / Merge / Decimate / Check · Fix Mesh / Append / Duplicate / Delete, OBJ / STL / FBX.
- 알파(기본 14개 · 지브러시 ZAlphas · 내 폴더), 텍스쳐 스탬프(Paint + 드래그 = DragRect, 크기 · 회전 · 대칭 · 마스크 보호 · Rgb Intensity, 기본 텍스쳐 11개), 메테리얼 / 스트로크 / 텍스쳐 썸네일 선택창, 점 개수 100만부터 Mil 표시, 리메시를 지브러시 점 개수로(Active Points Count).

## 0.24.59 — 아래 메인 메뉴, 레이어 창, 위쪽 공통 막대, 오른쪽 도구 패널, 빠른 컷, 깔끔한 GN 베벨 (2026-10-27)

- **위쪽 막대(가운데 위)**: 도형(라쏘 / 커브 라쏘 / 사각 / 원 / 타원 / 자유 / 커스텀)을 큰 아이콘으로, Line · Sketch · Slow Line(켜면 Strength · Radius 막대), Line 켜면 굵기 · 끝 모양 · Taper · Pressure · Attach Ends, Surface · Through · Sim, 대상(Auto / Selected / Active), 컷 계열은 깊이(Through All / From Surface + 깊이 막대) · Auto Apply, Ortho. 도구가 가진 것만, 좁으면 두세 줄로(줄 너비 고르게). Blender 위쪽 도구 헤더는 커스텀 PNG 고르는 칸만 남김.
- **오른쪽 도구 패널**: 지금 도구의 N 패널 내용을 그대로 읽어서 새 UI로 — 숫자는 HUD 같은 파란 막대(드래그 / 클릭 = 값 입력 / Ctrl+클릭 = 기본값 / Esc = 되돌림), 선택지는 알약 버튼, 닫힌 목록은 ▾ 버튼(누르면 목록), 켜기/끄기는 스위치, N 패널의 박스는 제목 있는 섹션(제목 클릭 = 접기), 버튼은 그대로 실행. Lasso 설정 · 도움말은 접힌 섹션으로 맨 아래. 위쪽 막대에 있는 것은 빠짐. 길면 휠로 스크롤, – 로 접기(작은 아이콘 탭). N 패널을 열면 숨김(같은 내용). 50개 도구 패널 전부 읽힘.
- **아래 메인 메뉴**: 모든 도구를 6:4 타일(아이콘 8 : 이름 2)로, 일 종류별 묶음(제목 + 얇은 구분선) 2줄씩 뷰포트 맨 아래 한 띠로(좁은 화면은 3줄). 지금 도구는 파란색, 긴 이름은 마우스를 올리면 위에 전체 이름, 예전 툴바 단축키 글자(D · C · B)는 타일 구석에. 크기는 아이콘 크기 탭의 Tool Strip.
- **동작 줄(예전 아래 툴바 자리)**: 메인 메뉴에 도구가 다 있어서 아래 툴바와 떠 있던 동작 카드 대신, 메뉴 바로 위 가운데에 큰 아이콘 + 이름 타일 — Select(F) / 고른 도구 켜기 · 끄기 / Apply Modifiers / Reset Axis / Origin to Geometry / Origin to 3D Cursor / Symmetry / Mirror.
- **레이어 창(왼쪽)**: 부품과 그룹 목록(그룹 아래 부품 들여쓰기, 화살표로 접기, 반복이 걸린 그룹은 Mirror 같은 주황 표시) — 줄 클릭 = 선택(Shift = 추가 / 빼기), 그룹 줄 = 그룹 선택, 눈 = 숨기기 / 보이기(그룹은 전체), → = 그룹 안에서 작업. 위에 Group / Ungroup / Merge / Enter(Exit). 아래에 접힌 **Export**(OBJ / FBX, Selected / Visible, Apply Modifiers, ZBrush-safe Faces, Scale, Export…)와 **ZBrush Bridge**(Send to ZBrush / Import Back / Open Folder, 교환 폴더, 보낸 부품 중 바뀐 수) — 둘은 같은 설정을 써서 같은 메시가 나감. 길면 휠 스크롤, – 로 접기. 그리기만으로는 교환 폴더를 만들지 않음.
- **예전 배치로**: Preferences의 Tool Menu Place = Left 면 0.24.58처럼 왼쪽 도구 줄(아이콘 + 이름) + 아래 툴바 + 동작 카드(레이어 창 · 메인 메뉴 · 동작 줄은 꺼짐). Layers Panel 켜고 끄기도 Preferences.
- **Apply Modifiers**: 메시를 선택해 둔 상태면 누르는 즉시 선택된 메시들에 적용(다시 고르지 않음). 선택된 메시가 없을 때만 클릭해서 고르기.
- **UI 크기 · 패널 투명도**: 레이어 창 맨 아래 접힌 **UI Size** 칸에서 바로 — Viewport Panels / RMB Menu / Tool Menu(아래 메뉴 타일 · 동작 줄) / **Panel Opacity** + Small · Normal · Large · Huge. Panel Opacity는 카드 배경만(우클릭 메뉴 · 막대 · 패널 · 카드 · HUD · 키 안내) — 아이콘 · 글자 · 버튼 · 값 막대는 그대로 진하게. Preferences의 Icon Size에도 있고 크기와 함께 저장.
- **Quick HUD**: 오른쪽 패널이 펼쳐져 있으면 숨김(같은 설정이 오른쪽 패널과 우클릭 메뉴에 있음). 오른쪽 패널을 접으면 다시 나옴.
- **위쪽 막대 위치**: Blender의 투명한 헤더 줄(Region Overlap) 아래로 — 헤더 버튼과 겹쳐 보이던 것 해결.
- **키 안내**: 카드 폭 = 키 칸 + 가장 긴 설명(키가 짧은 줄의 긴 설명이 카드 밖으로 나가던 것). 자리는 왼쪽 아래 구석(메인 메뉴 옆), 화면이 좁아 자리가 없으면 메뉴 · 동작 줄 위. 레이어 창은 그 위까지만.
- **숫자 막대(오른쪽 패널 · 위쪽 막대)**: 막대 전체 길이 = 막대 범위라서 채움이 마우스를 그대로 따라감(정수는 한 칸 최소 4px), Shift = 10배 느리게. 뷰포트 끝에 닿으면 커서가 가운데로 돌아가서 계속 끌 수 있음(오른쪽 패널이 화면 끝에 붙어 있어 조금만 끌리던 것 — 전에는 누른 곳에서 고정 300px에 범위 전체). 막대 범위를 넘은 큰 값(큰 장면)은 값 크기만큼 빠르게. Line Width 막대 범위 0.5 → 2.
- 위쪽 막대 · 메인 메뉴 · 동작 줄은 모두 화면 가운데 정렬(위쪽 막대는 양옆 패널보다 위에 있어서 전체 폭 사용, 여러 줄로 내려와 패널에 닿을 때만 비킴). 키 안내 · 오른쪽 패널 · 미러 카드는 메뉴와 동작 줄 위로.
- **우클릭 메뉴 크기 따로**: RMB Menu(메뉴만, 메뉴 안 − / + · Ctrl+휠도 이것) / Viewport Panels(HUD · 키 안내 · 카드 · 툴바 · 도구 줄) — 아이콘 크기 탭. 예전 크기 하나만 저장돼 있으면 메뉴는 그 크기 그대로. 메뉴를 열어도 다른 뷰포트 UI가 꺼지지 않음.
- **패널 클릭이 항상 먼저**: 뷰포트 위 패널(미러 카드 · HUD · 툴바 · 도구 줄 · 위쪽 막대 · 오른쪽 패널)을 보이지 않는 기즈모가 먼저 받음 — Blender Select / Move에서 카드를 누르면 선택이 먼저 풀려서 Ctrl+클릭만 되던 것 해결, 그냥 클릭 / 드래그. 점을 찍으며 그리는 중에 패널을 눌러도 점이 아니라 패널.
- **우클릭 메뉴에 Line / Sketch**: 도형 · 프로파일 아래 버튼(그 도구가 쓰는 것만).
- **컷 빠르게**: 여러 조각(관을 여러 개 붙인 메시)에서 컷 모양이 닿는 조각만 불린에 넣고 나머지는 그대로 다시 붙임(Exact 기준 1.0 → 0.4초, 미러 복사본 쪽 1.4 → 0.3초, 결과 동일). 메시와 안 겹치는 모양은 불린 전에 바로 알림(미러 복사본 쪽은 곧바로 뒤집어서 한 번만). 1.5초 넘게 걸린 컷은 메시지에 시간과 방식.
- **GN Edge 베벨 깔끔하게**: 손으로 그린(조금 지그재그) 컷에서 꺾일 때마다 이빨처럼 깨지던 것 → 폭 정도 거리 안에서 테두리 방향을 평균(진짜 모서리는 정확히 그대로). 얇은 부품에서는 폭을 남은 두께의 절반 아래로 자동 제한. 재현 시험: 열린 모서리 1 → 0, 15.6 → 6.0초.
- **그룹 박스**: 메시 크기에 맞는 상자(선택하면 주황) + 가운데 작은 십자 손잡이(전에는 긴 쪽 기준 큰 정육면체). 예전 그룹도 파일을 열 때 정리.
- 테스트: 150개 파일 — Blender 5.0.1 4112/4116, 5.2.3 4113/4117 (실패: test_v02319 시간 측정 1개 — 두 버전을 동시에 돌릴 때만, 혼자는 통과 / 키 안내 그리기 검사 2개 — 0.24.60에서 테스트 갱신). test_v02484 ~ v02490 추가, test_v02470 · v02471 · v02472 · v02479 갱신. ZIP sha256 `f0d0b2e15add56d3a4bbf1670284a532773428806906390358bf9ca1e34d3dc3`.

## 0.24.58 — 하단 툴바·왼쪽 도구 줄을 Mecha Menu 스타일로, Path Move Back Mask, 미러 Split·Box Hide, 안전 저장, Attach Ends 윗면 깨짐 수정 (2026-10-27)

- **하단 툴바**: 둥근 버튼 대신 어두운 막대 하나에 아이콘만(지금 도구는 파랑), 단축키 글자는 버튼 구석에 작게, 이름은 마우스를 올리면 말풍선. 좁은 화면에서는 버튼이 작아져 화면 안에 맞음.
- **왼쪽 도구 줄**: 모든 도구를 작업별(Block-out / Cut / Surface detail / Move / Symmetry & repeat / Curves / Creature / Cloth / Utility)로 묶은 세로 카드, 3열(화면이 낮으면 작아지거나 4~5열). 누르면 그 도구, 지금 도구는 파랑, 이름은 말풍선.
- 클릭은 Quick HUD와 같은 방식(어느 도구에서든 먼저 받음, 카드 위 클릭은 뒤로 안 넘어감). Quick HUD · 키 안내 · Tool Active 버튼은 도구 줄 오른쪽으로 비켜남.
- Preferences: Drawn Toolbar(끄면 예전 둥근 버튼) / Tool Strip(끄면 도구 줄 없음).
- **Base Mesh Attach Ends 윗면·아랫면 깨짐**: 평평한 면이 길쭉한 큰 면 몇 개라서, 3D로 휘면 비틀려 줄무늬처럼 깨져 보이던 것 → 휘기 전에 선을 따라 촘촘하게 잘라(48칸) 면이 고르게 따라 휨(시험: 비틀림 0.094 → 0.0000002).
- **Path Move Back Mask**(패널 버튼, 드래그 중 B): 얇은 부품을 당길 때 반대편 면(나를 등진 면)이 같이 끌려오던 것 → 켜면 반대편은 그대로. Stretch: 각 점이 나를 향한 정도만큼만 움직임(옆면은 조금씩). Extend Brush: 브러시 영역을 깔끔하게 못 잡으면 전체 단면으로 넘어가던 것(이게 반대편까지 끌려오던 원인) → 브러시를 작게(0.7, 0.5배) 다시 시도하고, 그래도 안 되면 아무것도 바꾸지 않고 알려 줌(Separate Tube도 안 만듦). Whole(전체 단면)은 원래대로 전체. Auto Apply 끈 편집 가능 이동에도 기억됨.
- **실시간 미러 + Split 실패**: 미러 복사본 쪽에 그리면 '메시와 안 겹친다'로 실패하던 것(Cut은 됐음) → 실제 메시 쪽으로 뒤집어서 Split(Gap Split 포함). Auto Apply를 끈 라이브 컷도 복사본 쪽에 그리면 아무 효과가 없던 것 → 컷터를 실제 메시 쪽으로 옮김.
- **Box Hide + 미러**: 미러 / 래디얼 / Kaleido가 켜진 부품은 그린 곳이 모든 대칭 복사본에서 같이 숨겨짐(Follow Symmetry, 기본 켬; 전에는 그린 쪽만). Alt로 다시 보이기 · Apply도 양쪽 같이. 미러 없는 부품은 예전 Mirror X 그대로.
- **Safety Save(안전 저장)**: 무거운 작업(모든 그리기 도구의 실행, Concept / Path Move) 직전과, 쉬는 동안(모달 작업 없고 Object Mode) 몇 분마다 파일 전체 복사본을 임시 폴더 `MechaLab_Recovery/<파일이름>_recovery.blend`에 저장. 열려 있는 파일·경로·저장 안 됨 상태, Blender 설정은 안 건드림. 저장 안 된 변경이 있을 때만, 3분에 최대 한 번(Preferences에서 0~60분, 0 = 매번). 바로 전 것은 `_recovery_prev.blend`로 보관, 저장 도중 죽어도 이전 복사본은 남음. Preferences > Mecha Lab: Open Last Recovery / Open Recovery Folder / Save Recovery Copy Now. (Blender 자체 Auto Save는 모달 작업 중엔 미뤄지고, 크래시 순간엔 아무것도 저장하지 않음.)
- 테스트: 143개 파일 3966/3966. test_v02479 · v02480 · v02481 · v02482 · v02483 추가, test_v02478 항목 추가. ZIP sha256 `6a18b4e29978fff7eab34166e41614d91b42fb0996fc2cb41d0ceef4fd7963d8`.

## 0.24.57 — 클릭 잘 먹게, 대칭 부품 그룹째 이동·그룹 미러, Base Mesh 라인 양 끝 붙이기, Edge Finish 고르게 (2026-10-27)

- **Quick HUD 슬라이더 / Symmetry 카드 클릭**: 빠르게 두 번 누르면 두 번째가 '더블클릭'이 되어 다른 기능(나사 되돌리기 등)이 가져가던 것 → HUD / 카드가 더블클릭도 받음. 줄 사이 틈·카드 가장자리를 눌러도 가장 가까운 줄로, 버튼 바로 옆(몇 px)도 그 버튼으로. 카드 위 클릭은 뒤의 도구로 넘어가지 않음. Object Mode 키맵에도 먼저 등록.
- **대칭 부품을 그룹으로 묶고 옮기기**: 미러 / 래디얼 / Kaleido 중심이 그룹을 따라감 — 그룹을 옮기면 대칭 복사본까지 한 덩어리로 움직임(전에는 중심이 월드 원점에 남아 복사본이 원점 둘레로 퍼졌음). Ungroup하면 중심은 그 자리에 남음.
- **그룹 자체를 미러**: 그룹(핸들)을 고른 채 메뉴 Mirror X / Y / Z = 그룹 Repetition 미러(월드 축, 켜면 파랑). 다시 누르면 끔.
- **Base Mesh 라인 모드 Attach Ends**: 선을 시작한 곳의 메시 표면과 손을 뗀 곳의 메시 표면에 양 끝이 붙음(사이는 3D로 이어짐). Between: **Smooth**(선을 부드럽게 다듬고 양 끝에서 완만하게 떠나고 붙음) / **As Drawn**(그린 선 그대로, 한쪽에서 다른 쪽으로 고르게 오르내림). Line 옆 버튼, 만든 뒤 LIVE 패널에서 바꾸면 바로 다시 휨. 끝 아래에 메시가 없으면 예전처럼 평평하게.
- **Cut / Split의 Edge Finish(Bevel / Chamfer, GN Edge 아닌 예전 메뉴)**: 촘촘한 메시에서 불린이 남긴 짧은 모서리 때문에 Blender 베벨이 거의 0으로 줄거나(삼각형 메시 0.0138) 홈이 파이고 폭이 0~2배로 들쭉날쭉하던 것 → 그런 경우에는 GN Edge와 같은 방식으로 테두리를 따라 깎아서 **폭이 정확히 같음**(시험: 2만 / 4만 면에서 0.050 일정, 1~2초). 폭이 컷만큼 크면 예전처럼 제한하고 알려 줌.
- 테스트: 138개 파일 3908/3908. test_v02477 · test_v02478 추가, test_v02424 · v02471 갱신. ZIP sha256 `cfdcfa871f2cc02ca56b3f2580babc8056e49c8d3858b499c2e46da97d6075d4`.

## 0.24.56 — 새 부품이 미러를 따라감, 마지막 컷 다시 조절, 그룹 Grid·목록, 도구 목록 그룹 (2026-10-27)

- **새 부품이 미러를 따라감**: 미러가 켜진 부품 위에 Armor / Creature Plate, Surface Draw, Flower, 나사를 만들면 같은 미러(평면, 같은 중심, Bisect·Flip)가 붙음 — 반대쪽에도 바로 보임. Preferences: New Parts Follow the Mirror.
- **마지막 컷 다시 조절(Live Last Cut)**: Cut 한 번(한 부품, 램프 아님) 뒤 다음 컷 전까지는 Cut Depth / Depth 방식 / GN Edge(종류·폭·단 수) / Edge Finish(종류·폭·단 수)를 Quick HUD·메뉴·패널에서 바꾸면 방금 컷이 그 값으로 다시 잘림. 컷 뒤에 메시를 편집했으면 편집을 지키고 더 이상 다시 자르지 않음. Preferences: Live Last Cut.
- **Symmetry 카드**: Clip 토글(Bisect / Flip / Clip), 카드가 떠 있는 동안 뷰포트에 반투명 미러 평면(X 빨강 / Y 초록 / Z 파랑).
- **그룹 Repetition Grid**: X × Y × Z 개, 그룹 크기 + Gap 간격으로 나란히. 카드에서 축별 − / +, Gap − / +. 메뉴 Repetition에 Repeat Grid.
- **그룹 목록**: 사이드바 Mecha Lab > Groups — 그룹(안쪽 그룹은 들여쓰기), 반복 방식, 고르기 / 들어가기, Exit.
- **도구 목록을 작업별로**: Block-out / Cut / Surface detail / Move / Symmetry & repeat / Curves / Creature / Cloth / Utility 제목 아래 묶음(사이드바·팝업 그리드).
- 테스트: 136개 파일 3883/3883. test_v02475 · test_v02476 추가. ZIP sha256 `0ae80b16db7252c2347a27bbe88c0cecd20cd8dd98c6e427c055b21d50b60bac`.

## 0.24.55 — Path Move: 전체(Whole) 모드를 바로 (2026-10-27)

- 예전처럼 부품 단면 전체를 끌어내는 Extend를 **Whole**(전 Section)로 부르고, 바로 바꿀 수 있게 함:
  - 드래그하는 **도중에 Tab** = Brush ↔ Whole (미리보기도 바로 바뀜, 헤더에 지금 방식 표시)
  - Quick HUD와 우클릭 메뉴 Settings에 Brush / Whole 버튼
  - 키 안내에 Tab 줄
- 테스트: 134개 파일 3847/3847. test_v02474 늘어남(16). ZIP sha256 `d52add2430582c08ff86f0f775bbd5f46d90bf07591191cd5551dab85c25b4b2`.

## 0.24.54 — 3D 마우스, Path Move Extend가 브러시 크기만큼만 (2026-10-27)

- **3D 마우스(MECHA LAB에서만 안 되던 것)**: 0.24.51에 넣은 휠 클릭 메뉴 게이트가 떠 있는 동안 다른 이벤트를 모두 잡아 두던 것을 고침 — 3D 마우스(NDOF)·트랙패드 이벤트가 오면 바로 놓아 주고, 나머지 이벤트도 그대로 넘김. (원인 추정: 실제 3D 마우스로는 확인 못 함 — 그래도 안 되면 Preferences > Middle Click = Mecha Menu를 끄고 알려 주세요.)
- **Path Move Extend, Area: Brush(새 기본값)**: 잡은 곳 주변의 면을 브러시 크기로 잘라(Ball = 팔각형, Box = 사각형) 그 조각만 경로를 따라 뽑아냄. 전에는 부품의 단면 전체를 평면으로 잘라 브러시의 5~6배가 끌려왔음. 패널 Method 아래 Area: Brush / Section(예전 방식). 패치를 만들 수 없는 곳(열린 모서리, 구멍)은 예전 단면 방식으로.
- 테스트: 134개 파일 3843/3843. test_v02474 추가. ZIP sha256 `24c5401726160e56b7d020f69a7c135a0b3c63732b760f95f2214ad5608ff2d4`.

## 0.24.53 — 써 보신 피드백 3가지, 속도·버그 수정, Quad Remesh 베벨 (2026-10-27)

- **피드백**
  - 그룹 Repetition의 Mirror / Radial / Kaleido가 이제 **월드 원점과 월드 축** 기준(전에는 그룹 핸들 기준이라 바로 옆에 붙어 나왔음). 카드의 Centre에서 World / Group / Cursor를 고를 수 있음.
  - Symmetry 카드가 물체 옆(물체 위를 가림)이 아니라 **뷰포트 오른쪽**(사이드바 바로 왼쪽)에 고정됨.
  - Base Mesh / Creature Base에서 우클릭 메뉴에 **라쏘 모양 줄(Lasso)**이 다시 나옴(메뉴로 바꾸면서 빠졌던 것).
- **GN Edge(컷 / 스플릿의 GN 챔퍼·베벨) 7~10배 빠르게**: 띠끼리만 정확하게 합친 뒤 본체에서는 빠른 Manifold로 뺌. 2만 면 부품 컷 8~13초 → 0.8~2초. 열린 메시이거나 결과가 깨끗하지 않으면 예전 방식으로 자동 전환.
- **GN Edge 모서리 폭**: 90° 모서리에서 폭이 71%로 좁아지던 것 → 모서리도 같은 폭.
- **Path Move Stretch**: 단계마다 메시를 다시 쪼개던 것을 한 번에 계산 — 1만 점 판에서 59초·40만 점·구멍 57개 → 1초·1.6만 점·구멍 없음. Auto Apply 끔 / 라이브일 때 경로 하나가 기록 하나(Undo Last가 경로 전체를 되돌림).
- **Ramp**: 라이브 램프의 바닥 배치를 기억해서 깊은 쪽을 바꿀 때 다시 만들지 않음. **램프를 만든 뒤 직접 편집한 내용이 Soft / Depth 슬라이더를 움직이면 말없이 지워지던 버그** 수정 — 편집이 감지되면 편집은 그대로 두고 램프를 확정함.
- **Quad Remesh Bevel Edges**: 쿼드 결과에 실시간 베벨. Outer(바깥 볼록 모서리만) / All, 폭·단 수(기본 2 = 전부 사각형)·모양 슬라이더, Apply로 확정.
- 테스트: 133개 파일 3831/3831. test_v02473 추가, test_v02472 · v02438 갱신. ZIP sha256 `fe29040e0980de94e33af1f282342b12d01a25aa1604c49c4f37d25e7fcda488`.

## 0.24.52 — 메뉴 셰이딩·계속 열림, Modeler식 대칭(Mirror / Radial / Kaleido), 그룹 (2026-10-27)

- **Mecha Menu**: Shading 줄(Flat / Auto Smooth / Smooth) 추가. 메뉴 안 클릭은 메뉴를 닫지 않음(도구 버튼도 그 자리에서 바뀜) — 마우스가 메뉴(카드 사이 틈 포함) 밖으로 나가면 닫힘. 우클릭 / Esc도 닫힘. 메뉴가 열려 있을 때 휠 클릭은 두 번째 메뉴를 열지 않음.
- **대칭(Substance 3D Modeler 방식)**: 파트마다 Off / Mirror / Radial / Kaleido.
  - Mirror = Alt+X 린 미러와 같은 `MCH_Mirror` 하나(메뉴 Mirror X/Y/Z, 카드, Apply, Enter 모두 같은 것). 0.24.49~51 메뉴 미러(`MCH_Symmetry`)는 자동으로 넘겨받음.
  - Radial = 축(X/Y/Z) 둘레로 Count개. 중심은 처음에 미러 중심(월드 원점 또는 3D 커서)과 같음 — Modeler의 "대칭 원점 하나". 카드에서 Part / World / Cursor로 옮김.
  - Kaleido(래디얼 미러) = 미러 평면이 래디얼 중심과 축을 지나서(미러 오브젝트 = 래디얼 중심) 조각마다 거울 대칭 → 2×Count 조각의 만화경. 새로 켜면 래디얼 축을 품는 평면(Z축이면 X 평면)으로 시작. 중심을 옮기면 평면도 같이 움직임. Kaleido에서 Mirror로 돌아가면 미러는 원래 미러 중심으로.
- **Symmetry 카드**: 미러 옆에 뜨던 버튼들 대신 파트 오른쪽에 카드 하나(Off / Mirror / Radial / Kaleido, X Y Z, Bisect, Flip, 축, − / + Count, 중심, Apply / Remove). 대칭이 있는 파트를 고르면 자동으로 뜨고, 메뉴 Symmetry > Card로도 염. Preferences: Symmetry Card(끄면 예전 옆 버튼).
- **그룹**: Group(빈 핸들 + 컬렉션, 핸들을 움직이면 안의 파트가 따라감), Ungroup(원래 컬렉션으로), Merge(메시 하나로), Enter / Exit(그룹 안에서만 작업, 나머지는 와이어·선택 불가), Select Group, 그룹 안 그룹.
- **Repetition**: 그룹 단위 Mirror / Radial / Kaleido 복사(Geometry Nodes 링크 복사 — 파트를 고치면 복사본도 바로 바뀜). 그룹 핸들을 고르면 같은 카드가 Repetition 카드가 됨. Apply = 복사본을 실제 오브젝트로.
- 테스트: 132개 파일 3805/3805. test_v02472 추가. ZIP sha256 `b0638f3431dc43530b07a5c224ff4b846923476ddd0b686f7c7b581b43aaab25`.

## 0.24.51 — Quick HUD 슬라이더 수정, 휠 클릭 메뉴, 팝업 크기 조절 (2026-10-26)

- **Quick HUD 슬라이더가 안 움직이던 문제**: 기즈모 대신 클릭 연산자(`mch.quick_hud_press`)가 모든 Mecha 그리기 도구(+ Screw, Primitive) 키맵 앞쪽(D 누르고 드래그 다음, 도구 클릭보다 먼저)과 3D View에서 먼저 받음 — HUD 위면 드래그(Shift 미세) / 클릭 입력 / Ctrl+클릭 기본값 / 제목 줄 드래그로 이동, 그 밖의 클릭은 그대로 도구로 넘어감.
- **가운데 버튼(휠) 클릭 = Mecha Menu**: 누르고 움직이지 않고 떼면 메뉴, 움직이면 Blender 회전으로 넘김. Shift / Ctrl + 휠 드래그(이동 / 확대)는 그대로. Preferences: Middle Click = Mecha Menu.
- **팝업 크기**: 메뉴 도구 줄 아래 − / + 버튼, 메뉴 위에서 Ctrl + 휠, 사이드바 Icon Size > Viewport Popups(Small/Normal/Large/Huge 프리셋 포함). 0.5~3배, ui_sizes.json에 저장. Quick HUD·키 안내도 같은 크기.
- 테스트: 131개 파일 3751/3751. test_v02471(19) 추가. ZIP sha256 `db6a105da0ee8a00a334d5bdb38d1e399ac083de26be73d917e1a36b57253dc9`.

## 0.24.50 — Mecha Menu (직접 그리는 우클릭 메뉴, Substance 3D Modeler 룩), Ctrl+Alt 홀드 (2026-10-26)

- **Mecha Menu**: 우클릭 팝업을 Blender 패널 대신 Mecha Lab이 직접 그림 — 거의 검정 둥근 카드 3장(도구 줄 | "Cut tool" 카드 | Actions). 아이콘 색은 패널과 같음.
  - 도구 줄: Select, 최근 도구, 즐겨찾기(파란 배경 = 지금 도구), 별, 세트 이름(클릭 = 다음 세트). 마우스를 올리면 이름 말풍선.
  - 카드: 글자 탭 Shapes / Stamps, 아이콘 그리드(선택 = 흰 배경), Settings = Modeler Dynamics식(이름 … 값, 가는 선 + 흰 손잡이 슬라이더 / 선택 버튼 / 토글). Base Mesh는 프로필 그리드.
  - Actions: 아이콘만(구분선 + 작은 회색 제목), 올리면 이름. Mirror X·Y·Z, Remesh / Quad / Low Poly, Radial / Curve Array / Radial Sym, Hide / Show All / Isolate, Live(Apply 등).
  - 슬라이더 드래그(Shift 미세), 클릭 = 값 입력, Ctrl+클릭 = 기본값. 도구 선택 / 마우스가 필요한 동작은 메뉴를 닫고, 모양·탭·설정·토글은 열어 둠. RMB / Esc / 바깥 클릭 = 닫기, 휠·가운데 버튼은 뷰 회전으로 통과.
  - 큰 화면 자동 확대(4K 100% → 약 2배) × Preferences **Mecha UI Size**. 예전 패널은 **Classic RMB Popup**으로.
- **Ctrl + Alt 홀드**: 0.25초 이상 누르면 메뉴가 뜨고, 누르는 동안 클릭해도 안 닫힘(도구는 그 자리에서 바뀜, Duplicate는 제자리 복제). 떼면 닫힘. 그 전에 클릭하면 원래 Ctrl+Alt 그리기. Preferences: Hold Ctrl + Alt.
- **Quick HUD / 키 안내**: 같은 어두운 카드, 큰 글씨, 크기 자동 확대. HUD는 뷰 이름 글자 아래로 이동, 둥근 값 막대.
- 테스트: 130개 파일 3732/3732. test_v02470(33) 추가. ZIP sha256 `c32d992db1ef0778e09d17350e60439e26be4877c2e6c7e5aff7955ca8f36bcf`.

## 0.24.49 — UI/UX 1단계: Modeler식 우클릭 팝업, 최근·즐겨찾기, Quick HUD, 툴바 자동 축소, 키 안내 (2026-10-26)

- **우클릭 팝업 (Substance 3D Modeler 배치 참고)**: 그리기 도구에서 RMB 한 번(두 번 = 도구 종료는 그대로) → 세 칸.
  - 왼쪽 **도구 줄**: 최근 도구 5개 → 구분선 → 즐겨찾기(최대 8, Mecha / Creature / Cloth 세트), 별 = 지금 도구 고정/해제. 아이콘만, 툴팁에 이름.
  - 가운데 **도구 카드**: "Cut tool" 제목, **Shapes / Stamps 탭**(Stamps = PNG 모양), 4열 모양 그리드, Settings(= Quick HUD와 같은 핵심 설정), Edge Finish. Base Mesh는 프로필 카드.
  - 오른쪽 **Actions 패널**: 아이콘 3열 + 작은 제목 — Actions(복제, 합치기, 삭제, 원점, 축 리셋, Auto Smooth) / Resolution(Remesh, Quad Remesh, Low Poly) / Symmetry(라이브 Mirror X·Y·Z — 컷·판이 따라감) / Repetition(Radial Array, Curve Array, Radial Symmetry) / Visibility(숨기기, 모두 보기, 따로 보기) / Live(Ramp·Quad Apply 등, Apply Modifiers).
  - **Select / Move에서 RMB**도 같은 팝업(MECHA LAB 안에서만, Blender 오브젝트 메뉴 버튼 포함). Preferences: RMB Actions Menu.
- **Quick HUD**: 뷰포트 왼쪽 위에 지금 도구의 핵심 설정 3~5개 슬라이더(Cut, Split, Base, Creature Base, Plate, Detail, Surface Draw, Screw, Concept/Path Move, Curve). 드래그 = 값(Shift 미세), 클릭 = 직접 입력, Ctrl+클릭 = 기본값, 선택형은 클릭으로 다음 값, 위 손잡이로 위치 이동. 자체 HUD가 떠 있으면(Armor Plate 라이브) 숨김. Preferences: Quick HUD.
- **하단 툴바**: 좁은 뷰포트에서 버튼이 줄어들다 두 줄로(화면 밖으로 안 나감). Windows 화면 배율(예: 150%)에서 가운데에서 밀리던 문제 수정.
- **키 안내**: 그리기 도구가 켜져 있으면 왼쪽 아래에 그 도구에서 Alt / Shift / Ctrl / 휠 / F / D / RMB / Q·V가 하는 일. 키 동작은 바꾸지 않음. Preferences: Key Legend.
- 테스트: 129개 파일 3699/3699. test_v02469(45) 추가. ZIP sha256 `101d2fb81f63578ef6e93abe84134c911806908ae374ed3990cbc2b23f3d6014`.

## 0.24.48 — Quad Remesh (컷 모서리 유지) (2026-10-26)

- **Quad Remesh (keep cut edges)**: Remesh 패널 새 상자. 선택한 부품(모디파이어 포함)을 복사해 전부 사각형 면으로 다시 짬. Edge Angle보다 날카로운 모서리(+ 직접 Sharp / Crease 지정한 모서리)를 쿼드 선으로 살림. 원본은 숨겨서 그대로 둠. Re-make / Show Original / Apply. 열린(구멍 난) 메쉬는 안내 후 아무것도 안 바꿈.
- 방식 두 가지:
  - **Flow**: Blender QuadriFlow(모서리 보존 켬). 흐르는 쿼드. 컷이 가는 조각을 남기면 그 부분 모서리를 놓칠 수 있음 → 놓친 모서리 길이를 재서 쿼드 1칸 이상이면 경고(보고 + 패널 줄): Faces를 올리거나 Patch 사용.
  - **Patch**: 모서리를 기준으로 평평한 면 조각을 나누고, 조각마다 그 외곽 방향에 맞춘 고른 격자를 채운 뒤 한 번 쪼개서 전부 사각형으로 만듦. 모서리는 원래 자리 그대로. 곡면 부분은 자기 면을 사각형으로 쪼갬. 평평한 하드서페이스 부품용.
- 테스트: 128개 파일 3654/3654. test_v02468(25) 추가. ZIP sha256 `ebb29728d8755767ef538eb56ebe5248003fd5c9c60f2bd78258ca41292ab27e`.

## 0.24.47 — Ramp 옆면 톱니 수정, Ramp Resolution (2026-10-26)

- **Ramp Soft 옆면이 톱니처럼 나오던 문제**: 옆면이 둥글게 넘어가는 구간 폭에 비해 점이 성겨 큰 삼각형으로 이어졌음 → 그 구간에 점 줄 6개를 넣고 간격을 좁힘(점 수 상한 안에서).
- **Ramp Resolution**: Cut GN Edge > Ramp에 슬라이더(기본 20, 움직이면 바로 다시 팜). Base Mesh Ramp는 Resolution을 Ramp Resolution으로 같이 표시.
- 테스트: 127개 파일 3655/3655. test_v02467에 톱니 검사 추가. ZIP sha256 `3d9d0e7d404ffce3d20445c04c57022de2694510c0ab338185dbd34bcb8698a5`.

## 0.24.46 — Cut GN Edge > Ramp, Ramp / Alt 파기 모서리 조각 수정 (2026-10-26)

- **Cut의 GN Edge 메뉴에 Ramp**: 켜고 자르면 평평한 홈 대신 경사 홈 — 처음 그은 변이 가장 깊고(Cut Depth) 반대쪽으로 표면과 만남. Ramp Length / Ramp Soft, GN Edge Chamfer / Bevel = 깊은 쪽 벽 모양(Off = 직각). Base Mesh Ramp처럼 live: ◀ ▶ / Pick Edge로 깊은 변, Cut Depth / 슬라이더로 바로 다시 팜, Apply / Remove. 일반 Cut만(Split · 반전 · Live 컷 제외).
- **Ramp / Base Mesh Alt 파기 모서리에 얇은 조각이 남던 문제**: 둥근 모서리(베벨) 위에 걸치면 커터의 뚜껑과 테두리 벽이 기울어진 표면 노멀을 따라가 조각("귀")이 남았음 → 뚜껑과 테두리 벽은 시선 방향으로 곧게, 안쪽 바닥만 표면을 따라감.
- 테스트: 127개 파일 3654/3654. test_v02467 추가, test_v02465에 모서리 검사 추가. ZIP sha256 `f9d943d57b574750075e334bf9cf167f2acb4ecfb61a38f4d3bbb1f207c4f146`.

## 0.24.45 — Alt: Ramp 깊은 변을 그린 뒤에 고르기 (2026-10-26)

- **Alt: Ramp가 그린 뒤에도 고칠 수 있는 상태(live)로 남음**: 파기 전 메쉬를 보관해 두고, Base Mesh 패널의 RAMP (live) 칸에서 ◀ ▶(다음 / 이전 변) 또는 **Pick Edge**(뷰포트에서 변 클릭)로 깊은 변을 바꾸면 보관한 메쉬에서 다시 팜. Carve Depth / Ramp Length / Ramp Soft를 움직여도 바로 다시 팜. **Apply** = 확정, **Remove** = 파기 전으로. 뷰포트에 다각형 변(흰 선)과 깊은 변(주황 굵은 선) 표시. 한 번에 하나만 live — 새 Ramp를 그리면 이전 것은 그대로 확정. Free Draw 모양은 꼭짓점을 찾아 변 단위로.
- 테스트: 126개 파일 3644/3644. test_v02466 추가. ZIP sha256 `edf257ab6a7e624e11ddf4da985b5316d1c0dd2e96c24f624af10a6603edf257`.

## 0.24.44 — Base Mesh Alt: Ramp(경사 파기) + Ramp Soft, Path Move 자동 Stretch 전환 제거 (2026-10-26)

- **Base Mesh Alt: Ramp**: Alt + 다각형 → 처음 찍은 변이 가장 깊고(Carve Depth, 0 = Height) 반대쪽으로 갈수록 얕아져 표면과 만나는 경사 홈(바닥 = 기운 면). 표면 위의 면이 살짝 눌려 들어간 듯한 다각형 묘사용. **Ramp Length**(1 = 반대쪽 끝에서 표면과 만남, 작을수록 앞쪽에서 만남), 깊은 쪽 벽 = Flat / Chamfer / Bevel 프로파일.
- **Ramp Soft**(기본 0.5): 경사가 표면에 꺾인 선 없이 부드럽게 이어지고, 얕은 쪽으로 갈수록 옆 벽이 둥글게 풀림(깊은 쪽 모서리는 각진 그대로). 0 = 곧은 경사.
- **Path Move**: 단면이 브러시보다 크면 Stretch로 바꾸던 동작(0.24.42) 제거 — 크래시가 났음. 고른 방식 그대로(Extend는 Extend). 급한 꺾임을 펴는 처리는 유지.
- 테스트: 125개 파일 3632/3632. test_v02465 추가, test_v02463 수정. ZIP sha256 `73c22730f70b5fd8f91c779ace079ed0e91a45968f46dce011eecd937cad8769`.

## 0.24.43 — 두 번째 컷이 첫 GN Edge 테두리를 망가뜨리던 버그, Edge Finish가 튀어나오던 문제, Armor Plate Alt Carve Depth (2026-10-26)

- **GN Edge 뒤 두 번째 컷이 첫 홈 테두리를 다시 깎던 버그**: GN 결과에 컷 표시 속성과 UVMap이 점 쪽에 한 벌 더 남아(테두리를 곡선으로 바꿀 때 따라옴) 커밋 때 하나만 지워짐 → 다음 컷이 지난 컷 면까지 새 테두리로 보고 다시 마감. 이제 쓸어 만든 몸체는 불리언 전에 속성을 버리고, 컷 표시 속성은 모두 지움(UVMap은 원래 하나만).
- **Edge Finish(기존 베벨 / 챔퍼)가 판 밖으로 튀어나오던 문제**: 홈이 판의 바깥 베벨 테두리와 만나는 모서리에서 Blender 베벨이 점을 판 밖으로 밀어냈음(검은 덩어리) → 베벨 뒤 원래 형태 밖으로 나간 점은 원래 표면 위로.
- **Armor Plate Alt Carve Depth**(패널, Face Size 아래): Alt 파기 깊이(0 = 플레이트 높이). 벽 모양은 같은 비율로.
- 테스트: 124개 파일 3621/3621. test_v02464 추가, test_v02462에 깊이 추가. ZIP sha256 `4b9c1ed3ab78eb0c5c87d56abcd8a9ee98f4dd5e9cd5e7fa2da80721f7dc3a78`.

## 0.24.42 — Armor Plate Alt = 반대로 파기, Path Move가 브러시보다 크게 늘어나던 / 지저분하던 문제 (2026-10-26)

- **Armor Plate Alt + 그리기**: 그 자리에 생길 플레이트를 표면 기준으로 뒤집어(바깥으로 나온 만큼 안으로) 불리언으로 파냄 → 플레이트 높이만큼 깊은 홈, 벽은 플레이트 프로파일(챔퍼 / 베벨 / 계단 …). 플레이트 오브젝트는 남지 않음. Alt 없이 = 예전처럼 플레이트.
- **Path Move가 작은 브러시인데 판 전체를 늘리던 문제**: Extend / Separate Tube는 잡은 곳의 단면 전체를 끌었음 → 단면이 브러시 반지름의 1.6배보다 크면(또는 단면을 못 찾으면) 그 드래그는 브러시 크기만큼만 끄는 Stretch로(헤더에 표시).
- **Path Move 마감이 지저분하던 문제**: 경로가 단면 반지름보다 급하게 꺾이면 링이 서로 겹쳐 접히고 찢어졌음 → 그런 곳은 단면 반지름 이상으로 둥글게 펴서 쓸어 감(끝점 그대로).
- 테스트: 123개 파일 3606/3606. test_v02462 · test_v02463 추가. ZIP sha256 `0aa33b1b8c021702ad7bc0faff156aa1bb5688e69bb5850a56fac264f2eea196`.

## 0.24.41 — GN Edge(지오메트리 노드 테두리 챔퍼 / 베벨), Stamp Face 바로 붙기, 나사가 기울어지던 문제 (2026-10-26)

- **GN Edge (Geometry Nodes)** — Cut / Split 패널의 새 메뉴(기존 Edge Finish와 따로): Off / Chamfer / Bevel, Width, Segments(Bevel), Split은 Both / Side A / Side B. 그은 영역의 테두리(새 모서리)를 따라 챔퍼 / 베벨 단면을 지오메트리 노드로 쓸어(Mesh to Curve → Curve to Mesh → Set Position → Mesh Boolean) 깎아냄 → 테두리 전체에 같은 너비로 고르게. 기존 Edge Finish는 촘촘한(삼각형) 메쉬에서 짧은 모서리 때문에 너비가 줄거나 거의 안 생겼음. 켜면 그 컷에서는 Edge Finish를 건너뜀. Auto Apply ON에서만.
- **Stamp Face**: 고스트 면을 찍으면 가장 가까운 메쉬 표면에 그 면이 바로 붙음. Stamp Face 상태에서 메쉬가 아닌 곳을 클릭하면 고스트를 옮기지 않고 이유를 알려줌(Targets가 Selected Only / Active면 그 메쉬를 선택하거나 Auto Target으로).
- **Screw Stamp가 비스듬히 서던 문제**: 클릭한 삼각형 하나의 방향 대신 나사 머리 아래 둘레 8곳을 찍은 평면 방향으로 섬 — 불리언으로 생긴 가는 삼각형 / 살짝 휜 큰 면에서 크게 기울어졌었음.
- 테스트: 121개 파일 3596/3596. test_v02460(나사), test_v02461(GN Edge) 추가, test_v02459에 가까운 표면 찾기 추가. ZIP sha256 `68baf53c89f001a1a8345a42eff237bfec40e4d4549357034b7cd35dbb2eb6fd`.

## 0.24.40 — Path Move Hardness, 프리미티브 Remember Turn · Stamp Face (2026-10-26)

- **Path Move 전용 Hardness**: Concept Move의 Hardness와 따로(기본 1 = 지금과 같음). 전에는 Move와 같은 값을 썼고, 기본 방식 Extend에서는 아무 효과가 없었음.
- **Extend / Separate Tube**: Hardness를 낮추면 경로가 꺾일 때 컷에서 각지게 꺾이지 않고 둥글게 휘어 나옴(낮을수록 크게, 섹션 반지름 × 3 × (1 − Hardness)). 원래 메쉬(컷 뒤쪽)는 그대로. 드래그 미리보기에도 보임.
- Stretch(slow)도 이 슬라이더를 씀(기본 1 = 단단하게; 전에는 Move의 0.5를 같이 씀).
- **프리미티브 Remember Turn**(기본 켬, Align to Surface 옆): 메쉬 표면에서 고스트를 돌려 놓으면, 다음에 다른 곳을 클릭해도 그 표면에 대해 같은 각도로 놓임(전에는 클릭할 때마다 Z가 표면 밖으로 리셋). 끄면 예전처럼, Turn 90의 Reset을 누르면 다시 처음부터.
- **프리미티브 Stamp Face**: Pick Stamp Face를 누르고 고스트의 한 점을 찍으면 그 면이 메쉬에 닿는 면이 됨(노란 점 + 화살표). 메쉬를 클릭하면 그 면이 표면을 향해 붙고 **Stamp Depth**(그 면 뒤로 모양이 뻗은 길이의 비율)만큼 들어감 → Add(Enter) = 붙이기, Subtract(Alt+Enter) = 그 면 모양으로 찍어 파기. **Stamp on Click**을 켜면 클릭하자마자 불리언(Alt+클릭 = 파기). X로 해제. 크기를 바꿔도 찍은 자리가 따라감.
- 테스트: 119개 파일 3576/3576. test_v02458 · test_v02459 추가. ZIP sha256 `16b2b9e46132c53ff22233ff22e00ebdd3f8275d9fa339df31ecba0cfbd1723f`.

## 0.24.39 — Base Mesh Alt 표면 파기 결과가 깨끗해짐, Bevel Segments · Resolution 적용 (2026-10-26)

- **Alt 파기(Carve Height / Through / Inside)가 깨끗하게**: 얇은 Line 띠 안에 점이 몇 개 안 들어가서 Chamfer 경사 · 바닥 · 벽이 들쭉날쭉하고 조각 면이 많았음 → 모양의 가장 좁은 폭에 맞춰 점을 고르게 깔고, Chamfer / Bevel 가장자리가 끝나는 자리에 점 한 줄을 정확히 넣어 벽이 곧게, 표면 방향(노멀)을 깊이만큼 부드럽게 이어 꺾인 판에서도 바닥이 고르게. Chamfer 시작점이 표면 살짝 위라 표면과 겹치는 조각 면이 안 생김. 굽은 판 테스트: 찌그러진 면 195 → 0, 사용자 FBX: 19 → 0(면 수 1984 → 983).
- **Bevel의 Segments 슬라이더가 Alt 파기에도 적용**(가장자리 둥근 단 수, 전에는 4단 고정), **Resolution**을 올리면 파는 모양의 점이 더 촘촘해짐(28 = 기본). Chamfer는 원래 한 면 경사라 단 수가 없음.
- 테스트: 117개 파일 3551/3551. test_v02457 추가(굽은 판에 Line으로 Chamfer / Bevel / Flat 파기 — 닫힌 메쉬, 조각 면 없음, 띠 가운데 깊이 = Carve Depth, Segments · Resolution). ZIP sha256 `f0ecf159ea8d5fcf95e237b9299a6c4476bbd34120d15961e4ee188e51f5bae8`.

## 0.24.38 — Base Mesh Alt 파기가 표면을 따라감, Alt: Through / Inside(내부 프레임), Carve Depth, Export Selected / Visible, 엉뚱한 곳이 깎이던 버그, Radial Symmetry 축 고정 · Distance, Mesh Curve 크기 점 위치 (2026-10-26)

- **Base Mesh Alt(Carve Height)가 표면을 따라 파임**: 그린 모양을 표면에 붙이고, 어디서나 표면에서 Height만큼 안으로 팜 → 굽은 면에서도 고른 깊이의 홈 / 포켓(전에는 평평한 판 커터라 바닥이 평평, 깊이가 들쭉날쭉). Flat = 직각 벽, Chamfer / Bevel = 입구 가장자리가 그 모양(Border Width). Line · 메쉬 밖까지 그은 선도. Creature 프로파일은 예전 방식, Alt: Like Cut은 Cut 툴 방식 그대로.
- **Carve Depth**(Alt: Carve Height일 때): Alt로 파는 깊이를 따로(0 = Height). 얇은 판을 같은 Height로 만든 뒤 Alt로 파면 판을 뚫고 반대쪽까지 잘렸음 → 판 두께보다 작게 두면 앞면만 파임.
- **Alt: Through**: 그 자리 두께를 재서 항상 반대편까지 뚫음(창문) — 나머지는 프레임.
- **Alt: Inside**(내부 프레임): 두께의 가운데만 파냄(앞 · 뒤 면은 **Skin** 비율만큼 남음) → 그린 선이 옆 벽을 지나가는 곳에 창문이 생김(파이프 내부 프레임 느낌).
- **엉뚱한 곳(옆 벽)이 깎이던 버그 수정**: 표면 정보 캐시가 이름 · 점 개수가 같은 다른 메쉬(또는 Edit Mode로 점만 옮긴 메쉬)의 옛 모양을 썼음 → 모양 자체로 구분. Surface Draw · Cape · 망토류 · Base Mesh 파기 모두.
- Sketch에서 Alt+Enter: 외곽선 가운데가 메쉬 밖이어도 대상을 찾음, Carve Height / Through / Inside도 표면을 따라감.
- **Radial Symmetry 축 고정**: Apply 전까지 처음 찍은 중심점 · 축이 그대로 — 오브젝트를 돌리거나 옮기면 그 오브젝트만 돌고 복사본은 같은 축을 중심으로 다시 배치(전에는 축이 같이 날아감). Pivot을 옮기면 전체가 따라감, Update 버튼 안 눌러도 됨.
- **Radial Symmetry Distance**: 축에서 거리 조절(+ 멀리, − 가까이) — 메쉬가 축에서 곧게 밀려나고 복사본도 같이.
- **Mesh Curve 주황 크기 점**: 굵기와 상관없이 항상 흰 점 바로 옆(화면 26px)에 — 전에는 반지름 거리(튜브 표면)라 굵으면 멀고 가늘면 겹쳤음. 끌면 거리 비율만큼 굵기(바깥 = 굵게, 안쪽 = 가늘게), 끄는 동안 점이 마우스를 따라오고 놓으면 다시 옆으로.
- **Export Selected / Export Visible**: 선택한 메쉬만 / 화면에 보이는 메쉬 전부(숨긴 건 제외). 선택이 없으면 Visible로.
- 테스트: 116개 파일 3542/3542. test_v02454에 공 위 파기(바닥이 표면에서 Height만큼 고르게) · Carve Depth 추가, test_v02455에 Selected / Visible 추가. ZIP sha256 `04ffc59c69b4418807fee075e5fed9e4a430aa6e4e15f893607e374c3a3a6750`.

## 0.24.37 — Base Mesh Invert, Alt = Height 깊이만큼 파기, Export 버튼, ZBrush에서 메쉬 깨짐 수정 (2026-10-26)

- **Base Mesh Invert**(Sketch · Stick to Surface 옆 버튼): 켜면 높이가 그린 위치에서 뒤로(메쉬 안쪽으로) 늘어남. Stick to Surface 켜고 끄고 둘 다, 외곽선 위치는 그대로. 만들 때의 방향(이미 만든 건 안 바뀜).
- **Base Mesh Alt = Height 깊이만큼 파기**(새 기본값): Alt + 그리기 = 그린 모양을 Height 깊이만큼 메쉬에 파냄. 패널 **Alt: Carve Height / Alt: Like Cut**에서 예전(0.24.5) Cut 툴 방식도 고를 수 있음. Line이 메쉬 밖으로 나가도 찾음, Invert 켜도 항상 안쪽으로, Sketch의 Alt+Enter도 같음.
- **Surface Draw Alt = 홈 파기**: 일반 메쉬 위에 Alt + 선 = 그 띠(폭 · 가장자리 그대로)를 Height 깊이만큼 홈으로 파냄, Fill Area + 라쏘 = 그 면적을 Height 깊이로 파냄. 이미 그린 띠 위의 Alt는 예전처럼 띠를 잘라냄. Alt 미리보기도 띠 모양.
- **Export 버튼(OBJ / FBX)**: 모든 툴 패널 아래 'Export Selected' + ZBrush 패널 맨 위. 선택한 메쉬를 파일로 저장(ZBrush 연결 필요 없음), 모디파이어 적용, 원래 이름 그대로.
- **ZBrush에서 메쉬가 찢어지던 문제**: Boolean / 컷으로 생긴 n-gon(5각 이상 · 오목한 면)을 ZBrush가 부채꼴로 쪼개 찢어짐 → **ZBrush-safe Faces**(기본 켬): 내보낼 때만 n-gon을 깔끔한 삼각형으로 나눔(사각형은 그대로, Blender 메쉬는 안 바뀜). Export 버튼과 ZBrush Send 둘 다.
- 테스트: 115개 파일 3523/3523. 새 test_v02453(Invert 7) · test_v02454(Alt 파기 11) · test_v02455(Export 8). test_v0100_regression · test_v0245의 0.24.5 Alt 검사는 Alt: Like Cut으로. ZIP sha256 `91fd65c098f7913cbc2a7bf28aa3465b6d0f3eb3b83ac90f25fa7bd123b21dbc`.

## 0.24.36 — 컷 라인 깊이(From Surface), Slow Line(레이지 마우스) 버튼, Shift = 0 / 45 / 90° 직선, Box Hide Line, Base Mesh 위치 수정 (2026-10-26)

- **컷 라인도 Cut Depth만큼만**: From Surface일 때 점 2개 직선 컷도 Cut Depth 깊이까지만 잘림(전에는 빠른 평면 자르기라 끝까지 잘림). 꺾인 선 · Line 모드는 원래 깊이 적용. Through All은 예전처럼 빠른 평면 컷.
- **Slow Line (Lazy Mouse) 버튼**: 모든 그리기 툴 패널 맨 위(대상 선택 아래)와 Path Move 패널에서 켜고 끔. 켜면 누르고 끌며 그리는 선(Free Draw, Line 모드 선, Path Move 길)이 마우스를 천천히 부드럽게 따라옴. Smoothing Strength · Lazy Radius · Guide 조절. 같은 설정 하나라 한 곳에서 켜면 모든 툴에 적용.
- **Shift = 0 / 45 / 90° 직선**: 누르고 끌며 그리는 선(Free Draw · Line 모드 선)에서 Shift를 누르고 있으면 Shift를 누른 지점부터 0 / 45 / 90° 방향 직선. 떼면 그 끝에서 다시 자유롭게 이어 그림(Slow Line 켜도 동작). 점 찍는 Lasso는 원래 Shift 45°.
- **Box Hide도 Line으로**: Line 버튼 켜고 그으면 선 따라 Line Width 폭의 띠만큼 숨김(Alt = 다시 보이기 그대로). Line이 동작하지 않는 툴에서는 Line 버튼이 흐리게 표시됨.
- **Base Mesh가 뒤에 생기던 문제 수정**: 선 / 외곽선의 한가운데가 메쉬 밖(허공)이면 3D 커서 깊이(오브젝트 안쪽)에 생겼음 → 이제 선 / 외곽선 아래에서 가장 앞에 있는 표면에 생김(Stick to Surface 켜고 끄고 둘 다). 가운데가 메쉬 위면 예전과 같음, 아래에 아무것도 없으면 예전처럼 3D 커서 깊이.
- 테스트: 112개 파일 3497/3497. 새 test_v02448(컷 깊이 3) · test_v02449(Slow Line 6) · test_v02450(Shift 직선 10) · test_v02451(Box Hide Line 2) · test_v02452(Base Mesh 위치 5). ZIP sha256 `b653fe720212e07815bd62eeb24842dcfa2e022174c27da5339a2af11724bbec`.

## 0.24.35 — Ctrl+Z에도 브러시 크기 유지, Knife Mesh 버튼 (2026-10-26)

- **Ctrl+Z 해도 브러시 크기 그대로**: 그린 걸 되돌려도 Line Width, Stamp Radius, Mask Brush Radius, Concept / Path Move 크기(Real Size 포함), Screw Size, Surface Draw 다음 획 Width / Height가 초기화되지 않음(브러시 모양 · 툴은 원래 유지).
- **Knife Mesh**(Concept Move · Path Move 패널): 선택한 메쉬를 X / Y / Z로 고르게 슬라이스 — 모양은 그대로, 면만 고르게 나눠서 무브가 원하는 곳에서 휨. **Cuts** = 가장 긴 변의 칸 수(기본 12), 다른 변도 같은 간격. Ctrl+Z로 되돌릴 수 있음.
- 테스트: 107개 파일 3471/3471. 새 test_v02447(7). ZIP sha256 `3475bb30649840d39f198f3c83c09eb7ad094a9aacd981027d8081da7bcdf6be`.

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
