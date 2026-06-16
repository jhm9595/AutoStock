$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\AutoStock.lnk")
$Shortcut.TargetPath = "C:\secjob\AutoStock\run.bat"
$Shortcut.WorkingDirectory = "C:\secjob\AutoStock"
$Shortcut.Save()
Write-Host "Desktop shortcut created successfully at: $DesktopPath\AutoStock.lnk"
