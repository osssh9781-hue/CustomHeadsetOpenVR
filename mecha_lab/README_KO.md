# Mecha Lab 0.7.0 (MVP) — 설치 · MECHA LAB Workspace · 사용법

> **검증 수준 먼저:** 이 버전은 Linux의 headless Blender **5.0.1** `bpy`에서 등록·기하·이벤트 상태머신·ZIP 설치까지
> 자동 테스트(358개 항목)를 통과했습니다. **Windows 11 + Blender 5.0.2 GUI에서는 아직 한 번도 실행되지 않았습니다.**
> Workspace 생성, 실제 마우스/키 입력, 팝업, 툴헤더 팔레트 표시는 `GUI_TEST_CHECKLIST_KO.md`로 확인이 필요합니다.
> 자세한 구분은 `test_report.md`, 남은 문제는 `KNOWN_LIMITATIONS.md`를 보세요.

버전 번호 0.7.0은 미검증 초안 v0.6.0과 혼동하지 않기 위해 건너뛴 번호입니다. 기준 소스는 배포본 v0.5.9입니다.

## 1. 설치

1. Blender에서 기존 Mecha Lab(0.5.x)을 **비활성화 후 제거**합니다 (Edit > Preferences > Add-ons).
2. Edit > Preferences > Get Extensions > 오른쪽 위 ▾ > **Install from Disk…** → `dist/mecha_lab-0.7.0.zip`.
3. 설치하면 자동 활성화됩니다. 이 단계에서는 **어떤 Workspace도 생성/변경되지 않습니다.**

요구 버전: Blender 4.5 이상(Manifold Boolean solver 사용). 실제 테스트는 5.0.1(headless)만 했습니다.

## 2. MECHA LAB Workspace 만들기 / 열기

다음 중 하나를 누르면 **현재 .blend 파일 안에** `MECHA LAB` 탭이 생기고 그 탭으로 이동합니다.

- 3D 뷰포트 `N` 사이드바 > **Mecha Lab** 탭 > `Open MECHA LAB Workspace`
- 상단 Workspace 탭 위에서 우클릭(또는 탭 메뉴) > `Open MECHA LAB Workspace`
- `F3` 검색 > "Open MECHA LAB Workspace"

동작 방식: 현재 Workspace를 **복제**해 새 탭을 만들고(기존 탭은 그대로), 새 탭의 3D 뷰에서 Toolbar·Tool Header·Sidebar를
켜고, 왼쪽에 좁은 Properties 영역(Tool 탭)을 분할해 큰 아이콘 도구 목록을 넣습니다. 이미 있으면 그 탭으로 이동만 합니다.

- 다른 .blend 파일에서도 쓰려면: 그 파일에서 다시 버튼을 누르거나, 원할 때만 Sidebar > Mecha Lab > `Workspace & Hotkeys` >
  `Save Current Layout as Startup File`(확인 창이 뜸, **Startup File을 덮어씀**). 되돌리기: File > Defaults > Load Factory Settings.
- 레이아웃이 깨졌을 때: `Workspace & Hotkeys` > `Repair MECHA LAB Layout`.
- 탭을 지우려면 탭 우클릭 > Delete. 애드온은 탭이 없어도 정상 동작합니다.

## 3. 화면 구성

```
[Layout] [Modeling] ... [MECHA LAB]
┌ 왼쪽 도구 목록 ┬ 뷰포트 왼쪽 위: 공통 Shape 팔레트 ───────────────┬ 오른쪽 Sidebar ┐
│ Cut            │ [Lasso][Curve Lasso][Rectangle][Circle][Ellipse] │ 현재 도구 1개의 │
│ Split          │ [Brush Stroke] [PNG 썸네일▾][Custom][Import]     │ 설정만 표시     │
│ Boolean        ├─────────────────────────────────────────────────┤ (Depth, Edge    │
│ Smart Fuse     │                3D VIEWPORT                       │  Finish, ...)   │
│ Mirror  ...    │  (T 툴바에도 Mecha Cut / Split / Mask 아이콘)     │                 │
└────────────────┴─────────────────────────────────────────────────┴─────────────────┘
```

- **왼쪽 도구 목록**: 큰 아이콘 + 이름. 같은 목록이 `Space` 팝업, 그리고 Sidebar의 접힌 `Tools (fallback list)` 패널에도 있습니다.
  (왼쪽 영역이 GUI에서 안 보이면 이 두 경로로 모든 도구를 쓸 수 있습니다.)
- **Shape 팔레트**: Cut / Split / Mask가 공유. 그 외 도구(Boolean 등)에서는 회색으로 비활성 + 안내 문구.
- **오른쪽**: 선택한 도구의 설정만. Cut과 Split은 별도 도구입니다.

