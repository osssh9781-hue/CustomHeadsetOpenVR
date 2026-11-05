# Mecha Lab v0.24.103 — Press Shape → Base Mesh Line 단면

## 기본 개념

프레스 컷에서 **Save Shape**로 저장한 스탬프 윤곽을 별도 변환 없이 **Base Mesh Line의 단면**으로 사용합니다. Press Cut의 Alt + 드래그로 실행되는 Base Mesh Line도 같은 단면 설정을 공유합니다.

## 사용 순서

1. **Press Cut**에서 기존 저장 모양을 선택하거나, Shift+드로잉으로 스탬프를 만들고 **Save Shape**로 저장합니다. 저장 대화상자의 `Use It`을 켜면 저장 즉시 프레스 컷의 현재 모양으로 선택됩니다.
2. **Base Mesh → Line Section → Section**을 `Press Cut Shape`로 변경합니다. 표시되는 프레스 컷 썸네일 목록에서 원하는 모양을 선택합니다.
3. 필요에 따라 `Section Width`, 기존 `Height`, `Section Rotation`, `Twist Along Line`, `End Taper`를 조절합니다.
4. **Base Mesh의 Line 모드**를 켜고 경로를 그리면, 선택한 스탬프 윤곽을 단면으로 하는 입체가 생성됩니다. Sketch First가 켜져 있어도 이 단면 모드는 입체를 즉시 생성합니다.
5. **Press Cut 통합 도구에서 Alt + 드래그**해도 같은 단면이 경로를 따라 생성됩니다. 짧은 Alt + 누르기의 기존 Grow Press는 그대로 유지됩니다.
6. 생성 후 Live Base Mesh 오브젝트를 선택하여 슬라이더를 조절할 수 있습니다. 저장 모양을 다른 것으로 교체하려면 프리셋을 선택한 후 `Use Press Shape`를 클릭합니다.

## 설정

- Normal Line: 기존 베이스 메쉬 라인 그대로 사용
- Circle: 원형 단면
- Square: 사각 단면
- Press Cut Shape: 기존 프레스 컷에서 저장/선택한 모양 또는 기본 프리셋

## 기술 노트 / 주의

- 그림 이미지를 매번 새로 벡터화하지 않고 `cut_presets.load_loops()`로 Press Cut의 현재 `shape` 프리셋을 직접 사용합니다.
- 생성 시 윤곽을 오브젝트에 스냅샷으로 보관하므로 프리셋 파일이 나중에 바뀌어도 기존 Live 메쉬 재생성이 가능합니다. 새 프리셋 적용은 버튼을 누릅니다.
- 여러 섬/구멍이 있는 단면을 지원하도록 구성했으나, 단면에 자체 교차가 있거나 경로의 급회전/과도한 Twist가 있으면 겹침과 비정상 면이 발생할 수 있습니다.
- 1,800개 이상의 윤곽 정점은 제한합니다. 너무 복잡한 알파는 단순화 후 저장하세요.
- 저장 프리셋은 사용자 프리셋 위치에 보관되며 ZIP에 개별 사용자 스탬프 데이터를 포함하지 않습니다.
- Python 문법/간단한 경로 로직 및 ZIP 무결성 검사 완료. 실제 Blender GUI에서의 생성/조작 테스트는 수행하지 못했습니다. 먼저 테스트용 씬에서 확인하세요.

## v0.24.104: 프레스 컷 직접 연동

Press Cut에서 **현재 선택된 스탬프**를 별도의 Base Mesh Section 설정 없이 사용합니다.
Press Cut에서 **Alt + 드래그**하면 현재 스탬프(저장 프리셋, 기본 쉐입 또는 이번 세션의 Shift + 드로잉)를 자동으로 단면으로 삼아 스윕합니다.
Alt + 누르고 유지하는 Grow Press는 기존대로 동작합니다.
Base Mesh 툴의 Line Section 메뉴 설정은 바뀌지 않습니다. 생성된 Live 메쉬는 그 시점 단면을 스냅샷으로 저장하여 나중에 선택 스탬프가 바뀌어도 유지합니다.
