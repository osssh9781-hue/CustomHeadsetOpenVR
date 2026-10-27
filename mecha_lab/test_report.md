# Test Report — Mecha Lab 0.24.57

## 0.24.57 결과: 138개 파일 3908/3908 (`tests/test_log_bpy501_v02457.txt`, Blender 5.0.1 bpy). test_v02477(17): HUD 더블클릭 키맵(3D View / Object Mode / 도구 / Screw 순서), 줄·틈·가장자리·제목·바깥 판정, 카드 버튼 옆 클릭·빈 카드, 래디얼 부품 그룹 이동 시 덩어리 유지, 그룹 Mirror X(월드, 메뉴 파랑, 반대편 인스턴스, 끄기), Ungroup 피벗. test_v02478(8): Attach Ends 기본값, path_param / ease, 끝점 표면(z 0.5 / 1.5), As Drawn 고르게, Smooth 라이브 재휨, 다른 슬라이더 뒤에도 유지, 도구 연결, 끝 아래 없으면 평평. test_v02424: 촘촘한 삼각형 메시 Bevel = 깎기 경로·닫힘. test_v0100_regression B10(폭 3.0 = 제한 알림) 그대로. 측정(헤드리스, 참고): 예전 Chamfer / Bevel 2만 면 1.0~1.3초, 4만 삼각형 1.5~2.2초, 폭 0.050 일정(전 0.000 / 0.073 / 0.11, 삼각형은 0.0138로 제한). 5.2.3 bpy에서도 test_v02477 · v02478 통과. 참고: test_v0243이 앞선 전체 실행에서 한 번 Blender 내부 충돌(segfault)로 끝났고, 따로 23번 돌려 1번 재현(나머지 통과) — 이번 변경과 무관한 드문 충돌로 보이며 원인은 못 찾음. 실제 화면은 미검증.

## 0.24.56 결과: 136개 파일 3883/3883 (`tests/test_log_bpy501_v02456.txt`, Blender 5.0.1 bpy). test_v02475(27): 미러 따라가기(같은 평면·중심·bisect·flip, 반대쪽 정점, 이미 있으면 그대로, 멀리 있으면 없음, 로컬 미러 = 원본 부품 기준, 나사 = 부모), 카드 Clip, 미러 평면 사각형·그리기(대역 페인터), 그룹 Grid(5 / 11개, 간격, 인스턴스, 카드 X/Y/Z·Gap, Apply), 그룹 목록(중첩 순서, 고르기 / 들어가기, 대역 레이아웃), 도구 그룹(모든 도구 한 번씩, 제목), Preferences 끔. test_v02476(9): Live Last Cut 조건, 도구 연결, 깊이 0.3 → 0.5 다시 자르기(닫힘), GN Chamfer 켜기, 편집 후 슬라이더 → 편집 유지·라이브 끝·백업 정리, Preferences 끔. 5.2.3 bpy에서도 test_v02475 · v02476 · v02474 통과. 실제 화면은 미검증.

## 0.24.55 결과: 134개 파일 3847/3847 (`tests/test_log_bpy501_v02455.txt`, Blender 5.0.1 bpy). test_v02474(16): + Tab 전환(Brush → Whole → Brush, 미리보기 다시 읽기), 이름 Whole, Quick HUD / 메뉴 설정에 path_area, 키 안내 Tab. 실제 화면은 미검증.

## 0.24.54 결과: 134개 파일 3843/3843 (`tests/test_log_bpy501_v02454.txt`, Blender 5.0.1 bpy). test_v02474(12): Area 기본값, 브러시 평면(8변, 축 정렬), 0 / 12 / 30 분할 판에서 브러시 폭(0.2)만큼만 올라옴·닫힘·바깥 법선·나머지 그대로, 미리보기 analyse가 같은 패치(단면보다 작음), Auto Apply 끔 기록에 반지름, 모달 전달, 휠 클릭 게이트가 NDOF / 트랙패드 / 다른 이벤트를 넘김. 5.2.3 bpy에서도 test_v02474 통과. 실제 3D 마우스와 화면은 미검증.

## 0.24.53 결과: 133개 파일 3831/3831 (`tests/test_log_bpy501_v02453.txt`, Blender 5.0.1 bpy). test_v02473(18): GN 그룹 노드 구성(UNION EXACT + DIFFERENCE MANIFOLD / 예전 EXACT), miter 길이(90° √2, 3배 제한), 닫힌 부품 GN Chamfer = fast 경로·닫힌 결과·모서리 폭, 열린 메시는 fast 안 씀; Path Move Stretch 한 번 계산(점 3배 미만, 닫힘, 기록 하나, 경로 따라감); Ramp 깊은 쪽 두 번 바꿔도 배치 1번, stamp, 편집 후 슬라이더 → 편집 유지·라이브 종료; Quad Bevel(기본 없음, WEIGHT·2단, Outer < All, 결과 전부 사각형, 끄기, Apply). test_v02472(62): 그룹 Repetition 월드 기준·Group·Cursor·핸들 이동, 카드 Centre, 카드 오른쪽 고정, Base Mesh 메뉴 Lasso. 측정(헤드리스, 참고): 2만 면 GN 컷 0.8~2.1초(전 8~13초), 1.6만 점 판 Stretch 0.96초(전 59초). 5.2.3 bpy에서도 test_v02473 · v02472 · v02470 · v02438 · v02461 · v02466 통과. 실제 화면은 미검증.

## 0.24.52 결과: 132개 파일 3805/3805 (`tests/test_log_bpy501_v02452.txt`, Blender 5.0.1 bpy). test_v02472: 메뉴 Shading 3개가 실제로 셰이딩을 바꿈, 클릭으로 안 닫힘 / 벗어나면 닫힘(`near` 판정), 휠 클릭 중복 방지; 메뉴 Mirror X = Alt+X와 같은 `MCH_Mirror`, Kaleido(미러가 배열 앞, 정점 수), Count, Radial만 / Mirror만 전환, 평면 X+Z, Bisect / Flip 토글, 마지막 평면 끄면 끝, 0.24.49 미러 넘겨받기, Apply; 카드(열기, 4모드, Kaleido 시작 평면, 미러 오브젝트 = 래디얼 중심, + Count, Remove 후 중심 정리), 실제 만화경 대칭(X 평면 거울·90° 회전 모두 정점 일치), 중심 이동, Mirror로 돌아가면 미러 중심 복귀; 그룹(생성·핸들 따라감·Repetition Mirror 2 / Radial 6 / Kaleido 10 인스턴스, 링크, 카드에서 Radial·+, Apply 6개 실제화, Enter / Exit, Merge, Ungroup 원래 컬렉션, 그룹 안 그룹, 그룹 안 파트로 새 그룹 → 그 안에 중첩, Ungroup하면 바깥 그룹으로). 5.2.3 bpy에서도 test_v02472 · v02470 · v02471 · ui_draw · zip_install 통과. 실제 화면(카드 위치·클릭, 메뉴 닫힘 느낌, 만화경 모양)은 미검증.

## 0.24.51 결과: 131개 파일 3751/3751 (`tests/test_log_bpy501_v02451.txt`, Blender 5.0.1 bpy). test_v02471(19): HUD 클릭 항목이 모든 도구 키맵 앞쪽(D+드래그 다음, 도구 클릭 전)·3D View에 1개, 기즈모 없음, HUD 밖 PASS_THROUGH, 가짜 영역에서 행/제목 줄/빈 곳 판정·이동 후에도 맞음, 모달 동작(드래그/Shift/Esc/선택형/기본값/undo/입력), 휠 클릭 키맵(수정키 없음)·회전 넘김·MECHA LAB 한정·끄기, − / + 크기(0.1, 0.5~3 제한), Ctrl+휠, 사이드바·프리셋·저장, 크기 계수 공유. 5.2.3 bpy에서도 test_v02471 · v02470 · v02469 · v02437 · ui_draw · zip_install 통과. 실제 화면(HUD 드래그, 휠 클릭과 회전 느낌)은 미검증.

## 0.24.50 결과: 130개 파일 3732/3732 (`tests/test_log_bpy501_v02450.txt`, Blender 5.0.1 bpy). test_v02470(33): 카드 3장 배치·화면 안(모서리에서 열어도), 도구 줄 순서/활성, 카드 제목·탭·4열 그리드, Settings 종류, Actions 섹션, 모든 버튼 = 실제 연산자, 큰 화면 확대(2배)·계수, 클릭(모양, 탭, Mirror X → 다음에 파란색, 선택 버튼, Ctrl+클릭 기본값, 클릭 = 입력, 별, 세트), 홀드 모드(도구 제자리 전환·메뉴 유지, Duplicate 제자리), Base Mesh 프로필 카드, RMB 연결, Ctrl+Alt 키맵 4개·지연·MECHA LAB 한정, HUD 위치·2배, 대역 그리기 함수로 그리기 코드 실행(모든 hover), 키 안내 카드, 이미지가 파일에 남지 않음. 5.2.3 bpy에서도 test_v02470 · v02469 · ui_draw · zip_install 통과. GPU 실제 그리기(이 환경은 GPU 없음)와 화면 모양은 미검증 — 같은 배치 데이터로 PIL 미리보기만 확인.

## 0.24.49 결과: 129개 파일 3699/3699 (`tests/test_log_bpy501_v02449.txt`, Blender 5.0.1 bpy). test_v02469(45): 최근(순서·중복·숨김 도구 제외·최대 5·재시작 후 유지, 사용자 설정 파일은 임시 경로), 즐겨찾기(기본 세트, 고정/해제, 8개 한도, 세트 전환, 연산자), 팝업(가짜 레이아웃으로 연산자 id·속성·아이콘 검증, Actions 아이콘만·섹션 제목, 카드 탭/설정, Base 카드, 툴팁 이름), Symmetry X/Z → mirror_reflections 1/3개, 모두 끄면 삭제, Apply Modifiers, RMB 키맵 1개·MECHA LAB 밖 비활성, Quick HUD(도구별 항목, 드래그 비율·Shift·정수·범위, 선택형 다음 값, 기본값, 위치·이동·화면 안), 툴바(1600/700/420px: 한 줄 그대로 / 축소 / 두 줄, 모두 화면 안), 키 안내. 5.2.3 bpy에서도 test_v02469 45/45, test_ui_draw 388/388, test_zip_install 19/19. 실제 화면(팝업 모양·HUD 조작·클릭)은 미검증.

## 0.24.48 결과: 128개 파일 3654/3654 (`tests/test_log_bpy501_v02448.txt`, Blender 5.0.1 bpy). test_v02468(25): 컷 + 불린 부품 Flow 3000면 → 전부 사각형 2919, 닫힘, 원본 숨김·그대로, 모서리 거리 중간 0.0009 / 95% 0.0033, 표면에서 최대 0.007; Re-make / Show Original / Apply; Edge Angle 10°이 20° 접힘을 살림, Sharp 표시 모서리 유지; 열린 메쉬 거부. 모서리를 뚫은 마름모 컷: Flow 놓친 길이 1.7칸 → 경고, Patch 3350 사각형, 놓친 길이 0, 원래 모서리에서 3e-8, 표면에서 0.0004, 윗면 대부분 정렬된 격자; 곡면(구) Patch도 전부 사각형·닫힘. 5.2.3 bpy에서도 test_v02468 25/25. 실제 화면은 미검증. (0.24.47 보고의 3655개는 집계 실수 — 같은 방식(줄 맨 앞 "N/N passed" 합)으로 다시 세면 0.24.47 = 3629개.)

## 0.24.47 결과: 127개 파일 3655/3655 (`tests/test_log_bpy501_v02447.txt`, Blender 5.0.1 bpy). test_v02467(10): + 길쭉한 기울어진 Cut Ramp(Soft 0.5) 옆면 띠(외곽에서 약 0.03 안)를 따라 60곳 깊이의 2차 변화 최대 0.001(수정 전 코드 0.007 → 실패 확인), 닫힘, UI 슬라이더. 시간(그 모양): Res 15 = 1.2초 · 1.3만 면, 20 = 2.3초 · 2만, 28+ = 4.4초 · 3.4만(상한). 5.2.3 bpy에서도 test_v02467 · v02465 · v02466 · v02454 · v02457 · v0245 · test_base_mesh · test_ui_draw 통과. 실제 화면은 미검증.

