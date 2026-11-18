"""0.24.233 How to use each tool, in Korean and English (user: "사용법들을 정리를 한 번 해야겠는데 … 지금처럼 툴 설명
펼치게 해서, 이 용어는 영어로 해도 돼" / "검색도 할 수 있게 해 줄래?").  Shown in the key legend card at the bottom
left (its title opens it) and searched by Ctrl+Shift+F (the card's "Search" too).

One entry per tool: what (one line) / how (the steps) / keys (the tool's own keys) / settings (the ones that matter,
with what they do) / tips.  Every text is (Korean, English); tool and setting names stay English in both.
A key or setting named here is checked against the add-on by tests/test_v02633_usage_docs.py.
"""
from __future__ import annotations

HEADS = {'what': ('무엇', 'What'), 'how': ('사용', 'How'), 'keys': ('키', 'Keys'), 'opts': ('설정', 'Settings'),
         'tips': ('팁', 'Tips')}
ORDER = ('what', 'how', 'keys', 'opts', 'tips')

COMMON = [
    ('Shift', '직선 0/45/90° · 정사각형 / 정원', 'straight 0/45/90° · square / circle'),
    ('Ctrl', '가운데부터 그리기', 'draw from the centre'),
    ('F  [ ]', '브러시 크기 · 선 굵기', 'brush size · line width'),
    ('RMB', '도구 휠 (다른 메뉴를 누르면 닫힘)', 'Tool Wheel (closes when you click another menu)'),
    ('Q', '선택 <-> 마지막 도구', 'Select <-> the last tool'),
    ('Ctrl+Z', '한 단계 되돌리기', 'one step back'),
]

