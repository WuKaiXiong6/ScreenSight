# 文件路径：screensight.spec
# 文件作用：PyInstaller 打包描述，单目录(onedir)输出 ScreenSight 后台服务 + 前端静态资源
# 最后更新时间：2026-06-29-0115
#
# 用法：
#   pip install -e backend[packaging]
#   cd frontend && npm install && npm run build && cd ..
#   pyinstaller screensight.spec --noconfirm
#
# 产物：dist/ScreenSight/ScreenSight.exe（含运行时依赖、prompts、frontend/dist）
# 用户数据（数据库/截图/模型/.env.local）默认放在 exe 所在目录的 data/ 与同级 .env.local
# 可通过环境变量 SCREENSIGHT_DATA_HOME 显式指定用户数据根
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

REPO_ROOT = Path(SPECPATH).resolve()
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

if not FRONTEND_DIST.exists():
    raise SystemExit(
        f"未找到前端构建产物 {FRONTEND_DIST}，请先执行 `cd frontend && npm run build`"
    )

# 数据文件：prompts 模板 + 前端 dist
# - prompts 放到 _MEIPASS/screensight/prompts，与源码模式 config.PROMPT_DIR 解析一致
# - frontend/dist 放到 _MEIPASS/frontend/dist，与 config.FRONTEND_DIST 解析一致
datas = [
    (str(BACKEND_DIR / "screensight" / "prompts"), "screensight/prompts"),
    (str(FRONTEND_DIST), "frontend/dist"),
]

# sqlite-vec 自带 vec0.dll，必须显式收集为数据文件让运行时 sqlite_vec.load 找到
datas += collect_data_files("sqlite_vec", include_py_files=False)

# 隐式 import：apscheduler 的 jobstore/executor、pynput/pystray 平台后端、uvicorn 协议子模块
hiddenimports = []
hiddenimports += collect_submodules("apscheduler")
hiddenimports += collect_submodules("sqlite_vec")
hiddenimports += [
    # pynput Windows 后端
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    # pystray Windows 后端
    "pystray._win32",
    # mss Windows 后端
    "mss.windows",
    # uvicorn 常用子模块（避免 ImportError）
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    # encodings（OpenAI SDK / httpx 偶发动态导入）
    "encodings.idna",
]

# 减小体积：排除测试/绘图/notebook 等无关依赖
excludes = [
    "tkinter",
    "matplotlib",
    "notebook",
    "IPython",
    "pytest",
    "pandas.tests",
]

block_cipher = None

a = Analysis(
    [str(BACKEND_DIR / "run.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# console=True：保留终端窗口便于查看日志；如需纯后台无窗口模式可改为 False（需注意 stdout 重定向）
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScreenSight",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ScreenSight",
)
