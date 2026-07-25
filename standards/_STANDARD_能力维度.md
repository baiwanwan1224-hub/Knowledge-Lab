---
type: standard
standard_id: L0-002
title: 能力维度定义
version: 1.0
created: 2026-07-25
immutable: true
scope: quiz_server.py /competency, dashboard_v2.html 雷达图
---

# _STANDARD_ 能力维度定义 v1.0

> L0 不可变 · 六维能力雷达图的数据来源和评分基准
> 变更必须记录到 `_LOG_标准变更记录.md`

---

## 一、六大维度定义

### 1. AI技术理解
- **定义**：对 AI/LLM 核心技术概念的理解程度，不需要写代码但需要懂原理
- **核心知识点**：
  - LLM 工作原理 (Token, Context Window, Temperature, Top-P)
  - RAG 架构 (Chunking, Embedding, 检索策略)
  - Agent 架构 (Tool Calling, Memory, Multi-Agent)
  - Prompt Engineering (System Prompt, Few-shot, CoT)
  - 模型选型 (GPT vs Claude vs DeepSeek vs Gemini 的能力边界)
- **关键词匹配**：AI技术, LLM, GPT, Claude, embedding, RAG, token, context, prompt, agent, orchestration, model, 模型
- **评分来源**：该维度相关题目的正确率 + 错题卡的 SM-2 掌握度

### 2. 评测体系搭建
- **定义**：设计 AI 产品评测体系的能力，这是 AI PM 最重要的差异化能力
- **核心知识点**：
  - 评分 Rubric 设计 (准确度/完整度/语气/格式)
  - LLM-as-Judge (自动评分)
  - Golden Dataset (人审过的标准答案集)
  - Bad Case 库 (幻觉/拒答/格式错/风格偏分类)
  - 线上监控 (模型输出质量持续追踪)
- **关键词匹配**：评测, 评估, evaluation, benchmark, golden, metric, accuracy, quality, rubric, 质量
- **评分来源**：该维度相关题目的正确率

### 3. 数据驱动决策
- **定义**：用数据驱动产品决策的能力
- **核心知识点**：
  - 指标体系 (北极星指标 + 过程指标 + 护栏指标)
  - A/B 测试 (实验设计 + 统计显著性)
  - 用户反馈闭环 (满意度 → NPS → 留存率 → 复购率)
  - 数据飞轮 (用户行为 → 标注数据 → 模型优化 → 更好体验)
  - SaaS 指标 (MRR, Churn, LTV, CAC)
- **关键词匹配**：数据, data, analytics, A/B, ab test, metric, NSM, north star, SaaS, 指标
- **评分来源**：该维度相关题目的正确率

### 4. 产品设计能力
- **定义**：0→1 产品设计全流程能力
- **核心知识点**：
  - 需求定义 → PRD → 原型 → MVP → 迭代
  - AI UX 设计 (对话式交互、容错机制、置信度展示)
  - 优先级框架 (RICE, Kano, MoSCoW)
  - 竞品分析 (功能对比、体验走查、技术栈分析)
  - 用户研究 (Discovery, JTBD, User Story Mapping)
- **关键词匹配**：用户故事, user story, PRD, JTBD, 优先级, priorit, 路线图, roadmap, discovery, 产品设计, positioning, 定位, problem framing, 竞品分析
- **评分来源**：该维度相关题目的正确率

### 5. 商业化思维
- **定义**：理解商业模式和市场竞争的能力
- **核心知识点**：
  - 定价模型 (SaaS 订阅 vs API 按量 vs Freemium)
  - 单位经济学 (Token 成本 vs 用户付费)
  - 市场格局 (开源 vs 闭源、大厂 vs 创业公司)
  - ROI 计算 (AI 项目的投入产出比)
  - TAM/SAM/SOM 市场容量分析
- **关键词匹配**：商业化, TAM, SAM, SOM, revenue, 收入, 定价, pricing, 市场, competitive, 竞争, 战略, business
- **评分来源**：该维度相关题目的正确率

### 6. 工程协作能力
- **定义**：与工程团队高效协作的能力
- **核心知识点**：
  - PRD/BRD/MRD 文档
  - OKR 制定与追踪
  - 技术方案评审 (RAG vs 微调 vs Prompt)
  - 跨部门协作 (算法/工程/设计/运营)
  - Stakeholder Management
  - Epic Hypothesis, Story Mapping
- **关键词匹配**：工程, stakeholder, 协作, epic, story mapping, 开发, 技术方案
- **评分来源**：该维度相关题目的正确率 + 错题卡 SM-2 数据

---

## 二、评分基准

| 参数 | 值 | 说明 |
|------|-----|------|
| 默认分数 | 50% | 未评估维度的中性基准 |
| 最低分 | 10% | 评估下限（防止极端值） |
| 最高分 | 95% | 评估上限（不设 100%） |
| 掌握门槛 | ≥ 70% | 该维度视为掌握 |
| 需加强 | 40%-69% | 需要重点学习 |
| 薄弱 | < 40% | 需要从基础重新学习 |

---

## 三、分数计算逻辑

```
维度得分 = (该维度正确题数 × 5 / 该维度总题数 / 5) × 100

如果该维度无数据 → 使用默认基准 50
如果该维度有错题卡 → 错题卡得分权重 0.3，答题得分权重 0.7
```

---

## 四、能力评估输出格式

```json
{
  "competency": {
    "AI技术理解": 10,
    "评测体系搭建": 20,
    "数据驱动决策": 10,
    "产品设计能力": 20,
    "商业化思维": 50,
    "工程协作能力": 10
  },
  "weakest": [{"dim": "AI技术理解", "score": 10}, ...],
  "strengths": [{"dim": "商业化思维", "score": 50}, ...],
  "recommendation": "基于标准 v1.0 生成的学习建议",
  "standard_version": "1.0",
  "assessed_at": "..."
}
```
