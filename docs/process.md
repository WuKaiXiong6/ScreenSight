# 文件路径：docs/process.md
# 文件作用：ScreenSight 项目总计划、阶段状态、验证记录、未完成事项
# 最后更新时间：2026-06-29-0115

# ScreenSight 项目过程文档

> 本文档记录项目总计划、各阶段状态、验证记录与未完成事项。重大决策直接记录于此。

---

## 1. 总计划与阶段状态

### 当前阶段：MVP + Windows 打包完成（待用户人工 UI 验证）

| 阶段 | 状态 | 说明 |
|---|---|---|
| 需求确认 | ✅ 已完成 | 通过 9 轮提问确认，产出 `docs/PRD.md` v1.0 |
| 技术验证 | ✅ 已完成 | LLM/VLM/embedding 三项核心能力全部验证通过 |
| 架构设计 | ✅ 已完成 | 产出 `docs/ARCHITECTURE.md`，固化技术细节 |
| 开发实现 | ✅ 已完成 | 后端+前端+托盘全部实现，单元测试 24 项通过 |
| 后端链路验证 | ✅ 已完成 | 端到端真实链路验证通过（见第 3 节） |
| 前后端联调 | ✅ 已完成 | API 巡检通过，RAG 问答准确回答用户行为 |
| Windows 打包 | ✅ 已完成 | PyInstaller 单目录方案，真实 exe 启动联调通过 |
| 人工界面验证 | ⏳ 待用户 | 前端 UI 视觉与交互需用户在浏览器人工验证 |

### MVP 范围
采用**全功能一次交付**策略，已实现：截屏、VLM 识别、存储、报告、搜索/RAG、时间线界面、费用统计、系统托盘全部模块。

---

## 2. 重大决策记录

### 决策 1：核心技术选型与隐私边界
```txt
时间：2026-06-28-1924
背景：需确定部署形态、VLM 来源、技术栈、隐私策略等基础架构方向
决策：
  - 部署形态：后台服务 + 本地 Web 界面（系统托盘常驻 + 浏览器访问 localhost）
  - VLM 来源：云端 API，遵循 OpenAI 兼容协议，用户自带 Key
  - 技术栈：Python（mss/Pillow/httpx/sqlite-vec）+ FastAPI + 前端 SPA
  - 隐私策略：纯本地存储不上云；云端 VLM 临时上传不留存（本地为唯一持久化）
备选方案：
  - 本地 VLM（隐私更强但需强 GPU、识别质量受限）
  - 原生桌面应用（Electron/Tauri，体验好但 AI 生态弱）
影响：确定了整体技术架构方向，云端 API 依赖网络与用户自有 Key
回滚条件或后续观察点：若云 API 费用过高或隐私诉求升级，可演进为混合（敏感窗口走本地）
```

### 决策 2：截屏与静默策略
```txt
时间：2026-06-28-1924
背景：需确定截屏间隔、静默/锁屏处理、多屏处理
决策：
  - 活跃期间隔 30 秒
  - 在线判断依据键鼠活动（不依赖画面变化）
  - 键鼠无活动超阈值 → 拉长间隔（初定 5 分钟无活动 → 间隔 5 分钟）
  - 锁屏/睡眠 → 完全停止截屏
  - 多屏：只识别焦点屏，其余仅存档
  - 手动暂停/恢复
备选方案：
  - 画面变化检测跳过识别（被否决，用户明确依据键鼠活动判断）
  - 多屏全识别（费用 ×屏数，被否决）
影响：确定了截屏模块的核心行为
回滚条件或后续观察点：若 30 秒间隔费用过高，可调长
```

### 决策 3：存储与保留策略
```txt
时间：2026-06-28-1924
背景：需平衡识别准确度、磁盘占用、可回溯性
决策：
  - 图片质量分离：VLM 用高质量原图，本地存档用低质量压缩
  - 截图三级梯度保留：近期(0-30天)留压缩原图 / 中期(30天-3月)降质 / 远期(>3月)仅留文本
  - 结构化数据用 SQLite，向量用 sqlite-vec
  - 支持手动删除（隐私擦除）与备份导出/恢复
备选方案：
  - PNG 无损（占用过大，被否决）
  - 永久保留原图（占用过大，被否决）
影响：存档图不可用于事后重新验证 VLM 识别（已知取舍）
回滚条件或后续观察点：若用户需重看原图验证识别，需调整质量分离策略
```

