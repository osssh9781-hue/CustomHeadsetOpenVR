# Mecha Lab v0.24.105 — Blender registration fix

이 버전은 v0.24.104에서 추가했던 기능을 유지하면서, 애드온을 등록할 때 발생하는
`AttributeError: '_RestrictData' object has no attribute 'scenes'`를 수정한 버전입니다.

- Groups 등록 단계에서 `bpy.data.scenes`를 순회하지 않습니다.
- 그룹 자동 소속 기능의 초기 씬 데이터 스냅샷은 등록 후 첫 타이머 실행 시 만들어집니다.
- 클릭/더블클릭 그룹 선택 단축키도 등록 후 키맵이 준비되면 설치합니다.
- 애드온 해제 시 해당 타이머를 해제합니다.

설치: 기존 Mecha Lab을 비활성화/제거하고 Blender를 재시작한 후 이 ZIP을 설치하세요.
알림: 실제 Blender 5.3 베타 GUI 실행은 이 환경에서 검증하지 못했습니다.
