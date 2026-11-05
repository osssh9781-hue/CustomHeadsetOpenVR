# Mecha Lab 0.24.97 — Blender 5.3 베타 호환 보완

0.24.96의 Alt 프레스 생성 기능을 포함합니다.

수정 내용:
- Creature Shell 설정 패널의 지오메트리 노드 입력을 5.2/5.3의 RNA API로 표시합니다.
- 자체 패널의 구형 소켓 경로 읽기/쓰기/토글을 새 API로 연결합니다.
- 노드 입력의 초기값과 범위를 그룹 인터페이스에서 읽어 리셋과 슬라이더에 사용합니다.
- 이전 Blender용 지오메트리 노드 입력 경로도 유지합니다.

기존 코드의 조각 브러시 전환/오토마스크 및 핵심 GN 입력에는 이미 새 API 대응이 있습니다.
설치 최대 버전 제한은 없습니다. 최소 버전은 기존 매니페스트와 동일한 4.5입니다.

검증: 전체 Python 문법 검사, 새/구형 API를 모사한 입력·UI 회귀 검사,
Alt 프레스 생성 로직 검사, ZIP 무결성 검사.
제한: Blender 5.3 베타 실행 환경에서 등록, 실제 GPU 표시 및 전체 도구 동작은 검증하지 못했습니다.
따라서 이 파일은 공식 문서에 따른 호환 보완본이며 전체 기능 호환 인증본은 아닙니다.

설치: 이 ZIP으로 업데이트한 뒤 Blender를 재시작하세요.

참고:
https://developer.blender.org/docs/release_notes/5.2/python_api/
https://docs.blender.org/api/5.3/bpy.types.NodesModifier.html
https://developer.blender.org/docs/release_notes/5.1/python_api/
