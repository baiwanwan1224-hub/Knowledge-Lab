# 目录结构迁移记录

> 状态：✅ 持续更新 · 2026-07-27 初版 · 2026-07-28 更新

---

## 参考来源

- `tmp/architecture/openclaw/` — 独立开发者全平台 AI 产品架构（目录组织/模块拆分/skills/docs）
- `tmp/architecture/MNN/` — 大厂开源 SDK 架构（source 七模块/schema 锁死格式/4 语 README）
- `tmp/architecture/anki/` — 垂直赛道开源典范（SM-2 → FSRS 算法 20 年演进/scheduler 独立目录）

---

## 迁移前（原始结构 · 2026-07-27 之前）

```
knowledge-lab/
├── dashboard/
│   └── dashboard_v2.html
├── server/
│   ├── quiz_server.py
│   ├── quiz_generator.py
│   ├── quiz_grader.py
│   └── vault_core.py
├── standards/
├── docs/
│   └── images/ (4张截图)
├── tools/
├── scripts/
├── templates/
├── sql/
├── vault/
├── .env / .env.example
├── .gitignore
├── README.md
├── AGENTS.md
├── LICENSE
├── requirements.txt
├── start.bat / start.sh
├── backup.bat
└── cookies.txt
```

## 第一阶段迁移（7/27 · 已确认）

```
knowledge-lab/
├── apps/web/                 ← 原 dashboard/（对标 MNN apps/ + OpenClaw apps/）
│   └── dashboard_v2.html
├── server/                   ← 原 server/（对标 MNN source/ + OpenClaw src/）
│   ├── quiz_server.py        # 已更新 dashboard 路径引用
│   ├── quiz_generator.py
│   ├── quiz_grader.py
│   └── vault_core.py
├── skills/                   ← 新建（对标 MNN skills/ + OpenClaw skills/）
├── standards/                ← 不变（对标 MNN schema/）
├── spec/                     ← 新建（对标 OpenClaw VISION.md + 对方 PM 要求）
│   ├── STRUCTURE_MIGRATION.md
│   ├── SERVER_REFACTOR_MIGRATION.md
│   ├── PRD.md
│   ├── ROADMAP.md
│   ├── RAG_PIPELINE_BENCHMARK.md
│   ├── prompts.md
│   ├── user-research.md
│   └── user-journey.md
├── docs/                     ← 扩充
│   ├── images/ (4张截图)
│   ├── architecture.md       ← 新建（M3+DeepSeek 5轮对抗式对齐）
│   └── api.md                ← 新建
├── scripts/                  ← 扩充
│   ├── vault-backup.sh
│   ├── vault-init.sh
│   └── backup.bat            ← 从根目录移入
├── tools/                    ← 不变
├── templates/                ← 不变
├── sql/                      ← 不变
├── tmp/                      ← 新建（对方 PM 直接建议）
│   ├── architecture/         # MNN + openclaw + anki
│   ├── pipeline/             # dify
│   └── modules/              # 预留
├── vault/                    ← 不变
├── .env / .env.example
├── .gitignore                # 已包含 /tmp/
├── README.md                 # 已更新目录结构图
├── AGENTS.md                 # 已更新
├── CONTRIBUTING.md           ← 新建
├── CHANGELOG.md              ← 新建
├── LICENSE
├── requirements.txt
├── start.bat
├── start.sh
├── backup.bat
└── cookies.txt
```

## 第二阶段：Flask 重构 + 质量体系（7/28 · 当前）

