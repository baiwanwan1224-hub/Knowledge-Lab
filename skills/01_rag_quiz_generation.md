---
skill_id: SKILL-001
name: RAG 自动出题
category: 核心能力
status: production
model: DeepSeek V4 Pro
created: 2026-07-26
updated: 2026-07-28
---

# RAG 自动出题 · Quiz Generation

## 做什么

扫描 Obsidian Vault 学习笔记 → 按主题匹配相关笔记 → 组装 Prompt → 调用 LLM 生成测验题 → QA 门禁校验 → 返回结构化题目。

## Prompt 模板

```
你是一位专业的 AI 产品经理考试出题专家。请根据以下学习笔记内容，生成 {count} 道测验题。

题型要求：{types}
难度等级：{difficulty}
主题领域：{topic}

出题要求：
1. 单选题：4 个选项，只有 1 个正确答案，选项要有迷惑性
2. 简答题：需要 2-5 句话回答，考察理解而非背诵
3. 场景题：给出真实工作场景，要求应用知识点解决问题
4. 每道题必须标注考查的知识点（knowledge_point）
5. 每道题必须提供详细解析（explanation）
6. 标注题目来源笔记（source_note）

参考笔记内容：
{notes_content}

请以 JSON 格式输出题目列表。
```

## 工作流程

1. **扫描 Vault**：遍历 `00_学习笔记/` + `Clippings/` + `网页提取/`，匹配 topic 关键词
2. **组装上下文**：取匹配度最高的前 5 篇笔记，提取正文内容
3. **调用 LLM**：DeepSeek V4 Pro，temperature=0.7，max_tokens=4000
4. **解析响应**：JSON 解析，容错处理（截断到最后一个 `}`）
5. **QA 门禁**：5 项检查（详见 SKILL-004）
6. **缓存结果**：SQLite 缓存，同 topic + difficulty + model_version 直接命中

## 关键参数

- `count`：题目数量（1-20，默认 5）
- `types`：题型，逗号分隔（single_choice / short_answer / scenario）
- `difficulty`：难度（easy / medium / hard）
- `temperature`：0.7（需要一定创造力但不过于随机）

## 代码入口

`server/quiz_generator.py` → `main()` → `build_prompt()` → `call_llm()` → `parse_response()` → `qa_check()`