## 0.24.46 결과: 127개 파일 3654/3654 (`tests/test_log_bpy501_v02446.txt`, Blender 5.0.1 bpy). test_v02467(9): 메뉴 · 기본 꺼짐, 큐브 Cut Ramp(왼쪽 깊음 · 가운데 0.1 · 끝 0.03 미만 · 닫힘), live 'cut', ▶▶ = 오른쪽, Cut Depth 0.1 → 0.095, Remove, Chamfer 깊은 벽, Apply, 꺼짐 = 평평한 홈 0.2. test_v02465(12): + 베벨 막대 끝에 걸친 Ramp — 모서리 안쪽 6곳 모두 0.15~0.17 파임(수정 전 코드 0.03만 → 실패 확인). 개발 중 회귀 테스트가 잡은 실수: cut_ramp를 끼워 넣다 perform_closed의 @_with_finish_notes가 빠짐 → 복구(B10 통과). 5.2.3 bpy에서도 test_v02467 · test_v02465 · test_v02466 · test_v02454 · test_v02457 · test_v0245 · test_base_mesh 통과. 실제 화면 입력은 미검증.

## 0.24.45 결과: 126개 파일 3644/3644 (`tests/test_log_bpy501_v02445.txt`, Blender 5.0.1 bpy). test_v02466(12): corners(클릭 다각형 그대로, 촘촘한 사각형 → 4변), nearest_side, 큐브 Ramp 뒤 live 기록 · 보관 메쉬 · 모서리 4개, 처음 = 왼쪽 깊음(0.191 / 0.009), ▶ = 위쪽 깊음 · 왼쪽 0.096 · 닫힘, ◀◀ = 아래쪽, Carve Depth 0.1 → 바로 0.095, 패널, Remove = 꼭짓점 8개로 · 기록 / 보관본 없음, ▶▶ + Apply = 오른쪽 깊음 · 정리됨, 다른 큐브에 새 Ramp = 이전 확정 · 보관본 1개. 5.2.3 bpy에서도 test_v02466 통과. Pick Edge 뷰포트 클릭과 선 그리기는 화면이 필요해 미검증.

## 0.24.44 결과: 125개 파일 3632/3632 (`tests/test_log_bpy501_v02444.txt`, Blender 5.0.1 bpy). test_v02465(11): ramp_scale(1 / 0.5 / 0, 변 방향 무관, Length 0.5), first_edge, 큐브에 사각형 Ramp(Flat, 0.2, Soft 0) — 닫힘, 깊이 0.19 / 0.10 / 0.03 미만, 바깥 그대로; Length 0.5 → 절반 너머 0; soften_ramp(깊은 끝 그대로, 표면 근처 완만, 외곽 근처 감소, Soft 0 = 그대로); Soft 1 큐브 — 깊이 0.191 / 0.096 / 0.012 / 0 · 닫힘. test_v02463(5): 작은 브러시도 Extend 유지. 5.2.3 bpy에서도 test_v02465 · test_v02463 · test_v02439 · test_v02458 통과. 렌더로 Soft 0 / 0.8 비교 확인. 실제 화면 입력은 미검증.

## 0.24.43 결과: 124개 파일 3621/3621 (`tests/test_log_bpy501_v02443.txt`, Blender 5.0.1 bpy). test_v02464(12): 바깥 베벨 판에 가장자리를 넘는 홈 — Edge Finish Bevel / Chamfer × From Surface / Through 모두 판 밖 점 0 · 닫힘(수정 전 3~6개 튀어나옴), GN Edge도 같음; GN Bevel / Chamfer 컷 뒤 컷 표시 속성 없음 · UVMap은 CORNER 하나, 두 번째 컷 뒤 첫 홈의 모든 점이 원래 표면 위(1e-5 이내; 수정 전 코드에서는 0.0017~0.0024 변형되어 실패 확인). test_v02462(8): + Alt Carve Depth 0.02 = 깊이 0.02 · 닫힘, scale 0.5 대칭, 패널. 5.2.3 bpy에서도 test_v02464 · test_v02462 · test_v02461 통과. 실제 화면 입력은 미검증.

## 0.24.42 결과: 123개 파일 3606/3606 (`tests/test_log_bpy501_v02442.txt`, Blender 5.0.1 bpy). test_v02462(5): `mirrored_into`(0.3 위 → 0.3 아래, 표면 / 살짝 아래 → lift 위), 큐브에 타원 플레이트 Alt — 닫힘 · 플레이트 오브젝트 없음, 홈 깊이 = 플레이트 높이(±20 %), 바깥 윗면 그대로, cut_engine 분기. test_v02463(5): 90° 꺾인 경로 → 최소 회전 반지름 ≥ 0.4 · 끝점 · 점 수 그대로, 직선은 그대로, section_radius, 3 × 1 × 0.1 판 끝을 잡은 드래그 판단(브러시 0.1 = Stretch, 0.4 = Extend). 5.2.3 bpy에서도 test_v02462 · test_v02463 통과, 기존 플레이트 테스트(test_v0160 · v0190 · v0192 · v0193 · v0194 · v0200 · v0220 · v0223) 5.0 통과. 실제 화면 입력은 미검증.

## 0.24.41 결과: 121개 파일 3596/3596 (`tests/test_log_bpy501_v02441.txt`, Blender 5.0.1 bpy). test_v02461(12): 기본 Off, 촘촘한(10등분) 큐브에 타원 포켓 — Chamfer: 테두리 밖 w/2 지점 12곳 높이 = 1 − w/2(±0.012), w 2배 밖은 그대로, 닫힘, 보조 속성 없음; Bevel: 그 지점이 챔퍼선과 윗면 사이(둥금); Split Both = 양쪽 조각 모두 챔퍼 · 닫힘, Side B = 조각만; 패널 함수. 개발 중 잡은 버그: 표면 방향 판정(큰 면 중심 → 루프 왼쪽), 곡선 방향이 제각각이라 촘촘한 메쉬에서 스윕이 뒤집혀(부피 음수) 안 깎이던 것 → 점별 내적 캡처 후 Reverse Curve. 렌더 비교(삼각형화된 10등분 큐브): 기존 Edge Finish는 너비 제한 경고 + 거의 안 보임, GN Edge는 고름. test_v02460(5): 45° 기운 가는 삼각형 클릭 → 둘레 평면 2° 이내, 나사 축 5° 이내, 구 위 3° 이내, 가장자리 = 원래 노멀. test_v02459(20): + nearest_surface(가까운 메쉬 · 범위 밖 없음 · Selected Only에서 제외). 5.2.3 bpy에서도 test_v02461 · test_v02460 · test_v02459 · test_v0240b · test_v02423 · test_v0140 · test_v0143 · test_v0150 통과. 실제 화면 입력은 미검증.

## 0.24.40 결과: 119개 파일 3576/3576 (`tests/test_log_bpy501_v02440.txt`, Blender 5.0.1 bpy). test_v02458(8): 전용 Hardness(기본 1, Move 0.5 그대로), 패널에 표시, `soften_path` = 시작이 잡은 방향(x 성분 > 0.9), 점 개수 같음, 뒤쪽 경로 그대로, Hardness 1 = 부드러운 구간 없음; 막대(3 × 0.5 × 0.5)에 45° 경로 Extend — Hardness 1 / 0.3 둘 다 닫힌 메쉬 · 컷 뒤 메쉬 그대로, 0.3은 컷 바로 뒤 튜브 평균 높이 0.33 → 0.27(완만), 끝 위치 같음. test_v02459(17): `stamp_transform`(+X 면이 아래로 · hit 위, depth, Align 끔 = 이동만), 고스트 레이 픽(−Y 면 · 빗나가면 없음), behind_extent, Size 비율 유지, 큐브 위 0.4 × 0.4 × 1.2 상자 +X 면 스탬프 → Subtract 0.1 깊이 1.2 × 0.4 홈 · 닫힌 메쉬, 옆면 Add = 합쳐짐 · 닫힘, Remember Turn(같은 방향 표면 = 같은 회전, +X 면 = 같은 30° 기울기, 끄면 리셋, Reset 후 리셋), 버튼 · Alt+클릭 키. 5.2.3 bpy에서도 test_v02458 · test_v02459 · test_v02439 · test_v02437 · test_v02438 · test_v02447 · test_v0140 · test_v0143 · test_v0150 · test_v02324 통과. 실제 화면 클릭 · 드래그는 미검증.

## 0.24.39 결과: 117개 파일 3551/3551 (`tests/test_log_bpy501_v02439.txt`, Blender 5.0.1 bpy). test_v02457(9): 굽은 저폴리 판(두께 0.08)에 Line(폭 0.08)으로 Chamfer / Bevel / Flat Alt 파기 — 비매니폴드 0, 보이는 크기의 찌그러진 면(3° 미만) 0, 띠 가운데 깊이 0.035 ± 0.006(세 곳), Bevel Segments 2 → 8 = 면 증가 · 깨끗, Resolution 28 → 70 = 면 증가 · 깨끗(라인 끝 둥근 마개에 면적 1e-6 미만 미세 삼각형 몇 개는 제외), `smooth_normals` 단위 길이. 사용자 FBX(MCH_Base.032, Chamfer, Carve Depth 0.072, Border 0.049): 찌그러진 면 19 → 0, 면 1984 → 983. 5.2.3 bpy에서도 test_v02457 · test_v02454 · test_v0245 통과. 실제 화면 입력은 미검증.

## 0.24.38 결과: 116개 파일 3542/3542 (`tests/test_log_bpy501_v02438.txt`, Blender 5.0.1 bpy). test_v02454(13): + 공 위 Alt 파기 — 바닥이 중심에서 0.898~0.900(표면에서 Height 0.1 고르게), Carve Depth 0.2. test_v02454(17): + Through(0.15 판에 0.6 × 0.6 창문, 뚫림), Inside(앞면 유지, 1 × 0.1 × 0.1 채널, 옆으로 관통 · 위 벽 유지) — Inside 테스트가 이름 같은 이전 큐브의 BVH 캐시 버그를 잡음. test_v0230(48): 주황 점 = 화면 26px, 두 배 거리로 끌면 반지름 두 배, 놓으면 다시 옆(기즈모 쪽은 화면 없이 테스트 불가 = 미검증). test_v02456(9: 핸들러 등록, 돌리고 옮겨도 복사본 = 같은 pivot · Z로 1/4 회전(점마다), pivot 그대로, 복사 0 = 메쉬, pivot 옮기면 따라감, Distance +0.5 / −0.3 · 높이 유지, Apply 후 정리). test_v02455(11): + Selected = 선택만, Visible = 보이는 것(숨긴 것 제외), 선택 유지. 사용자 FBX(얇은 판 MCH_Base.032)로 확인: 앞면이 파이고, Height 0.144 ≥ 두께 ≈ 0.1이면 뚫림(Carve Depth로 해결). 5.2.3 bpy에서도 test_v02454 · test_v02455 · test_v02456 · test_v02443 · test_v0230 · test_v0245 · test_v0100_regression 통과. 실제 화면 입력은 미검증.

## 0.24.37 결과: 115개 파일 3523/3523 (`tests/test_log_bpy501_v02437.txt`, Blender 5.0.1 bpy). 새 test_v02453(7: Invert 옵션, 표면 위 앞 / 뒤, 허공 앞 / 뒤, 외곽선 위치 유지, 닫힘), test_v02454(11: 기본 Carve Height, 0.6 × 0.6 × 0.5 포켓 부피 · 바닥 위치, Invert 켜도 안으로, Like Cut = 관통, 메쉬 밖까지 선, Surface Draw 홈 부피 · 바닥, Fill Area 포켓, 메쉬 없으면 안내, 엔진 연결), test_v02455(8: 버튼, L자 블록 n-gon 2개, OBJ에 4각 초과 없음 · 옆 사각형 6개 유지, 이름 그대로, 원본 그대로 · 남는 오브젝트 없음, 끄면 n-gon 그대로, FBX, 브리지 복사본도 깨끗). test_v0100_regression · test_v0245 Alt 검사 = Like Cut. 5.2.3 bpy에서도 test_v02453 · test_v02454 · test_v02455 · test_v0100_regression · test_v0245 · test_v02441 · test_v02452 통과. 실제 화면 입력은 미검증.

