# Mecha Lab 0.24.93 — 설치 · MECHA LAB Workspace · 사용법

> **검증 수준:** Linux headless Blender **5.2.3**(`bpy`)에서 자동 테스트 209개 파일 / 5,258개 항목(전체 실행에서 코너 카드 글자 기대값 2개 실패 — 고친 뒤 통과) + 무작위 기능 조합 크래시 테스트 280개, 그리고 0.24.81부터 리눅스 가상 화면의 **진짜 Blender 5.2.3 창** 자동 테스트(설치 · 워크스페이스 · 그려진 막대 · 진짜 마우스 Cut · Tab · 단축키 충돌 목록) 13/13를 돌렸습니다(결과: `test_report.md`).
> **Windows 11 + Blender 5.0.2 GUI에서는 실행된 적이 없습니다.** `GUI_TEST_CHECKLIST_KO.md` 맨 위 0.24.81 절을 먼저 확인해 주세요.
> 문제가 남아 있으면 N > Mecha Lab > Workspace & Hotkeys > **Run Mecha Lab Self Test** 결과(클립보드)를 보내 주세요.

## 0.24.93 Paint Lab · 앞판 + 뒷판 봉제 · Sew Copy · Stop at Pins · 패딩
- **PAINT**(오른쪽 위 카드 MECHA | ZBRUSH | PAINT): 폴리페인트 화면. 브러시 선반에 Paint · PaintSoft · PaintSquare · PaintBlend · Smear · Blur. 왼쪽 선반: **Load Photo** 로 사진을 가져와 Hue · Saturation · Contrast · Brightness · Rotation · Flip 으로 보정하면 그게 브러시 텍스처 / 스텐실; **Q** 로 스텐실을 켜고 끄고(켜지면 오른쪽 드래그로 옮김, Shift: 크기, Ctrl: 회전); **Alt + 모델 클릭** = 폴리페인트 색 스포이드(Alt + 다른 메시 = 선택); 마스크 **By Brightness**(Black · White 범위) · **By Edges**(각도 · Soft · Grow) · **By Cavity** · Invert · Clear; **Look** Paint(기본) / Exact / Material — 색이 그대로 보이는 세팅(paint 스튜디오 라이트 · Standard 뷰 변환, Material 은 중성 HDRI + Khronos PBR Neutral).
- Cloth Drape 패널의 **Front + Back**: 라쏘 하나로 몸의 앞 · 뒤에 같은 조각을 깔고 옆선을 봉제해 몸을 감쌉니다(위아래는 열림, Pin Rim = 윗변만). **Sew Copy**: 뽑아 둔 판을 복사해 가장자리끼리 꿰매고 판을 콜리전으로 복사본만 시뮬(Puff · Wrap Pressure · Looseness · Gravity).
- **Stop at Pins**(Wrinkle Lines · Cloth Drape): 켜면 천이 가장 낮은 고정 점보다 아래로 안 처집니다.
- 패딩: ZBrush 탭에서 Ctrl 드래그로 누빔선을 마스크하고 선반의 Cloth Filter **Inflate** 를 끌면 마스크 선은 그대로, 칸만 부풀어 누빔 패딩이 됩니다(실제 창에서 확인).

