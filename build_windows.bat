@echo off
REM 文件路径：build_windows.bat
REM 文件作用：一键构建 ScreenSight Windows 单目录发行包
REM 最后更新时间：2026-06-29-0115
REM
REM 前置条件：已安装 Python 3.10+ 与 Node 18+；并已在 backend/frontend 安装依赖
REM   pip install -e backend[windows,packaging]
REM   cd frontend ^&^& npm install ^&^& cd ..
REM 产物：dist\ScreenSight\ScreenSight.exe

setlocal
cd /d "%~dp0"

echo [1/3] 构建前端生产产物 ...
pushd frontend
call npm run build
if errorlevel 1 (
  echo [错误] 前端构建失败
  popd
  exit /b 1
)
popd

echo [2/3] 清理上次产物 ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] 运行 PyInstaller ...
pyinstaller screensight.spec --noconfirm
if errorlevel 1 (
  echo [错误] PyInstaller 构建失败
  exit /b 1
)

echo.
echo 构建完成，产物位于 dist\ScreenSight\
echo 启动方式：dist\ScreenSight\ScreenSight.exe
echo 首次启动需在 dist\ScreenSight\ 旁放置 .env.local（参见 README）
endlocal
