---
skill_id: SKILL-003
name: AI 内容结构化
category: 内容处理
status: production
model: DeepSeek V4 Pro
created: 2026-07-26
updated: 2026-07-28
---

# AI 内容结构化 · Content Structuring

## 做什么

接收原始文本（URL 网页、粘贴文章、PDF 提取文字）→ 调用 LLM 结构化 → 输出格式化的 Markdown 学习笔记。

## 结构化 Prompt

```
请将以下文本整理为结构化的 Markdown 笔记。添加合适的标题、分段、列表。保留所有原始信息，只调整格式：

{raw_text}
```

## 处理策略

| 输入类型 | 处理方式 |
|------|------|
| URL 网页 | MCP fetch 抓取 → 提取正文 → LLM 结构化（限 10000 字） |
| 粘贴文本 | 直接结构化（上限 500K 字） |
| PDF 文本 | PyPDF2 逐页提取 → LLM 结构化（每段 30000 字 × 不限 tokens） |
| 截图 OCR | MiniMax M3 多模态识别 → 直接保存 Markdown |
| .md .txt 文件 | 已有 Markdown 格式的直接保存，纯文本的走结构化 |

## 长文档处理

- 单段 ≤ 30000 字
- 超过则按段落边界切分，每段独立结构化
- 长段失败回退到原始文本（不丢弃内容）
- 每段标注 `(第 N/M 部分)`

## 输出规范

- 自动提取首行 `# 标题` 作为文件标题
- 生成 YAML frontmatter（title / topics / source / date / status）
- 文件名 = 日期 + 原始文件名
- 状态：draft（待用户审核确认）

## 代码入口

`server/blueprints/notes.py` → `_ai_structure()` | `_save_note()`