## 0.24.36 결과: 112개 파일 3497/3497 (`tests/test_log_bpy501_v02436.txt`, Blender 5.0.1 bpy). 새 test_v02448(3: Through All 2점 = 평면 컷 끝까지, From Surface 2점 = 깊이까지 계단 · 닫힘, 꺾인 선 깊이), test_v02449(6: 이름, 패널 · Path Move에 있음, 켜면 슬라이더 · Lasso 안내, 모든 그리기 모드에서 스태빌라이저 시작, 천천히 따라옴, 끄면 비활성), test_v02450(10: Shift 45° 직선 · 앞부분 유지 · 0° 스냅 · 떼면 이어짐 · 놓으면 90° 끝, Slow Line 켜고 끄고 각각), test_v02451(2: HIDE가 Line 툴, 2점 선 = Line Width 0.5 × 4 × 4 = 8 숨김), test_v02452(5: 가운데 빗나감 → 앞면, plane_frame · surface_frame 앞면, 메쉬 위 외곽선 = 가운데, 아무것도 없으면 커서 깊이). 5.2.3 bpy에서도 test_v02448 · test_v02449 · test_v02450 · test_v02451 · test_v02452 · test_v02316 · test_v02317 · test_v0241 · test_cut_geometry · test_v090_features · test_v0100_regression · test_ui_draw · test_v02437 · test_v02439 통과. 실제 화면 입력은 미검증.

## 0.24.35 결과: 107개 파일 3471/3471 (`tests/test_log_bpy501_v02435.txt`, Blender 5.0.1 bpy). 새 test_v02447(7: UNDO_KEEP에 크기들, 스냅샷 → 복원으로 크기 유지, 큐브 4 cuts = 9 슬라이스, 간격 이하 엣지, 모양 · 닫힘 유지, 버튼 = 패널 Cuts 값 · 변마다 고른 간격, 패널에 있음). 5.2.3 bpy에서도 test_v02447 · test_v02437 · test_v02438 · test_v02439 · test_ui_draw · test_v0113 통과. 실제 화면 입력은 미검증.

## 0.24.34 결과: 106개 파일 3464/3464 (`tests/test_log_bpy501_v02434.txt`, Blender 5.0.1 bpy). 새 test_v02444(15: 기본 Auto, Selected Only / Active 레이가 앞 메쉬를 뚫음, pick_surface · pick_body · belt pick · cut pick, Surface Draw가 선택 메쉬에, 다음 획도 같은 메쉬, 선택 없음 = 안내), test_v02445(17: Scarf Cape 툴 등록, 가로 / 세로 주름 방향, Gravity 처짐 · 양 끝 고정, 끝 페이드, 선 → 외곽선, 몸 위 생성 · 폭 = 선 길이, 라이브 Gravity, 설정 분리, Apply), test_v02446(12: 모든 그리기 툴 키맵에 F, 툴 밖 F = Select / Move, 툴별 크기 대상, 2배 · 한계, Surface Draw width / height 같이). 5.2.3 bpy에서도 test_v02444 · test_v02445 · test_v02446 · test_v02428 · test_v02437 · test_ui_draw · test_v0120 · test_v0113 · test_v0100_regression 통과. 실제 화면 입력은 미검증.

## 0.24.33 결과: 103개 파일 3407/3407 (`tests/test_log_bpy501_v02433.txt`, Blender 5.0.1 bpy). 새 test_v02439(21: Path Move Extend / Separate Tube / Merge), test_v02440(24: Perforate 4패턴 · 여백 · Mirror 앞 · Apply / Remove), test_v02441(31: Surface Draw 가장자리 · 같은 크기 · 안 쌓임 · Fill Area · Alt 컷 7개 · Cloth 툴 없음), test_v02443(11: Radial Symmetry). 5.2.3 bpy에서도 test_v02441 · test_v02443 · test_ui_draw · test_v0120 · test_cut_geometry 통과. 실제 화면 입력은 미검증.

## 0.24.32 결과: 99개 파일 3297/3297 (`tests/test_log_bpy501_v02432.txt`, Blender 5.0.1 bpy). test_v02437(43): + 화면 기준 Ctrl 회전(좌우 = 화면 세로축, 위아래 = 가로축, 시점 따라감), + Path Move(스텝 수 · 꺾임 합 90° · 박스 축 회전 · Taper 0 · Follow Turns 끔 · 떨림 정리 · 박스 / 구 끝까지 폭 유지 · 몸통 · 꺾인 길에서 위로 · 끝 단면이 돎). test_v02436(Jungle Gym) 삭제. 새 test_v02438(17: Auto / Selected / Active 잡기, From Surface / Through All 대상, 두 오브젝트 동시 무브, 회전 · 크기 오브젝트 장면 기준 무브, Auto Apply 끔 → Undo Last · Clear · Apply, Path Move Through All · 편집 가능). 5.2.3 bpy에서도 test_v02437 · test_v02438 통과. 실제 화면 입력은 미검증.

## 0.24.31 결과: 99개 파일 3301/3302 (속도 검사 1개가 이 기기에서 0.547초 > 0.5초로 실패, 단독 재실행 통과, 0.24.30 코드도 여기서 0.55초) (`tests/test_log_bpy501_v02431.txt`, Blender 5.0.1 bpy). 새 파일: test_v02432(후드 · 스카프 코드 36), test_v02433(Quad Cloth 코드), test_v02434(Concept Move 20), test_v02435(천 툴 숨김 9), test_v02436(Jungle Gym 36: 기어가기 · 45° · 지우기 · 휠 깊이 · Magnet / Corner · 튜브 / 베이스 메쉬 · Follow Body · 주황 X·Y·Z), test_v02437(메뉴 연결 · D 홀드 · Ctrl 돌리기 · 브러시 크기 · 미러 통일 · 가벼운 미리보기 · Even Out). 새 파일들은 Blender 5.2.3 bpy에서도 통과. 실제 화면 입력 · 3D 마우스 · 오버레이 표시는 미검증.

## 0.24.30 결과: 92개 파일 3099/3099 (`tests/test_log_bpy501_v02430.txt`). test_v02428(26): + Straight 1 = 밑단 폭이 Straight 0보다 좁음(옆선 수직), 닫힌 메쉬. 실제 화면 입력은 미검증.

## 0.24.29 결과: 92개 파일 3098/3098 (`tests/test_log_bpy501_v02429.txt`). test_v02429(20): 뿌리 개수 · 영역 안 · 시드, 튜브 반지름(테이퍼 / 로프), 가닥이 올라갔다가 중력으로 내려감, 마네킹 머리에 Dreads / Tentacles / Quills / Strands = 라이브 + 닫힌 튜브, Dreads가 머리 아래로, Quills는 서 있음, 링 = 슬롯 2 + 기본 머티리얼, 몸 안으로 안 들어감, Count / Rings 라이브, Straight 1 = 어깨 아래 퍼짐이 0보다 좁음, rope · wave 닫힘, Apply, 머리 밖 = 안내, 툴 목록 / 아이콘 / Enter / 디스패치. 실제 화면 입력은 미검증.

## 0.24.28 결과: 91개 파일 3064/3064 (`tests/test_log_bpy501_v02428.txt`). test_v02428(25): hem / tatter / columns, 마네킹에 Capelet / Cloak / Poncho / Ragged = 라이브 + 닫힌 메쉬 + 등 뒤, Capelet 짧고 Cloak 다리까지, Poncho가 더 넓음, Cloak이 몸 안으로 안 들어감, Length / Wrap 라이브, 주름 0 / 찢김 닫힘, Outline = 밑단이 그린 아랫변, 이전 망토 통과, Apply, 몸 밖 = 안내, 툴 목록 / 아이콘 / Enter / 디스패치. 실제 화면 입력은 미검증.

## 0.24.27 결과: 90개 파일 3026/3026 (`tests/test_log_bpy501_v02427.txt`). test_v0248: S + 선택 = 통과(Scale), D / Shift+S + 선택 = Split. 실제 키 입력(Blender 화면)은 미검증.

## 0.24.26 결과: 90개 파일 3024/3024 (`tests/test_log_bpy501_v02426.txt`). test_v02424(70): 24각형 꼭짓점 유지 / 프리드로우 직선화, 5 · 6 · 8 · 12 · 20 · 24각형 + 12 · 16점 별 × 6 패턴(챔퍼) 닫힘 + 모든 변 + 3초 이내, 5 · 6 · 8각형 Hip 면 수, Plate Detail 1 / 2 / 3 Alt 일반 메쉬 = 파임(새 오브젝트 없음, 얕음, 닫힘), 살아있는 디테일 Alt = 잘린 벽 flat + sharp 경계. 별도 스트레스(테스트 파일 밖): 3–24각형 · 불규칙 · 별 192 케이스 × Sharp / Chamfer / Bevel 전부 닫힘. 실제 화면 입력은 미검증.

## 0.24.25 결과: 90개 파일 2996/2996 (`tests/test_log_bpy501_v02425.txt`). test_v02424(42): Gable(긴 쪽) 2면 + 능선 양 끝까지, 마스크, Turn = 가로 방향, Shed 1면 + 닫힘 + Turn으로 다음 변, Half Hip 3면, Corner 2면 + 닫힘, Every Other 2면, 엣지 버튼 → Custom '0111' 3면, 마지막 경사 변 유지, 육각형 Every Other(Turn 1) = {1, 3, 5}. 실제 패널 버튼 클릭은 미검증.

## 0.24.24 결과: 90개 파일 2986/2986 (`tests/test_log_bpy501_v02424.txt`). test_v02424: ccw / Straighten / 쐐기 평면, 박스 = 정확히 4면 + 각 면 기울기 = Slope, 능선 높이 = 벽 + 반폭·tan, Sink, Max Height = 평평한 윗면(라이브), Gable = 경사 2면 + 능선이 양 끝까지 + 닫힌 메쉬, Swap Axis, end_edges, Ridge Chamfer / Bevel(둥근 면 smooth, 주름만 sharp), Outer Edge Chamfer, 다음 플레이트 설정 유지, Apply, L자(오목) 외곽 구 위 닫힌 메쉬 + 표면 위, 다른 프로파일은 기존 Armor Plate; Cut Crisp Shading(경계 sharp, 띠 / 벽 flat, 몸통 smooth, 닫힌 메쉬), 커스텀 노멀 제거 / 끄면 유지, 촘촘한 삼각형 메쉬 정리 후 테두리 점이 잘린 벽 위(1e-4 이내). 실제 화면 표시 · 마우스 입력은 미검증.

## 0.24.23 결과: 89개 파일 2954/2954 (`tests/test_log_bpy501_v02423.txt`). test_v02422(8): Array → Bevel → Subsurf 순서 적용 = 스택이 보여준 메쉬와 같은 정점 / 면 수, 꺼 둔 Wireframe은 남음, 닫힌 메쉬, Bevel → 겹치는 Array 순서 유지, 모디파이어 없음 = 오류 없음, 클릭 없이 실행 = 선택한 메쉬. test_v02423(19): 크리쳐 플레이트 Alt = 파냄(새 오브젝트 없음, 가운데가 낮아짐, 관통 안 함, 바깥 그대로, 닫힌 메쉬, Height로 깊이), 살아있는 플레이트 위 = 플레이트 구멍, 스케치 Alt+Enter = 파냄 / Enter = 플레이트, 크리쳐 베이스 Alt 그리기 / 스케치 Alt+Enter = 파냄. test_v02421 스케치 + 프리드로우 = 스케치에 바로 추가로 수정, test_v02420 Puff 거절 → Dome 거절, [ / ] Object Mode 키 + poll(Mecha 툴만), Sculpt G 키 + poll, 삼각분할 icosphere(5) Cut Bevel / Chamfer, Split Bevel = 폭 제한 없음 + 닫힌 메쉬(수정 전 0.0015로 제한되는 것 확인). 실제 키 입력 우선순위, 클릭 / 버튼 표시는 미검증.

