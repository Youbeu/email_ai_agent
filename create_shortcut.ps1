$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "Email AI Agent.lnk"
$TargetPath = "C:\Users\LENOVO\Documents\github\email_ai_agent\Lancer_Application_Desktop.bat"
$WorkingDir = "C:\Users\LENOVO\Documents\github\email_ai_agent"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "Email AI Agent - Tri, Brouillons et Anti-Spam Local"
$Shortcut.IconLocation = "shell32.dll,156"  # Icône d'enveloppe/messagerie officielle Windows
$Shortcut.Save()

Write-Host "Raccourci Bureau créé avec succès : $ShortcutPath"
