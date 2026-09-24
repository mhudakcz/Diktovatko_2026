# Přidá Diktovátko do automatického spuštění po přihlášení (spusťte znovu s -Remove pro odebrání).
param([switch]$Remove)
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Diktovatko.lnk'
if ($Remove) { Remove-Item $lnk -ErrorAction SilentlyContinue; "Odebráno z autostartu."; return }
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$s.Arguments = '"' + (Join-Path $PSScriptRoot 'diktovatko.py') + '"'
$s.WorkingDirectory = $PSScriptRoot
$s.Save()
"Přidáno do autostartu: $lnk"
