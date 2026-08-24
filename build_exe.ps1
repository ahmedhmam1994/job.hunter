# Builds dist/JobHunter.exe — a standalone Windows desktop app, no Python install needed to run it.
# NOTE: Glassdoor/Indeed scraping uses Playwright's Chromium browser, which is
# NOT bundled into the exe by PyInstaller (it lives outside site-packages).
# Anyone running the built exe on another machine still needs to separately
# run `python -m playwright install chromium` once, or those two sites will
# fail (the app degrades gracefully — other sites keep working).
# Usage: pwsh ./build_exe.ps1

pip install -r requirements.txt
pip install -r requirements-build.txt
python -m playwright install chromium
pyinstaller JobHunter.spec
Write-Host "Built: dist\JobHunter.exe"
