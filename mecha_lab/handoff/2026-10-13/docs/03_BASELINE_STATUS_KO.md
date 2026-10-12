# 소스 기준 및 기존 수정 상태

- 최신 소스: v0.7.2 beta (ChatGPT가 Claude Code v0.7.0을 수정). 이 ZIP에서 작업 시작.
- v0.7.1: 트리플 좌클릭 선택 복귀 + Ortho Lock 기능 추가. bpy 5.2.2 일부 검증, 실제 GUI 미확인.
- v0.7.2: 마스크 폴리곤 중심점만 검출하던 문제 개선(뷰 raycast), 열린 Mask Brush Stroke, 새 엣지 베벨 수 진단 및 Live Cut 미지원 경고. bpy 5.2.2 일부 검증, 실제 GUI 미확인.
- 현재 문제/한계: Mask Face 단위 선택, 고정밀 윤곽 불가; Mask의 Boolean Protect 및 Weight Extract/Pose 미구현; Live Cut 베벨 미적용; Smart Fuse 닫힌 교차 메쉬 중심으로 제한; Asset FBX cutter 미구현.
- 새 요구의 Esc selection / Lasso 원거리 dblclick / Curve Lasso smooth / Free Drawing press-drag는 **아직 사용자 의도대로 보장되지 않음**, 실제 구현·테스트해야 함.
- Base Mesh profile tool, ZBrush Bridge, Loft/Surface는 새 개발 요청. 구현 완료라고 써서는 안 됨.
- Claude Code v0.7.0 원본의 358 checks는 Claude 보고서 기준이며, ChatGPT v0.7.2의 기능 전체 358개 검증을 의미하지 않음.
- 과거 `reference/OLD_*`의 UI 설명은 최신 사용자 변경 사항이 우선함.