## 0.24.22 결과: 91개 파일 2968/2968 (`tests/test_log_bpy501_v02422.txt`). test_v02421 추가분: Taper 버튼 끔 = 같은 폭 / 켬 = 면적 < 80 %, Pressure 기본 꺼짐, Creature Plate Alt 빼기 = 가운데 레이가 몸체에 닿음(구멍), 가장자리 = 홈, 높이 슬라이더 후 구멍 유지, 플레이트 없는 곳 = 안내, Apply 후 기록 삭제 / 구멍 유지, Plate Detail 3 Alt 빼기. 실제 Alt 입력은 미검증.

## 0.24.21 결과: 91개 파일 2958/2958 (`tests/test_log_bpy501_v02421.txt`). test_v02421: Resolution 15(Creature Base / Plate, Base Mesh 28 유지, 한 번만), Sketch + Free Draw 놓으면 POINTS(6–60점), 점 끌기, Enter = 스케치 추가, Sketch 끄면 바로 적용, 스컬프트 브러시 6개가 Blender 라이브러리에 있음 / 아이콘 / 대상 메쉬 / Sculpt Mode 전환, Taper(끝 폭 < 절반, 가운데 같음), 필압(약하게 = 가늘게), [ / ] 키맵과 그리는 중 변경, 안쪽 벽이 있는 합친 메쉬 감지 + 안내 문구. test_v0100_regression F08(Base Mesh)은 Sketch 끈 상태로. test_v02420_bridge: 맞닿은 덩어리 Fill Crease 0 = 숨음, 0.5 = 골짜기 위로 보임, 위쪽은 메쉬, 닫힌 메쉬. 실제 마우스 입력 · 브러시 활성화(배경 모드) · 패널은 미검증.

## 0.24.20 결과: 90개 파일 2923/2923 (`tests/test_log_bpy501_v02420.txt`). 새 test_v02420(크리쳐 베이스 메쉬 Puff / Height), test_v02420_bend(Band / Angle, 마이터 연속, Outer / Inner Round, 닫힌 메쉬, Bend Position), test_v02420_bridge(soft_fill 하모닉 / 바이하모닉, bump, spread, Trim to Gap 덮기 / Round / Fill, 전체 라쏘 곡선 연결 · 대칭 Fill · 오류), test_v02420_cushion(두께 = Height, 대칭, 솔기, Edge Round), test_v02420_keys(Remesh 실행 키 미지정 등록, 새 아이콘 파일, Plate Detail Line), test_v0220(라인 모드 누르고-끌고-떼기, Plate Detail 1 / 2 / 3 라인), test_v0113(내장 모양 13개). 실제 마우스 입력 · 패널 · 아이콘 표시는 미검증.

## 0.24.19 결과: 82개 파일 2668/2668 (`tests/test_log_bpy501_v02419.txt`) (`tests/test_log_bpy501_v02419.txt`). test_v02419(21): 위 뷰 좌클릭 = +X로 복사(x -0.2..0.2) + BAKE → 적용 후 모디파이어 없음, 우클릭 = -X로(x -0.8..0.8) + 적용, 뒤 뷰 좌클릭 = -X, 앞 뷰 좌클릭 = X축(Z 아님), Shift+좌클릭 축 추가 유지 / 잠긴 Y + 좌클릭 = X+Y, Esc 취소, 다른 오브젝트 가리킨 채 우클릭 = 그 건너편, modal BAKE는 keep_live여도 적용 / APPLY+keep_live = live, 인스턴스 좌 / 우클릭 = BAKE + 살아있는 쌍둥이 1개, 상태줄 문구. 실제 마우스 입력은 미검증.

## 0.24.18 결과: 81개 파일 2647/2647 (`tests/test_log_bpy501_v02418.txt`) (`tests/test_log_bpy501_v02418.txt`). test_v02418(16): Cap / Open 둘 다 Split Off → 별도 메쉬, 원본 모디파이어 없음, 둘 다 닫힘, 부피 합 = 원래(2 + 6 = 8), 새 조각 선택, 볼륨 안 남음, 숨긴 게 없으면 아무것도 안 함, L 메뉴 커스텀 칸 기본 접힘 / 펼치면 그려짐. test_v0245 +4: Box Hide 툴에서 선택 없이 Enter → 적용(면 늘어남, 모디파이어 없음), 다른 툴에서는 대상 없음. test_stroke_events(68): 라쏘 누른 채 39번 움직여도 점 1개, 클릭하면 2개(예전 "드래그 = 연속 점" 검사를 바꿈), Free Draw 연속 경로는 그대로. 실제 마우스 입력은 미검증.

## 0.24.17 결과: 80개 파일 2572/2572 (`tests/test_log_bpy501_v02417.txt`; 전체 실행에서 test_registration_recovery의 '키맵 중복' 검사 4개가 키가 비어 있는 툴 키 항목들을 같은 항목으로 봐서 실패 - 항목의 동작(action / tool)까지 비교하도록 고쳐 그 파일만 다시 실행 38/38) (`tests/test_log_bpy501_v02417.txt`). test_v02417(18): L = SHAPES, 왼쪽 메뉴 툴마다 키 항목(기본 비어 있음, C / S / Alt+A 유지), 편집 상자에 툴 전부 + Save / Default, Ctrl+K = Base Mesh / J = Cut 저장 → 키맵 다시 만들어도 유지, 다른 키 그대로, 툴 키 → 그 툴 / L → 모양 팝업, Default Keys → 파일 삭제 + 기본값; Line Curve: 점 반지름 1 / 3 / 0.3 + 시작 / 끝 0.5 / 2에도 굵기 0.1 일정(점 아님), Thickness 0.25 → 전체 0.25, Line Curve 툴 소유, 주황 손잡이 / Ctrl+휠 없음, Mesh Curve는 점 반지름 따름; 새 아이콘 9개 파일·stem, 왼쪽 메뉴에서 같은 그림 없음. 실제 키 입력 / 화면은 미검증.

## 0.24.16 결과: 79개 파일 2554/2554 (`tests/test_log_bpy501_v02416.txt`) (`tests/test_log_bpy501_v02416.txt`). test_v02416(8): Puff 1은 pressure 안 바꿈, 2 = 2배 / 0 = 0, Cloth 프리셋은 2에서 > 1, 새 천 Puff 1, 바꾸면 표시만(굽기 안 함), Refresh 2.5 → 값 유지 + 95% 높이 > 1.1배, 0 → 프리셋보다 낮음. 비교 렌더 `reference/panel_cloth_puff_v02416.png`(Cycles CPU, headless). 뷰포트 미검증.

## 0.24.15 결과: 78개 파일 2546/2546 (`tests/test_log_bpy501_v02415.txt`) (`tests/test_log_bpy501_v02415.txt`). test_v02415(10): 몸통 가리킴 → 피벗 위치 (1.5, 0, 0), X축 + 뒤집기, 'across Body', 평가 메쉬 x 최대 ≈ 5, 빈 곳 → 원점 복귀, 확정 후 유지, 자기 자신은 피벗 아님, 인스턴스는 자기 콜렉션 제외 + 몸통 너머 x = 5, Esc. test_v02413(21): + 실제 mch.mirror_lean poll 통과(메쉬 선택) / 두 연산자 클래스 분리 / start_mirror에 poll 오류 없음, 커브만 선택 → 안내 문구(poll 오류 아님, 'Curve' 표시), 커브 + 인스턴스 → 인스턴스, 왼쪽 Mirror / Symmetry 버튼 → 메쉬(keep_live True / False) / 인스턴스. test_v0248 / test_v0232: 새 진입점에 맞게 목업 / 소스 검사 갱신(test_v0232는 클래스 주석 검사 복원 - 0.24.13 회귀를 잡는 검사였음). 실제 키 입력은 미검증.

## 0.24.13 결과: 77개 파일 2529/2529 (`tests/test_log_bpy501_v02413.txt`; 전체 실행에서 test_v0232의 keep_live 검사 1개가 Python 클래스 주석을 읽다 실패 - 연산자 속성은 그대로 있음을 확인하고 등록된 RNA 속성을 보도록 고쳐 그 파일만 다시 실행 19/19) (`tests/test_log_bpy501_v02413.txt`). test_v02413(14): 인스턴스 인식, 기울이기 시작 → 같은 콜렉션 거울 인스턴스 1개, 행렬 = X 반사 @ 원본(행렬식 음수), 원본 이동 / 회전 → 따라옴, X+Y → 3개, 다시 미러 → 교체, Esc → 이전 것 복원, 지우면 도우미 없음, 3D 커서 기준면, 거울 인스턴스가 자기 콜렉션에 안 들어감, Alt+X 분기(인스턴스 / 메쉬). 실제 제스처 화면은 미검증.

## 0.24.12 결과: 76개 파일 2515/2515 (`tests/test_log_bpy501_v02412.txt`) (`tests/test_log_bpy501_v02412.txt`). test_v02412(16): 겹친 큐브 5개 한 번에 → 하나의 닫힌 솔리드(길이 > 7.5), 떨어진 큐브는 남고 나머지 붙음, 미리보기 위에 다음 퓨즈 → 앞의 것 확정 + 새 미리보기, 두 개씩 4번 → 매번 닫힌 솔리드 + 이음새 표시 없음, 그 뒤 떨어진 것은 거절, 미리보기에 컷 → 확정 후 원래 상대 쪽 자리에 구멍(x 2.0 ~ 2.4), 닫힌 솔리드. 수정 전 재현: 두 개씩 4번째에 비다양체 엣지 122개(옛 이음새 재베벨), 떨어진 큐브가 '붙음'으로 삭제. 뷰포트 미검증.

## 0.24.11 결과: 75개 파일 2499/2499 (`tests/test_log_bpy501_v02411.txt`) (`tests/test_log_bpy501_v02411.txt`). test_v02411(11): 두 큐브를 덮는 스케치 + Selected Only(A만 선택) → A만 숨김, 아무것도 선택 안 함 → 안 숨김, Auto → 둘 다; Shift+D처럼 복사한 오브젝트는 처음엔 같은 볼륨 → A에 다시 숨기면 복제본은 자기 볼륨(첫 모양 그대로), A는 두 모양, 볼륨 이름표 각자, 공유 중 Show All은 볼륨을 안 지움. 뷰포트 미검증.

## 0.24.10 결과: 74개 파일 2488/2488 (`tests/test_log_bpy501_v02410.txt`; 전체 실행에서 test_v02321의 소스 문자열 검사 1개가 HUD 판정을 tool_owns로 옮긴 탓에 실패 → 실제 동작 검사로 고쳐 그 파일만 다시 실행 13/13) (`tests/test_log_bpy501_v02410.txt`). test_v02410(31): 두 툴이 툴 목록 / 아래 버튼 / 설정 패널 / enum에 있음, Detail 3 라쏘 → 평평한 판(높이 단계 2개: 윗면, 묻힌 바닥), 기본 높이 2 %, 닫힌 솔리드, 벽이 수직(윗면 폭 = 바닥 폭), Height / Lift 실시간, Enter 대상, Detail 1은 계단 그대로; Line Curve: 점 반지름 1 / 3 / 0.3 + Start 0.5 / End 2에도 복사본 4개 크기 같음, Radius ×2 / Size ×0.5가 전체에 똑같이, 일반 Repeat은 여전히 크기가 달라짐, 이름 Line Curve, Mesh Curve 기본값 / Mode 토글에 Line Curve 없음, Line Curve는 토글로 안 바뀜, HUD는 각자 툴에서만. 뷰포트 미검증.

## 0.24.9 결과: 73개 파일 2439/2439 (`tests/test_log_bpy501_v0249.txt`) (`tests/test_log_bpy501_v0249.txt`). test_v0249(15): 원본 쪽 / 미러 쪽 / 뒤집은 뒤(scale.x -1) 양쪽에서 Cut 성공, 홈 위치가 원본 반쪽 x 2.2 ~ 2.8, 닫힌 솔리드 유지, 피벗(Empty x=1) 미러 반대쪽 → 2.55 ~ 3.05, 미러 없는 메쉬 옆은 그대로 '변경 없음', 임시 메쉬 안 남음. Box Hide Ctrl+Z는 headless에서 Undo를 못 돌려 재현 못 함.

