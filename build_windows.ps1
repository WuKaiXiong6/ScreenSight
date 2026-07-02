# 文件路径：build_windows.ps1
# 文件作用：一键构建 ScreenSight Windows 单目录发行包（PowerShell 版）
# 最后更新时间：2026-06-29-0115
#
# 前置条件：已安装 Python 3.10+ 与 Node 18+；并已在 backend/frontend 安装依赖
#   pip install -e backend[windows,packaging]
#   cd frontend; npm install; cd ..
# 产物：dist\ScreenSight\ScreenSight.exe

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "[1/3] 构建前端生产产物 ..." -ForegroundColor Cyan
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "前端构建失败"
}
Pop-Location

Write-Host "[2/3] 清理上次产物 ..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

Write-Host "[3/3] 运行 PyInstaller ..." -ForegroundColor Cyan
pyinstaller screensight.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败"
}

Write-Host ""
Write-Host "构建完成，产物位于 dist\ScreenSight\" -ForegroundColor Green
Write-Host "启动方式：dist\ScreenSight\ScreenSight.exe"
Write-Host "首次启动需在 dist\ScreenSight\ 旁放置 .env.local（参见 README）"