## 0.24.92 Wrinkle Lines(주름 선)
- MECHA LAB 의 **Wrinkle Lines** 도구(Cloth 그룹; ZBrush 선반의 "Draw Lines" 버튼으로도): 메시 위에 선을 **드래그**로 긋고(점 드래그 = 이동, Shift+클릭 = 점 추가, Ctrl+클릭 = 점 삭제, X = 선 삭제), **Space** = 선을 따라 얇은 튜브(슬라이더 실시간: Wrinkle Size · Fold Strength · Tube Lift · End Fade · Line Strength), **Space 한 번 더** = 메시 복사본을 천으로 덮어 시뮬(Looseness · Shrink · Gravity · Silhouette Keep · 원단), **Enter** = 메시에 쓰기, **Esc** = 되돌리기. 선을 안 긋고 Space 를 누르면 **내가 스컬핑한 능선 그대로**가 콜리전이 되어 천이 떨어집니다(튜브 단계 건너뜀).
- 기본값은 참고 영상에 가장 가까웠던 조합(헐렁함 20 %, 중력 100 %, Cotton). 천 조건은 전부 슬라이더라 취향대로 바꾸고 Presets 에 저장.
- 콜리전은 거리 격자로 가볍게, 4만 점 넘는 메시는 데시메이트 사본에서 돌고 결과만 원래 메시에(**Sim Points**, 0 = 끔).
- **Cloth Drape**(Cloth 그룹): 메시 위에 라쏘 → 그 영역에 헐렁한 천이 "Cloth Drape" 오브젝트로 생김 → **Space** 로 떨어뜨림(가장자리만 고정, 라쏘 아래 몸만 콜리전) → **Enter** 남김 / **Esc** 지움. 원단 · 헐렁함 · 조임 · 중력 · 달라붙음 · 틈 · 세밀도 · 프레임 슬라이더, 바꾸고 Space 면 다시. **Drape This Mesh** 버튼: 라쏘 대신 내가 리메시한 메시 자체를 천으로(활성 = 천, 같이 선택한 메시 = 몸; 열린 가장자리 · 선택한 점 고정; Esc 되돌림). **Wrap This Mesh** 버튼: 보자기처럼 몸 전체를 같은 형태의 천이 감쌈(Looseness + Wrap Pressure; 원통은 위아래 끝 고정). **Thickness** 로 두께. 몸에 Wrinkle Lines 로 선을 그어 두면(**Draw Lines**) 세 모드 모두 그 선이 튜브가 되어 천이 걸림(**Lines as Tubes**).
- **ZBrush 탭**: Blender 클로스 브러시 8개(ClothDrag …; 선반에 4개, B 팝업에 전부), 왼쪽 선반에 Cloth Brush 설정 상자와 Cloth Filter 버튼.
- 메시는 **면이 고른 것**(DynaMesh · Quad Remesh 결과)이 좋습니다. 가로 세로가 심하게 다른 길쭉한 면의 격자에서는 세로 줄무늬가 납니다(KNOWN_LIMITATIONS).

## 0.24.91 컷 Edge Finish · 정리 속도
- 들쭉날쭉한 테두리(DynaMesh 노이즈)에 베벨 · 챔퍼 컷이 몇 분씩 걸리던 것: 폭을 줄여 다시 하고, 그래도 안 되면 1초 안에 건너뛰고 경고줄에 이유. 퍼즈 측정 90초 → 28초.
- 컷 결과 정리(바늘면 · 스파이크)가 부품 전체가 아니라 그 둘레만 다룸.

## 0.24.90 Cloth Plate 라이브 값
- 5.2 에서 사라졌던 LIVE 상자의 값들(Trim Width · Trim Height · Puff · Fold …)이 그룹별 슬라이더로 돌아옴. 길이는 부품 크기의 %.

## 0.24.89 Belt Maker
- 폭이 **루프 크기의 %**(Relative, 기본 7.5 %)라 큰 몸통에서도 가늘지 않음. 끄면 길이로. Defaults 버튼으로 기억된 설정 초기화.
- 130만 면 몸통: 첫 벨트 0.8초, 슬라이더는 바로.

## 0.24.88 Panel Cloth 빠르게 · 품질
- **Background 켜져 있으면 클로스 베이크가 두 번째 블렌더에서** 돌고 창은 그대로. 천은 바로 생기고 끝나면 주름이 얹힘. 상자에 진행 줄 + Cancel.
- 자기 충돌 기본 켜짐: 천 계열 프리셋의 "뚫고 지나간 면" 0. Padding 계열은 35 ~ 45 % 빨라짐. 자세한 숫자는 CHANGELOG.

## 0.24.87 그룹 박스선 전체 끄기
- 장면 설정 **Group Box Lines**(기본 켜짐): Layers 패널 머리의 상자 버튼 또는 Groups 카드 맨 위 토글. 끄면 모든 그룹의 상자 선이 안 보입니다(선택해도). 그룹별 눈은 그대로.
- 컷 엔진 검토 문서 `CUT_ENGINE_REVIEW_KO.md`(국소 Boolean vs SDF 측정 비교, 다음 단계).