## 0.24.8 결과: 72개 파일 2424/2424 (`tests/test_log_bpy501_v0248.txt`) (`tests/test_log_bpy501_v0248.txt`). test_v0248(10): 키맵 3개(Object Mode), S는 선택 있으면 통과(PASS_THROUGH) / 없으면 Split, Alt+A → Armor Plate, Alt+X 선택 없으면 경고 / 메쉬 선택이면 mirror_lean(keep_live=True). 실제 키 입력은 미검증.

## 0.24.7 결과: 71개 파일 2414/2414 (`tests/test_log_bpy501_v0247.txt`) (`tests/test_log_bpy501_v0247.txt`). test_v0247(17): JPG 12개 한 번에 → 12개, 미리보기 새로 고침 1번, 목록 50번 다시 그려도 JSON 읽기 0번(같은 목록 객체), 바뀐 파일 이름 반영, 1600 px 원본 → 작은 `_thumb.png`를 아이콘으로, 라이브러리 사본 ≤ 192 px, 지우기 = JSON / 원본 / 썸네일, 오래된 `mch.stamp_scale` 키 항목 삭제, Cut 툴 키맵에 남은 옛 휠 항목이 다시 등록하면 사라짐. 실제 Blender 창에서 목록 속도 / 휠은 미검증.

## 0.24.6 결과: 70개 파일, 2396 / 2397 (`tests/test_log_bpy501_v0246.txt`). 실패 1개 = test_v02319 "드래그 한 번 0.5초 이내"(0.514초) - 단독 재실행 0.497 / 0.567 / 0.539, 0.24.4 커밋을 worktree로 받아 같은 검사를 돌려도 0.519 / 0.609 / 0.542(예전 0.42 ~ 0.48)라 코드 변경이 아니라 지금 머신이 느린 것. 여러 파일 불러오기는 전체 실행 뒤 추가 → test_png_shapes(85) / test_v0245(22) / test_ui_draw(191) / test_register(11) 재실행 통과. test_v0245: 알파 PNG(투명 위 검은 네모) + JPG(흰 원)를 한 번에 → 2개, 각각 외곽선 1개. 뷰포트 미검증.

## 0.24.5 결과: 70개 파일, 2396 / 2396 (`tests/test_log_bpy501_v0245.txt`, 최종 코드로 단독 실행). test_v0245(21): Enter 키맵 / 대상 / 적용, 더블클릭(그린 것 없음 → 취소 + 메쉬 선택, invoke 더블클릭, 그리는 중엔 닫기), 나사 되돌리기, JPEG 실제 파일 불러오기(원 1개, PNG 사본), 휠 크기(스탬프일 때만), Base Mesh 설정 유지(0.77 / Chamfer / 0.11), Alt Base Mesh = Cut(From Surface 0.3 → 뒷면 그대로). test_v0100_regression: 옛 "Alt 커터 = 뒤집힌 챔퍼 포켓" 검사 3개를 새 동작(Cut처럼) 검사로 바꿈. 뷰포트 미검증.

## 0.24.4 결과: 69개 파일, 2377 / 2377 (`tests/test_log_bpy501_v0244.txt`, 다른 실행과 겹치지 않게 단독). 이 실행 뒤 Plate Detail 2 Foot + Wall을 추가해 test_v0240(23) / test_v0241(16)을 다시 돌려 통과(프리셋, 바닥 접선 / 벽 각도 검사). test_v02328(12): Refresh 버튼(바꿔도 안 구움, 표시, Refresh로 굽기). 렌더로 모양 확인 `reference/plate_detail2_presets_v0244.png`. 뷰포트 미검증.

## 0.24.3 결과: 69개 파일, 2371 / 2372 (`tests/test_log_bpy501_v0243.txt`). 실패 1개는 test_v02319 시간 검사(0.599초, 전체 실행 두 개가 겹쳐 돌던 중) → 단독 재실행 0.418초 통과. 이 전체 실행 뒤 Box Hide 스케치(Alt + Enter)를 한 번 더 바꿔서 관련 테스트 test_v0193 / v02317 / v0241 / v0243을 다시 돌려 모두 통과. test_v0243(9): 핸들러가 depsgraph.updates를 읽지 않음(읽으면 예외 나는 가짜 depsgraph), undo 뒤 쉼, Box Hide 스케치 추가 / Alt + Enter 다시 보이기 / Enter 숨기기. 크래시 자체는 헤드리스에서 실행취소가 안 돼 재현 불가 - Blender에서 미검증.

## 0.24.2 결과: 68개 파일, 2363 / 2363 통과 (`tests/test_log_bpy501_v0242.txt`). Plate Detail 다시 만들기 측정(큰 판): 7px 3.2 ~ 5초 → 20px 0.2 ~ 0.4초. Panel Cloth: 0.23.25 코드와 새 코드의 기본 결과 정점 좌표 numpy array_equal로 동일 확인(Padding, Cloth). Fast Start: 준비 9.3초 → 0.02초, 주름 위치 최대 1 ~ 4 %(판 크기 대비) 다름. test_v02328(11): 슬라이더 + Fast Start. test_v02319 시간 검사 1회 실패(다른 측정과 동시에 돌려서 0.525초) → 단독 재실행 0.479초 통과. Ctrl+Z 크래시는 헤드리스에서 실행취소가 안 돼 재현 불가 - 미검증.

## 0.24.1 결과: 68개 파일, 2361 / 2361 통과 (`tests/test_log_bpy501_v0241.txt`). test_v0241(12): Detail / Detail 2 / Box Hide 스케치 키, Detail 스케치 두 사각형 → Enter 한 번(L자 합집합), Lift ±, Detail 2 스케치 + Alt 구멍, Round 곡선(바닥·위 평평), Chamfer 직선, 바닥 샤프 엣지, Box Hide 스케치. 면 줄이기는 휜 원통 위 렌더로 직접 확인: 처음 버전은 큰 판이 평평한 면으로 합쳐져 표면 아래로 꺼짐 → 곡률 격자로 고침, 또 Detail 2 곡률을 경사에서 재서 칸이 너무 잘았음 → 영역 패치에서 재도록 고침. 뷰포트 미검증.

## 0.24.0 결과: 67개 파일, 2349 / 2349 통과 (`tests/test_log_bpy501_v0240.txt`). test_v0240(23): 라쏘 → 디테일(부모, 닫힌 솔리드, 낮음, Edge High 최고점), 넓이 / 높이 변경 다시 만들기(타이머), 3겹 프리셋, Inside High 높이 합, 나사 2, 값 기억, Apply, 아머 플레이트 위에 그리기, Detail 2(높이, Slope Width 넓을수록 윗면 좁음, 4가지 모양), Remove. 처음엔 띠 경계가 한 정점에서 꼬이는 곳에 4면 엣지 1개 → 정점 섹터 분리로 고침. test_v0240b(17): 4종 머리 닫힌 솔리드 / 높이 / 구멍, 윗면·옆면 클릭 방향, 메쉬 따라감, 라이브 높이 / 머리, Alt 지우기, Join. test_v02328(9): Tension / Gravity 다시 굽기, 값 유지, 프리셋 다시 굽기. 프로토타입 렌더 `reference/plate_detail_proto*.png`. 뷰포트 클릭 / 드래그 / 나사 모양 렌더 확인은 미검증.

## 0.23.27 결과: 64개 파일, 2270 / 2270 통과 (`tests/test_log_bpy501_v02327.txt`). test_v02327(38): 모든 도구에서 Lasso Settings poll + draw(가짜 layout에 stroke_smooth), 도구 패널에 사본 없음, Cut 라쏘 Edge Finish 유지, Alt 빨강 / Alt 없으면 도구 색. 바뀐 동작에 맞게 고친 옛 검사: test_v0141(Cut Alt 하늘색), test_v02317(Box Hide Alt 주황). 사이드바 / 선 색 화면 확인은 뷰포트 필요 - 미검증.

## 0.23.26 결과: 63개 파일, 2232 / 2232 통과 (`tests/test_log_bpy501_v02326.txt`, 한 번에 통과). test_v02326(14): 추가 / 표면 위치 / 반지름 0.5 자동, 근처만 움직임, 윗면까지 감쌈, 핸들 이동 반영, Mirror, Taper, 음수 Depth, 패턴 화살표 다시 굽기, 여러 개, 별도 패널, Overall Scale 무관, 삭제, Apply. 렌더 검토에서 주름 줄무늬(조각 겹침) 발견 → 획마다 거리 하나로 고침. 뷰포트 / 파일 다시 열기 미검증.

## 0.23.25 결과: 62개 파일, 2218 / 2218 통과 (`tests/test_log_bpy501_v02325.txt`). 팝업 기즈모 그룹 클래스를 0.23.22와 diff로 비교해 동일 확인. 버튼이 다시 보이는지는 뷰포트 필요 - 미검증.

## 0.23.24 결과: 62개 파일, 2218 / 2218 통과 (`tests/test_log_bpy501_v02324.txt`). 바뀐 동작에 맞게 고친 옛 검사: test_v0234 / v0238 / v02319 / v02321(HUD 슬라이더 목록, Tube poll 개수). test_v02324: 팝업 버튼만, Base Mesh에서 Robot만 보이고 Detail Stamp 등 숨김, Cut에서 Robot 숨김. Select에서 보이는지는 헤드리스로 확인 불가 - 미검증.

## 0.23.23 결과: 61개 파일, 2207 / 2207 통과 (`tests/test_log_bpy501_v02323.txt`). 헤드리스에서 HUD 슬라이더 기즈모의 invoke / modal을 직접 불러 드래그(100 → 120 %) 동작 확인 - 코드 경로는 정상, 그래서 기즈모 손잡이 누락을 원인으로 보고 수정(실제 Blender에서 원인 확인은 못 함). test_v02323: 사이드바 150 % ↔ HUD 100 % 동기화, 손잡이 없는 HUD에 손잡이 생성. 처음엔 ob['mch_cloth_scale']로 필드를 맞추려다 Blender 5에서 안 돼 가드 방식으로 고침. 뷰포트 미검증.

## 0.23.22 결과: 60개 파일, 2204 / 2204 통과 (`tests/test_log_bpy501_v02322.txt`). test_v02322: 배율 0.01인 둥근 큐브 스컬핑(3.3만 면) → 1.1초, 33면, 닫힘, 엔곤은 평평(크기의 0.02 % 이내, 작은 모서리 사각형 하나만 0.3 %), 크기 비슷, Bevel 1 → 4 세그먼트, Flatten 끄면 면 많아짐, Apply. 사용자 FBX 수동 확인: 23면 / 점 77 / 닫힘. 처음 테스트에서 크기를 갱신 전에 읽은 검사와 기대치(면 30 이하, 모든 면 평평)를 측정에 맞게 고침. 뷰포트 미검증.

## 0.23.21 결과: 59개 파일, 2194 / 2194 통과 (`tests/test_log_bpy501_v02321.txt`). test_v02321: Cloth Plate HUD가 Cut에서 숨고 Cloth Plate에서 보임, 7개 HUD poll이 실제로 실행됨(이걸로 import 누락 발견 - 전체 테스트는 poll을 부르지 않아 통과했었음). 뷰포트 미검증.

## 0.23.20 결과: 58개 파일 통과 (`tests/test_log_bpy501_v02320.txt`). test_v02319에 드래그 한 단계 시간(약 0.4초) 추가. 실제 뷰포트 다시 그리기는 헤드리스에서 확인 불가 - 미검증.

## 0.23.19 결과: 58개 파일, 2182 / 2182 통과 (`tests/test_log_bpy501_v02319.txt`, 한 번에 통과). test_v02319: Overall Scale 200 % → 길이 값 전부 ×2, 두께 ×2, Trim / 각도 / Fan 그대로, 100 %로 원래 값. 뷰포트 미검증.

