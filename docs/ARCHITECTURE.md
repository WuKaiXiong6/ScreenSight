# 文件路径：docs/ARCHITECTURE.md
# 文件作用：ScreenSight 技术架构设计，定义模块边界、数据流、技术选型与关键实现细节
# 最后更新时间：2026-06-29-0115

# ScreenSight 技术架构文档

> 版本：v1.1
> 状态：MVP 完成 + Windows 打包验证通过
> 最后更新：2026-06-29-0115

---

## 1. 总体架构

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│  前端 SPA (浏览器 localhost)                              │
│  时间线 / 报告 / 搜索 / 设置 / 费用统计                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/REST (FastAPI)
┌────────────────────────▼────────────────────────────────┐
│  API 层 (FastAPI)                                        │
│  路由 / 鉴权(CORS本地) / 请求校验                          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  业务服务层 (Service)                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 截屏调度  │ │ 识别编排  │ │ 报告生成  │ │ 搜索/RAG │    │
│  │Capture   │ │Recognize │ │ Report   │ │ Search   │    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │
└───────┼────────────┼────────────┼────────────┼──────────┘
        │            │            │            │
┌───────▼────────────▼────────────▼────────────▼──────────┐
│  基础设施层 (Infra)                                       │
│  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │截图引擎 │ │AI客户端   │ │存储仓库   │ │向量化引擎    │  │
│  │(mss)   │ │(OpenAI   │ │(SQLite + │ │(bge-large-zh│  │
│  │        │ │ 兼容SDK)  │ │sqlite-vec│ │ +sentence-  │  │
│  │        │ │LLM/VLM   │ │)         │ │transformers)│  │
│  └────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐                │
│  │活动检测   │ │系统状态   │ │后台调度     │                │
│  │(键鼠钩子) │ │(锁屏检测) │ │(APScheduler)│                │
│  └──────────┘ └──────────┘ └────────────┘                │
└──────────────────────────────────────────────────────────┘
```

### 1.2 进程模型
- **单进程多线程**架构，后台服务常驻。
- 主线程运行 FastAPI（uvicorn）；后台线程跑截屏调度与定时任务。
- VLM/LLM 调用为 IO 密集，用异步（asyncio）或线程池避免阻塞。
- 系统托盘独立线程，与 FastAPI 通过共享状态通信。

### 1.3 关键技术决策（已验证）

| 能力 | 选型 | 验证结论 |
|---|---|---|
| 截图 | mss | 多显示器支持，Python 3.14 兼容 |
| 图像处理 | Pillow | 压缩/质量分离 |
| VLM | 云端 mimo-v2.5 (OpenAI 兼容) | 推理模型，max_tokens≥2000，7-8s/次 |
| LLM | 云端 glm-5.5 (OpenAI 兼容) | 推理模型，max_tokens≥2000 |
| Embedding | 本地 bge-large-zh-v1.5 (1024维) | 加载 0.3s，编码快，语义效果好 |
| 结构化存储 | SQLite | 单文件易备份 |
| 向量存储 | sqlite-vec | 与 SQLite 同库，易管理 |
| Web 后端 | FastAPI + uvicorn | 异步 IO 友好 |
| 后台调度 | APScheduler | 定时报表/保留策略 |
| 前端 | React + Vite | 生态成熟，SPA 适合 |

---

## 2. 目录结构

```
ScreenSight/
├── backend/                      # Python 后端
│   ├── screensight/              # 主包
│   │   ├── __init__.py
│   │   ├── config.py             # 配置加载（.env.local 分段解析）
│   │   ├── models.py             # 数据模型（Pydantic + SQLAlchemy）
│   │   ├── db.py                 # SQLite 连接与初始化（含 sqlite-vec）
│   │   ├── repositories/         # 数据访问层
│   │   │   ├── capture.py        # 截图记录仓储
│   │   │   ├── activity.py       # 活动/时段仓储
│   │   │   └── report.py         # 报告仓储
│   │   ├── services/             # 业务服务层
│   │   │   ├── capture_service.py    # 截屏调度与多屏/焦点处理
│   │   │   ├── recognize_service.py  # VLM 识别编排
│   │   │   ├── activity_service.py   # 活动合并与时段管理
│   │   │   ├── report_service.py     # 报告生成（规则+LLM）
│   │   │   ├── search_service.py     # 关键词+RAG 搜索
│   │   │   └── retention_service.py  # 三级梯度保留与清理
│   │   ├── infra/                # 基础设施
│   │   │   ├── screenshot.py     # mss 截图封装
│   │   │   ├── ai_client.py      # OpenAI 兼容客户端（LLM/VLM）
│   │   │   ├── embedder.py       # 本地 bge 向量化
│   │   │   ├── activity_monitor.py  # 键鼠活动检测
│   │   │   └── session_monitor.py   # 锁屏/会话状态检测
│   │   ├── api/                  # FastAPI 路由
│   │   │   ├── timeline.py       # 时间线
│   │   │   ├── reports.py        # 报告
│   │   │   ├── search.py         # 搜索
│   │   │   ├── settings.py       # 设置
│   │   │   └── stats.py          # 费用统计
│   │   ├── prompts/              # Prompt 模板
│   │   │   ├── recognize.md      # VLM 识别 Prompt
│   │   │   ├── report_daily.md   # 日报润色 Prompt
│   │   │   └── rag_answer.md     # RAG 问答 Prompt
│   │   ├── app.py                # FastAPI 应用入口
│   │   └── tray.py               # 系统托盘（pystray）
│   ├── tests/                    # 测试
│   ├── pyproject.toml            # 依赖管理
│   └── run.py                    # 启动入口
├── frontend/                     # React 前端
│   ├── src/
│   │   ├── pages/                # 时间线/报告/搜索/设置
│   │   ├── components/           # 色块时间轴/筛选器等
│   │   └── api/                  # 后端 API 调用
│   └── package.json
├── data/                         # 运行时数据（gitignore）
│   ├── screensight.db            # SQLite 主库
│   ├── screenshots/              # 截图文件（按日期分目录）
│   └── models/                   # bge 模型缓存
├── docs/                         # 文档
├── AGENTS.md
├── .env.local                    # 敏感配置（gitignore）
└── README.md
```

---

## 3. 数据模型（SQLite Schema）

### 3.1 核心表

```sql
-- 截图记录：每次截屏一条
CREATE TABLE captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,           -- ISO8601 时间戳
    monitor_index INTEGER NOT NULL,      -- 显示器序号
    is_focused BOOLEAN NOT NULL,         -- 是否焦点屏
    archive_path TEXT,                   -- 存档图路径（低质量压缩）
    width INTEGER,
    height INTEGER,
    recognition_status TEXT NOT NULL,    -- pending/success/failed/skipped
    recognition_id INTEGER,              -- 关联 recognitions.id
    FOREIGN KEY (recognition_id) REFERENCES recognitions(id)
);

