# Mecha Lab v0.5.8 — PNG → Cut 프리셋

## 한 번만 등록하고 여러 작업에서 재사용

1. Blender `N` → `Mecha Lab` → `01 CUT` 펼치기.
2. `PNG TO VECTOR CUT` 아래 `Import PNG Shape` 클릭.
3. PNG 선택. 검정 배경·흰 문양은 `Foreground: White / Bright`(기본값). 투명 PNG 문양은 `Alpha Channel` 선택.
4. `Threshold`, `Invert`, `Simplify (px)` 조절 후 가져오기.
5. 썸네일 갤러리에서 도형 선택 → `Stamp Selected`.
6. 절단할 메쉬를 **Object Mode에서 선택**한 상태로 마우스를 메쉬 표면에 갖다 대고 클릭해서 절단. 다시 클릭하면 연속 적용.
7. 마우스 휠 = 크기 변경, `R` = 15° 회전, `Q`/`Esc` = 종료.

기존 Mecha Lab의 Auto Apply가 ON이면 직접 메쉬에 적용됩니다. OFF면 원본 수정 가능한 Boolean 커터 오브젝트를 남깁니다.

## 형상의 의미

- `White / Bright`: 흰 부분에 컷을 생성, 검정 부분은 유지. 투명 배경은 무조건 제외.
- `Alpha Channel`: 불투명한 부분이 컷. 흑색 실루엣을 투명 배경에 그려둔 PNG도 사용 가능.
- `Invert`: 선택한 채널의 밝고 어두운 면 반전. 필요할 때만 켜세요.
- **원본 PNG 픽셀로 직접 불린하지 않습니다.** 2D 윤곽선 좌표를 JSON 파일로 저장하고 Blender 곡선 → 닫힌 메쉬 커터로 변환합니다.
- 서로 떨어진 섬 및 내부 구멍이 있는 문양도 지원합니다.

## 프리셋 저장 위치

`Blender 사용자 CONFIG / mecha_lab/cut_shapes/` 디렉터리 안에 `.json`(벡터 윤곽) + `.png`(썸네일)가 저장됩니다. 작업 중인 .blend 파일과 별도로 유지됩니다.

## 정확한 구현 범위와 미구현 사항

- v0.5.8에 추가한 것은 PNG **가져오기, 벡터화, 썸네일 갤러리, 메쉬 표면 스탬프 불린**입니다. 기존 Cut의 직접 드로잉 방식과는 별도의 `Stamp Selected` 입력 도구입니다.
- PNG는 현재 뷰포트 방향의 **평면 프로젝션**으로 찍힙니다. 자유곡면에 UV처럼 감기는 방식이나, 그린 곡선 전체를 자동으로 베지어 핸들로 변환하는 기능은 아닙니다.
- `Edit Shape`, `Overwrite Preset`, Cut 우클릭 팝업으로 사용자 PNG 프리셋 자동 로드 등은 아직 구현하지 않았습니다.
- PNG가 너무 복잡하거나 셀프 인터섹트된 경우, 커터 생성이 거부될 수 있습니다. 해상도·노이즈를 줄이거나 Simplify 값을 높이세요.
- 리메시 / 새 Quad Retopo 알고리즘은 사용하지 않습니다.
- Blender 5.2.2 headless `bpy`에서 임포트·Boolean 메쉬 연산을 검증했습니다. Blender 5.0.2 GUI의 마우스 입력/썸네일 표시/FPS는 아직 검증하지 않았습니다.
