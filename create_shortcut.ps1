$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "Email AI Agent.lnk"
$ProjectDir = $PSScriptRoot
$ExePath = Join-Path $ProjectDir "dist\Email_AI_Agent\Email_AI_Agent.exe"
$BatPath = Join-Path $ProjectDir "Lancer_Application_Desktop.bat"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
if (Test-Path $ExePath) {
    $Shortcut.TargetPath = $ExePath
    $Shortcut.WorkingDirectory = Split-Path $ExePath
} else {
    $Shortcut.TargetPath = $BatPath
    $Shortcut.WorkingDirectory = $ProjectDir
}
$Shortcut.Description = "Email AI Agent v2.0 - Poste de Pilotage Intelligent & Anti-Spam"
$Shortcut.IconLocation = "shell32.dll,156"
$Shortcut.Save()

Write-Host "Raccourci Bureau créé avec succès : $ShortcutPath"
