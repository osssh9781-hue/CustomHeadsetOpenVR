# Retired tests

Tests of features taken out of the add-on's UI. They are kept for reference and are **not** run by `run_all.py`
(it only collects `tests/test_*.py`).

- 0.24.137 (user: "HDRI 는 다른 애드온 쓸 거라 배경만 내가 원하는 색으로 바꿀 수 있게 해 주라, 너가 만든 게 너무 무거워"):
  the Mecha HDRI library page (HDRI list, preview pictures, folders, picture backgrounds) left the Render page.
  `test_v02495_hdri_backdrop.py`, `test_v02495_hdri_bg.py`, `test_v02495_hdri_heavy.py`,
  `test_v02495_hdri_previews.py`, `test_v02495_scifi_hdri.py` tested that page. The code behind it stays in the
  add-on (a scene still using a Mecha HDRI world can be switched back with "Mecha HDRI Off" on the Render page).