## 0.24.86 하이폴리 컷(실험) · 정리 · 구멍 메움 영역만 · 백그라운드 Quad Remesh / Re-Fix
- **High Poly(실험, 기본 꺼짐)**: 컷 설정 Advanced. 켜면 10만 면 이상 부품의 Cut · Split 불리언이 획 주변만 상대하고, 결과가 이상하면 전체 불리언으로 자동 전환. 전체 불리언과 같은 솔리드(부피 1e-6 이내, 닫힘, 바깥 면 동일)인지 세 부품에서 확인함. 속도는 Exact 가 필요한 부품과 100만 면 이상에서 2 ~ 4배(CHANGELOG 표).
- **컷 정리 · 구멍 메움이 영역만**: 5만 면 이상 부품의 컷에서 정리가 바뀐 면만 꺼내서 처리 → 130만 면 라쏘 컷 10.4 → 5.5초(기존 경로, High Poly 끄고도; 켜면 3.3초), 210만 면 24 → 22초(켜면 8.5초).
- **Background**(ZBrush 선반 · Mesh Tools, 기본 켜짐): Quad Remesh · Re-Fix 가 2만 면 이상이면 두 번째 블렌더에서 돌고 창은 그대로. 상태 줄 + Cancel. 돌아가는 동안 그 부품을 바꾸면 결과는 버림.
- 하드웨어: 데시메이트 · 쿼드 리메시 C 엔진은 코어 수만큼 스레드(32스레드 머신에서 32), 백그라운드 작업은 남는 코어. 블렌더 불리언 · DynaMesh 의 스레드 수는 애드온에서 못 바꿈.

## 0.24.85 하이폴리 컷 속도 · 결과 음영 · 연결된 그룹 복사 · 박스선 눈 · 미러 평면
- **컷 · 스플릿이 하이폴리에서 3 ~ 4배 빨라짐**(82k면 2.8 → 0.6초, 327k면 8.8 → 2.4초): 결과 정리가 컷 주변 면만 봄. **데시메이트 속도**도 0.24.81 수준으로 돌아옴(정리 단계가 결과 면 수만큼 느리게 하던 것).
- **Shading**(Decimate 줄, 기본 Smooth): Decimate · Quad Remesh · Re-Fix 결과를 스무스 + 각도(Hard Edges 각도)보다 꺾이는 변 샤프로 — 메시 데이터라 내보낸 파일이 받는 쪽에서 설정 없이 같은 모양. Flat / Keep 도.
- **Re-Fix** 결과 면 정리: DynaMesh 뒤 스무딩 2회(Smooth 0 ~ 6) + Decimate Quads.
- **Linked Copy**(Groups 카드 · 메카 메뉴 Groups): 복사한 그룹의 부품이 원본과 한 메시 — 원본을 Cut · Decimate · Re-Fix 하면 복사본도 바뀜. Box Hide 같은 모디파이어 단계는 오브젝트마다라 전파 안 됨. Duplicate 는 전처럼 독립.
- **그룹 박스선 눈**: Layers 패널 그룹 줄 · Groups 카드 — 그룹마다 상자 선 끄기.
- **미러 평면**: Symmetry 카드 Mirror 절의 Plane 토글 · −5 % / +5 %, Preferences 의 Show Mirror Planes / Mirror Plane Opacity.

## 0.24.84 Re-Fix 버튼
- **Re-Fix**(Mesh Tools / ZBrush N 패널 Geometry / 액션 `REFIX`): 지저분해진 부품을 DynaMesh(알맞은 점 수) → 깨끗한 Decimate 또는 Quad Remesh 로 한 번에 되돌림. Faces 0 = Auto. 라이브 단계는 먼저 굳힘, 메시지에 전후 면 수 · 열린 변 · 자기 교차.
- 넓은 베벨이 안 들어가던 촘촘한 부품은 Re-Fix 한 번 뒤에 넣으면 됩니다.

## 0.24.83 컷 · 컷 베벨 · GN Edge · 컷 램프 · Box Hide · ZBrush 파이프라인 깨짐 수정
- 0.24.82의 결과 정리가 **닫힌 컷을 열던 것** 수정(정리 단계마다 열리면 버림, 0-면적 · 바늘 면은 하나씩).
- **From Surface** 로 두 부품 위에 그리면 둘 다 자기 표면에서 포켓(위에 뜬 판이 안 잘리고 Box Hide 가 아무것도 안 하던 것).
- **Box Hide** 를 같은 부품에 두 번 / 가려진 부품 위 띠가 "non-manifold" 로 실패하던 것 수정.
- **Hard Edges** 베벨이 촘촘한 몸통에서 깨지면 폭을 줄이고, 안 되면 베벨 없이 + 메시지.
- **크래시 수정**: 컷 설정(Cut Depth · GN Edge · Ramp)을 바꿀 때 마지막 컷이 다시 잘리는 것이 설정 업데이트 안에서 돌다 블렌더가 죽던 것 → 타이머로 미뤄 돌림.
- 컷 베벨 · GN Edge 가 메시를 깨뜨리면 그 마감만 버리고 평범한 컷을 남김(메시지).
- GN Edge 가 남기던 작은 네면체 조각 제거. 컷이 깨지면 부품이 자기 자신을 가로지르는지 알려 줌(DynaMesh / Fix Mesh 먼저).
- Cut Ramp 는 테스트로 측정(깊은 쪽 0.26 / 가운데 0.14 / 반대쪽 0.03 of 0.3). 자세한 것은 CHANGELOG.
- 설치: 이전 0.24.8x 위에 그대로 설치됩니다. Preferences 맨 위 빌드 도장이 zip 이름과 같은지 확인하세요.

