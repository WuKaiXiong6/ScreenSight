# 文件路径：README.md
# 文件作用：ScreenSight 项目说明、使用/运行/部署说明
# 最后更新时间：2026-06-29-0115

# ScreenSight

> Windows 平台的屏幕时间线工具：截屏 + 视觉大模型（VLM）识别，细粒度还原你在每一时刻的行为，并生成小时报/日报/周报/月报。

## 这是什么

ScreenSight 通过定时截取屏幕并交给云端 VLM 分析，识别你正在做什么（不只是"工作/娱乐"的粗分类，而是细化到"在 VSCode 写 Python 代码，项目是 ScreenSight"这种程度），并基于识别结果生成多粒度报告，让你清晰看到时间花在了哪里。

## 核心特性

- **细粒度行为识别**：23 类一级分类 + VLM 动态二级描述，识别具体项目/对象
- **智能截屏策略**：活跃时 30 秒一次，键鼠空闲自动拉长间隔，锁屏暂停
- **多屏支持**：只识别焦点屏，其余仅存档，节省 API 费用
- **本地优先隐私**：所有数据纯本地存储，云端仅临时上传识别不留存
- **多粒度报告**：小时报/日报/周报/月报，规则统计保准确 + LLM 润色
- **双模搜索**：关键词搜索 + RAG 问答检索，支持时间/类目/项目/置信度筛选
- **三级存储梯度**：近期留原图、中期降质、远期仅留文本，平衡占用与可回溯性

## 项目状态

✅ **MVP 已完成**（2026-06-28）

- ✅ 截屏调度（ACTIVE/IDLE/LOCKED/PAUSED 状态机，多屏焦点屏识别，键鼠空闲检测，锁屏暂停）
- ✅ VLM 行为识别（23 类一级分类 + 动态二级描述，准确识别项目/对象）
- ✅ 活动合并（连续同类合并为时段）
- ✅ 存储（SQLite + sqlite-vec，三级梯度保留，手动删除）
- ✅ 报告（小时/日/周/月报，规则统计 + LLM 润色，Markdown 导出）
- ✅ 搜索（关键词 LIKE + RAG 问答，时间/类目/项目/置信度筛选）
- ✅ 时间线界面（色块时间轴 + 详情列表）
- ✅ 系统托盘 + 自动打开浏览器
- ✅ 后端端到端真实链路验证通过
- ✅ Windows 打包（PyInstaller 单目录，含真实 exe 启动联调）

详见 [docs/process.md](docs/process.md) 的验证记录。

## 文档导航

| 文档 | 说明 |
|---|---|
| [AGENTS.md](AGENTS.md) | AI Agent 项目工作规则 |
| [docs/PRD.md](docs/PRD.md) | 产品需求文档 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术架构文档 |
| [docs/process.md](docs/process.md) | 总计划、阶段状态、验证记录 |

## 技术栈

- **后台服务**：Python 3.10+（mss 截图 / Pillow 图像处理 / openai SDK 云 API / sqlite-vec 向量检索 / pynput 键鼠检测 / pywin32 锁屏检测）
- **本地 Web 后端**：FastAPI + uvicorn
- **前端**：React 18 + TypeScript + Vite + Ant Design
- **存储**：SQLite + sqlite-vec（向量）+ FTS5（全文索引）
- **VLM**：云端 API（OpenAI 兼容协议，用户自带 Key）
- **本地 Embedding**：bge-large-zh-v1.5（1024 维，数据不出本机）
- **托盘**：pystray
- **定时调度**：APScheduler

## 使用方式

### 1. 配置云端 API

在项目根目录创建 `.env.local`（已 gitignore，不入版本库），配置 LLM 与 VLM：

```ini
# LLM 配置（文本/报告润色/RAG回答）
LLM_PROVIDER=openai_compat
LLM_BASE_URL=<你的LLM地址>
LLM_API_KEY=<API_KEY>
LLM_MODEL=<模型名>

# VLM 配置（视觉识别）
VLM_PROVIDER=openai_compat
VLM_BASE_URL=<你的VLM地址>
VLM_API_KEY=<API_KEY>
VLM_MODEL=<模型名>
```

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -e ".[dev]"
# Windows 平台额外安装
pip install pywin32

# 前端
cd ../frontend
npm install
```

### 3. 构建前端（生产模式）

```bash
cd frontend
npm run build
```

### 4. 启动

```bash
cd backend
python run.py
```

启动后：
- 系统托盘出现 ScreenSight 图标
- 自动打开浏览器访问 `http://127.0.0.1:8765`
- 后台开始定时截屏 + VLM 识别

### 5. 开发模式（前后端分离）

```bash
# 终端1：启动后端
cd backend && python run.py

# 终端2：启动前端 dev server（带热更新）
cd frontend && npm run dev
# 访问 http://localhost:5174
```

### 首次运行注意

首次启动时，本地 embedding 模型（bge-large-zh-v1.5，约 1.3GB）会自动从 ModelScope 下载到 `data/models/`，需联网等待。下载完成后后续启动无需联网即可向量化。

## Windows 打包（PyInstaller）

可将后端 + 前端 dist + 托盘打成单目录发行包，目标机器无需安装 Python。

### 构建步骤

```powershell
# 1. 安装打包依赖
pip install -e backend[windows,packaging]

# 2. 构建前端生产产物
cd frontend; npm install; npm run build; cd ..

# 3. 运行 PyInstaller（或直接调用脚本）
pyinstaller screensight.spec --noconfirm
# 也可一键执行：
.\build_windows.ps1   # PowerShell
.\build_windows.bat   # CMD
```

构建产物位于 `dist/ScreenSight/`，可整体压缩或安装包形式分发。入口程序为 `dist/ScreenSight/ScreenSight.exe`，约 690 MB（含 torch / sentence-transformers）。

### 发行包目录约定

打包后运行时的路径策略：
- **只读资源**（prompts、前端 dist、`vec0.dll`）位于 `_internal/`，由 PyInstaller 自动解压到 `_MEIPASS`
- **用户数据**（数据库、截图、模型缓存）默认写到 `ScreenSight.exe` **所在目录**的 `data/`
- **`.env.local`** 默认从 `ScreenSight.exe` **所在目录**读取
- 可通过环境变量 `SCREENSIGHT_DATA_HOME=<绝对路径>` 显式指定用户数据根（含 `.env.local` 与 `data/` 子目录）

### 发布前清单

- [ ] 在 `dist/ScreenSight/` 旁放置 `.env.local`（含 LLM/VLM 配置；切勿在分发前留有真实 Key）
- [ ] 首次启动需联网下载 embedding 模型（1.3 GB），完成后可离线运行
- [ ] 若目标机器无 VC++ 运行库，需补装 Microsoft Visual C++ Redistributable
- [ ] PDF 导出（weasyprint）默认未打包，按需另行安装

## 配置说明

> 需配置云 VLM API（OpenAI 兼容协议）：
> - `base_url`：API 地址
> - `api_key`：用户自有的 API Key（**请勿提交真实 Key 到版本库**，配置示例使用 `<API_KEY>` 占位符）

## 开发参与

详见 [AGENTS.md](AGENTS.md) 了解项目工作规则（文档管理、Git 规范、安全边界、测试验证门禁等）。