### 决策 4：报告与搜索策略
```txt
时间：2026-06-28-1924
背景：报告是核心痛点，搜索是关键回溯能力
决策：
  - 报告：规则统计(保准确) + LLM 润色(自然语言)，避免 LLM 幻觉
  - 报告时机：每时/每日/每周/每月自动 + 手动触发
  - 报告导出：界面/Markdown/PDF
  - 关键词搜索：识别描述+报告+标签对象名（不做 OCR）
  - RAG：问答式检索，识别后即时向量化
  - 搜索筛选：时间+类目+项目+置信度
备选方案：
  - 纯 LLM 生成报告（可能幻觉，被否决，改为规则+LLM）
  - 截图 OCR 搜索（额外成本，被否决）
影响：明确了报告与搜索的功能边界
回滚条件或后续观察点：若搜索命中率不足，可考虑补 OCR
```

### 决策 5：本地 embedding 模型选型
```txt
时间：2026-06-28-1949
背景：用户配置的火山方舟(glm-5.2)与小米(mimo-v2.5)两家均不支持 embedding 端点，RAG 需要向量能力
决策：
  - 采用本地 embedding 模型 BAAI/bge-large-zh-v1.5（1024 维，中文专精，约 1.3GB）
  - 数据不出本机，符合"纯本地存储不上云"原则
  - 模型经 ModelScope 镜像下载，加载 0.3s，编码 4 条 0.35s
备选方案：
  - 云端 embedding API（被否决，与纯本地原则不符且需额外 Key）
  - bge-m3（2.3GB，中英文通用，体积偏大，留作后续可选升级）
影响：引入 sentence-transformers + torch 依赖（体积较大，但为本地 RAG 必要成本）
回滚条件或后续观察点：若需多语言或更高精度，可升级为 bge-m3
```

### 决策 6：Windows 打包方案
```txt
时间：2026-06-29-0115
背景：MVP 完成，分发要求脱离 Python 环境运行
决策：
  - 采用 PyInstaller 单目录(onedir)方案，入口 ScreenSight.exe
  - 资源路径双根分层：只读资源 → sys._MEIPASS；用户数据 → exe 同级目录（可被 SCREENSIGHT_DATA_HOME 覆盖）
  - bge embedding 模型不打入 exe，沿用 ModelScope 懒加载（首次启动联网下载）
  - prompts / 前端 dist / sqlite_vec/vec0.dll 通过 spec datas 与 collect_data_files 收集
  - apscheduler / sqlite_vec / pynput / pystray / mss / uvicorn 关键子模块显式声明 hiddenimports
备选方案：
  - PyInstaller onefile：启动慢（解压 torch 数十秒），被否决
  - Nuitka：打包结果更小但兼容性风险大、调试成本高，留作后续优化方向
  - Electron 重写：违背"Python + FastAPI"既有技术栈，工作量过大
影响：分发体积约 690 MB（torch + sentence-transformers 占主），首次启动需联网下载 embedding 模型
回滚条件或后续观察点：若体积无法接受，可尝试剥离 torch CUDA 部分或换 onnxruntime
```

---

## 3. 验证记录