## 0.24.82 Redo Last · 빌드 도장 · 내보내기 정리 · Quad Remesh 수율
- **Redo Last**: 부품 만드는 도구로 그린 뒤 설정을 바꾸고 Actions 카드 / 메카 메뉴 / N 패널의 **Redo with current settings** → 같은 획이 지금 설정으로 다시 그려짐(만든 부품은 교체).
- **Live Stack**: Layers 패널 LIVE STACK 섹션 / N 패널 — 부품의 라이브 단계(Mirror · Box Hide · Armor Shell · 베벨 …)를 순서대로, 눈 · ▲▼ · Apply · 제거 · Apply All.
- 실패 · 경고 메시지가 뷰포트 아래에 4초 토스트로.
- Preferences > Hotkeys > **Check Conflicts**: Mecha 키가 가리는 블렌더 키 목록(클립보드).
- zip 이름이 `mecha_lab-0.24.82_<날짜-시각>.zip`, Preferences 맨 위에 설치된 빌드 도장.
- Export: 빈 오브젝트 제외, 작은 단순 부품의 쿼드 과밀 수정(자기 면 수 8배 상한), Client Look 열린 엣지 수정(0.24.81).
- Quad Remesh: 얇은 벽 부품에서 요청의 1/6만 나오던 All Quads가 모자란 만큼 자동 재시도. 단계별 측정표는 CHANGELOG.
- 설치: 이전 0.24.8x를 제거하지 않아도 같은 확장 ID라 덮어써집니다. Preferences의 빌드 도장이 zip 이름과 같은지 확인하세요.

## 0.24.81 그룹 복사 · 그룹 원점 · Quad Remesh 속도 · 알파 커서
- 그룹을 고르고 **Shift+D**(Alt+D, 메뉴 Duplicate): 핸들만이 아니라 그룹 통째(부품 · 안의 그룹 · 반복)가 복사되고 바로 이동. Groups 카드 / 메카 메뉴에 **Origin to Geometry**(핸들을 부품 가운데로).
- ZBrush 선반 · Mesh Tools의 **Quad Remesh**가 하드 엣지 많은 부품에서 2 ~ 4배 빨라지고 면 수가 요청에 가깝게(4배 재시도 없앰).
- ZBrush 브러시 원 안에 알파가 검게 그려지던 것 기본 끔(Preferences > Alpha in Brush Circle).
- Cut · Split · 라인 컷 · Box Hide가 깨진 부품에서 manifold 경고만 내고 안 잘리던 것: 자르기 전에 Fix Mesh 자동(Preferences > Auto Fix Mesh before Cut). Mirror 켠 부품에 Box Hide 하면 사라지던 것 수정. Export Quad Mesh + Client Look에 열린 엣지가 남던 것 수정.
- 깨진 부품에서 Cut / Split / Box Hide가 "manifold" 경고만 내고 안 잘리던 것: 자르기 전에 Fix Mesh가 자동으로 돎(Preferences > Auto Fix Mesh before Cut). Mirror를 켠 부품에 Box Hide 하면 부품이 사라지던 것 수정.

## 0.24.80 전체면 익스트랙트(Armor Shell)
- Face Extract 도구 패널 맨 위 **Extract Whole Surface**: 부품 겉면 전체를 감싸는 닫힌 껍데기(Gap만큼 띄우고 Thickness만큼 바깥으로). Gap · Thickness · Smooth · Detail · Fewer Faces 슬라이더가 바로 반영되고, 그대로 Cut / Split로 잘라 갑옷 판으로(자르기 전에 알아서 굳음, 안의 부품은 안 잘림).
- ZBrush 탭: N 패널 Extract 옆 **Shell**, SubTool 카드 **Armor Shell**(두께 = Thick, 바로 일반 메시).