DOCS = {
    'CUT': dict(
        what=('그린 모양만큼 파트를 파낸다', 'Removes the inside of the shape you draw from a part'),
        how=[('위 라쏘 바의 모양에서 라쏘 · 사각형 · 원 … 을 고른다', 'Pick a Shape in the Lasso bar (lasso, rectangle, circle ...)'),
             ('파트 위에 그리고 놓으면 잘린다', 'Draw over a part and let go: it is cut'),
             ('스케치: 여러 획을 그린 뒤 Enter', 'Sketch: several strokes, then Enter')],
        keys=[('Alt', '안쪽만 남김 (라인: 클릭한 쪽 남김)', 'keep the inside (Line: keep the clicked side)'),
              ('T', '대상 자동 <-> 선택됨', 'Target Auto <-> Selected')],
        opts=[('Depth', '전체 관통: 끝까지 · 표면에서: 표면부터 깊이 만큼만', 'Through All / From Surface, Depth deep'),
              ('Targets', '자동: 마우스 아래 파트 · 선택됨: 선택한 것 모두 · 활성: 활성 파트만', 'Auto under the mouse · Selected · Active'),
              ('GN Edge', '잘린 테두리를 챔퍼 / 베벨로 (나중에도 바꿀 수 있음)', 'Chamfer / Bevel the cut rim (live)'),
              ('Auto Apply', '끄면 커터가 살아 있어 고칠 수 있음 - 실시간 컷 적용으로 확정', 'off: the cutter stays live - Apply Live Cut')],
        tips=[('해상도가 낮으면 둥근 모양이 각져 보임', 'A low Resolution makes round shapes faceted')]),
    'SPLIT': dict(
        what=('그린 모양으로 파트를 두 덩어리로 나눈다 (둘 다 닫힌 솔리드)', 'Splits a part in two along the shape you draw (both solid)'),
        how=[('파트 위에 모양을 그리고 놓는다', 'Draw a shape over a part and let go'),
             ('안쪽과 바깥쪽이 각각 따로 파트가 됨', 'The inside and the outside become parts of their own')],
        keys=[('T', '대상 자동 <-> 선택됨', 'Target Auto <-> Selected')],
        opts=[('Split Mode', '간격: 두 파트 사이에 간격 폭만큼 틈 (자동 적용을 켜야 함)',
               'Gap: a gap of Gap Width between the parts (needs Auto Apply)'),
              ('Side A / B', '각 쪽 테두리를 챔퍼 / 베벨로, ⇄ 교체로 두 쪽을 바꿈', 'each side\'s rim Chamfer / Bevel, ⇄ Swap')],
        tips=[('나눈 뒤 레이어 창에서 각 파트를 숨기거나 옮길 수 있음', 'Hide or move each part from the Layers panel')]),
    'BASE': dict(
        what=('그린 외곽선으로 새 솔리드 파트를 만든다', 'Draws a new solid part from the outline you draw'),
        how=[('빈 곳이나 파트 위에 외곽선을 그린다', 'Draw an outline, on empty space or on a part'),
             ('놓으면 새 파트 (스케치: 여러 획 → Enter)', 'Let go: a new part (Sketch: strokes, then Enter)'),
             ('만든 뒤 엣지 · 높이를 바꾸면 바로 따라 바뀜', 'Change Edge / Height afterwards: it follows')],
        keys=[('Alt', '스케치에서 빼기 / 메쉬에 파기', 'subtract from the sketch / cut into the mesh'),
              ('Enter', '스케치로 만들기 (Alt+Enter: 파 넣기)', 'make the sketch (Alt+Enter: cut it in)')],
        opts=[('Edge', '평평하게 · 챔퍼 · 베벨 - 위 / 아래 테두리', 'Flat · Chamfer · Bevel - the top / bottom rim'),
              ('Sides', '위 · 아래 · 양쪽 · 꺼짐, 동일을 끄면 위아래 폭을 따로', 'Top · Bottom · Both · Off; Same off: each its own'),
              ('Stick to Surface', '파트 위에 그리면 그 표면에 붙음', 'drawn on a part: it sits on that surface')],
        tips=[('위 바의 폭 칸은 끌면 섬세하게 움직임 (Shift 더 섬세)', 'The Width cells drag finely (Shift: finer)')]),
    'PLATE': dict(
        what=('파트 위에 라쏘로 그린 자리에 깨끗한 면의 장갑판을 따로 만든다', 'A separate armour plate of clean faces where you draw on a part'),
        how=[('파트 위에 라쏘를 그린다', 'Draw a lasso on a part'),
             ('그리는 동안 마우스 휠로 단면을 바꾼다', 'Mouse wheel while drawing: the profile'),
             ('놓으면 새 판 파트 (원래 메쉬는 그대로)', 'Let go: a new plate part (the mesh stays as it was)')],
        keys=[('Alt', '판을 파 넣기', 'carve the plate in'),
              ('Wheel', '그리는 중 단면 바꾸기', 'the profile, while drawing')],
        opts=[('Profile', '평평한 플레이트 · 챔퍼 45 · 중갑 … 단면 프리셋', 'Flat Plate · Chamfer 45 · Heavy Armor ... section presets'),
              ('Thickness', '판 두께', 'the plate\'s thickness')],
        tips=[('리토폴로지 없이 바로 깨끗한 면', 'Clean faces with no retopology')]),
    'PRESS': dict(
        what=('저장한 모양을 도장처럼 눌러 솟게 하거나 파 넣는다', 'Presses a saved shape like a stamp: it grows out or is cut in'),
        how=[('위 바의 스탬프 칸을 눌러 모양을 고른다 (고르면 닫힘)', 'Pick the stamp in the top bar\'s stamp cell (a pick closes it)'),
             ('파트 위에서 누르고 있으면 오래 누를수록 높이 솟음, 놓으면 확정', 'Hold LMB on a part: it grows taller the longer you hold; let go keeps it'),
             ('끌면 그 모양이 단면인 선 (Base Mesh 선)', 'Drag: a line with the stamp as its section')],
        keys=[('Alt + 누름', '파 넣기 - 오래 누를수록 깊게', 'press it in (a cut) - deeper the longer'),
              ('Esc / RMB (누르는 중)', '되돌리기', 'put it back'),
              ('F  [ ]', '스탬프 크기', 'stamp size'),
              ('R + 마우스', '돌리기 (Shift 섬세, Ctrl 5°), Shift+R 0°', 'turn (Shift fine, Ctrl 5°), Shift+R 0°'),
              ('Shift + 그리기', '내 스탬프 만들기', 'your own stamp')],
        opts=[('Plate', '아머 / 크리쳐 - 스탬프 모양 판으로', 'Armor / Creature - the stamp as a plate'),
              ('Save Shape', '방금 그린 라쏘를 스탬프로 저장', 'keep the lasso you drew as a stamp')],
        tips=[('선의 끝 표시에서 다시 끌면 이어서 그림', 'Start a drag on a line\'s end mark: it goes on from there')]),
    'CDRAPE': dict(
        what=('파트 위에 천을 덮어 실제 천처럼 주름지며 떨어지게 한다', 'Lays a cloth over a part that falls and folds like real cloth'),
        how=[('라쏘로 덮을 자리를 그린다 (또는 마스크를 칠한 뒤 드레이프 마스크)', 'Draw a lasso where it goes (or paint a Mask, then Drape Mask)'),
             ('Space 로 떨어뜨리고 / 멈추고, Enter 로 확정', 'Space drapes / pauses, Enter keeps it'),
             ('이 메쉬 드레이프 / 이 메쉬 감싸기: 고른 메쉬를 천으로', 'Drape This Mesh / Wrap This Mesh: a mesh you pick as the cloth')],
        keys=[('Space', '떨어뜨리기 / 멈추기', 'drape / pause'), ('Enter', '천 확정', 'keep the cloth'),
              ('Esc', '천 버리기', 'drop it')],
        opts=[('Fabric', '면 · 데님 · 실크 · 가죽 · 니트', 'Cotton · Denim · Silk · Leather · Knit'),
              ('Looseness', '클수록 헐렁 - 주름이 많음', 'higher: looser, more folds'),
              ('Cloth Detail', '작을수록 촘촘 - 잔주름 (느려짐). 드레이프 마스크는 점 개수', 'less = finer: small wrinkles (slower). Drape Mask: Points'),
              ('Pins & Stitches', '천을 몸에 고정 · 박음질 선으로 모으기', 'pin it to the body · gather it along stitch lines')],
        tips=[('뒷면까지 감싼 마스크도 사각 격자로 고르게 주름짐', 'A mask round the body is a grid of quads too: even folds')]),
    'BBEVEL': dict(
        what=('파트의 모서리를 따라 끌어 그만큼 챔퍼 / 둥글게 깎는다', 'Drag along an edge of a part: that much is chamfered / rounded'),
        how=[('파트에 마우스를 올리면 쓸 수 있는 모서리가 파랗게 보임', 'Hover a part: the edges you can use show blue'),
             ('모서리를 따라 끌면 끈 만큼, 클릭하면 모서리 전체', 'Drag along an edge: that much; click: the whole edge')],
        keys=[('Shift + 클릭', '면을 한 바퀴 도는 모서리 루프 전체', 'the whole edge loop round the face'),
              ('Alt + 클릭', '깎은 것 떼기 (컷 방식에서만)', 'take a cut off (Cut method only)'),
              ('T', '대상 자동 <-> 선택됨', 'Target Auto <-> Selected')],
        opts=[('Method', '점 옮기기: 메쉬 점만 옮김 (조밀한 메쉬, 빠름) · 컷: 불린으로 깎음',
               'Move Points: the mesh\'s own points move (dense meshes, fast) / Cut: a boolean'),
              ('Profile', '챔퍼: 평평하게 · 둥글게: 둥글게', 'Chamfer flat / Round'),
              ('Width', '깎는 폭', 'how wide')],
        tips=[('점이 적은 메쉬는 점 옮기기로 옮길 점이 없음 - 컷을 쓰기', 'A sparse mesh has no points to move: use Cut')]),
    'SUBD': dict(
        what=('서브디비전 판을 오브젝트 모드에서 바로 점 · 모서리로 다듬는다', 'A subdivided plate shaped by its points and edges, right in Object Mode'),
        how=[('서브디 플레인 만들기로 3D 커서에 판을 만든다', 'Create SubD Plane: a plate at the 3D cursor'),
             ('점을 끌어 옮기고, 바깥 모서리를 끌어 새 면을 뽑는다', 'Drag points to move them, drag an outline edge to pull a new face out'),
             ('다 되면 전체 적용으로 모디파이어를 굽는다', 'Apply All bakes the modifiers when done')],
        keys=[('점 끌기', '점 이동 - 다른 점 가까이 놓으면 붙어서 합쳐짐', 'move it - let go near another point: they join'),
              ('모서리 끌기', '바깥 모서리면 새 면이 나옴', 'an outline edge: a new face comes out'),
              ('Shift + 끌기', '모서리 이동 (새 면 없이)', 'move the edge (no new face)'),
              ('Alt + 클릭', '점 지우기', 'remove a point'),
              ('Ctrl + 클릭', '모서리 크리스 켜기 / 끄기', 'crease an edge on / off'),
              ('Ctrl (끄는 중)', '붙지 않게', 'no snapping')],
        opts=[('Simple / Catmull-Clark', '두 서브디비전 단계 - 단순은 조밀하게, 카트멀-클락은 둥글게', 'two levels - Simple densifies, CC rounds'),
              ('Thickness / Offset', '두께와 두께 방향', 'thickness and which way'),
              ('Crease', 'Ctrl + 클릭한 모서리를 얼마나 날카롭게', 'how sharp a creased edge is')],
        tips=[('같은 사각형의 대각선 점끼리 붙이면 그 면은 없어짐', 'Joining the diagonal corners of one quad removes that face')]),
    'SMART': dict(
        what=('파트를 손으로 들어 다른 표면에 놓는다 (회전 · 크기 그대로)', 'Places a part by hand on another surface (rotation and size unchanged)'),
        how=[('파트를 클릭해 든다 (원점에 고리 표시)', 'Click a part to hold it (a ring on its origin)'),
             ('표면을 클릭하면 원점이 그 자리로', 'Click a surface: its origin goes there'),
             ('3D 마우스로 원점 둘레로 돌리기', 'The 3D mouse turns it about its origin')],
        keys=[('Enter / Space / RMB', '확정 (한 번에 되돌릴 수 있음)', 'keep it (one undo step)'),
              ('Esc', '제자리로', 'put it back'),
              ('S (드는 중)', '스마트 크기 - 3D 마우스로 크기', 'Smart Size - the 3D mouse scales it')],
        opts=[('Lift', '표면에서 띄우는 높이', 'how far off the surface'),
              ('Turn Axes', 'Blender · 턴테이블 · 보기 · 월드, 속도, 반전', 'Blender · Turntable · View · World, Speed, Invert'),
              ('Push', '꺼짐 · 노멀 · 자유 - 3D 마우스로 밀기', 'Off · Normal · Free - push with the 3D mouse')],
        tips=[('E 키: 어느 도구에서나 마우스 아래 파트를 스마트 이동', 'E: Smart Move the part under the mouse, in any tool')]),
    'PRIMITIVE': dict(
        what=('고스트 도형을 놓고 메쉬에 더하거나 뺀다', 'Places a ghost shape, then adds it to or carves it from a mesh'),
        how=[('창에서 도형을 고르면 고스트가 나타남', 'Pick a shape in the window: a ghost shows'),
             ('메쉬를 클릭하면 고스트가 그 표면으로', 'Click a mesh: the ghost goes onto that surface'),
             ('손잡이로 크기 · 회전을 맞춘 뒤 Enter', 'Size / turn it with its handles, then Enter')],
        keys=[('Enter', '닿은 메쉬에 합치기', 'merge into the mesh it touches'),
              ('Alt+Enter', '닿은 메쉬에서 빼기', 'carve it out of the mesh it touches')],
        opts=[('Station Primitive', '갑옷 부위 도형 프리셋 (Helmet · Torso …)', 'armour part presets (Helmet · Torso ...)'),
              ('Show Ghost', '고스트 보이기 / 숨기기', 'the ghost shown / hidden'),
              ('Live Parametric Primitives', '나중에도 고칠 수 있는 도형', 'shapes you can change later')],
        tips=[('메쉬와 겹친 면은 미리 표시됨', 'Faces that touch a mesh are shown in advance')]),
}


