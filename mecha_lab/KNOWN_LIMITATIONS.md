# KNOWN LIMITATIONS — Mecha Lab 0.7.0

## A. 검증되지 않은 것 (가장 중요)
1. **Windows 11 + Blender 5.0.2 GUI에서 실행된 적이 없습니다.** 테스트는 Linux headless `bpy 5.0.1`뿐입니다.
   headless에는 창·영역·실제 이벤트가 없으므로 아래는 전부 **NOT TESTED**:
   - `MECHA LAB` Workspace 생성(`workspace.duplicate`), 지연 실행되는 왼쪽 영역 분할(`screen.area_split`), 기본 도구 지정.
   - 왼쪽 Properties(Tool 탭) 영역에 `MCH_PT_tool_list`가 실제로 그려지는지. 설계 근거: Blender 5.0 소스의
     `properties_workspace.py`에 "VIEW_3D/UI/Tool 카테고리 패널은 Properties Tool 탭에도 표시된다"는 주석. 안 보이면
     Sidebar `Tools (fallback list)`, Space 팝업, T 툴바(Cut/Split/Mask)로 대체 가능.
   - Tool Header 팔레트 표시(`VIEW3D_HT_tool_header.prepend`), 버튼 클릭.
   - 실제 마우스/키 이벤트 순서, 더블클릭 판정, RMB 팝업 위치/타이밍, `wm.call_panel` 팝업 크기.
   - WorkSpaceTool 키맵이 Object Mode의 RMB 컨텍스트 메뉴/LMB 선택보다 우선하는지(Blender 설계상 우선해야 함).
   - Space가 다른 애드온/사용자 키맵과 충돌하는지.
   - 실제 GUI 성능(드로잉 지연). 오버레이는 Boolean을 실행하지 않지만 측정은 안 함.
2. 위 항목은 `GUI_TEST_CHECKLIST_KO.md`로 사용자 확인이 필요합니다. 결과(특히 System Console 오류)를 알려주세요.

## B. 알려진 제한 (구현됐지만 범위가 좁음)
- **우클릭 선택(Right-Click Select) 키맵** 사용자는 Mecha 도구 활성 중 RMB가 선택 대신 Shape 팝업/종료로 동작합니다.
- **Mecha 도구 3개(Cut/Split/Mask)는 모든 Workspace의 Object Mode T툴바에 나타납니다** (Blender 도구 등록이 전역).
  단축키는 MECHA LAB 탭 전용이지만 아이콘 자체는 다른 탭 툴바에도 보입니다.
- Object Mode 전용. Edit Mode에서 Cut 도구는 동작하지 않습니다(v0.5.9 C키 Edit Mode 진입 기능 없음).
- 컷은 **뷰 방향 투영**입니다. 곡면을 따라 감기는(geodesic) 컷이 아닙니다. `From Surface` 깊이는 커서 아래 한 점 기준
  평면이므로 경사면에서는 깊이가 일정하지 않습니다.
- Curve Lasso 핸들은 **좌우 대칭 라운드**입니다. 좌우 독립 Bezier 핸들, 첫 점 라운드(첫 점 클릭은 닫기)는 미구현.
- Brush Stroke는 "자유곡선 닫힌 외곽선"입니다. 폭을 가진 브러시 띠(홈 파기)는 아닙니다.
- Live 모드(Auto Apply OFF)에서는 Edge Finish가 적용되지 않습니다. Live 커터는 단순 메쉬(편집 모드로 수정)이며
  v0.5.9의 편집 가능한 베지어 경로+GN 커터는 새 Cut에서 만들지 않습니다(옛 파일의 경로 커터는 `Apply Live Cut`으로 적용 가능).
- 셰이프 키가 있는 메쉬, 라이브러리 링크 메쉬, 뷰포트 비활성 메쉬는 Cut을 거부합니다(메시지 표시, 무변경).
- 컷이 메쉬 일부만 지나가도 Edge Finish 폭이 너무 크면 bevel clamp로 폭이 줄어듭니다.
- Boolean 도구(`mch.boolean`)에 사용자가 고른 커터는 cutter 속성이 없어 Edge Finish 대상이 아닙니다(Cut/Split 전용).
- Smart Fuse: 서로 실제로 겹치는 닫힌 메쉬만 지원. seam이 없으면 거부합니다. 복잡한 교차에서 fillet 품질/겹침은 Blender
  Bevel 모디파이어 한계를 그대로 가짐. 사용자 환경의 원래 오류는 아이콘 크래시로 추정(확정은 사용자 로그 필요).
- PNG 벡터화: 512px로 축소 후 픽셀 윤곽 기반(Chaikin+RDP). 진짜 베지어 피팅/편집은 아님. 98장 컨택트시트는 개별
  원본이 아니므로 기본 프리셋을 포함하지 않았습니다.
- Mask는 **면 단위**이며 Cut/Boolean을 **보호하지 않습니다**. Split/Extract는 v0.5.9 수준(Extract & Raise만).

## C. 미구현 (P1/P2 백로그)
- Mask: 정확 윤곽 마스크, Protect(컷 차단), Mask→Cut/Split, Weight Paint 연동, blur/falloff.
- Pose: Rigid / Soft Pose 전체(현재 패널에 "NOT IMPLEMENTED" 표시, Sculpt Move 버튼만).
- FBX / Asset Browser 오브젝트를 커터로 불러오기.
- 사용자 지정 단축키 전용 UI (현재는 Preferences > Keymap에서 "mch." 수정 가능).
- Radial Array 개별 복제 방향 문제(docs/03 #8) — 이번에 손대지 않음.
- Panel/Curve 도구가 공통 Shape 팔레트를 쓰는 것 — 현재는 v0.5.9의 별도 그리기 연산자 그대로.
- Workspace 템플릿 `.blend` 파일 — GUI 없이 만들 수 없어 생략(버튼으로 생성).

## D. 재현했지만 원인 확정 못한 것
- 스크린샷 01의 "Boolean result is non-manifold" 메시지: 깨끗한 큐브/구/원기둥에서는 v0.5.9도 결과 비매니폴드가 재현되지
  않았고, **대각선 접촉 픽셀에서 커터 자체가 비매니폴드**가 되는 것만 재현했습니다. 사용자의 메쉬가 이전 컷으로 이미 열려
  있었을 가능성도 있습니다. 0.7.0은 결과를 검증하고 실패 시 원본을 바꾸지 않습니다.