### 技术验证：LLM/VLM/Embedding 连通性与输出质量
```txt
验证时间：2026-06-28-1949
验证对象：云端 LLM(火山方舟 glm-5.2) / 云端 VLM(小米 mimo-v2.5) / 本地 embedding(bge-large-zh-v1.5)
验证环境：Python 3.14.3 / openai SDK 2.44.0 / sentence-transformers 5.6.0
操作步骤：
  1. 用 OpenAI 兼容协议分别调用 LLM 与 VLM，传结构化 Prompt 要求输出 JSON
  2. VLM 用程序生成的模拟"VSCode 写 Python"截图测试视觉识别
  3. 加载本地 bge-large-zh-v1.5 测试中文语义相似度
观察现象：
  - LLM/VLM 均为推理模型(reasoning model)，max_tokens<1000 时输出为空（token 全用于推理）
  - max_tokens=2000 时输出正常：LLM 8.2s/次，VLM 7.3s/次，输出在 content 字段，推理在 reasoning_content 字段
  - VLM 准确识别"VSCode 编辑 Python，项目 ScreenSight，在写截屏函数"，置信度 0.95
  - 本地 embedding 加载 0.3s，编码 4 条 0.35s，「写代码」与「编写Python脚本」相似度 0.87（高），与「看电影」0.19（低）
结论：通过
遗留问题：
  1. 推理模型耗时 7-8s/次，需异步调用避免阻塞截屏
  2. 两个模型均为推理模型，token 消耗含 reasoning_tokens，费用统计需包含此项
  3. .env.local 中 LLM 与 VLM 段变量同名(TALK2ESP_LLM_*)，应用层需用不同前缀(LLM_*/VLM_*)解析
```
```txt
验证时间：2026-06-28-1924
验证对象：docs/PRD.md
验证环境：需求确认阶段（无代码）
操作步骤：9 轮交互式提问，逐项确认部署形态/VLM/技术栈/隐私/截屏/识别/存储/报告/搜索/MVP
观察现象：所有关键决策已明确，无未决项阻塞 PRD
结论：通过
遗留问题：8 项技术细节待架构设计阶段细化（见 PRD 第 6 节）
```

### 验证：后端核心链路端到端真实运行
```txt
验证时间：2026-06-28-2016
验证对象：截屏→VLM识别→活动合并→报告生成→关键词搜索→RAG问答 全链路
验证环境：Python 3.14.3 / 真实云端VLM(mimo-v2.5)+LLM(glm-5.2)+本地embedding(bge-large-zh)
操作步骤：
  1. 真实截取焦点屏，调用云端VLM识别
  2. 识别结果合并为活动时段
  3. 生成日报（规则统计+LLM润色）
  4. 关键词搜索识别记录
  5. RAG问答检索（问题向量化→向量检索→LLM生成回答）
  6. Markdown导出
观察现象：
  - VLM准确识别"代码审查 / Talk2ESP / 通过AI工具优化Talk2ESP项目的UX优化文档"
  - 报告总时长2.0h，LLM生成自然语言总结与洞察
  - 关键词搜索"代码"命中相关记录
  - RAG问答"我今天在做什么？"准确回答并引用来源
  - Markdown导出688字符，含分类占比/Top项目/总结/时间轴
结论：通过
遗留问题：无，后端核心链路全部验证可用
```

### 验证：前后端联调与完整产品运行
```txt
验证时间：2026-06-28-2036
验证对象：完整产品（后端+前端+托盘）真实运行
验证环境：Python 3.14.3 / Node 24 / 真实云端VLM+LLM+本地embedding
操作步骤：
  1. 构建前端生产产物（npm run build）
  2. 启动后端（python run.py，含托盘+前端托管+截屏调度）
  3. 等待积累真实识别数据
  4. 巡检全部 API 端点
  5. 验证报告生成（规则统计+LLM润色）与 RAG 问答
观察现象：
  - 系统托盘正常启动，浏览器自动打开 http://127.0.0.1:8765
  - 后端真实截屏并识别：编码开发/代码审查/文档撰写/即时通讯等类别，准确识别 Talk2ESP 项目
  - 时间线显示带时长的活动时段（修复了单条截图 duration=0 问题）
  - 日报生成成功：规则统计准确，LLM 生成自然语言总结
  - RAG 问答"我刚才在做什么"准确回答并引用 5 条来源记录
  - 暂停/恢复控制正常（PAUSED↔ACTIVE）
  - 全部 API 巡检通过：时间线/报告/搜索/设置/统计/控制
结论：通过
遗留问题：
  1. 前端 UI 视觉效果与交互需用户在浏览器人工验证（Agent 无法直接操作浏览器）
  2. Windows 打包方案（PyInstaller/Nuitka）未实现，当前需 Python 环境运行
  3. PDF 导出需额外安装 weasyprint（体积大，按需启用）
```

