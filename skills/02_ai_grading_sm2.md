---
skill_id: SKILL-002
name: AI 评分 + SM-2 间隔重复
category: 核心能力
status: production
model: DeepSeek V4 Pro
created: 2026-07-26
updated: 2026-07-28
---

# AI 评分 + SM-2 间隔重复 · Grading & Spaced Repetition

## 做什么

用户提交答案 → LLM 逐题评分（按 L0-001 Rubric）→ 错题触发 SM-2 调度 → 生成错题卡写入 Vault → 返回评分结果和能力反馈。

## 评分 Rubric（L0-001）

| 题型 | 满分 | 评分标准 |
|------|:--:|------|
| 单选题 | 1 | 选对 1 分，选错 0 分 |
| 简答题 | 5 | 0=完全错误/空白 · 1-2=方向对但不完整 · 3-4=基本正确 · 5=完美（含关键概念+具体例子） |
| 场景题 | 5 | 同上 + 额外考察"是否结合真实场景" |

≥70% 为及格线

## 评分 Prompt

```
你是 AI 产品管理领域的评分专家。请根据以下标准评分。

题目：{question}
标准答案：{correct_answer}
用户答案：{user_answer}
满分：{max_score} 分
题型：{type}

请从以下维度评估：
1. 答案准确性（是否理解核心概念）
2. 答案完整性（是否覆盖关键要点）
3. 表达清晰度（是否逻辑清晰）
4. 实践结合度（场景题适用：是否结合真实场景）

输出 JSON：{ score, is_correct, feedback, strengths[], gaps[], weakness_tags[], misunderstanding }
```

## SM-2 算法

```
quality = (score / max_score) * 5

if quality >= 3:  # 答对
    if review_count == 0: interval = 1, ease = 2.5
    elif review_count == 1: interval = 6, ease = 2.5
    else: ease += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
          interval = round(current_interval * ease)
else:  # 答错
    interval = 1, ease = ease_factor

next_review = now + interval 天
```

- `ease_factor`：最小 1.3
- `review_count`：每次复习 +1
- 错题卡写入 `vault/01_错题本/{主题}/错题_{日期}_{题目摘要}.md`

## 代码入口

`server/quiz_grader.py` → `main()` → `grade_answer()` → `sm2_schedule()` → `write_wrong_answer_card()`