-- 识别结果：VLM 返回的结构化数据
CREATE TABLE recognitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL,
    category TEXT NOT NULL,              -- 一级类别（23类之一）
    sub_desc TEXT,                       -- 二级动态描述
    object_name TEXT,                    -- 项目/对象名
    activity TEXT,                       -- 一句话活动描述
    confidence REAL NOT NULL,            -- 0-1
    is_low_confidence BOOLEAN NOT NULL,  -- 低置信标记
    raw_response TEXT,                   -- VLM 原始返回（调试用）
    llm_tokens_used INTEGER,             -- token 用量（费用统计）
    llm_cost_estimate REAL,              -- 预估费用
    created_at TEXT NOT NULL,
    FOREIGN KEY (capture_id) REFERENCES captures(id)
);

-- 活动时段：合并连续同类识别结果
CREATE TABLE activity_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,            -- 时段开始
    end_time TEXT NOT NULL,              -- 时段结束
    category TEXT NOT NULL,
    sub_desc TEXT,
    object_name TEXT,
    capture_ids TEXT NOT NULL,           -- JSON 数组：含的截图 ID
    capture_count INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_low_confidence BOOLEAN NOT NULL,
    created_at TEXT NOT NULL
);

-- 报告
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,           -- hourly/daily/weekly/monthly
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    stats_json TEXT NOT NULL,            -- 规则统计结果（JSON）
    llm_summary TEXT,                    -- LLM 润色后的自然语言总结
    generated_at TEXT NOT NULL,
    is_manual BOOLEAN NOT NULL
);

-- 配置/设置
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 向量表（sqlite-vec 虚拟表）
CREATE VIRTUAL TABLE recognition_vectors USING vec0(
    recognition_id INTEGER PRIMARY KEY,
    embedding FLOAT[1024]
);