## 0.24.79 컨셉 무브 설정 위 막대 · 화면 이동 NAV
- Concept Move · Path Move · Silhouette Move의 브러시 설정이 Mecha 위 막대에.
- 오른쪽 위 카드 **NAV ZBrush | Blender**: ZBrush 화면은 그대로 두고 화면 이동만 블렌더 기본(가운데 버튼)으로. Blender로 두면 MECHA LAB 선택 도구가 빈 곳 드래그로 박스 선택.
- ZBrush 이동일 때: 빈 곳 클릭 = 선택 해제, ZBrush 화면 선택 모드(Q)에서 다른 SubTool 클릭 = 그것으로.

## 0.24.78 라쏘 설정은 위 막대 같은 자리에 · 도구별 기억
- 모든 그리기 도구의 위 막대에서 SHAPE 바로 옆에 LASSO(모양 옵션) · CORNERS(모서리 Round / Chamfer). 잘린 엣지 베벨(Cut / Split GN Edge · Edge Finish · Split 면별, Base Mesh 테두리 베벨)도 위 막대.
- 라쏘 설정이 도구마다 따로 기억됨(Preferences > Lasso Settings per Tool로 끄기).
- 컨셉 무브 · Path Move · Silhouette Move가 블렌더 위 막대를 설정으로 채우지 않음(설정은 오른쪽 패널).

## 0.24.77 지브러시 화면에서도 각지게 · 컷 챔퍼 끝 · 쿼드 내보내기 · Wire / Solo
- 라인 컷이 판 테두리로 빠져나가는 곳의 GN Chamfer / Bevel 끝에 뾰족한 이빨이 남던 것 수정. 깨진 부품에서 Chamfer / Bevel이 약 3배 빨라짐(그래도 깨진 부품은 먼저 **Fix Mesh** 권장 — 경고에 나옴).
- Export > Quad Mesh가 작은 · 디테일 많은 부품도 모양 그대로(부품마다 쿼드 크기, 모양이 벗어나면 더 촘촘하게, 안 되면 고친 원래 모양).
- MECHA LAB 화면 오른쪽 위 카드에 **VIEW Wire / Solo**: 와이어프레임 켜기 / 끄기, 고른 부품만 보기.
- Path Move(Whole) · Silhouette Move가 어떤 메쉬에서는 Separate Tube로 빠지던 것 수정.
- Make Quad · Quad Remesh처럼 면은 스무스 + 엣지는 Sharp인 부품이 지브러시 화면(조각 모드)에서 매끈하게 보이던 것: 지브러시 화면에 있는 동안만 Sharp 엣지 옆 면을 평면으로 보여 주고, MECHA LAB으로 돌아오면 원래대로.
- Alt가 안 되면 Edit > Preferences > Input > Mouse > Emulate 3 Button Mouse를 끄고 ☰ > Save Preferences.

## 0.24.76 Fix Mesh · 깨진 부품 쿼드 · 쿼드로 내보내기 · 꺾인 면 자르기 · 지브러시 키 · 펜 우클릭 · Silhouette Move
- **Fix Mesh**(Mesh Tools 탭 · Remesh 도구 패널): 불린 · 합치기 · 내보내기 뒤에 남는 틈 · 찌그러진 면 · 안쪽 벽 · 작은 구멍을 고쳐서 닫힌 부품으로. Make Quad · Quad Remesh는 이걸 먼저 저절로 함.
- **Remesh 도구 패널**: 맨 위가 새 **Quad Remesh**(권장), 아래가 예전 **Make Quad**(Flow / Patch). 둘 다 면 1개부터. 결과는 와이어프레임으로 보임.
- **Export**: **Quad Mesh**를 켜면 모든 오브젝트가 쿼드로(Quad Size = 전체 크기의 %), **Client Look**을 켜면 각진 엣지의 베벨 + Subdivide까지 구워서. 블렌더 메쉬는 그대로. 오브젝트당 수 초.
- **꺾인 면 자르기**: Base Mesh Alt(Height / Ramp)와 Cut Ramp가 꺾인 표면에서 평평한 면마다 깨끗한 바닥. **Steep Edges**: Even(모든 면 같은 깊이) / Limit(보는 방향으로 같은 깊이, 가파른 옆면은 얕게).
- **Silhouette Move**(새 도구): Path Move인데 항상 부품 전체가 따라옴 — 잡고 끌면 부품이 늘어나고 휘어서 실루엣이 바뀜(예전 Path Move 느낌, Tab 필요 없음).
- **Select**(F / Q / 아래 막대)가 블렌더 Select Box: 클릭 · 박스로 고르고 G / R / S로 이동 · 회전 · 크기.
- **Make Quad → Cut → Re-make Quad**: 컷이 그대로 남음(바뀐 메시는 숨은 `…_Changed`로 보관).
- **팝업 메뉴가 뜻밖에 뜨면**: 화면 아래 상태 줄에 "Mecha Menu (무엇이 열었는지)"가 나옵니다 — 그 글자를 알려 주세요. Emulate 3 Button Mouse가 켜져 있으면 패널에 빨간 경고가 나옵니다(Alt+클릭이 가운데 클릭이 됨).
- **지브러시 화면**: **X** 대칭이 실제로 켜짐 · **Tab** = MECHA LAB ↔ ZBRUSH · **Q** = 선택 모드(기즈모) ↔ 브러시, 선택 모드에서 **G / R / S** = 이동 / 회전 / 크기 · 들어갈 때 셰이딩이 부드럽게 바뀌지 않음 · 조각 중인 SubTool만 밝게(다른 오브젝트는 흐리게) · 펜 옆 버튼 우클릭이 조금 흔들려도 메뉴.