## 0.23.18 결과: 57개 파일, 2176 / 2176 통과 (`tests/test_log_bpy501_v02318.txt`). 사용자 설정 재현(높이 0.06, Chamfer, Width 2): 예전엔 0.057로 잘림 → 이제 모양에 맞춰 0.98(4 × 2 판). test_v02318: Width 0.4 → 윗면 ±1.6, 닫힘; Bevel 높이 6단; 너무 넓음 → 노트; Bottom; Both; Mirror 버튼 Cut에선 숨김. 중간에 겹침 검사가 약해 뾰족한 홈 모양에서 판이 바깥으로 뒤집힌 것을 발견 → 검사 강화(이제 뾰족한 모서리가 있으면 그 모양 전체 Width가 줄어듦). 뷰포트 미검증.

## 0.23.17 결과: 56개 파일, 2158 / 2158 통과 (`tests/test_log_bpy501_v02317.txt`). 측정(10만 면 구, 헤드리스): Exact 46.1초 / Float 0.91초 / Manifold 0.23초 → Cap 0.27초, Open 0.25초. 중간에 Open을 '안쪽 점 삭제'로 했더니 낮은 폴리 큐브에 구멍이 안 생겨(test_v02316 실패) 컷 + 막은 면 삭제로 바꿈. 뷰포트 미검증.

## 0.23.16 결과: 55개 파일, 2151 / 2151 통과 (`tests/test_log_bpy501_v02316.txt`, 한 번에 통과). test_v02316: 4 큐브에 2×2 숨김 → 평가 부피 64 → 48, 닫힘; 메쉬 데이터 그대로; Open = 구멍(비매니폴드 8); Alt 같은 곳 = 모디파이어 제거; Alt 일부 = 52.8; 겹친 숨김 39.6; Show All; Mirror X = 48; Apply = 실제 부피 48, 닫힘; 빈 곳 = 메시지. 뷰포트 / 속도 미검증.

## 0.23.15 결과: 54개 파일, 2129 / 2129 통과 (`tests/test_log_bpy501_v02315.txt`, 한 번에 통과). Cloth Plate / Panel Cloth를 0.23.9로 되돌림(0.23.10~0.23.13 클로스 테스트 3개 파일 삭제, 옛 테스트는 0.23.9 버전). test_v02315: 큰 판 → 작은 판 길이 비율, 프리셋 크기, 길이 제한, Billow 기본값, 0.23.9 코드 확인, Space 이동. 뷰포트 미검증.

## 0.23.14 결과: 57개 파일, 2155 / 2155 통과 (`tests/test_log_bpy501_v02314.txt`). test_v02313에 추가: 큰 판(크기 4.97) → 작은 판(0.46)에서 Pinch Length / Puff가 크기 비율로 줄어듦, Fan(길이 아님)은 그대로, 작은 판이 작게 유지, 크기 없는 옛 길이 값 버림, 작은 판 프리셋을 큰 판에 불러오면 Puff가 크기를 따름. 첫 실행에서 test_v0200의 "같은 숫자" 검사 2개가 실패 → 비슷한 크기(0.5~2배)는 같은 숫자로 유지하도록 고치고 프리셋도 크기 포함으로 고친 뒤 전체 재실행. 사용자 cloth.fbx 대상 + 스크린샷의 값으로: 수정 전 판 0.66 × 0.50 × 0.56 m(대상 0.49 × 0.13 × 0.23)의 파편 덩어리, 수정 후 0.34 × 0.05 × 0.17 m. 뷰포트 미검증.

## 0.23.13 결과: 57개 파일, 2148 / 2148 통과 (`tests/test_log_bpy501_v02313.txt`). 새 `test_v02313.py`: 막 높이 - 정사각형 대각선을 가로지르는 2차 차분이 간격 절반에 1/3.88(매끈, 테두리 거리는 1/2.0 = 능선), 패딩 판 생성, Space 이동(점 전부 +40/-50 이동, 놓은 뒤에는 이동 안 함). 바뀐 동작에 맞게 고친 옛 검사: test_v0200(Center Calm 0으로 측정), test_v02312(기본 0.9), test_stroke_events / test_v0113 / test_workspace_data(Space 메뉴 제거). 첫 실행에서 이 검사들이 실패해 고친 뒤 전체를 다시 돌림. Base Mesh 생성 후 Bevel 전환은 헤드리스에서 사각형/원/라쏘 20·120점/표면 부착 모두 정상 - 사용자 GUI 보고(안 됨)는 재현 안 됨, 미해결. 뷰포트 미검증.

## 0.23.12 결과: 56개 파일, 2112 / 2112 통과 (`tests/test_log_bpy501_v02312.txt`, 한 번에 통과). Center Calm 0 vs 1: 가운데(반경 25 %) 높이 편차 0.028 → 0.0, 테두리 근처 0.035 → 0.033(Solidify 끈 표면만 측정). 렌더 비교. 뷰포트 미검증.

## 0.23.11 결과: 55개 파일, 2109 / 2109 통과 (`tests/test_log_bpy501_v02311.txt`). 전체 실행에서 `test_v0238.py` 1회 실패: 새 판 Pinch 2 = Pinch 1을 기대하던 검사(0.23.11에서 일부러 절반) → 검사 수정, 그 파일만 다시 실행해 구간 교체. `test_v0234` 주름 방향 검사는 비대칭이 옮겨간 FOLD_D를 측정하도록 변경. 0.23.2 코드(git 22e4911)와 같은 라쏘로 Cycles 렌더 비교. 구슬 원인은 Pinch 0 / Pinch 2 0 / Stitch 0 비교로 긴 주름 필드로 확인. 뷰포트 미검증.

## 0.23.10 결과: 54개 파일, 2101 / 2101 통과 (`tests/test_log_bpy501_v02310.txt`, 한 번에 통과). 압력 / Shrink 조합별 높이 측정(P6 S-0.05: 0.59, P0 S-0.05: 0.24, P0 S0: 0.04)으로 Puff 설계. 테스트: 슬라이더 채움, Puff 0.3 / 0 높이, Detail 1 → 3 면 수, Decimate 예산, 박스 위 / 열린 반원통에서 바깥 방향 유지. 프로파일: Draft 시뮬 자체 0.75초, 새 파일에서 처음 한 번 노드 그룹 생성이 약 8초(헤드리스). 실제 PC 속도 / 멈춤 여부는 미검증.

## 0.23.9 결과: 53개 파일, 2089 / 2089 통과 (`tests/test_log_bpy501_v0239.txt`, 한 번에 통과). `test_v0238`의 오퍼레이터 인자 `collide=False` → `collider='NONE'`(옵션 이름 변경). 라쏘 → Sim(Puffer) → 베이크, 임시 충돌체 제거, 몸 미변경, 박스 위로 부풀고 안 꺼짐, Cloth로 다시 굽기(더 평평), Split Angle 큐브 6조각, Seam 분할, Remove Faces. 프리셋 9개 모양은 Cycles 렌더로 확인. 뷰포트 / 실제 PC 속도 미검증.

## 0.23.8 결과: 52개 파일, 2075 / 2075 통과 (`tests/test_log_bpy501_v0238.txt`). 전체 실행에서 `test_v0200.py` 1회 실패: "Strength 0 = 평평" 검사가 Pinch만 0으로 만들고 새 Pinch 2는 안 만듦 → Pinch 2 추가, 그 파일만 다시 실행해 구간 교체. Panel Cloth는 헤드리스에서 실제 클로스 캐시를 프레임 진행으로 계산해 검사(부풀기, 고정된 테두리, 몸 관통 없음, 임시 충돌체 제거, Through 두 판 → 끝 두 개만 열린 하나의 링, Edit Mode 선택 면). 뷰포트 대화창 / 실제 PC 속도는 미검증.

## 0.23.7 결과: 51개 파일, 2059 / 2059 통과 (`tests/test_log_bpy501_v0237.txt`). 전체 실행에서 `test_v0235.py`가 1회 실패: Skin Organic / Irregular가 맨 끝 입력이라고 가정한 예전 검사(0.23.7에서 Crumple 입력이 뒤에 붙음) → 순서 검사로 고치고 그 파일만 다시 실행해 로그 구간 교체. Through: 원통 위 띠 = 위 반 / 아래 반 2패널, 큐브 Crease 50° = 6, 180° = 2, 실제 도구로 Cloth / Armor 각각 2개, Through 판 Face Size 재생성. 옷 모양은 Cycles 렌더로 비교. 원근 뷰 / 뷰포트 동작은 미검증(테스트는 정사영 프로젝터).

## 0.23.6 결과: 50개 파일, 2040 / 2040 통과 (`tests/test_log_bpy501_v0236.txt`, 한 번에 통과). `test_v0234`의 "다섯 스킨" 검사는 앞 5개만 보도록 수정(Croc Back 추가). 가시: 높은 점이 중간값 위로 튀어나온 정도가 악어보다 큰지(5.39 대 1.77). 모양은 Cycles 렌더로 비교. 뷰포트는 미검증.

## 0.23.5 결과: 49개 파일, 2035 / 2035 통과 (`tests/test_log_bpy501_v0235.txt`, 한 번에 통과). Edge Shrink 검사: 경계에서 Shrink Width × 2.2보다 먼 안쪽 점은 높이 변화 0, 경계 근처는 변함. 모양은 Cycles 렌더로 확인. 뷰포트 HUD 슬라이더 동작은 미검증.

## 0.23.4 결과: 48개 파일, 2024 / 2024 통과 (`tests/test_log_bpy501_v0234.txt`). 전체 실행에서 `test_v0120.py`가 1회 실패: 새 Skin/Shell 툴바 항목이 tool id가 아니라 `mch.creature_brush`로 가는데 예전 검사가 tool id만 허용 → 검사 수정 후 그 파일만 다시 실행해 로그의 해당 구간을 교체(로그 끝에 기록). 주름 방향은 서 있는 패널에서 세로 엣지의 오르막/내리막 개수로 검사(Up 1380/995, Down 998/1377). 스킨 / 갑각 모양은 Cycles 렌더로 확인. 실제 뷰포트 HUD·툴바 버튼 동작은 미검증.

## 0.23.3 결과: 47개 파일, 1995 / 1995 통과 (`tests/test_log_bpy501_v0233.txt`). 주름 단면은 Cycles 렌더로 비교, IK는 순수 함수 테스트. 실제 뷰포트에서 IK 드래그는 미검증.

## 0.23.2 결과: 46개 파일, 1983 / 1983 통과 (`tests/test_log_bpy501_v0232.txt`). 전체 실행에서 test_v0192.py의 예전 기대값(미러 버튼 = 즉시 모디파이어) 1개 실패 → 새 동작(제스처, live 유지) 확인으로 고친 뒤 그 파일만 다시 실행(32/32)해 로그에 반영. 미러 제스처·커브 기즈모 드래그·버튼 줄은 실제 뷰포트에서 실행 못 함 — 미검증. 중력은 Cycles 렌더로 확인.

## 0.23.1 결과: 45개 파일, 1961 / 1961 통과 (`tests/test_log_bpy501_v0231.txt`). 주황 핸들 드래그는 가짜 이벤트로 확인, 실제 뷰포트 표시는 미검증.

## 0.23.0 결과: 45개 파일, 1958 / 1958 통과 (`tests/test_log_bpy501_v0230.txt`). Tube는 가짜 이벤트(정면 Ortho)로 점 추가/드래그/삽입/삭제/굵기, 설정, Repeat, Apply 확인 + Cycles 렌더. 실제 뷰포트 조작은 미검증.

## 0.22.2 결과: 44개 파일, 1912 / 1912 통과 (`tests/test_log_bpy501_v0222.txt`). 전체 실행에서 test_v0222.py의 예전 기대값 2개(Surface = Cut/Split만)가 실패 → 기대값을 고친 뒤 그 파일만 다시 실행(22/22)해 로그에 반영. 구에 앞/옆 시점으로 그린 판을 Cycles로 렌더해 확인, 실제 뷰포트 조작은 미검증.

