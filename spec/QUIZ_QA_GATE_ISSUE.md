# 出题 QA 门禁过严问题 · 排查记录

> P1 · 2026-07-28 发现 · ✅ 2026-07-29 修复

## 根因

1. **LLM 返回不带 `questions` 字段的 JSON** → `result.get('questions', [])` = `[]` → API 返回 `status: "success"` 但零题目
2. **前端未处理空 questions** → `quizData.questions[0]` = `undefined` → `renderQuiz()` 在渲染题目卡片时崩，`resetQuizSetup()` 未隐藏 `quizArea`，导致僵尸按钮 UI
3. **非选择题 QA 评分不公平** — 简答/场景题最大 3 分但分母用 5 → 天生劣势

## 修复内容 (2026-07-29)

| 修复 | 文件 | 说明 |
|------|------|------|
| QA 评分按题型归一化 | `quiz_generator.py` | 选择题 /5，简答&场景 /3 |
| explanation 阈值降低 | `quiz_generator.py` | 20 → 10 字符 |
| 空 questions 调试日志 | `quiz_generator.py` | LLM 返回 0 题时 stderr 打印 raw content |
| 前端空 questions 检查 | `dashboard_v2.html` | 生成后检查 `questions.length === 0`，显示 toast 并重置 |
| resetQuizSetup 补隐藏 | `dashboard_v2.html` | 补 `quizArea.classList.add('hidden')` |
| eval.py 同步 | `eval.py` | QA 评分逻辑同步更新 |
