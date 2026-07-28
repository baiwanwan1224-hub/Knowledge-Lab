# Knowledge Lab · AI Agent 上下文

> 本项目 AI 入口。任何 AI 工具（Trae Work / Claude Code / Codex）打开本项目首先读本文件。
> L0 标准原文在 `standards/` 目录，此处只放摘要。

---

## 项目定义

Knowledge Lab = RAG 驱动的自测学习平台
- 后端：Python HTTP Server（标准库，无框架）→ `server/quiz_server.py`
- 前端：纯 HTML/CSS/JS SPA（零依赖）→ `dashboard/dashboard_v2.html`
- Vault：Obsidian 笔记库 → `C:\Users\27224\Documents\Obsidian Vault\Knowledge Lab`
- AI 引擎：DeepSeek V4 Pro（默认），支持 OpenAI / Zhipu / Ollama 切换
- 语音：faster-whisper (tiny) + yt-dlp
- 数据：默认 JSON 文件，可选 PostgreSQL

---

## 启动方式

```bash
# Windows
start.bat

# Mac/Linux
bash start.sh
```

服务运行在 `http://localhost:5050`

---

## API 端点（14个）

### POST
- `/quiz/generate` — 基于笔记生成测验题
- `/quiz/grade` — 批改答案 + SM-2 错题卡
- `/notes/import` — URL 导入（含 YouTube 字幕）
- `/notes/upload` — 上传 PDF/MD/TXT
- `/notes/transcribe` — YouTube 视频转录
- `/notes/verify` — 确认笔记（draft → ready）
- `/notes/delete` — 删除笔记
- `/notes/paste` — 粘贴文本导入
- `/notes/screenshot_ocr` — 截图 OCR（需 MiniMax M3）

### GET
- `/` → Dashboard SPA
- `/health` / `/topics` / `/notes` / `/note` / `/notes/drafts`
- `/competency` — 六维雷达图
- `/history` / `/wrong-answers` / `/dashboard`

---

## L0 不可变标准

| ID | 名称 | 核心 |
|----|------|------|
| L0-001 | 评分标准 | 单选 0/1 · 简答/场景 0-5 · ≥70%及格 · SM-2 间隔重复 |
| L0-002 | 能力维度 | AI技术理解/评测体系/数据驱动/产品设计/商业化/工程协作 · 6维雷达图 |
| L0-003 | 内容质量 | 5项检查（概念准确/有案例/可出题/来源可追溯/格式规范）· draft→ready→outdated |
| L0-004 | 命名规范 | `YYYYMMDD_{主题}_{来源标签}.md` · 来源标签：手动/URL/GH/课程/LLM |

---

## 项目结构

```
knowledge-lab/
├── apps/web/        ← 客户端：Web SPA 前端
├── server/          ← 后端：API + RAG + 评分 + Vault
├── skills/          ← 项目级 AI 技能定义
├── standards/       ← L0 不可变标准
├── spec/            ← PRD、用户研究、架构文档
├── docs/images/     ← 截图
├── scripts/         ← 启动 + 备份脚本
├── tools/           ← 开发工具
├── templates/       ← Obsidian 笔记模板
├── sql/             ← PostgreSQL DDL
├── tmp/             ← 参考项目 (dify/MNN/openclaw, gitignored)
└── vault/           ← 本地知识库
```

## Vault 结构

```
Knowledge Lab/
├── 00_学习笔记/     ← 198 篇笔记（LENNY/PM_amplitude/PM_phuryn/PM_kalyvask）
├── 01_错题本/       ← SM-2 间隔重复错题卡
├── 06_产品层/       ← L0 标准 + 变更日志
└── .vault-meta/     ← 完整性追踪
```

---

## 笔记格式

```yaml
---
type: note
topic: 主题
topics: [标签1, 标签2]
difficulty: medium
status: draft | ready | needs_revision | outdated
source_url: https://...
created: 2026-07-26
---
```

只有 `status: ready` 的笔记才能用于出题。

---

## 启用的 Skills

| Skill | 用途 |
|-------|------|
| note-auditor | 按 L0-003 审核文档质量 |
| quiz-generator | 基于材料生成测验题 |
| rubric-grader | 按 L0-001 标准评分 |
| skill-creator | 封装新 Skill |
| brainstorming | 结构化头脑风暴 |
| pdf | PDF 内容提取 |
| frontend-design | UI 设计/优化 |
| ui-ux-pro-max | 67风格+96色板+57字体 |

---

## 默认 LLM 配置

| 场景 | 模型 |
|------|------|
| 日常主力 | DeepSeek V4 Pro |
| 质量审核 | MiniMax M3 |
| 英文内容 | GPT-4.1（星链4SAPI） |
| 本地离线 | Ollama (qwen2.5:7b) |
