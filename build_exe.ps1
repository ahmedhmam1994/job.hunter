# Builds dist/JobHunter.exe — a standalone Windows desktop app, no Python install needed to run it.
# Usage: pwsh ./build_exe.ps1

pip install -r requirements.txt
pip install -r requirements-build.txt
pyinstaller JobHunter.spec
Write-Host "Built: dist\JobHunter.exe"
