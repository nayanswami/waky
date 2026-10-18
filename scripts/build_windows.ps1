# Builds dist\Waky (PyInstaller) and, when Inno Setup is installed, dist\installer\Waky-Setup-<version>.exe
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

$Version = (Select-String -Path "app\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

& $Python tools\make_icon.py
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $Python -m PyInstaller --noconfirm --distpath dist --workpath build packaging\waky.spec

if (-not (Test-Path "dist\Waky\Waky.exe")) {
    throw "Build failed: dist\Waky\Waky.exe was not created."
}
Write-Host "Built dist\Waky\Waky.exe ($Version)"

$Iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $Candidate = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path $Candidate) { $Iscc = Get-Item $Candidate }
}
if ($Iscc) {
    & $Iscc.Source "/DAppVersion=$Version" packaging\waky.iss
    Write-Host "Installer: dist\installer\Waky-Setup-$Version.exe"
} else {
    Write-Warning "Inno Setup (iscc) not found; skipped installer. Install it from https://jrsoftware.org/isinfo.php"
}
