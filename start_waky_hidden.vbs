Option Explicit

Dim shell, fso, projectDir, pythonw, mainPy, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = projectDir & "\.venv\Scripts\pythonw.exe"
mainPy = projectDir & "\main.py"

If Not fso.FolderExists(projectDir) Then
    MsgBox "Waky startup failed: project folder not found." & vbCrLf & projectDir, vbCritical, "Waky"
    WScript.Quit 1
End If

If Not fso.FileExists(pythonw) Then
    MsgBox "Waky startup failed: pythonw.exe not found." & vbCrLf & pythonw, vbCritical, "Waky"
    WScript.Quit 1
End If

If Not fso.FileExists(mainPy) Then
    MsgBox "Waky startup failed: main.py not found." & vbCrLf & mainPy, vbCritical, "Waky"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectDir
command = """" & pythonw & """ """ & mainPy & """"

' Window style 0 keeps the launch hidden. False returns immediately.
shell.Run command, 0, False
