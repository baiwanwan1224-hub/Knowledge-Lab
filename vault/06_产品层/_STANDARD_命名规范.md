---
type: standard
standard_id: L0-004
title: 命名与元数据规范
version: 1.0
created: 2026-07-25
immutable: true
scope: 所有知识库笔记, quiz_server.py /notes/import
---

# _STANDARD_ 命名与元数据规范 v1.0

> L0 不可变 · 所有笔记文件必须遵守
> 变更必须记录到 `_LOG_标准变更记录.md`

---

## 一、文件名规范

### 格式

```
YYYYMMDD_{主题简写}_{来源标签}.md
```

### 字段说明

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| `YYYYMMDD` | 8 位日期 | `20260725` | 导入或创建日期 |
| `{主题简写}` | 中文或英文 slug | `AI-PM能力模型` / `context-engineering` | 建议 ≤ 40 字符 |
| `{来源标签}` | 固定标签词 | `手动` `URL` `GH` `课程` `LLM` | 见下表 |

### 来源标签

| 标签 | 含义 | 使用场景 |
|------|------|---------|
| `手动` | 手动撰写 | 自己写的笔记、总结 |
| `URL` | URL 导入 | 网页文章自动导入 |
| `GH` | GitHub 仓库 | 从 GitHub 拆解的技能文档 |
| `课程` | 在线课程 | 吴恩达、李宏毅等课程笔记 |
| `LLM` | LLM 生成 | AI 生成的摘要或整理 |

### 示例

- `20260725_AI产品经理核心能力_手动.md`
- `20260725_context-engineering_GitHub技能_GitHub.md` → `20260725_context-engineering_GH.md`
- `20260725_LLM评测最佳实践_URL.md`
- `20260725_吴恩达AI入门_课程.md`

### 模板文件

模板文件前缀 `模板_`，不参与出题：
- `模板_学习笔记.md` — 通用笔记模板
- `模板_错题卡.md` — 错题卡模板

---

## 二、Frontmatter 规范

### 必填字段

```yaml
---
type: study-note          # 固定值
topic: 主分类              # 1 个主要分类，必须匹配已有分类
topics: [分类1, 分类2]     # 多个分类标签
source: 来源描述           # 人类可读的来源
source_url: https://...    # 来源链接（可选但推荐）
difficulty: medium         # easy | medium | hard
status: draft              # draft | ready | outdated | archived
created: YYYY-MM-DD        # 创建日期
---
```

### 可选字段

```yaml
imported: ISO-8601         # URL 导入的精确时间
verified: YYYY-MM-DD       # 人工确认日期
review_count: 0            # 被测验引用的次数
quality_score: 0.0-1.0    # LLM 自动质量评分
tags: [tag1, tag2]         # 自由标签
updated: YYYY-MM-DD        # 最后修改日期
```

### 类型对照

| 旧字段名 (废弃) | 新字段名 | 说明 |
|----------------|---------|------|
| `topic` (单数) | `topics` (复数数组) | 统一用数组 |
| `source_url` | `source_url` | 保持不变 |
| `url` | `source_url` | URL 导入改用 `source_url` |
| `type: learning-note` | `type: study-note` | 统一类型名 |
| — | `source` | 新增：人读来源描述 |

---

## 三、内容结构规范

每篇笔记建议包含以下章节（参考 `模板_学习笔记.md`）：

1. **核心概念** — 2-3 句话概括
2. **详细内容** — 主要知识点
3. **关键框架** — 框架/模型/方法论
4. **实践案例** — 实际例子
5. **可出题的知识点** — 至少 2 个出题点（checklist 格式）
6. **参考资源** — 相关链接

---

## 四、标准化迁移指引

对现有 32 篇笔记的处理：

| 现命名模式 | 数量 | 处理方式 |
|-----------|:--:|------|
| `AI产品经理核心能力模型.md` | 1 | 重命名为 `20260724_AI产品经理核心能力_手动.md` |
| `20260724_*_PM方法论.md` | 30 | 不重命名（避免破坏引用），新笔记用新规范 |
| `模板_*.md` | 2 | 更新 frontmatter 为标准格式 |
| URL 导入新笔记 | — | 全部使用新规范 |
