---
skill_id: SKILL-008
name: 数据清洗管线
category: 数据处理
status: production
created: 2026-08-01
updated: 2026-08-01
---

# 数据清洗管线 · Data Cleaning Pipeline

## 做什么

将任意来源的原始内容（URL/PDF/YouTube/截图/粘贴）导入 Knowledge Lab 时，自动执行 7 步数据清洗，确保入库内容质量可控。

## 清洗管线（7 层）

```
原始输入 → HTML清洗 → 转录降噪 → 空源检测 → LLM结构化 → 去重检查 → 质量门禁 → Obsidian Vault
```

| 层 | 模块 | 功能 |
|:--:|------|------|
| 1 | `html_cleaner.py` | 去 script/style/nav/footer → 实体解码 → 主内容提取 |
| 2 | `transcription_cleaner.py` | 去时间戳/说话人标签/重复行/填充词 → 段落分段 |
| 3 | `frontmatter_utils.py` | 统一 YAML frontmatter 解析/构建，前后端一致 |
| 4 | 空源检测 | 内容 <100 字符 → 标记 `[CONTENT_EMPTY]` → 拒绝入库 |
| 5 | LLM 结构化 | 原始文本 → 结构化 Markdown，反幻觉指令 |
| 6 | `dedup.py` | SHA-256 精确匹配 + 5-gram Jaccard 近似匹配（阈值 0.85） |
| 7 | `quality_gate.py` | L0-003 质量门禁 · 仅 `status: ready` 用于出题 |

## 设计原则

1. **先清洗再入库** — 不在 Vault 里存垃圾
2. **非破坏性** — 清洗发生在导入管道，原始数据可回溯
3. **逐层防御** — 每层独立验证，任意层拒绝则整条管道终止
4. **透明可观测** — 每层操作打日志，问题可追溯

## 为什么需要这些

### 实锤案例

| 问题 | 后果 | 修复 |
|------|------|------|
| 飞书 URL 导入 → SSR JS 代码被当作文本结构化 | 笔记内容为 "SSR 布局与初始化脚本整理" | HTML 清洗去 script 块 |
| 知乎 URL 抓取失败 → LLM 编造整篇文章 | 虚构笔记 "AI 产品经理在跨境电商中的实践" | 空源检测拒绝入库 |
| Rick Astley MV 转录 → 分类为学习笔记 | 无意义内容混入知识库 | 转录降噪 + 质量闸门 |
| 205 篇笔记 0 篇 ready → 测验无法出题 | 质量完全失控 | L0-003 代码化 + 批量审核 |
| 同 URL 导两次 → 两份副本 | 知识库膨胀 | SHA-256 + Jaccard 去重 |

## 差异化

网页端 ChatGPT/Claude 能做到：
- ❌ HTML 自动清洗（需手动粘贴纯文本）
- ❌ 去重检测
- ❌ 增量管理（每次对话独立）
- ❌ 本地存储（Obsidian vault）
- ❌ 空源检测

本管线全做到。

## 代码位置

| 模块 | 文件 |
|------|------|
| HTML 清洗 | `server/html_cleaner.py` |
| 转录降噪 | `server/transcription_cleaner.py` |
| Frontmatter 统一 | `server/frontmatter_utils.py` |
| 去重引擎 | `server/dedup.py` |
| 质量门禁 | `server/quality_gate.py` |
| 导入管线 | `server/blueprints/notes.py` |
| 分类管线 | `server/classifier.py` |

## CLI 工具

```bash
# 扫描现有知识库的重复笔记
python server/dedup.py --scan --dir vault/Knowledge Lab/00_学习笔记

# 合并重复（保留旧版，合并 topic，删除新版）
python server/dedup.py --merge --execute --dir vault/Knowledge Lab/00_学习笔记

# 批量晋升草稿为 ready
python -c "from server.quality_gate import batch_promote; print(batch_promote(dry_run=True))"
```
