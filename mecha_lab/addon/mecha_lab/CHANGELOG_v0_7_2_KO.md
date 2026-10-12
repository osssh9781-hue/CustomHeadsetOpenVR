# Mecha Lab v0.7.2 beta — 마스크 작동 개선 · 베벨 진단

## 수정한 내용
- 기존 **Mask 도형 페인팅이 큰 폴리곤의 중심점 밖에서는 0개 면만 선택**하던 버그 수정. 실제 드로잉 영역에 포함된 화면 좌표에서 메쉬 면을 레이캐스팅해 인식.
- **Mask의 Brush Stroke**는 열린 획을 원형 브러시 반경(`Mask Brush Radius`)으로 처리. 기존에는 획의 시작과 끝을 이어 닫힌 도형으로 인식했습니다.
- **Edge Finish**가 실제 적용된 새 절단 엣지 수를 완료 알림에 표시. 도형 컷과 직선(Plane) 컷 양쪽에 적용.
- `Auto Apply`가 OFF일 때 Live Cut에서 Edge Finish가 실행되지 않는 상태를 완료 알림에 명시.
- 이미 선택한 마스크 미리보기 메쉬를 뷰포트 레이캐스트가 실제 컷 대상처럼 집어내는 문제 예방.

## 중요한 한계
- **마스크는 아직 FACE(폴리곤 면) 단위**입니다. 저폴리곤 표면의 일부를 칠해도 그 폴리곤 전체가 마스크됩니다. 원하는 정확한 윤곽으로 Extract하려면 먼저 메쉬를 적절히 분할해야 합니다. 픽셀 수준 마스크나 웨이트 그라데이션이 아닙니다.
- **마스크가 Cut·Boolean으로부터 보호해주는 기능은 여전히 없습니다.** Pose와 Weight Extract 역시 아직 없습니다.
- **Live Cut에서는 Edge Finish가 적용되지 않습니다.** 새 엣지에 베벨을 적용하려면 `Auto Apply = ON`으로 컷해야 합니다. 이미 생성된 라이브 커터에 대해서는 별도 사후 적용 구현이 필요합니다.
- 작은 구멍이나 근접 엣지에서는 Blender의 `clamp_overlap`이 베벨 폭을 제한하므로 기대보다 얇아 보일 수 있습니다.
- v0.7.2는 Linux headless **Blender bpy 5.2.2**에서 검증했으며 Windows Blender 5.0.2의 GUI 이벤트·화면 렌더링은 검증하지 않았습니다.

## 기본 확인 결과
- 기존 v0.7.1: 큐브 큰 면 구석(면 중심 밖) 마스크 0개 → v0.7.2: 1개 면 마스크.
- 마스크 지우기, 열린 스트로크, 고밀도 큐브 9개 면 마스크, Extract & Raise(솔리디파이) 성공.
- 도형 컷 베벨 8개 엣지, 직선 컷 베벨 4개 엣지 확인.
- Live Cut에서 베벨이 생략된 이유를 완료 메시지에 표시.

## 설치
1. Blender → `Edit > Preferences > Get Extensions` → `Install from Disk`.
2. 기존 0.7.1을 비활성화·제거한 뒤 `mecha_lab-0.7.2_mask_bevel_beta.zip`을 **압축 풀지 않고 설치**.
3. `MECHA LAB` 작업공간 → Mask 선택 → Shape 팔레트의 Rectangle 또는 Brush Stroke 선택 → 기존 메쉬에 드로잉.
4. 오른쪽 Mask 설정에서 마스크 두께를 조절하고 `EXTRACT & RAISE` 실행.
5. 베벨은 Cut 설정에서 `Auto Apply ON` 및 `Edge Finish: Bevel`을 선택한 상태로 테스트.
