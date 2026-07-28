---
skill_id: SKILL-004
name: QA 出题质量门禁
category: 质量保障
status: production
created: 2026-07-26
updated: 2026-07-28
---

# QA 出题质量门禁 · Quality Assurance Gate

## 做什么

LLM 生成的每道题在交付给用户前，自动通过 5 项 QA 检查。未通过的题目直接丢弃，保证出题质量。

## 5 项检查

| # | 检查项 | 标准 | 不通过扣分 |
|:--:|------|------|:--:|
| 1 | 题干完整性 | ≥ 10 字符，不是占位符 | ❌ 直接丢弃 |
| 2 | 解析长度 | ≥ 20 字符（简答/场景题） | -20% |
| 3 | 选项数量 | 单选题 = 4 个选项 | ❌ 直接丢弃 |
| 4 | 答案有效性 | 单选题答案必须是 A/B/C/D | ❌ 直接丢弃 |
| 5 | 知识点标注 | knowledge_point 字段不能为空 | -10% |

- quality_score < 0.5 → 丢弃
- 0.5 ≤ quality_score < 1.0 → 保留但标记 quality_issues
- quality_score = 1.0 → 完美通过

## 为什么需要

- LLM 偶尔生成不完整题目（题干截断、选项缺失）
- JSON 解析容错（截断到最后一个 `}`）
- 没有 QA Gate 之前，出题失败率约 15%，之后 < 5%

## 代码入口

`server/quiz_generator.py` → `qa_check()`
