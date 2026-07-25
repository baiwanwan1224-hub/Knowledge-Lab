---
type: standard
standard_id: L0-003
title: 内容质量标准
version: 1.0
created: 2026-07-25
immutable: true
scope: quiz_generator.py, quiz_server.py /notes/import, 知识库管理
---

# _STANDARD_ 内容质量标准 v1.0

> L0 不可变 · 所有入库内容的质量门禁
> 变更必须记录到 `_LOG_标准变更记录.md`

---

## 一、笔记质量检查清单

每篇笔记进入知识库前，必须通过以下 5 项检查：

| # | 检查项 | 判定标准 | 不通过后果 |
|---|--------|---------|-----------|
| 1 | **概念准确** | 核心概念描述与行业公认定义一致，无事实错误 | ❌ 标记 `draft`，人工修正 |
| 2 | **有案例** | 至少 1 个实践案例或应用场景 | ⚠️ 可入库但标记 `needs_example` |
| 3 | **可出题** | 至少 2 个明确的出题点 | ⚠️ 可入库但不出题 |
| 4 | **来源可追溯** | 有 `source_url` 或 `source` 字段 | ❌ 标记 `draft`，需补充来源 |
| 5 | **格式规范** | 符合 `_STANDARD_命名规范.md` 的 frontmatter 要求 | ⚠️ 自动补全缺失字段 |

---

## 二、内容状态流转

```
         ┌─────────┐
         │ clipped │  从 Web Clipper / URL 导入
         └────┬────┘
              ↓
         ┌─────────┐
         │  draft  │  ← 默认导入状态，等待人工确认
         └────┬────┘
              ↓ (人工确认 / POST /notes/verify)
         ┌─────────┐
         │  ready  │  ← 已确认，可用于出题
         └────┬────┘
              ↓ (内容过时 / 新信息出现)
         ┌──────────┐
         │ outdated │  标记为过时，不再出题
         └──────────┘
```

| 状态 | 出题可用 | 说明 |
|------|:--:|------|
| `draft` | ❌ | 新导入/待确认，不出题 |
| `ready` | ✅ | 已确认，可用于出题 |
| `needs_example` | ✅ | 可出题但缺少案例 |
| `outdated` | ❌ | 内容过时，待更新或归档 |
| `archived` | ❌ | 已归档 |

---

## 三、URL 导入验证流程

```
URL 输入
  ↓
1. 抓取网页内容（requests + 文本提取）
  ↓
2. LLM 提取核心内容 + 自动归类
  ↓
3. 保存为笔记（status: draft）
  ↓
4. 用户点击"确认入库" → status 变为 ready
  ↓  （或在 Obsidian 中手动改 frontmatter status）
5. 笔记可被出题系统使用
```

**导入防污染机制**：
- 导入的笔记默认 `status: draft`
- 仪表盘知识库显示 draft 笔记（灰色标记）
- 出题时不使用 draft 笔记
- 用户需要手动验证内容准确性后改为 `ready`

---

## 四、出题质量门禁 (QA Check)

出题后对每道题进行自动化质量检查：

| 检查项 | 通过条件 | 权重 |
|--------|---------|:--:|
| 题干完整 | 题目文本 ≥ 10 字符 | 1/5 |
| 解析充分 | 解析文本 ≥ 20 字符 | 1/5 |
| 选项完整 | 单选题必须恰好 4 个选项 | 1/5 |
| 答案有效 | correct_answer 存在于选项中 | 1/5 |
| 知识点标注 | 有 knowledge_point 字段 | 1/5 |

**质量分** = 通过项数 / 5，≥ 0.6 (3/5) 视为通过。

连续 3 次 QA 不通过 → 暂停出题，检查 prompt 或模型。

---

## 五、内容验证 API

### POST /notes/verify
```json
{
  "file": "20260725_xxx_URL.md",
  "action": "approve|reject"
}
```

- `approve`：将 status 从 `draft` 改为 `ready`
- `reject`：将 status 从 `draft` 改为 `needs_revision`，附加原因

### GET /notes/drafts
返回所有 status 为 `draft` 的笔记列表，用于人工审核队列。
