GoZ 한 번에 설치 (ZBrush 의 GoZ 목록에 Blender 넣기)
=====================================================

쓰는 법:
  1. ZBrush 를 한 번 켰다가 끔 (GoZ 공용 폴더가 생기도록. 이미 써 왔으면 건너뜀).
  2. goz_setup.bat 을 더블클릭.
     - ZBrush 의 GoZ 폴더(C:\Users\Public\Pixologic 또는 Maxon)와 Blender 를 알아서 찾음.
     - Blender 가 여러 개면 Program Files\Blender Foundation 안에서 이름 순서로 마지막 것(보통 가장 새 버전)을 씀.
       다른 Blender 를 쓰려면 blender.exe 를 goz_setup.bat 위로 끌어다 놓기.
  3. ZBrush 를 다시 켜고 Preferences > GoZ 에서 Blender 를 고름.
  4. Blender 의 Mecha Lab > ZBrush 브릿지 > GoZ 칸에서 Send (GoZ) / Import (GoZ) / Auto.

이 파일이 하는 일:
  GoZApps\Blender 폴더에 글 파일 두 개(GoZ_Info.txt, GoZ_Config.txt)를 씀. 그 밖에는 아무것도 바꾸지 않음.
  (Blender 안의 "Set Up GoZ for Blender" 버튼과 같은 일.)
  GoZ 폴더가 없으면 ZBrush 에 들어 있는 GoZ 설치 프로그램을 대신 띄워 줌 - 끝난 뒤 이 파일을 다시 실행.

되돌리기:
  GoZApps\Blender 폴더를 지우면 됨.

알아 둘 것:
  Windows 와 ZBrush 가 없는 곳에서 만든 파일이라 실제로 실행해 보지 못함.