## 0.22.1 결과: 43개 파일, 1902 / 1902 통과 (`tests/test_log_bpy501_v0221.txt`). Surface Lasso는 원통에 앞/뒤 시점을 바꿔가며 점을 찍는 가짜 이벤트로 확인(분리·Gap·닫힘). 실제 뷰포트 그리기/궤도 회전 조작은 미검증.

## 0.22.0 결과: 42개 파일, 1880 / 1880 통과 (`tests/test_log_bpy501_v0220.txt`). 몸통·머리는 보내주신 FBX와 Cycles로 나란히 렌더해 비교. 라인 라쏘·디테일 스탬프는 가짜 마우스 이벤트로 로직만 확인 — 실제 뷰포트 조작은 미검증.

## 0.21.1 결과: 39개 파일, 1749 / 1749 통과 (`tests/test_log_bpy501_v0211.txt`). 보내주신 FBX 조각과 생성 메쉬를 Cycles로 나란히 렌더해 비교, 뷰포트 팝업·패널 조작은 미검증.

## 0.21.0 결과: 38개 파일, 1633 / 1633 통과 (`tests/test_log_bpy501_v0210.txt`). 로봇 모양은 Cycles CPU 렌더로 확인, 뷰포트 팝업·N 패널 조작은 미검증.

## 0.20.4 결과: 37개 파일, 1581 / 1581 통과 (`tests/test_log_bpy501_v0204.txt`).

## 0.20.3 결과: 37개 파일, 1578 / 1578 통과 (`tests/test_log_bpy501_v0203.txt`).

## 0.20.2 결과: 37개 파일, 1576 / 1576 통과 (`tests/test_log_bpy501_v0202.txt`). 모양은 Cycles CPU 렌더로 확인, 뷰포트 조작은 미검증.

## 0.20.1 결과: 37개 파일, 1565 / 1565 통과 (`tests/test_log_bpy501_v0201.txt`). Cloth Plate 모양은 Cycles CPU 렌더로 확인, 뷰포트 팝업 조작은 미검증.

## 0.20.0 결과: 37개 파일, 1558 / 1558 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0200.txt`). 주름 미리보기는 Cycles CPU 렌더로 확인. 뷰포트 팝업 조작은 미검증.

## 0.19.3 결과: 35개 파일, 1518 / 1518 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0193.txt`). Sketch 버튼·키 입력은 GUI에서 실행하지 못함 — 미검증.

## 0.19.2 결과: 34개 파일, 1505 / 1505 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0192.txt`). 뷰포트 버튼·팝업 고정은 GUI에서 실행하지 못함 — 미검증.

## 0.19.1 결과: 33개 파일, 1475 / 1475 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0191.txt`). 우클릭 메뉴·F9 조정 창은 GUI에서 실행하지 못함 — 미검증.

## 0.19.0 결과: 32개 파일, 1459 / 1459 통과 (headless bpy 5.0.1, `tests/test_log_bpy501_v0190.txt`). GUI(HUD 버튼·슬라이더 드래그)는 실행하지 못함 — 미검증.

## 환경
| 항목 | 값 |
|---|---|
| Blender | `bpy` 5.0.1 (build a3db93c5b259), **headless / background** |
| Python / OS | 3.11 / Linux 6.18 (클라우드 컨테이너) |
| 사용자 환경 | Windows 11 + Blender **5.0.2 GUI** — **실행 안 됨** |
| 사용자 설정 | 임시 `BLENDER_USER_*` 폴더 사용, 실제 설정·Startup 미사용 |
| 기준 | ChatGPT v0.9.3 무수정 ZIP (sha256 `3b66e845…a1e4cd`) |

명령: `<bpy python> tests/run_all.py` · 로그: `tests/test_log_bpy501_v0111.txt`
ZIP: `dist/mecha_lab-0.11.1.zip` (sha256 `fb8960ae4fc08a273b09cb6d1cfca01a7efda2da8d16ee193d1ec480423f0593`)

**변경 전(v0.9.3 무수정)에도 같은 headless 테스트는 모두 통과**했습니다(경로 누락 2건 제외). 즉 사용자 보고 고장 대부분은
headless로 재현되지 않았고, 아래 "GUI 검증" 열은 전부 미검증입니다.

## 0.18.0 결과: 31개 파일, 1438 / 1438 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Mirror HUD 배치·아이콘, X/Y/Z·Bisect·Flip 즉시 반영, 마지막 축 보호, Apply·Remove | O | O | **미검증 (화면)** |

## 0.17.0 결과: 30개 파일, 1425 / 1425 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 중심점 샘플·Lloyd·칸 나누기, 윤곽 단순화·Gap·뒤집힘 거부, 테두리 조각 | O | O | 미검증 |
| 6면 박스 위 판 여러 개(박스 그대로, 닫힘, 새 면), 프로필 섞임 | O | O | 미검증 |
| Density·Panel Size·Seed(같은 Seed = 같은 배치)·Reroll | O | O | 미검증 |
| Edge Pieces 객체, Mirror(모디파이어 + 한쪽만), Apply / Cancel, 편집 모드 선택 면만, 구면 | O | O | 미검증 |
| HUD 배치·슬라이더 | O | O (계산) | **미검증 (화면)** |

## 0.16.0 결과: 29개 파일, 1401 / 1401 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 새 면 패치(테두리 다시 나누기, 꼭짓점 유지, 넓이 정확, 구멍, 큰 판 자동 경량) | O | O | 미검증 |
| 6면 박스 위 판: 별도 오브젝트, 박스 그대로, 새 면(대부분 사각형), 테두리 0.1 px 이내, 표면 위, 닫힌 솔리드 | O | O | 미검증 |
| 판 위에 그리면 아래 메시에, 휠 = 프로필, 곡면(구) 위에 붙음, 프로필 버튼 라이브 | O | O (가짜 이벤트) | **미검증** |
| 메시 밖 = 메시지, 일부 밖 = 생성 + 알림 | O | O | 미검증 |

## 0.15.0 결과: 28개 파일, 1365 / 1365 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 아이콘 타일 = 큰 그림 + 이름 버튼 | O | O (그리기 호출) | **미검증 (모양)** |
| 왼쪽 떠 있는 툴 목록(배치, 여러 줄, 툴팁) | O | O (계산) | **미검증** |
| HUD 배치(오른쪽, 화면 안, 끝 버튼), 슬라이더 값/범위, 모드 | O | O | **미검증 (클릭/드래그)** |
| Station Apply + 합치기 / − 파내기 / 안 닿으면 확정 / 빼기 실패 메시지 | O | O | 미검증 |
| 겹치는 면 검사(같은 크기 6면, 큰 도형 0, 높이만 다름 4면) | O | O | **미검증 (빨간 점선)** |
| Up/Down + Left/Right 동시, Twist, 예전 Bend 변환(모양 동일) | O | O | 미검증 |
| 다이얼 방향(보는 쪽으로 뒤집기) | O | O (계산) | **미검증 (드래그)** |
| Polygon Prism: 서서 시작, Sides 3–64, 베벨/챔퍼, 위/아래 구간 ±, 접힘 점 순환, 모든 조합 닫힘 | O | O | 미검증 |

## 0.14.4 결과: 27개 파일, 1315 / 1315 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Base Mesh 빼기 선 = 빨간색(더하기 주황과 다름), Cut 색 그대로 | O | O (색 값) | **미검증 (화면)** |

## 0.14.3 결과: 27개 파일, 1313 / 1313 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 위/아래 크기(부피 공식), 피라미드, 베벨·챔퍼(닫힘), 실제 메시 반영 | O | O | 미검증 |
| 이동 화살표(축 방향만, 기준점 고정), 전체 크기 점, 다이얼 3개(드래그 기준) | O | O (계산) | **미검증 (드래그)** |
| 도형 되돌리기/다시(드래그 = 한 단계), Enter 후 기록 초기화 | O | O | 미검증 |
| 도형 고르기 전 숨김, Station 생성 시 숨김 | O | O | 미검증 |
| Enter 직후 외곽선만, 살아 있는 Base Mesh 동결 | O | O | **미검증 (화면)** |
| Station 핸들 실행 취소 단계 | O | O (기록 시점) | **미검증** |
| Stick to Surface(기울어진 면 법선, 바닥 묻힘, 구면 더 깊게, 끄면 예전) | O | O | 미검증 |
| 아이콘 버튼 타일, 왼쪽 툴 메뉴 격자 | O | O (그리기 호출) | **미검증 (모양)** |
| 아이콘 크기 파일 저장/읽기 | O | O | 미검증 (재시작) |

## 0.14.2 결과: 26개 파일, 1260 / 1260 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 설정 3개(기본 1.0), 프리셋 버튼 | O | O | 미검증 |
| 썸네일 전부 Panel Icons 적용(소스 검사) | O | O | **미검증 (화면)** |
| 아래 툴바 크기·간격·가운데 정렬 | O | O | **미검증 (화면)** |
| 핸들 크기 배율 | O | X (그리기 불가) | **미검증** |

## 0.14.1 결과: 25개 파일, 1247 / 1247 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 스케치 합치기/구멍/노치/두 조각/섬/전부 빼기/모서리 공유 | O | O | 미검증 |
| 획 → 스케치(메시 안 생김), Alt 획 = 빼기, Backspace | O | O (가짜 이벤트) | 미검증 |
| Enter = 라이브 Base Mesh(부피 정확, 구멍 저장, 프로필 변경 재생성) | O | O | 미검증 |
| Alt+Enter = 아래 메시에 포켓, Esc = 지우기, 빈 스케치 Enter 거부 | O | O | 미검증 |
| Sketch First 끔 = 예전 즉시 생성 / Alt 커터 | O | O | 미검증 |
| 주황색 스케치 그리기 | O | X (그리기 불가) | **미검증** |

## 0.14.0 결과: 24개 파일, 1219 / 1219 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 6가지 도형 형상(닫힘, 바깥 방향, 크기), 알약 부피 | O | O | 미검증 |
| 비대칭 크기 조절(반대 면 고정), 핸들 배치, 표면 정렬 | O | O | **미검증 (드래그)** |
| Enter 합치기(겹친 메시 / 없으면 새 오브젝트), 활성 오브젝트 우선 | O | O | 미검증 |
| Alt+Enter 빼기, 안 닿으면 변경 없음, Chamfer 이음새 | O | O | 미검증 |
| 라이브 Station Primitive 동결 후 빼기 | O | O | 미검증 |
| 반투명 그리기 / Alt 빨간색 / 클릭 이동 | O | X (그리기 불가) | **미검증** |
| 스탬프 커서 = 마우스 위치 | O | O (좌표만) | **미검증 (화면)** |
| 툴바 툴팁 = 버튼 이름, 이름 표시 기본 켜짐 | O | O | 미검증 |
| 패널·RMB 메뉴 도형 격자 | O | O (그리기 호출만) | **미검증 (모양)** |

## 0.13.2 결과: 23개 파일, 1172 / 1172 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| Curved Plate (정점 수, 크라운 높이, 두께 일정, 높은 크라운) | O | O | 미검증 |
| 아머 5종 (닫힌 쉘, 경고 없음, 사람 크기, Blender 생성·편집) | O | O | 미검증 |

## 0.13.1 결과: 22개 파일, 1152 / 1152 통과
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 옆으로 꺾기(±90°, 평평 유지, 닫힌 솔리드) | O | O | 미검증 |
| Fold / Tight / Band (Tight 90° 경고 없음) | O | O | 미검증 |
| 지점별 단면(정점 수 동일, 중간 링 = 평균, 박스→원 닫힌 솔리드) | O | O | 미검증 |
| 방향 버튼, Left = Right, 구간 삽입(끝점 유지) | O | O | 미검증 |
| 핸들 배치(점/+/다이얼/화살표), 다이얼 라디안↔도, 대칭 폭 핸들 | O | O | **미검증 (드래그)** |
| Mirror 라이브 유지 · Apply 시 동결 | O | O | 미검증 |

