Option Explicit

Dim shell, fso, folder, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & folder & "\start_windows.bat" & Chr(34) & " --background"
shell.CurrentDirectory = folder
shell.Run command, 0, False