import re

_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+'&]*(?:[ -][A-Za-z0-9+'&]+)*")


def ko_terms(text):
    """0.24.233 the English names inside a Korean line said as the Korean screen says them (Through All -> 전체 관통),
    so the card and the window use the same words; a name the table does not know stays English."""
    from . import i18n

    def one(m):
        w = m.group(0)
        t = i18n.tr(w)
        if t != w:
            return t
        parts = w.split(' ')                       # (a longer run: each known word on its own is not changed -
        return w                                   #  "Draw Stitches" stays whole or English)
    return _TERM.sub(one, text)


def lang_index():
    from . import i18n
    return 0 if i18n.lang() == 'KO' else 1


def card_rows(tool_id, name):
    """The key legend card's rows for ``tool_id`` (None when there is no entry): [(kind, key, text)] with kind
    'title' / 'head' / 'kv' / 'text'."""
    d = DOCS.get(tool_id)
    if d is None:
        return None
    li = lang_index()
    out = [('title', '', name.upper())]
    for part in ORDER:
        v = d.get(part)
        if not v:
            continue
        out.append(('head', '', HEADS[part][li]))
        say = (lambda t: t)
        if part == 'what':
            out.append(('text', '', say(v[li])))
        elif part in ('how', 'tips'):
            for n, line in enumerate(v):
                out.append(('kv', f'{n + 1}' if part == 'how' else '·', say(line[li])))
        else:
            for key, ko, en in v:
                out.append(('kv', key, say((ko, en)[li])))
    out.append(('head', '', ('공통', 'All tools')[li]))
    for key, ko, en in COMMON:
        out.append(('kv', key, (ko, en)[li]))
    return out


def search_entries(tools):
    """[(identifier, shown text)] for the search: every line of every tool (both languages), and every tool's name
    and description.  ``tools``: tool_state.TOOLS."""
    out = []
    for t in tools:
        tid, name, desc = t[0], t[1], t[2]
        out.append((f'{tid}|0', f'{name}  -  {desc[:90]}'))
        d = DOCS.get(tid)
        if d is None:
            continue
        n = 1
        for part in ORDER:
            v = d.get(part)
            if not v:
                continue
            lines = [v] if part == 'what' else v
            for line in lines:
                if len(line) == 3:
                    texts = [f'{line[0]}  {line[1]}', f'{line[0]}  {line[2]}']
                else:
                    texts = list(line)
                for tx in texts:
                    out.append((f'{tid}|{n}', f'{name}  -  {tx}'))
                    n += 1
    return out