## 0.24.75 Quad Remesh — 컷으로 만든 가벼운 부품
- Base Mesh + Cut으로 만든 부품(또는 데시메이트한 부품)에 **Quad Remesh**를 누르면 자동으로 부품의 엣지를 그대로 따라가는 쿼드가 됩니다(버튼 · 설정은 그대로). 메시지에 "(low-poly part: its own edges kept)".
- 쿼드 한 칸보다 좁은 홈이 있으면 저절로 2배 · 4배 촘촘하게 다시 하고(메시지에 "2x finer"), 그래도 남은 틈은 메웁니다. 열린 판의 원래 경계는 메우지 않습니다.
- 주황 하드 엣지가 중간에 끊기는 곳: 두 엣지가 쿼드 한 칸보다 가까운 좁은 띠 · 여러 엣지가 만나는 모서리 · 얕게(30~40°) 꺾인 엣지 · 아주 짧은 엣지. **Target을 올리면** 좁은 띠가, **Hard Edges 각도를 낮추면** 얕은 엣지가 이어집니다.

## 0.24.74 Edge Mesh — Auto Detail · Match Original
- **Auto**(기본 켜짐) + **Tolerance**(기본 0.006%): Detail을 직접 고르지 않아도 됩니다. 줄인 메쉬가 원본에서 부품 크기의 Tolerance% 넘게 벗어나기 직전까지 줄여서, 단순한 부품은 가볍게, 디테일 많은 부품은 촘촘하게 남깁니다. 찾은 삼각형 수는 **Detail** 칸에 적힙니다(사용자 FBX: 2,098 / 로봇 부품 5개: 588 ~ 5,660).
  - 더 가볍게 / 더 촘촘하게 하려면 Tolerance를 키우거나(가볍게) 줄이세요(촘촘하게). **Half / Double**을 누르면 찾은 수의 절반 / 두 배로 Auto가 꺼진 채 직접 정하게 됩니다.
  - 평면 · 곡면은 Fit to Original이 원본 모양으로 다시 붙이므로 덜 따지고, 각진 엣지 근처를 더 따집니다.
- **Match Original**(기본 켜짐): 원본에서 날카로운 엣지는 Width 그대로 얇게, 원본에서 둥글게 깎인 엣지는 그만큼 넓은 베벨(최대 부품 크기의 5%). Width는 "가장 얇은 베벨"이 됩니다. 끄면 예전처럼 모든 엣지가 Width 하나.
- 데시메이트 엔진: 거의 선처럼 얇은 삼각형(한 줄 위의 세 점 — n각형을 단순 분할한 메쉬에 많음) 옆에서 면이 뒤집혀 접히던 것을 막음.