-- 费用统计聚合
CREATE TABLE usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,             -- YYYY-MM-DD
    api_type TEXT NOT NULL,              -- vlm/llm/embedding
    call_count INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost_estimate REAL NOT NULL,
    UNIQUE(stat_date, api_type)
);
```

### 3.2 索引
- `captures(captured_at)`、`captures(recognition_status)`
- `recognitions(category)`、`recognitions(object_name)`、`recognitions(confidence)`
- `activity_segments(start_time)`、`activity_segments(category)`
- `reports(report_type, period_start)`

---

## 4. 关键模块设计

### 4.1 截屏调度模块 (capture_service)

#### 4.1.1 截屏循环（状态机）
```
状态：ACTIVE / IDLE / LOCKED / PAUSED

ACTIVE（活跃）:
  - 键鼠活动正常
  - 每 30s 截屏一次
  - 转换: 键鼠无活动 >5min → IDLE

IDLE（空闲）:
  - 键鼠无活动
  - 每 5min 截屏一次（仅检测是否恢复）
  - 标记"空闲"时段
  - 转换: 键鼠恢复 → ACTIVE；锁屏 → LOCKED

LOCKED（锁屏）:
  - 完全停止截屏
  - 转换: 解锁 → ACTIVE

PAUSED（手动暂停）:
  - 用户手动暂停
  - 完全停止截屏
  - 转换: 用户恢复 → ACTIVE
```

#### 4.1.2 焦点屏判定
- 用 `win32gui` 获取前台窗口所在显示器（`MonitorFromWindow`）。
- 该屏截高清图送 VLM；其余屏截低质图仅存档。
- 单屏时无需额外处理。

#### 4.1.3 锁屏检测
- 用 `pywin32` 监听 `WTS_SESSION_LOCK` / `WTS_SESSION_UNLOCK` 事件（`WTRegisterSessionNotification`）。
- 备用方案：检测前台窗口是否为 Logon UI（`GetForegroundWindow` + 进程名）。

#### 4.1.4 键鼠活动检测
- 用 `pynput` 监听键盘/鼠标事件，记录最后活动时间戳。
- 判定 `now - last_activity > threshold` 决定状态。

### 4.2 VLM 识别模块 (recognize_service)

#### 4.2.1 调用流程
```
1. 取焦点屏截图（PNG，高质量）
2. base64 编码
3. 构造 messages（system + user[text+image_url]）
4. 调用 VLM (max_tokens=2000, temperature=0.2)
5. 解析 content 字段为 JSON
6. JSON 解析失败 → 重试一次（换更严格 prompt）
7. 二次失败 → 标记 recognition_status=failed，保留截图
```

#### 4.2.2 Prompt 模板（recognize.md）
```
你是屏幕活动识别助手。根据截图判断用户当前正在做什么，只输出 JSON，不要输出思考过程或多余文字。

一级类别必须从以下 23 类中选择其一：
1.编码开发 2.代码审查 3.调试排错 4.终端操作 5.文档撰写 6.文档阅读 7.技术资料查阅 8.笔记知识整理
9.UI/UX设计 10.图像编辑 11.音视频制作 12.即时通讯 13.邮件处理 14.视频会议
15.网页浏览 16.社交媒体 17.视频/电影 18.音乐/播客 19.游戏
20.在线学习 21.文件管理 22.系统工具 23.其他/空闲

输出 JSON 格式（严格 JSON，无 markdown 代码块）：
{
  "category": "一级类别名（如 编码开发）",
  "sub_desc": "二级动态描述（如 Python-ScreenSight-截图模块）",
  "object_name": "项目名或对象名（如 ScreenSight，无则填空字符串）",
  "activity": "一句话描述当前行为",
  "confidence": 0.0-1.0
}

识别要点：
- 关注标题栏、文件栏、代码内容、地址栏等关键细节推断具体项目/对象
- 写代码时：尝试从文件栏和标题栏推断项目名、语言、文件名
- 看视频时：尝试识别影片/节目名称
- 写文档时：尝试从内容推断文档主题
- 置信度反映画面信息充分程度，信息少或模糊时给低值
```

#### 4.2.3 配置解析（解决 .env.local 同名冲突）
`.env.local` 中 LLM 段与 VLM 段变量同名（`TALK2ESP_LLM_*`），按注释分块解析为两个独立配置：
```python
# config.py 分段解析逻辑
def load_config():
    # 按 # LLM 配置 / # VLM 配置 注释分块
    # LLM 段 → LLM_BASE_URL/LLM_API_KEY/LLM_MODEL
    # VLM 段 → VLM_BASE_URL/VLM_API_KEY/VLM_MODEL
