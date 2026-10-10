' ===========================================================================
'  Kimi quota pet - silent autostart launcher (no console window).
'  Same as the normal launcher, plus a duplicate guard: if the pet is already
'  running (started by hand, or by a second logon), this does nothing.
'  Kept ASCII-only on purpose: wscript.exe reads .vbs as ANSI without a BOM.
' ===========================================================================
Option Explicit

Dim fso, shell, here, script, cmd, running, wmi, procs, proc

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(here, "kimi_pet.ps1")

If Not fso.FileExists(script) Then WScript.Quit 0
If Not fso.FileExists(fso.BuildPath(here, "sprite.png")) Then WScript.Quit 0

' Already running? (best effort - a WMI failure must not block the start)
running = False
On Error Resume Next
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE Name='powershell.exe'")
If Err.Number = 0 Then
    For Each proc In procs
        If Not IsNull(proc.CommandLine) Then
            If InStr(LCase(proc.CommandLine), LCase(script)) > 0 Then running = True
        End If
    Next
End If
Err.Clear
On Error GoTo 0

If running Then WScript.Quit 0

shell.CurrentDirectory = here
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """"
shell.Run cmd, 0, False