### 验证：Windows 打包后真实 exe 启动联调
```txt
验证时间：2026-06-29-0115
验证对象：PyInstaller 打包产物 dist/ScreenSight/ScreenSight.exe
验证环境：Windows 10 / Python 3.14 / PyInstaller 6.21.0 / Node 24 / 真实云端 VLM+LLM
操作步骤：
  1. 安装 packaging 依赖（pyinstaller>=6.6）
  2. cd frontend && npm run build（前端生产产物已存在则跳过）
  3. python -m PyInstaller screensight.spec --noconfirm
  4. 用临时数据根启动：SCREENSIGHT_DATA_HOME=C:\Users\..\Temp\screensight-pkg-test，SCREENSIGHT_PORT=8766
  5. 在该临时根放入 .env.local（含真实 LLM/VLM 配置）
  6. 启动 dist/ScreenSight/ScreenSight.exe，等待初始化
  7. 巡检 /api/health、/api/control/status、/api/timeline、/api/stats/usage、/、/assets/...
观察现象：
  - 打包耗时约 7 分钟，产物 dist/ScreenSight/ 共 691 MB（torch 占大头）
  - 资源收集正确：_internal/screensight/prompts/、_internal/frontend/dist/、_internal/sqlite_vec/vec0.dll 全部就位
  - 启动日志按序输出：托盘启动 → 键鼠监听 → 锁屏监控 → 截屏调度 → APScheduler → lifespan 完成
  - 截屏循环工作正常：30 秒内即触发首次 VLM 调用（mimo-v2.5 返回 200，6479 tokens）
  - 识别结果落库：/api/timeline 返回 1 条"编码开发 / Screensight"活动时段，含起止时间与时长
  - SPA 入口正常：GET / 返回前端 index.html，可被浏览器加载
  - 费用统计：/api/stats/usage 记录 vlm 1 次调用 6479 tokens
  - 用户数据隔离生效：SCREENSIGHT_DATA_HOME 下生成 data/screensight.db、data/screenshots/、data/models/
结论：通过
遗留问题：
  1. 体积约 690 MB，主要来自 torch；后续可剥离 CUDA 仅保留 CPU runtime（约可省 300+ MB）
  2. 首次启动若联网失败将无法下载 bge embedding 模型（已在 README 标注）
  3. 控制台窗口可见（console=True），正式分发可改为 console=False（需调整 stdout 重定向以保留日志）
```

---

## 4. 未完成事项

- [x] 产出 `docs/ARCHITECTURE.md`：8 项技术细节已全部细化并固化（见架构文档）
- [x] 后端基础设施层（配置/数据库/AI客户端/embedder/截图/活动检测/锁屏检测）
- [x] 数据访问层 repositories（含 sqlite-vec KNN 检索修复）
- [x] 核心服务层（识别/活动合并/存储/截屏调度状态机）
- [x] 报告服务（规则统计+LLM润色/Markdown导出）
- [x] 搜索与 RAG 服务（关键词LIKE+向量问答）
- [x] FastAPI 路由层与定时调度
- [x] 后端端到端真实链路验证通过
- [x] 前端 SPA（时间线/报告/搜索/设置，React+AntDesign）
- [x] 系统托盘与后台启动（pystray + 自动打开浏览器 + 前端托管）
- [x] 前后端联调与 API 巡检通过
- [x] Windows 打包方案（PyInstaller 单目录 + 双根路径策略 + 真实 exe 启动联调）
- [ ] 人工界面验证：前端 UI 视觉与交互需用户在浏览器验证
- [ ] PDF 导出（需额外安装 weasyprint）
- [ ] 打包瘦身（剥离 torch CUDA 仅留 CPU runtime，预计可省 300+ MB）

---

## 5. 变更历史

| 时间 | 内容 |
|---|---|
| 2026-06-28-1924 | 初始创建，记录需求确认阶段成果，产出 PRD v1.0 |
| 2026-06-28-1949 | 技术验证通过，产出 ARCHITECTURE.md，记录 embedding 决策 |
| 2026-06-28-2016 | 后端核心链路端到端验证通过，进入前端开发 |
| 2026-06-28-2036 | MVP 完成：前端+托盘+联调验证通过，待人工界面验证 |
| 2026-06-29-0115 | Windows 打包完成：PyInstaller 单目录方案 + 真实 exe 启动联调通过 |