```

### 4.3 活动合并模块 (activity_service)

#### 4.3.1 合并算法
```
对连续的 recognition 记录，按时间排序后：
  若相邻两条满足：
    - category 相同
    - object_name 相同（或都为空）
    - 间隔 < 2*截屏间隔（即 60s，允许一次漏截）
  → 合并为同一 activity_segment
  segment.start_time = 第一条时间
  segment.end_time = 最后一条时间 + 30s
  segment.capture_ids = [所有 capture_id]
  segment.duration_seconds = end - start
```

#### 4.3.2 实时合并 vs 批量合并
- 采用**增量合并**：每次新识别结果产生时，检查与当前活跃 segment 是否可合并：
  - 可合并 → 更新 segment.end_time 与 capture_ids
  - 不可合并 → 关闭当前 segment，新建 segment
- 避免全表重算，保证时间线实时性。

### 4.4 存储与保留模块 (retention_service)

#### 4.4.1 图片质量分离
| 用途 | 格式 | 参数 | 说明 |
|---|---|---|---|
| 送 VLM | PNG | 无损 | 内存中 base64，不落盘 |
| 存档（近期） | WebP | quality=70, 缩放至 50% | 平衡体积与可辨识 |
| 存档（中期降质） | WebP | quality=40, 缩放至 30% | 进一步压缩 |
| 远期 | 删除文件 | - | 仅留识别文本 |

#### 4.4.2 三级梯度保留
```python
# 每日定时任务（APScheduler cron 03:00）
def retention_job():
    # 近期→中期：30天前的存档图降质压缩
    downgrade_old_archives(days=30)
    # 中期→远期：3个月前的截图文件删除（保留 recognition 记录）
    delete_old_screenshots(days=90)
    # VACUUM 数据库
```

#### 4.4.3 手动删除
- 删除 activity_segment → 级联删除其 capture_ids 对应的 captures、recognitions、recognition_vectors、截图文件。
- 事务化保证一致性。

### 4.5 报告模块 (report_service)

#### 4.5.1 规则统计部分（保准确）
```python
def compute_stats(period_start, period_end):
    segments = query_segments(period_start, period_end)
    return {
        "total_duration": sum durations,
        "by_category": {category: {duration, percentage}},  # 23类时长占比
        "by_object": {object_name: duration},  # 按项目聚合
        "timeline": [{start, end, category, object_name}],  # 时间轴
        "top_objects": sorted by duration top 10,
        "low_confidence_count": count,
    }
```

#### 4.5.2 LLM 润色部分
```python
def llm_polish(stats, report_type):
    prompt = render("report_daily.md", stats=stats, type=report_type)
    resp = call_llm(prompt, max_tokens=2000)
    return resp.content  # 自然语言总结与洞察
```
- LLM 只接收**统计后的聚合数据**，不接收原始记录，避免幻觉且省 token。

#### 4.5.3 定时生成（APScheduler）
```python
scheduler.add_job(hourly_report, 'cron', minute=59)      # 每小时末
scheduler.add_job(daily_report, 'cron', hour=23, minute=30)  # 每日
scheduler.add_job(weekly_report, 'cron', day_of_week='mon', hour=8)  # 每周一
scheduler.add_job(monthly_report, 'cron', day=1, hour=8)  # 每月1号
```

#### 4.5.4 导出
- **Markdown**：Jinja2 模板渲染统计 + LLM 总结。
- **PDF**：Markdown → PDF（用 `markdown` + `weasyprint` 或 `pdfkit`）。

### 4.6 搜索与 RAG 模块 (search_service)

#### 4.6.1 关键词搜索
```sql
-- 用 SQLite FTS5 全文索引覆盖识别描述+报告+标签对象名
CREATE VIRTUAL TABLE search_index USING fts5(
    content, source_type, source_id, tokenize='unicode61'
);
-- 搜索时 MATCH 关键词，再 JOIN 原表返回完整记录
```

#### 4.6.2 RAG 问答流程
```
1. 用户问题 → bge 向量化 → 得到 query_vector(1024维)
2. sqlite-vec 检索 top-K 相似 recognition_vectors
3. 取对应 recognitions 记录（含时间/类别/描述/对象）
4. 组装上下文 → 调 LLM 生成回答
5. 返回回答 + 引用的记录列表
```

#### 4.6.3 向量化时机
- VLM 识别成功后，立即对 `activity` + `sub_desc` + `object_name` 拼接文本做 embedding，写入 `recognition_vectors`。
- 报告生成后，对报告 LLM 总结文本做 embedding，写入 search_index。

#### 4.6.4 筛选实现
- 时间范围：SQL WHERE captured_at BETWEEN
- 类目：WHERE category IN
- 项目/对象：WHERE object_name =
- 置信度：WHERE confidence >= threshold
- 以上均可叠加在关键词搜索或 RAG 检索结果上。

---

## 5. API 设计（REST）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/timeline | 获取时间线（按天/周/月，含 segments） |
| GET | /api/timeline/{date} | 某天详情 |
| DELETE | /api/timeline/segment/{id} | 删除某时段（隐私擦除） |
| GET | /api/reports | 报告列表 |
| GET | /api/reports/{id} | 报告详情 |
| POST | /api/reports/generate | 手动生成报告 |
| GET | /api/reports/{id}/export?format=md\|pdf | 导出 |
| GET | /api/search/keyword?q=&start=&end=&category=&object=&min_conf= | 关键词搜索 |
| POST | /api/search/rag | RAG 问答（body: {question, filters}） |
| GET | /api/stats/usage | 费用统计 |
| GET | /api/settings | 获取设置 |
| PUT | /api/settings | 更新设置 |
| POST | /api/control/pause | 暂停记录 |
| POST | /api/control/resume | 恢复记录 |
| GET | /api/control/status | 当前状态（ACTIVE/IDLE/LOCKED/PAUSED） |

---

## 6. 配置管理

### 6.1 .env.local 结构（分段解析）
```ini
# LLM 配置
LLM_PROVIDER=openai_compat
LLM_BASE_URL=<火山方舟地址>
LLM_API_KEY=<API_KEY>
LLM_MODEL=glm-5.2

