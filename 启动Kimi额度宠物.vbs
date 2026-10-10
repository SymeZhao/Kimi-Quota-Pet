' ===========================================================================
'  Kimi quota pet - silent launcher (no console window).
'  Double-click this file to start the pet.
'  Kept ASCII-only: wscript.exe reads .vbs as ANSI without a BOM.
' ===========================================================================
Option Explicit

Dim fso, shell, here, script, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(here, "kimi_pet.ps1")

If Not fso.FileExists(script) Then
    MsgBox "kimi_pet.ps1 is missing next to this launcher.", 16, "Kimi Quota Pet"
    WScript.Quit 1
End If

If Not fso.FileExists(fso.BuildPath(here, "sprite.png")) Then
    MsgBox "sprite.png is missing next to this launcher.", 48, "Kimi Quota Pet"
    WScript.Quit 1
End If

shell.CurrentDirectory = here
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """"
shell.Run cmd, 0, False