## 0.24.73 Edge Mesh — 촘촘한 메쉬 → 클라이언트에게 줄 깨끗한 메쉬
1. 지브러시 화면 왼쪽 선반 **Edge Mesh** 상자(또는 사이드바 Mecha Lab 탭 > **Mesh Tools**, 오브젝트 모드에서 선택한 메쉬 전부).
2. **Detail**(기본 2,000 삼각형)을 정하고 **Edge Mesh**: 데시메이트를 여러 번 누르듯 단계적으로 줄여 엣지를 찾고, 평면은 쿼드로 이어 붙인 뒤 라이브 베벨 + Subdivide + Fit to Original이 붙습니다.
3. Hard Edges 상자에서 **Width**(베벨 두께) · **Segments** · **Bevel Style**(Round 둥글게 / Chamfer 평평하게 깎기) · **Subdivide**를 바로 조절합니다. 좁은 곳은 자동으로 얇게 들어갑니다.
4. 마음에 들면 **Apply**: 커스텀 노멀 · 샤프 없는 보통 메쉬(마야 · 맥스 · 지브러시에서 같은 모양). Detail을 바꾸고 싶으면 Apply 전에 Edge Mesh를 다시 누르세요(처음 원본에서 다시 만듭니다).
- 원본 촘촘한 메쉬는 Apply / Clear 전까지 씬 밖에 보관됩니다(화면 · Outliner · FBX에는 나오지 않음).
- Apply 하지 않고 그대로 **File > Export > FBX**(기본 Apply Modifiers 켜짐)로 내보내도 클라이언트 메쉬(베벨 + Subdivide + Fit 적용)로 나갑니다.
- **Adaptive**(둥근 끝 · 모서리 보존) · **Straighten**(엣지 선 펴기) · **Fit to Original**(원본 모양에 다시 맞추기)은 기본으로 켜져 있습니다.

## 0.23.2
- **V** = 도구 파이. 왼쪽 **Mirror** 버튼도 기울이기 제스처(화면 아래 가운데 표시), 결과는 살아 있는 미러.
- Cloth Plate **Gravity**. **Mesh Curve** = 새 커브 도구(점 드래그·주황 굵기 점·아래 버튼 줄, Repeat에 내 오브젝트 링크 + 간격).

## 0.23.0
- 새 **Tube** 도구: 점을 찍으면 바로 솔리드 튜브(굵기·단면·캡·구멍·비틀기), 또는 Repeat(오브젝트/구를 커브 따라 반복). Apply 전까지 살아 있음.

## 0.22.2
- Armor Plate / Cloth Plate에서도 **Surface**: 표면에 점 찍고(화면 돌려도 붙어 있음) Enter = 플레이트. Line을 같이 켜면 표면 따라 띠.

## 0.22.1
- **Q** 한 번 = Select ↔ 마지막 도구, **Shift+Q** = 도구 파이.
- Cut / Split 헤더 **Surface**: 메쉬 표면에 점을 찍고(화면 돌려도 붙어 있음) 부위를 한 바퀴 감은 뒤 Enter = 그 자리에서 분리(Gap).

## 0.22.0
- Robot Base Mesh(인간형): Chest / Pelvis / Head 추가(부위별 슬라이더 8개 + Anatomy Detail), Bulge Shape(원기둥/네모), 위아래 노치, 구멍(관통 가능).
- 헤더 **Line** 버튼: 라쏘로 그은 선을 띠로(폭 = Line Width).
- N 패널 **Detail Stamp**: 내 디테일 메쉬(원점 = 바닥)를 프리셋으로 저장 → Start Stamping, 표면 따라 이동, 클릭 = 배치.

## 0.21.1 인간형 팔다리
- Humanoid로 Upper Arm / Forearm / Thigh / Calf를 추가하면 관절 없는 팔다리 베이스. 선택 후 팝업/N 패널의 Limb Shape 슬라이더(아래 굵기, 가늘어지는 위치, 근육 볼륨·홈·능선, 비틀기, 휘기, V 홈, 끝 단면 기울기)로 형태를 잡습니다.

## 0.21.0 Robot Base Mesh
- N > Mecha Lab > **Robot Base Mesh**: Humanoid / Industrial, Sleek / Rugged 고르고 **Whole Body**(파츠 14개, 각각 별도 오브젝트) 또는 부위 버튼.
- 파츠를 선택하면 옆 팝업과 패널에서 길이·폭·두께·테이퍼·볼륨·둥글기·해상도·베벨(폭/세그먼트/각도)·끝면 모양(원 → 네모/다각형) 실시간 조절, Apply로 일반 메쉬.

기준 소스: ChatGPT v0.9.3 (Claude 0.9.0 + ChatGPT Deform 0.9.1 + Primitive 0.9.2/0.9.3). 변경 내용은 `CHANGELOG.md` 0.10.0.

