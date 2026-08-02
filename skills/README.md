# Knowledge Lab · AI Skills

> 通过 Vibe Coding 积累的 AI 协作技能清单。每个技能是一个可复用的方法论。
> 对标 MNN skills/ + OpenClaw skills/ — 2026 年 AI-native 项目标配。

---

## 技能索引

| ID | 技能 | 分类 | 状态 | 代码位置 |
|:--:|------|------|:--:|------|
| SKILL-001 | [RAG 自动出题](01_rag_quiz_generation.md) | 核心能力 | ✅ | `server/quiz_generator.py` |
| SKILL-002 | [AI 评分 + SM-2](02_ai_grading_sm2.md) | 核心能力 | ✅ | `server/quiz_grader.py` |
| SKILL-003 | [AI 内容结构化](03_content_structuring.md) | 内容处理 | ✅ | `server/blueprints/notes.py` |
| SKILL-004 | [QA 出题质量门禁](04_qa_gate.md) | 质量保障 | ✅ | `server/quiz_generator.py` |
| SKILL-005 | [截图 OCR 多模态识别](05_screenshot_ocr.md) | 内容处理 | ✅ | `server/blueprints/notes.py` |
| SKILL-006 | [Vault 防丢架构](06_vault_anti_loss.md) | 基础设施 | ✅ | `server/vault_core.py` |
| SKILL-007 | [Vibe Coding Prompt 工程](07_prompt_engineering.md) | 开发方法论 | ✅ | `spec/prompts.md` |
| SKILL-008 | [数据清洗管线](08_data_cleaning_pipeline.md) | 数据处理 | ✅ | `server/html_cleaner.py` · `server/dedup.py` · `server/quality_gate.py` |

---

## 为什么有这些技能

Knowledge Lab 不是传统手写代码的项目——90% 的代码是通过 Claude Code（Vibe Coding）生成的。但这些不是"让 AI 瞎写"，每个功能背后都有：

1. **精心设计的 Prompt 模板**（见 SKILL-001/002/003/005）
2. **不可变的 QA 标准**（见 SKILL-004 + standards/）
3. **自动化的验证机制**（pytest + QA Gate + 缓存命中率监控）
4. **防丢的基础设施**（见 SKILL-006）

这些都是 Vibe Coding 产品工程师的核心竞争力——不只是会调 API，而是构建了完整的"AI 协作生产线"。

## 技能驱动开发（Skill-Driven Development）

```
发现问题 → 设计 Prompt → 验证 Prompt（对抗式求解）→ 写代码（AI 生成）→ QA 门禁 → 上线
                                                      ↑______________|
                                                    人工审核 + 自动测试
```
