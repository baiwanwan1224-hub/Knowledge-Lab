# 后端 API 重构记录 · http.server → Flask

> 状态：✅ 已完成 · 2026-07-27 · M3 + DeepSeek 7 轮对抗式对齐（v2.2）
> 范围：仅 `server/` 内部，项目顶层目录结构零改动

---

## 一、重构前后对比

### 改前（原始结构）

```
server/
├── quiz_server.py        ← 1224 行单文件，所有逻辑混在一起
├── quiz_generator.py
├── quiz_grader.py
└── vault_core.py
```

### 改后（当前结构）

```
server/
├── __init__.py           ← new   暴露 create_app()
├── app.py                ← new   Flask 入口（43 行）
├── config.py             ← new   全局配置中心（16 行）
├── errors.py             ← new   统一错误码枚举（21 行）
├── schemas.py            ← new   pydantic 请求验证（42 行）
├── blueprints/
│   ├── __init__.py       ← new   注册所有 Blueprint
│   ├── quiz.py           ← new   /quiz/generate, /quiz/grade（76 行）
│   ├── notes.py          ← new   9 个 POST + 8 个 GET（431 行）
│   └── web.py            ← new   /, /health, /dashboard（46 行）
├── quiz_generator.py     ← 不动  业务逻辑不变
├── quiz_grader.py        ← 不动  业务逻辑不变
├── vault_core.py         ← 不动  业务逻辑不变
└── quiz_server.py        ← 保留  原始备份，随时可回滚
```

**新增总行数：681 行（7 个文件） vs 原来 1224 行（1 个文件）**

## 二、解决的主要问题

| # | 问题 | 重构前 | 重构后 |
|---|------|--------|--------|
| 1 | **单文件巨型** | 1224 行全在一个文件，找代码靠翻 | Blueprint 拆分，quiz/notes/web 各司其职 |
| 2 | **路由混乱** | `if path == '/quiz/generate': ... elif ... elif ...` 11 个分支 | `@bp.route('/quiz/generate')` 装饰器，一眼看出路由 |
| 3 | **无请求验证** | 手动 `json.loads()` + 逐个 `if 'key' in body` 检查 | pydantic `BaseModel` 自动校验，字段错误自动返回 400 |
| 4 | **错误码散落** | `{"error": "invalid input"}` 字符串硬编码 | `ErrorCode` 枚举 + `error_response()` 统一入口 |
| 5 | **无法单测** | 改一行要启动整个 server 验证 | 每个 Blueprint 独立，可单独写测试 |
| 6 | **配置散落** | 白名单、大小限制躲在 handler 函数里 | `config.py` 集中管理，一处改全局生效 |
| 7 | **无扩展性** | 加一个新端点要在 1224 行里找插入位置 | 新建 Blueprint 文件，`app.py` 加一行注册 |

## 三、原则约束（严格遵守）

| 约束 | 状态 |
|------|:--:|
| 业务逻辑零改动（generator/grader/vault_core 没动） | ✅ |
| URL 路径、HTTP 方法、响应结构完全不变 | ✅ |
| 前端 `dashboard_v2.html` 的 fetch 调用不改 | ✅ |
| 纯同步 Flask（零异步依赖） | ✅ |
| 原始 `quiz_server.py` 保留为备份 | ✅ |
| 启动端口不变（5050） | ✅ |
| `.env` 加载机制不变 | ✅ |

## 四、变更明细

| 文件 | 操作 | 说明 |
|------|------|------|
| `server/__init__.py` | 新建 | 暴露 `create_app` |
| `server/app.py` | 新建 | Flask app 工厂 + 入口 |
| `server/config.py` | 新建 | 白名单、大小限制、路径集中管理 |
| `server/errors.py` | 新建 | 13 个错误码枚举 + `error_response()` |
| `server/schemas.py` | 新建 | 9 个 pydantic 请求 Schema |
| `server/blueprints/__init__.py` | 新建 | Blueprint 注册 |
| `server/blueprints/quiz.py` | 新建 | generate/grade |
| `server/blueprints/notes.py` | 新建 | import/upload/transcribe/verify/delete/paste/ocr + 8 个 GET |
| `server/blueprints/web.py` | 新建 | Dashboard + health |
| `server/quiz_server.py` | 保留 | 原始备份，可随时回滚 |
| `requirements.txt` | 更新 | 新增 `flask>=3.0` `pydantic>=2.5` |
| `start.bat` | 更新 | `python server/quiz_server.py` → `python -m server.app` |
| `start.sh` | 更新 | 同上 |

## 五、启动方式

```
# Windows（不变，双击 start.bat）
start.bat

# Mac/Linux（不变，运行 start.sh）
bash start.sh

# 或直接命令行
python -m server.app
```

## 六、回滚方式

如需回滚到原始版本：