# VLM 配置
VLM_PROVIDER=openai_compat
VLM_BASE_URL=<小米地址>
VLM_API_KEY=<API_KEY>
VLM_MODEL=mimo-v2.5
```
> 注：用户现有 .env.local 用 TALK2ESP_LLM_* 同名前缀，应用层解析时兼容映射为 LLM_*/VLM_*。

### 6.2 可调参数（存 settings 表，界面可改）
| 参数 | 默认值 | 说明 |
|---|---|---|
| capture_interval_active | 30 | 活跃截屏间隔（秒） |
| capture_interval_idle | 300 | 空闲截屏间隔（秒） |
| idle_threshold | 300 | 进入空闲的阈值（秒） |
| low_confidence_threshold | 0.6 | 低置信度阈值 |
| archive_quality_near | 70 | 近期存档质量 |
| archive_scale_near | 50 | 近期存档缩放% |
| retention_near_days | 30 | 近期保留天数 |
| retention_mid_days | 90 | 中期保留天数 |
| merge_gap_tolerance | 60 | 合并间隔容忍（秒） |

---

## 7. 错误处理与降级

| 场景 | 处理 |
|---|---|
| VLM 调用超时/失败 | 重试 1 次，仍失败标记 failed，保留截图，不中断截屏循环 |
| LLM 报告生成失败 | 返回纯规则统计（无 LLM 总结），标记 report.llm_summary=null |
| Embedding 失败 | 跳过该条向量化，关键词搜索仍可用 |
| 数据库锁 | WAL 模式 + 重试 |
| 磁盘不足 | 停止截图，托盘告警 |
| 模型未下载 | 首次启动引导下载 bge 模型 |

---

## 8. 依赖清单

### 8.1 Python 依赖（pyproject.toml）
```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "mss>=9.0",
    "Pillow>=10.0",
    "openai>=2.0",
    "sqlite-vec>=0.1",
    "sentence-transformers>=3.0",
    "torch",
    "pywin32>=306",          # Windows API（锁屏/窗口）
    "pynput>=1.7",           # 键鼠活动检测
    "pystray>=0.19",         # 系统托盘
    "Pillow",                # 托盘图标
    "apscheduler>=3.10",     # 定时任务
    "sqlalchemy>=2.0",       # ORM（可选）
    "pydantic>=2.0",
    "jinja2>=3.1",           # 报告模板
    "markdown>=3.5",         # MD 渲染
    "weasyprint>=60",        # PDF 导出（可选，体积大）
]
```

### 8.2 前端依赖
- React 18 + Vite + TypeScript
- UI 组件：Ant Design 或 Mantine（后续确定）
- 图表：Recharts（报告统计图）
- 时间轴：自研色块组件

---

## 9. 待后续细化

- ~~Windows 打包方案（PyInstaller / Nuitka，需验证 bge 模型打包）~~ → 已采用 PyInstaller 单目录方案（见 §10）
- 前端 UI 组件库最终选型
- weasyprint 体积过大时的 PDF 替代方案
- 多用户场景预留（当前不做，但 schema 不阻断）

---

## 10. Windows 打包（PyInstaller）

### 10.1 形态选型
- 采用 **PyInstaller 单目录(onedir)** 方案，产物为 `dist/ScreenSight/`（含 `ScreenSight.exe` + `_internal/`）。
- 不用 onefile：onefile 启动需解压全部依赖（含 torch ~500MB），冷启动延迟数十秒；onedir 启动几乎即时。
- bge embedding 模型（1.3 GB）**不打入产物**，按现有 ModelScope 懒加载机制首次启动时下载到 `data/models/`。

### 10.2 资源 / 数据路径分层
`config.py` 引入 frozen 检测，区分两类根：

| 用途 | 源码模式 | 打包模式 |
|---|---|---|
| 只读资源 `RESOURCE_ROOT`<br>（prompts、frontend dist、vec0.dll） | 仓库根 | `sys._MEIPASS`（启动时解压目录） |
| 用户数据 `PROJECT_ROOT`<br>（数据库、截图、模型、.env.local） | 仓库根 | `Path(sys.executable).parent` |
| 覆盖项 | — | 环境变量 `SCREENSIGHT_DATA_HOME=<绝对路径>` 优先 |

派生路径：
- `DATA_DIR = PROJECT_ROOT/data`
- `DB_PATH = DATA_DIR/screensight.db`
- `SCREENSHOT_DIR = DATA_DIR/screenshots`
- `MODEL_CACHE_DIR = DATA_DIR/models`
- `PROMPT_DIR = RESOURCE_ROOT/screensight/prompts`（打包模式）
- `FRONTEND_DIST = RESOURCE_ROOT/frontend/dist`（打包模式）

### 10.3 PyInstaller 关键配置（`screensight.spec`）
- 入口：`backend/run.py`
- `datas`：
  - `backend/screensight/prompts/` → `screensight/prompts/`
  - `frontend/dist/` → `frontend/dist/`
  - `collect_data_files("sqlite_vec")` 拉入 `vec0.dll`
- `hiddenimports`：
  - `collect_submodules("apscheduler")` / `collect_submodules("sqlite_vec")`
  - `pynput.keyboard._win32` / `pynput.mouse._win32` / `pystray._win32` / `mss.windows`
  - `uvicorn.loops.auto` / `uvicorn.protocols.http.auto` / `uvicorn.protocols.websockets.auto` / `uvicorn.lifespan.on`
- `excludes`：tkinter / matplotlib / notebook / IPython / pytest / pandas.tests
- `console=True`：保留控制台便于查看日志（可视实际分发改 False）

### 10.4 构建脚本
- `build_windows.bat` / `build_windows.ps1`：一键构建（前端 build → 清理 build/dist → 调用 pyinstaller）
- 依赖：`pip install -e backend[windows,packaging]`，需 Node 18+

### 10.5 发行包目录结构
```
dist/ScreenSight/
├── ScreenSight.exe                  # 入口，等价 backend/run.py
├── .env.local                       # 用户配置（分发时不应预置真实 Key）
├── data/                            # 运行时生成（数据库 / 截图 / 模型缓存）
│   ├── screensight.db
│   ├── screenshots/
│   └── models/BAAI/bge-large-zh-v1.5/
└── _internal/                       # PyInstaller 收集的依赖
    ├── frontend/dist/...            # 前端静态资源
    ├── screensight/prompts/...      # Prompt 模板
    ├── sqlite_vec/vec0.dll
    ├── torch/ / sentence_transformers/ / ...
    └── python314.dll
```

### 10.6 产物体积
- 约 690 MB：torch 占大头（~500 MB），sentence-transformers 约 100 MB，其他 Python 运行时与依赖约 90 MB。
- 进一步瘦身路径（暂未启用）：剥离 torch CUDA 部分仅保留 CPU、剔除 sklearn/scipy 等非必需子包。

### 10.7 验证策略
- 自动化：在临时 `SCREENSIGHT_DATA_HOME` 下启动 exe，巡检 `/api/health` / `/api/timeline` / `/api/control/status` / `/api/stats/usage`，确认托盘 / 调度器 / 云端 VLM 调用全部正常。
- 人工：在干净 Windows 机器解压发行包，按 README 流程跑一遍完整链路（截屏 → 识别 → 时间线 → 报告 → RAG）。