## 4. Cut / Split 조작

Cut·Split·Mask는 Blender 네이티브 도구(WorkSpaceTool)입니다. 획과 획 사이에는 아무 모달도 돌지 않으므로 메뉴·사이드바·
다른 에디터 클릭, `Ctrl+Z`가 평소 Blender처럼 동작합니다. **컷 1번 = Undo 1단계**입니다.

| 입력 | 동작 |
|---|---|
| LMB (뷰포트) | 현재 Shape로 획 시작. 대상: 활성 메쉬(없으면 커서 아래 메쉬) |
| Lasso / Curve Lasso | 클릭으로 점 추가, `Enter` 또는 더블클릭 또는 첫 점 클릭 = 적용 |
| Lasso 2점 + Enter | 직선 컷: 지울 쪽을 클릭(Alt+클릭 = 그쪽 유지). Split은 바로 양분 |
| Curve Lasso | 찍은 점을 다시 클릭 = 직각→약→중→강→직각 라운드, 점/핸들 드래그 |
| Rectangle / Circle / Ellipse | 드래그 후 놓으면 적용 (Shift 정사각/원, Ctrl 중심에서) |
| Brush Stroke | 드래그로 자유 외곽선, 놓으면 자동으로 닫혀 적용 |
| Custom (PNG) | 클릭 = Stamp Radius 크기로 찍기, 드래그 = 크기 지정 |
| `Alt` | Cut: 안쪽 유지(바깥 제거) / Mask: 지우기 |
| `Shift` | 45° 스냅 |
| `Backspace`, `Ctrl+Z` (획 중) | 마지막 점 취소 · `Ctrl+Shift+Z` 다시 |
| `Ctrl+Z` (획 밖) | 마지막 컷 전체 Undo (Blender 기본) |
| `Esc` | 그리던 획만 취소, 도구 유지 |
| `F` | Lasso를 열린 선(가로지르는 컷)으로 전환 |
| RMB 1번 | Shape / PNG 썸네일 팝업 (더블클릭 간격만큼 기다린 뒤 열림) |
| RMB 더블클릭 | 도구 종료(Select Box로 전환) |
| `Space` | 큰 아이콘 도구 메뉴 (MECHA LAB 탭에서만) |

설정(오른쪽): Depth `Through All` / `From Surface`(+깊이), Targets Active/Selected, Auto Apply(OFF = 편집 가능한 와이어 커터 +
라이브 Boolean, `Apply Live Cut`으로 확정), Split의 Cap, **Edge Finish Off/Bevel/Chamfer — 새로 잘린 엣지에만 적용**,
Advanced(Solver, Hole Tolerant, Shared Mesh 정책, 2점 평면 컷).

공유 메쉬(Alt+D): 기본은 `This Object Only`(이 오브젝트만 단일 사용자로 만들어 자름, 다른 복제본은 그대로).
`All Linked Copies`를 고르면 공유 데이터 자체를 바꿔 모든 복제본이 함께 잘립니다.

## 5. 단축키 범위

- `Space`(도구 메뉴), `B`(Boolean Difference), `C`(Cut 도구)는 **MECHA LAB Workspace 안에서만** 동작합니다.
  다른 탭에서는 Blender 원래 기능(재생/박스 선택/원 선택 등)이 그대로 실행됩니다.
- Preferences > Add-ons > Mecha Lab에서 Space 메뉴, B/C 단축키를 각각 끌 수 있습니다. 키 변경은 Preferences > Keymap에서 "mch." 검색.
- 애드온을 끄면 모든 Mecha 단축키가 제거됩니다(테스트로 확인).

## 6. PNG Custom Cut Shape

`Import PNG`(팔레트 또는 Shape 팝업) → 흰 글자/검정 배경은 `White / Bright`, 투명 PNG는 `Alpha Channel`.
Threshold, Invert, Simplify, Smooth Steps, Remove Specks 조절. 프리셋은 Blender 사용자 설정 폴더
`mecha_lab/cut_shapes/`에 저장되어 모든 .blend에서 보입니다. v0.5.9에서 만든 프리셋은 그대로 읽히며,
겹치는 윤곽이 있으면 저장된 원본 PNG에서 자동으로 다시 벡터화합니다.

## 7. 제거

Preferences > Add-ons > Mecha Lab > Remove. 생성된 MECHA LAB 탭은 .blend 안에 남아 있을 수 있으니 필요하면 탭을 지우세요.
Startup File을 저장하지 않았다면 다른 파일에는 아무 흔적이 남지 않습니다.