```
knowledge-lab/
├── apps/web/
│   └── dashboard_v2.html     # UI 全面翻新（Inter字体 + Indigo配色 + SVG图标）
├── server/                   # Flask 重构完成
│   ├── app.py                ← Flask 应用工厂（CORS + Swagger + 蓝图 + 根路由SPA）
│   ├── config.py             ← 集中配置
│   ├── constants.py          ← 端点注册表
│   ├── errors.py             ← 13 个统一错误码
│   ├── schemas.py            ← 9 个 Pydantic 模型（types 数组/字符串兼容）
│   ├── cache.py              ← SQLite LLM 响应缓存（三层失效）
│   ├── stats.py              ← LLM 调用统计
│   ├── vault_core.py         # 原子写入 + WAL + 完整性校验
│   ├── eval.py               ← 跨 LLM 评测框架
│   ├── quiz_generator.py     # RAG 出题引擎
│   ├── quiz_grader.py        # LLM 评分 + SM-2 调度
│   ├── quiz_server.py        # 原始单文件备份（1224行）
│   ├── blueprints/           ← 新建（Flask Blueprint 模块化）
│   │   ├── __init__.py       # 蓝图注册表
│   │   ├── quiz.py           # /quiz/generate + /quiz/grade
│   │   ├── notes.py          # 17 个端点（导入/OCR/CRUD/列表/统计）
│   │   └── web.py            # / + /health + /dashboard + /stats
│   └── middleware/            ← 新建
│       └── auth.py           # API Key 认证（可选的 before_request）
├── tests/                    ← 新建 — 32 个自动化测试
│   ├── conftest.py           # Flask 测试客户端 fixtures
│   ├── test_api.py           # 21 个 API 端点测试（含 types 回归保护）
│   └── test_schemas.py       # 11 个 Schema 验证测试
├── spec/                     # 新增 4 份方案文档
│   ├── MOBILE_RESPONSIVE.md  ← 移动端适配方案（P1）
│   ├── MULTI_USER_ISOLATION.md ← 多用户隔离方案（P2）
│   ├── PDF_LONG_SPLIT.md     ← 长 PDF 拆分排查
│   └── (以上 8 份 + PRD/ROADMAP/等)
├── docs/
│   └── SETUP.md              ← 新建 — 新用户完整配置指南
├── data/                     ← 运行时数据
│   ├── cache.db              # SQLite 缓存
│   ├── stats.db              # SQLite 统计
│   └── sessions/             ← 新建 — 测验历史 JSON 持久化
├── .github/workflows/        ← 新建 — CI/CD
│   └── ci.yml                # GitHub Actions（Python 3.10/3.12 + pytest）
├── vault/                    # 知识库笔记
│   ├── 00_学习笔记/
│   ├── 01_错题本/            # SM-2 错题卡按主题分目录
│   └── 06_产品层/            # L0 标准副本
├── templates/
│   ├── 模板_学习笔记.md
│   └── 模板_错题卡.md
├── .env.example              # 已补充 MINIMAX_API_KEY 说明
└── start.bat                 # 重写：自动检测Python + 安装依赖 + 打开浏览器
```

## 变更明细（全量）

| # | 日期 | 操作 | 内容 |
|---|:--:|------|------|
| 1 | 7/27 | 迁移 | `dashboard/` → `apps/web/` |
| 2 | 7/27 | 新建 | `skills/` `spec/` `tmp/` |
| 3 | 7/27 | 新建 | `CONTRIBUTING.md` `CHANGELOG.md` |
| 4 | 7/27 | 新建 | `docs/architecture.md` `docs/api.md` |
| 5 | 7/28 | Flask重构 | `server/` 拆分为 blueprints/ + middleware/ + 8 个模块文件 |
| 6 | 7/28 | 新建 | `tests/` — 32 个 pytest 用例（21 API + 11 Schema） |
| 7 | 7/28 | 新建 | `.github/workflows/ci.yml` |
| 8 | 7/28 | 新建 | `data/sessions/` — 测验历史持久化 |
| 9 | 7/28 | 新建 | `docs/SETUP.md` — 新用户配置指南 |
| 10 | 7/28 | 新建 | `spec/MOBILE_RESPONSIVE.md` `spec/MULTI_USER_ISOLATION.md` `spec/PDF_LONG_SPLIT.md` |
| 11 | 7/28 | 更新 | `dashboard_v2.html` UI 全面翻新（Inter+Indigo+SVG） |
| 12 | 7/28 | 更新 | `.env.example` 补充 MINIMAX_API_KEY 说明 |
| 13 | 7/28 | 更新 | `start.bat` 重写（自动检测+安装+启动） |
| 14 | 7/28 | 更新 | `requirements.txt` 补充 flasgger |

## 后续待办

- [x] spec/ 内 PRD / user-research / user-journey（✅ 7/27 完成）
- [x] skills/ 内项目级 Skill 定义（✅ 7/28 — 7 个技能文件）
- [ ] VISION.md（对标 OpenClaw，可放 spec/ 内）
- [ ] SECURITY.md
- [ ] server/ 内部拆分为 api/ core/ providers/（等代码规模再大一些）