```bash
# 启动命令改回
python server/quiz_server.py --port 5050

# 删除新增文件
rm -r server/blueprints/ server/app.py server/config.py server/errors.py server/schemas.py server/__init__.py
```

原始 `quiz_server.py` 完整保留，未修改。

---

## 七、复审修正（2026-07-27 · M3+DeepSeek 复审）

> **复审背景**：项目上传 GitHub 后定位从"纯个人本地工具"变为"个人工具 + 公开开源项目"。定位变化驱动决策反转。

### P0 · 立即做

| 项 | 原判断 | 修正后 | 反转原因 |
|------|:--:|:--:|------|
| **API Key 认证** | ❌ 不借鉴 | ✅ 轻量版 X-API-Key | 非 JWT 多租户方案，~50 行 middleware 保护 LLM 调用 |
| **Swagger 文档** | ❌ 单人维护 | ✅ flasgger 自动生成 | 写完 Schema 文档自动有，零额外维护 |

### P1 · 尽快做

| 项 | 原判断 | 修正后 | 反转原因 |
|------|:--:|:--:|------|
| **版本前缀 `/v1`** | ❌ 不借鉴 | ✅ 必做 | GitHub 公开项目需要版本管理，~2h 一次性迁移 |

### P2 · 中期做

| 项 | 触发条件 | 备注 |
|------|------|------|
| **响应 Envelope** `{code, data, message}` | 第二个非同源跨技术栈客户端出现（CLI/移动端/第三方集成） | 纯同源前端项目不触发 |
| **关键端点幂等性** | 写操作端点出现误触发/重试场景 | `Idempotency-Key` header + TTL 缓存 |
| **端点 Blueprint 分组** | 端点数 > 30 或单文件 > 500 行 | 当前 14 端点不值得拆 |

### P3 · 触发式（按需，触发条件明确）

| 项 | 触发条件 | 实现方式 | 备注 |
|------|------|------|------|
| **文件上传 multipart** | 出现"导入文档"功能需求 | 复用已有 `/notes/upload` 端点 | 当前无此功能 |
| **异步后台任务** | 出现耗时操作（>3s 解析/索引） | Celery/BackgroundTasks | 本地工具暂不需要 |
| **JWT 多用户认证** | 出现远程访问或多用户需求 | 替换当前轻量 API Key 方案 | 商业化时 |
| **限流中间件** | 出现公网部署或 SaaS 暴露 | flask-limiter | 商业化时 |
| **WebSocket 流式输出** | 出现 LLM chat 实时对话功能 | flask-socketio | 功能触发 |
| **文档摄入端点契约** | 出现"用户导入文档"需求前 | 预留 `POST /documents` `GET /documents/:id/status` | 避免后期 API 重设计 |
| **Deep document parsing API** | 出现 PDF/复杂文档解析需求 | 参考 RAGFlow 解析状态机 | 功能触发 |

---

## 八、不借鉴项（定位选择，明确不做）

以下 4 项来自 Dify 对比，**每一项都是平台必需而非质量优势**，引入只会增加复杂度而无对应收益：

| 项 | Dify 做法 | 为什么不借鉴 |
|------|---------|------|
| **路由分组策略** | `console` 管理端 + `service_api` 对外 API 双入口 | Knowledge Lab 只有一个前端客户端，无第三方 API 调用者。双路由分组 = 为不存在的场景加代码 |
| **API 文档** (Swagger) | Flask-RESTX 自动生成 | 单人项目，API 受众只有自己 + 自己的前端。Swagger UI 的维护成本（schema 注解、版本同步）高于收益（没人看） |
| **认证授权** | API Key / JWT / Workspace 多租户 | 本地单用户工具，不暴露公网。加认证 = 每次本地调用都要传 token，纯属自己折腾自己 |
| **中间件/钩子** | 登录态校验、限流、日志中间件 | 限流：1 个用户不存在流量控制需求。日志中间件：Flask 内置日志已够用。鉴权钩子：无认证则无钩子 |

> **核心原则**：每一项"不做"都有明确的理由——不是不会做，不是不想做，是**定位决定了不需要**。企业平台的基础设施 ≠ 个人工具的质量标准。

---

## 九、对抗式对齐记录

| 轮次 | 模型 | 产出 | 关键决策 |
|:--:|------|------|---------|
| 1 | M3 | 初版方案 | Blueprint 拆分 + pydantic 设计 |
| 2 | DeepSeek | 审核不通过 | 3 个关键问题（upload 签名错误/query schema 缺失/错误码不全） |
| 3 | M3 | v2.0 修订 | 补全设计 |
| 4 | DeepSeek | 审核不通过 | 2 个严重问题（调用签名/query schema） |
| 5 | M3 | v2.1 修订 | 修正所有问题 |
| 6 | DeepSeek | 审核通过 | 2 个 minor 建议 |
| 7 | M3 | v2.2 终版 | 落实 minor 建议，可进入实施 |