## 0.13.0 결과: 21개 파일, 1124 / 1124 통과
로그 `tests/test_log_bpy501_v0130.txt`, ZIP `dist/mecha_lab-0.13.0.zip` (sha256 `a9dba3e703b9d92e5f0cbd761033fb0f663bfe871f1a857641868192b83133f9`).
| 항목 | 코드 | headless | Windows GUI |
|---|---|---|---|
| 단면 7종 · 비대칭 · 릿지 (정점 수 고정, 값 검증) | O | O | 미검증 |
| 지점 사슬 30°+45°, 시나리오 E(앞 지점 수정 후 뒤 상대각·값 유지) | O | O | 미검증 |
| 접힘 마이터(부피 보존), 감싸기 200°, 자동 세그먼트, 반경 보정 경고, Step/Smooth, 뾰족 끝 | O | O | 미검증 |
| 프리셋 6개 메시 유효성 | O | O | 미검증 |
| Blender: 생성·실시간 재생성·지점 추가/삭제/이동·Shell·저장 후 재편집·Cut/Boolean 동결·Apply·패널 그리기 | O | O | **미검증** |
| 뷰포트 핸들 | 없음 | — | — |

## 0.12.0 결과: 20개 파일, 1074 / 1074 통과
로그 `tests/test_log_bpy501_v0120.txt`, ZIP `dist/mecha_lab-0.12.0.zip` (sha256 `270841f19e16687320f5e91e0567a7e5b6b414dd5407e8228a1140304417c7fe`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 자동 대상 / 선택만 (Cut·Split·Lasso, 잠금·와이어 제외, 원근 뷰) | O | O | 미검증 |
| T 토글, 헤더 토글 | O | 키맵 등록 | 미검증 |
| Q 파이 / Shift+Q | O | 키맵·상태 로직 (팝업 표시는 불가) | **미검증** |
| 하단 툴바 (기즈모 버튼, 크기, 이름 표시) | O | 등록·아이콘·배치 계산 (그리기 불가) | **미검증** |
| V/N 해제 | O | O | 미검증 |
| 기존 0.11.x 테스트 | — | 키 변경에 맞춰 3항목 수정 후 통과 | — |

## 0.11.3 결과: 19개 파일, 1046 / 1046 통과
로그 `tests/test_log_bpy501_v0113.txt`, ZIP `dist/mecha_lab-0.11.3.zip` (sha256 `deed2943d3d8276a383cdf338455d393e508cf337c6d42e01a1f98c9604e2c37`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 스탬프 도형 6종 (로드·정규화·실제 Cut) | O | O | 미검증 (아이콘 표시) |
| V / N / F 단축키 | O | 등록만 | **미검증** |
| Ctrl+Z 후 도형·도구 유지 | O | 복원 함수 O (실제 Undo는 headless 불가) | **미검증** |
| Cable → Mesh | O | O | 미검증 |
| Curve Lasso 직선 시작 / 클릭 순환 / 핸들 | O | O | 미검증 |
| Lean Mirror (축 선택, ±방향, Shift 추가, Enter 적용, Esc 복구) | O | O (가짜 이벤트) | **미검증** (오버레이·실제 마우스) |
| Radial Array 충돌 | — | 재현 안 됨 | **미해결 (crash 로그 필요)** |

## 0.11.2 결과: 18개 파일, 1012 / 1012 통과
로그 `tests/test_log_bpy501_v0112.txt`, ZIP `dist/mecha_lab-0.11.2.zip` (sha256 `000db2d3d84a0215dcfd1b55fcd296e59267c1e091a2be5d04af7593676c0aa5`).
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 실패 메시지 진단(덮는 정점 수·픽셀·뷰·Alt·버전) | O | O (전체 덮음 / Alt 빗나감) | 미검증 |
| Edit Mode에서 Cut / Split | O | O | 미검증 |
| Self Test 실제 3D View 투영 Cut / Alt Cut / Split | O | O (bpy의 실제 RegionView3D 1574x954 원근 + 대역 원근/직교) | 사용자 실행 필요 |
| 일반 Cube "whole object" | — | 재현 안 됨 | **미해결 (사용자 메시지 필요)** |

## 0.11.1 결과: 18개 파일, 1007 / 1007 통과
`test_v0100_regression.py` 108항목(0.11.0 96 → Alt 클릭/드래그 블록을 0.11.1 블록으로 교체). 나머지 17개 파일 항목 수 그대로.

| 요청 테스트 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 1. Cube Rectangle Cut | O | O (부피 8 → 6) | 미검증 |
| 2. Curve / Lasso Cut | O | O | 미검증 |
| 3. Split | O | O | 미검증 |
| 4. Alt 반전 (누를 때 / 그리는 중 / Alt+클릭 점) | O | O | 미검증 |
| 5. Ctrl 중심 그리기 | O | O | 미검증 |
| 6. Split Gap / Bevel | O | O (기존 Split Gap·Bevel 테스트) | 미검증 |
| 7. Select / Move 메뉴 + W 단축키 | O | 등록·키맵·버튼 그리기만 (실제 기즈모/입력 없음) | **미검증** |
| 8. Select / Move 후 Cut/Split 재진입 | O | O (툴 변경 → 모달 CANCELLED, 새 모달 새 획으로 Cut) | 미검증 |
| 9. 다중 오브젝트 Cut / Split | O | O (F01) | 미검증 |
| 10. 설치·활성·재시작 | O | 설치·비활성·재활성 3회 (재시작 = 새 프로세스는 headless 미실행) | **미검증** |
| MCH_Box(Live Primitive) Cut "whole object" | O | O (재현 → 수정) | 미검증 |
| 일반 Cube "whole object" | — | 재현 안 됨 | 미검증 |
| Alt 모드 전환 코드 제거 | O | O (메서드·연산자·키맵 없음 확인) | — |

## 0.11.0 결과: 18개 파일, 995 / 995 통과
| 신규/변경 | 항목 | 내용 |
|---|---|---|
| test_mechanical_toolkit.py | 99 | **신규** — 사양서 13절: Face Extract(곡면·노멀 방향·원본 유지·챔퍼 3모드 수치·Outward·외곽/측면 엣지·쉘·오프셋·설정 유지·다중 오브젝트), Armor(한 방향만 두께/챔퍼/베벨, 6프리셋 형상 변화와 서로 다름, 회전·스케일, Y 가지별 길이·폭, 능선 6프로필, 방향 회전, 곡면, 설정 복사), Edge Molding(파츠 경계·별도 오브젝트·폭/높이/베벨 독립·프로필·중앙선·면 경계), Curve Array(개수·커브 편집 갱신·Fit·Offset·Deform·World X/Y 배치), Curve Deform, Cable(두 오브젝트 클릭·끝점 고정·노멀 출발·처짐·점 추가·두께·프로필·테이퍼·Edge to Cable), Hollow(다중·내부 쉘·방향·개구부·Rim·과두께 검출·Reset/Apply) |
| test_v0100_regression.py | 96 | +탭 이동 시 Base Mesh 자동 Apply 3, +Tab 통과 1 |
| test_ui_draw.py | 130 | +새 도구 5개 패널(라이브 파츠/Armor Y/몰딩/쉘/배열/케이블) |
| test_self_test.py | 4 | 자가 진단 12단계로 확장, 데이터 잔여 없음 |

| 0.11.0 기능 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| 탭 이동 시 Base Mesh 자동 Apply | O | O (판정 함수) | 미검증 (타이머) |
| Face Extract Basic (모든 슬라이더) | O | O | 미검증 |
| Armor Sculpt (방향·프리셋·능선·전환) | O | O | 미검증 |
| Edge Molding | O | O | 미검증 |
| Hollow / Shell | O | O | 미검증 |
| Mesh Along Curve (Deform / Array / 배치) | O | O | 미검증 |
| Cable Generator (클릭 모달은 로직만, Edge to Cable) | O | O | 미검증 |
| Tab으로 Edit Mode, 설정 유지 | O | O (모달 Tab 통과·재선택 유지) | 미검증 |
| Undo / Redo | O (UNDO 플래그) | 실행 불가(headless) | 미검증 |

## (0.10.0) 결과: 17개 파일, 875 / 875 통과
| 파일 | 항목 | 0.10.0 |
|---|---|---|
| test_v0100_regression.py | 92 | **신규** — B01–B10, F01/F02/F08, Alt, V/Shift+A |
| test_deform.py | 109 | **신규** — 단일 점 회전/스케일이 주변 메쉬 변형, Resolution, Bend twist/radius, 드래그 |
| test_registration_recovery.py | 38 | **신규** — B09 잔여 등록·해제 중 예외·등록 중 예외·두 사본 |
| test_self_test.py | 4 | **신규** — 인-블렌더 자가 진단이 데이터를 남기지 않음 |
| test_zip_install.py | 19 | 비활성/재활성 **3회**, 키맵 중복 없음 |
| test_ui_draw.py | 113 | 모든 패널 draw (Mask 툴바 도구 제외로 1 감소) |
| test_stroke_events.py | 68 | 새 사양으로 2개 수정(Alt는 드래그, 3회 클릭 제거) |
| test_cut_geometry.py / test_legacy_features.py | 93 / 26 | Boolean 선택 규칙 새 사양(활성=커터)으로 수정 |
| test_base_mesh / png_shapes / loft / zbrush / workspace / register / performance / v090 | 83/85/22/17/17/11/8/70 | 그대로 통과 |
| tests/chatgpt_v093/* (Primitive) | 26 + 11 + 출력형 | 경로만 바꿔 수동 실행, 통과 |

## 기능별 상태 (docs/04 C: 서로 다른 열)
| 항목 | 코드에 존재 | headless 통과 | Windows GUI 검증 |
|---|---|---|---|
| B09 등록 자가 복구, 두 사본 경고 | O | O (38) | 미검증 |
| B01 Mirror world/local/cursor × XYZ, 다중, 변경/Apply/Remove, Collection | O | O | 미검증 (원인 재현 못 함) |
| B02 Loft | O (변경 없음) | O (기존 22 + 자가 진단) | 미검증 (원인 재현 못 함) |
| B03 Smart Fuse 10회, 상태 복구, 고아 그룹 정리 | O | O | 미검증 |
| 도구 목록 → 툴 전환(3D View 컨텍스트), 고착 시 선택 도구 우선 | O | 일부(판정 로직만, 실제 창 없음) | 미검증 |
| B04 아무 곳 더블클릭(PRESS만 와도) / 시작점 클릭 | O | O | 미검증 (실제 이벤트 순서) |
| B05 Mesh Curve 더블클릭 1회 전환 | O | O | 미검증 |
| B06 PNG R 회전 + 커서 미리보기 | O | O (미리보기 그리기 자체는 GPU라 미검증) | 미검증 |
| B07 Split Gap Enter/시작점/더블클릭 | O | O | 미검증 |
| B08 Mask 숨김, 데이터 보존 | O | O | 미검증 |
| B10 큰 베벨, 제한 메시지, Clamp | O | O | 미검증 |
| ~~Alt 짧은 클릭/드래그, Alt+클릭 복귀~~ (0.11.1에서 삭제) | — | — | — |
| V 빠른 메뉴 / Shift+A | O | 등록만 | 미검증 |
| Boolean 활성=커터 다중 대상 | O | O | 미검증 |
| Cut/Split 다중 대상, 실패 보존 | O | O | 미검증 |
| Base Mesh Bevel Sides / Both 별도 폭 / Alt 커터 / 세션 Auto Apply / 마이그레이션 | O | O | 미검증 |
| Deform 기즈모(Mecha) | O | 수학·드래그 로직 O, 기즈모 표시·클릭 미검증 | 미검증 |
| Deform Blender 기즈모 + Proportional | O | O (`transform.rotate/resize` + proportional로 단일 점 → 주변 변형 확인) | 미검증 |
| Free Draw Stabilizer | O | O (떨림 감소/지연 증가 수치, dt 독립, 지연 원, 종료) | 미검증 (프레임/타이머 체감) |
| 자가 진단 버튼 | O | O | 사용자 실행 필요 |

`GUI_TEST_CHECKLIST_KO.md`의 0.10.0 항목을 Windows Blender 5.0.2에서 확인해 주세요. headless 통과는 GUI 동작 인증이 아닙니다.
