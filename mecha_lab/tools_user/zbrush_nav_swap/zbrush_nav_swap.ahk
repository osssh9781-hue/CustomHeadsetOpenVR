; Mecha Lab - ZBrush viewport: Shift and Alt swapped, for navigation only.
; Needs AutoHotkey v2 (https://www.autohotkey.com).  Works only while a ZBrush window is in front.
;
;   Shift + right button drag  ->  ZBrush gets Alt + right button   (move the view)
;   Alt   + right button drag  ->  ZBrush gets Shift + right button (snap the turn to a straight view)
;
; Brushes are left alone: Alt (the brush reversed) and Shift (Smooth) with the left button / the pen tip
; are not touched, and no other program is affected.
#Requires AutoHotkey v2.0
#SingleInstance Force
A_MenuMaskKey := "vkE8"          ; (so a lone Alt press does not open a menu)

#HotIf WinActive("ahk_exe ZBrush.exe")

+RButton:: SwapNav("Shift", "Alt")
!RButton:: SwapNav("Alt", "Shift")

#HotIf

SwapNav(held, sent) {
    Send "{Blind}{" held " up}{" sent " down}{RButton down}"
    KeyWait "RButton"
    Send "{Blind}{RButton up}{" sent " up}"
    if GetKeyState(held, "P")    ; (still held by hand: give it back, so the next drag works too)
        Send "{Blind}{" held " down}"
}
