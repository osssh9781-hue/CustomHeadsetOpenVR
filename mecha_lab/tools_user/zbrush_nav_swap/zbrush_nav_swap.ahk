; Mecha Lab - ZBrush viewport: Shift and Alt swapped, for navigation only.
; Needs AutoHotkey v2 (https://www.autohotkey.com).  Works only while a ZBrush window is in front.
;
;   Shift + drag on the EMPTY canvas  ->  ZBrush gets Alt   (move the view; let go of Shift while dragging = zoom)
;   Alt   + drag on the EMPTY canvas  ->  ZBrush gets Shift (snap the turn to a straight view)
;   the same with the right button, anywhere.
;
; On the model nothing changes: Alt (the brush reversed) and Shift (Smooth) stay as they are.
;
; How it tells the empty canvas from the model: by the colour under the cursor.  Teach it the background once:
;   Ctrl + Alt + B   with the cursor over the empty canvas  = remember this background colour
;                    (the background is a gradient: press it at the top, the middle and the bottom)
;   Ctrl + Alt + N   = forget the colours
; The colours are kept in  %APPDATA%\MechaLab\zbrush_nav_swap.ini
#Requires AutoHotkey v2.0
#SingleInstance Force
CoordMode "Pixel", "Screen"
CoordMode "Mouse", "Screen"
A_MenuMaskKey := "vkE8"          ; (so a lone Alt press does not open a menu)

global INI := A_AppData "\MechaLab\zbrush_nav_swap.ini"
global TOL := 10                 ; how far a channel may be outside the remembered range
global LO := [255, 255, 255], HI := [0, 0, 0], KNOWN := false
LoadColours()

LoadColours() {
    global LO, HI, KNOWN
    s := IniRead(INI, "background", "range", "")
    p := StrSplit(s, ",")
    if p.Length = 6 {
        LO := [Integer(p[1]), Integer(p[2]), Integer(p[3])]
        HI := [Integer(p[4]), Integer(p[5]), Integer(p[6])]
        KNOWN := true
    }
}

Channels(c) {
    return [(c >> 16) & 255, (c >> 8) & 255, c & 255]
}

OverEmpty() {
    if !KNOWN
        return false
    MouseGetPos &x, &y
    ; (a few pixels beside the cursor too: the brush circle / the cursor itself may sit on the exact pixel)
    for d in [[0, 0], [-3, -3], [3, -3], [-3, 3], [3, 3]] {
        ch := Channels(PixelGetColor(x + d[1], y + d[2]))
        ok := true
        loop 3
            if ch[A_Index] < LO[A_Index] - TOL || ch[A_Index] > HI[A_Index] + TOL
                ok := false
        if ok
            return true
    }
    return false
}

#HotIf WinActive("ahk_exe ZBrush.exe")

^!b:: {
    global LO, HI, KNOWN
    MouseGetPos &x, &y
    ch := Channels(PixelGetColor(x, y))
    loop 3 {
        LO[A_Index] := Min(LO[A_Index], ch[A_Index])
        HI[A_Index] := Max(HI[A_Index], ch[A_Index])
    }
    KNOWN := true
    DirCreate A_AppData "\MechaLab"
    IniWrite LO[1] "," LO[2] "," LO[3] "," HI[1] "," HI[2] "," HI[3], INI, "background", "range"
    ToolTip "Background colour remembered (" ch[1] ", " ch[2] ", " ch[3] ")"
    SetTimer () => ToolTip(), -1500
}

^!n:: {
    global LO, HI, KNOWN
    LO := [255, 255, 255], HI := [0, 0, 0], KNOWN := false
    try FileDelete INI
    ToolTip "Background colours forgotten"
    SetTimer () => ToolTip(), -1500
}

+RButton:: SwapNav("Shift", "Alt", "RButton")
!RButton:: SwapNav("Alt", "Shift", "RButton")

#HotIf WinActive("ahk_exe ZBrush.exe") && OverEmpty()

+LButton:: SwapNav("Shift", "Alt", "LButton")
!LButton:: SwapNav("Alt", "Shift", "LButton")

#HotIf

SwapNav(held, sent, button) {
    Send "{Blind}{" held " up}{" sent " down}{" button " down}"
    down := true
    while GetKeyState(button, "P") {
        ; the key let go while dragging (ZBrush: Alt let go = zoom): pass that on
        if down && !GetKeyState(held, "P") {
            Send "{Blind}{" sent " up}"
            down := false
        }
        Sleep 10
    }
    Send "{Blind}{" button " up}" (down ? "{" sent " up}" : "")
    if GetKeyState(held, "P")    ; (still held by hand: give it back, so the next drag works too)
        Send "{Blind}{" held " down}"
}
