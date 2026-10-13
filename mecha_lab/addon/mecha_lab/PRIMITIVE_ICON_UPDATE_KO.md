# Mecha Lab v0.9.3 — Primitive 메뉴 개별 아이콘

- 기존 v0.9.2 프리미티브 시스템에 박스·원기둥·구·원뿔·캡슐용 128×128 PNG 아이콘 5종 추가
- 각 도형의 썸네일과 이름을 우클릭 Shape Picker에 표시
- 라이브 프리미티브 선택 시 `Change Selected Primitive`와 `Create New Primitive` 메뉴에 동일 아이콘 표시
- Blender 기본 프리뷰 API(`bpy.utils.previews`)로 아이콘을 로딩하고, 실패 시 기존 Blender 아이콘으로 대체
- 형상 계산 및 기존 다른 도구 로직 변경 없음

**테스트:** bpy 5.2.2 아이콘 로드 및 메뉴 draw, 설치/활성화/비활성화. Windows Blender 5.0.2 GUI 시각 검증은 아직 별도 필요.

**설치:** Blender > Edit > Preferences > Get Extensions > 메뉴 > Install from Disk… ZIP 선택. 기존 버전은 비활성화 후 제거 권장.
