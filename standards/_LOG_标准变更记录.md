---
type: log
title: 标准变更记录
created: 2026-07-25
scope: 所有 _STANDARD_ 文件的变更历史
---

# _LOG_ 标准变更记录

> L1 · 记录所有 L0 标准文件的版本变更
> 每次变更 = 新条目 · 旧版本保留于 Git 历史

---

## 变更历史

### 2026-07-25 · v1.0 · 初始建立

**创建文件**：
- `_STANDARD_评分标准.md` v1.0 — 三类题型 rubric + SM-2 参数 + 质量阈值
- `_STANDARD_能力维度.md` v1.0 — 六维能力定义 + 评分基准 + 计算逻辑
- `_STANDARD_内容质量.md` v1.0 — 笔记质量清单 + 状态流转 + URL 导入流程
- `_STANDARD_命名规范.md` v1.0 — 文件名格式 + frontmatter 规范 + 迁移指引

**影响范围**：
- quiz_server.py：启动时加载标准文件，注入到 LLM prompts
- quiz_grader.py：引用评分标准 rubric
- quiz_generator.py：引用内容质量 QA 标准
- dashboard_v2.html：能力雷达图引用维度定义

**关联组件**：
- 新增 POST /notes/verify 端点
- 新增 GET /notes/drafts 端点
- URL 导入默认 status 改为 draft

---

## 待校准项

| 项目 | 状态 | 说明 |
|------|:--:|------|
| Golden Test Set (5题) | ✅ 8/5 | `data/golden_set.json` 5 题 + `scripts/golden_regression.py` · 首跑 5/5 通过（G003-005 dev=1.0 临界：LLM 偏严约 1 分）· 每周回归 |
| 双模型评分校准 | ⬜ | GPT-4.1 vs DeepSeek 评分偏差追踪 |
| 能力维度权重调优 | ⬜ | 等待 ≥ 50 次测验数据后首次调参 |
| SM-2 参数验证 | ⬜ | 等待 ≥ 30 天复习数据后验证间隔合理性 |

---

## 变更模板

```markdown
### YYYY-MM-DD · vX.Y · 变更简述

**变更文件**：_STANDARD_xxx.md → vX.Y
**变更内容**：
- xxx

**影响范围**：quiz_server.py / quiz_grader.py / ...

**迁移动作**：
- [ ] 更新 Python 脚本
- [ ] 更新 dashboard 引用
- [ ] 通知用户
```