## 0.13.0 Station Primitive
- Primitive 도구 패널 맨 위 "STATION PRIMITIVE": 프리셋 선택 → 지점 목록에서 지점 고르고 꺾임·폭·두께 조절 → Add Station으로
  이어서 꺾기 → Apply. 반경 0 = 날카로운 접힘, 반경 > 0 = 부드러운 꺾임/감싸기.

## 0.12.0 빠른 안내
- **하단 툴바**(뷰포트 아래 가운데) 또는 **Q 파이**로 도구 선택, **Shift+Q** = Select ↔ 마지막 도구, **F** = Select / Move.
- Cut/Split은 기본이 **자동 대상**: 그린 도형이 덮는 메시를 바로 자름. 선택한 것만 자르려면 헤더 "Selected Only" 또는 **T**.
- V는 비었고, N은 Blender 사이드바입니다.

## 0.11.1 입력 변경
- **Alt+클릭 모드 전환은 삭제됐습니다.** Alt는 v0.9.3처럼 **Cut 반전(안쪽 남기기)** 만 합니다(누르고 시작하거나 그리는 중 눌러도 됨).
- **Ctrl+드래그** = 중심에서 그리기(그대로).
- 선택/이동이 필요하면 **Select / Move**(Mecha Lab 메뉴 맨 위, 기본 단축키 **W**, Preferences에서 변경 가능). Blender 선택 +
  이동 기즈모(다중 선택 가능)로 바뀌고, 진행 중이던 Cut/Split 획은 안전하게 취소됩니다. 다시 Cut/Split을 고르면 새로 시작.
- Live Primitive(MCH_Box 등)를 자르면 먼저 일반 메쉬로 굽힌 뒤 자릅니다("whole object" 오류 수정).

## 0.11.0 Mechanical Toolkit 빠른 안내
작업 흐름: ZBrush 베이스 → Blender → **Face Extract → Armor Sculpt → Edge Molding → Curve Array / Cable → Hollow**.
- **Face Extract**: Tab → 면 선택 → Basic Extract / Armor Sculpt. 파츠마다 설정이 남고 다시 선택하면 그대로 편집.
- **Armor Sculpt**: 방향별(N/E/S/W) 두께·경사·챔퍼·베벨, 중앙 능선 6종(일자·십자·Y·X·S·Z)과 회전·스케일·가지별 길이·폭, 능선 단면 6종.
- **Edge Molding**: 면 외곽 / 엣지 / 파츠 경계 / Armor 중앙선 → 별도 몰딩 오브젝트.
- **Mesh Along Curve**: Curve Deform, Curve Array(Rigid/Deform), 커브 기준선 Free / World X·Y·Z.
- **Cable**: 두 표면 클릭(다른 오브젝트 가능) 또는 Edge to Cable, 두께·단면·처짐·꼬임.
- **Hollow / Shell**: 여러 메쉬 동시, 개구부·Rim, 자기교차 검사.
- Base Mesh: 다른 탭으로 나가면 이번에 만든 도형이 자동 Apply.

## 0.10.0 빠른 안내
- (0.11.1에서 변경) **Alt** = 도구별 보조(Cut: 안쪽 남기기, Base Mesh: 파내기). 모드 전환은 **Select / Move (W)**.
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
2. Get Extensions > ▾ > **Install from Disk…** → `dist/mecha_lab-0.11.0.zip` (압축 풀지 말 것).
3. 설치만으로는 어떤 Workspace도 바뀌지 않습니다.

## 2. MECHA LAB Workspace
N 사이드바 > Mecha Lab > `Open MECHA LAB Workspace` (또는 탭 메뉴 / F3). 현재 탭을 복제해 새 탭을 만들고,
왼쪽 도구 목록 · 뷰포트 왼쪽 위 공통 Shape 팔레트 · 오른쪽 현재 도구 설정 구성을 만듭니다. 다른 탭과 Startup File은
건드리지 않습니다(Startup 저장은 확인 창이 있는 별도 버튼).

도구 목록: **Cut, Split, Base Mesh, SubD Plane, Primitive**, Boolean, Smart Fuse, Mirror, Curve Array, Radial Array, Mesh Curve,
**Deform**, **Face Extract / Armor Sculpt, Edge Molding, Hollow / Shell, Mesh Along Curve, Cable**, **Loft / Surface, ZBrush Bridge**, Surface Conform, Assets, Remesh, Live Result. (Mask는 0.10.0에서 숨김)
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
