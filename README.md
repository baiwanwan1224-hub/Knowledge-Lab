# Knowledge Lab · 自测学习平台

> Obsidian + LLM + Whisper · RAG 自测学习系统  
> 既是学习工具，也是 AI PM 能力展示项目

## 架构

```
┌── 仪表盘 HTML ──┬── quiz_server.py (API) ──┬── quiz_generator.py (出题)
│  (单文件 SPA)    │                           │
│  📊 仪表盘       │  POST /quiz/generate      │  读取 Obsidian 笔记
│  📚 知识库       │  POST /quiz/grade          │  → DeepSeek 出题
│  🧪 出题测验     │  POST /notes/import        │  → QA 质量检查
│  ❌ 错题本       │  POST /notes/upload        │
│  📈 历史记录     │  POST /notes/transcribe    ├── quiz_grader.py (批改)
│                  │  POST /notes/verify        │
│                  │  DELETE /notes             │  读取评分标准
│                  │  GET  /competency          │  → DeepSeek 评分
│                  │  GET  /dashboard           │  → SM-2 排程
│                  │  GET  /history             │  → 错题卡写入
└──────────────────┴───────────────────────────┴──────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | 纯 HTML/CSS/JS（无框架，单文件 SPA）|
| 后端 | Python HTTP Server (标准库) |
| AI 引擎 | DeepSeek v4-pro（出题 + 批改 + 笔记整理）|
| 语音识别 | faster-whisper (tiny) + yt-dlp |
| 数据库 | PostgreSQL（可选，也可纯文件模式）|
| 知识库 | Obsidian vault（Markdown + YAML frontmatter）|
| 标准体系 | L0 不可变标准文件（评分/能力/质量/命名）|

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export DEEPSEEK_API_KEY="sk-your-key"
export PG_HOST="localhost"
export PG_PORT="5432"
export PG_DATABASE="n8n_scraper"
export PG_USER="n8n"
export PG_PASSWORD="your-password"
export VAULT_PATH="/path/to/ObsidianVault/AI-PM-学习"
```

### 3. 初始化数据库（可选）

```bash
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -f sql/schema.sql
```

### 4. 启动

```bash
python server/quiz_server.py --port 5050
```

浏览器打开 `http://localhost:5050`

## 项目结构

```
knowledge-lab/
├── server/
│   ├── quiz_server.py        # API 服务（HTTP + 标准加载）
│   ├── quiz_generator.py     # RAG 出题（笔记→LLM→题目+QA）
│   └── quiz_grader.py        # 批改评分（LLM 评分 + SM-2 + 错题卡）
├── dashboard/
│   └── dashboard_v2.html     # 统一仪表盘 SPA
├── standards/                # L0 不可变标准文件
│   ├── _STANDARD_评分标准.md
│   ├── _STANDARD_能力维度.md
│   ├── _STANDARD_内容质量.md
│   └── _STANDARD_命名规范.md
├── sql/
│   └── schema.sql            # PostgreSQL 建表语句
├── templates/                # Obsidian 笔记模板
│   ├── 模板_学习笔记.md
│   └── 模板_错题卡.md
├── LICENSE                   # AGPL v3
├── README.md
├── requirements.txt
└── .gitignore
```

## 六维能力评估

| 维度 | 定义 | 评分来源 |
|------|------|---------|
| AI技术理解 | LLM/RAG/Agent/Prompt 原理 | 相关题目正确率 |
| 评测体系搭建 | Rubric 设计 + Golden Set | 相关题目正确率 |
| 数据驱动决策 | 指标体系 + A/B + 数据飞轮 | 相关题目正确率 |
| 产品设计能力 | 0→1 产品全流程 | 相关题目正确率 |
| 商业化思维 | 定价/市场/TAM/ROI | 相关题目正确率 |
| 工程协作能力 | PRD/OKR/技术方案/跨部门 | 相关题目正确率 |

## 内容质量保障

```
URL/文件导入 → status: draft → 人工 /notes/verify → status: ready → 可出题
```

- `draft` 笔记不出题
- `ready` 笔记可出题
- L0 标准文件定义评分 rubric、能力维度、内容质量清单

## 视频导入

```
YouTube → 有字幕？→ youtube-transcript-api
        → 无字幕？→ yt-dlp 下载音频 → faster-whisper 语音转文字
        → 无字幕无描述 → 拦截，不创建空笔记
```

## License

本项目采用 GNU Affero General Public License v3.0 (AGPL-3.0)。

**商用许可**：如需将本软件用于商业目的（包括企业内部部署、SaaS 服务、嵌入商业产品），需获得单独的商用许可。

联系：baiwanwan@reforox.com

---

Built by [@baiwanwan1224-hub](https://github.com/baiwanwan1224-hub) · 2026
