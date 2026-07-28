# Vibe Coding · Prompt Engineering 实践记录

> 5 条高质量 Claude Code Prompt 模板 · 均来自 Knowledge Lab 开发实战 · 2026-07-27

---

## Prompt 1：参考竞品架构重构项目目录

**场景**：需要把 Knowledge Lab 从扁平结构重构为 MNN/openclaw 风格

**给 Claude Code 的指令**：
```
参考 tmp/architecture/openclaw 和 tmp/architecture/MNN 的目录组织方式，
将当前项目重构为：
- apps/web/    放 dashboard 前端（对标 openclaw apps/ + MNN apps/）
- server/      保持后端不动
- skills/      新建，对标两者 skills/
- standards/   不变，对标 MNN schema/
- spec/        新建，放产品文档（对标 openclaw VISION.md）
- docs/        放技术文档 + 截图
- scripts/     放启动和备份脚本（对标 openclaw scripts/）
- tmp/         放参考项目，按 architecture/pipeline/modules 三分

约束：
- dashboard/ → apps/web/，别动业务逻辑
- 更新 quiz_server.py 里的 dashboard 路径引用
- 别动 server/ 里的任何 import 关系
```

**实际效果**：一次性完成，dashboard 路径更新、backup.bat 归类、start.bat 引用同步更新，0 报错。

**关键经验**：把"参考 XX"和"别动 YY"同时写进 prompt，AI 不会自作主张。

---

## Prompt 2：M3 + DeepSeek 对抗式出技术文档

**场景**：需要产出 architecture.md 和 api.md，要求两个模型对齐后输出

**给 Claude Code 的指令**：
```
用对抗式求解器跑：为 Knowledge Lab 设计 docs/architecture.md 和 docs/api.md。
实际项目信息：
- Python stdlib http.server + 纯 HTML 前端
- 14 个 API 端点（POST /quiz/generate, /quiz/grade, /notes/* ×7, GET /*）
- 4 个 L0 标准、Obsidian vault
- 无向量库、无 chunking、无 embedding

要求：
- architecture.md：7 章、1.5 页、含 Mermaid 图、含 Failure Modes
- api.md：4 章、19 个端点完整文档、错误码与架构文档 1:1 对齐
- 跨文档一致性约束：路径/模块/错误码三向映射
```

**实际效果**：5 轮对抗对齐，产出 151+193 行，含 Mermaid 图、失败模式四类三字段、错误码双向映射表。

**关键经验**：给对抗式求解器的 task 描述越具体越好——把实际项目信息（端点数量、技术栈、约束）全塞进去，M3 才有足够的上下文出方案。

---

## Prompt 3：批量探索 + 对比 + 出 HTML 报告

**场景**：需要对比 5 个产品的 RAG Pipeline 并产出可视化 HTML

**给 Claude Code 的指令**：
```
Knowledge Lab 与 Dify/Quivr/AnythingLLM/RAGFlow 四个 RAG 产品的 Pipeline 对比。

先探索 tmp/pipeline/dify/api/core/rag/ 的模块结构
（datasource/extractor/splitter/embedding/index_processor/retrieval/rerank），
然后基于探索结果 + Knowledge Lab 实际 pipeline，做 11 阶段 × 5 产品映射表。

输出 HTML 放桌面，要求：
- 每个产品的 pipeline 用流程图可视化（有该阶段=蓝框，没有=红框删除线）
- 优劣势量化对比（含文献引用 Karpicke 2008 / Cepeda 2006）
- 白底蓝主色调，中文
```

**实际效果**：探索了 dify/api/core/rag/ 下 12 个子模块，产出了 5 条完整 pipeline 流程图 + 11 阶段映射表 + 优劣势双栏量化对比。

**关键经验**："先探索 X，再基于探索结果对比 Y，最后输出 HTML"——这个三段式 prompt 模板可以复用到任何竞品对比场景。

---

## Prompt 4：对抗式评估"该不该借鉴竞品"

**场景**：对比完发现 KL 有 5 个劣势，需要评估哪些值得借鉴

**给 Claude Code 的指令**：
```
Knowledge Lab 的 5 个劣势：无chunking、无embedding、无向量检索、无rerank、无高并发。
场景前提：个人学习工具，198 篇笔记，单用户。

用对抗式求解器评估：
1）哪些值得从竞品借鉴到个人学习场景？
2）借鉴后的提升和代价？
3）ROI 评估（值得/不值得/远期可选）+ 优先级排序

表格格式：借鉴项 | 来源产品 | 借鉴内容 | 提升 | 代价 | ROI | 优先级

关键约束：劣势不做 ≠ 产品有问题，是定位选择。
```

**实际效果**：3 轮对抗 PASS，产出 5 项×7 维度的借鉴评估表 + Embedding 决策树 + 代价分层 + Step 0-3 演进路径。

**关键经验**：在 prompt 里明确"场景前提"和"关键约束"——否则 AI 会按通用 RAG 标准评判，得出"全部要补"的错误结论。

---

## Prompt 5：把对话上下文中的产出记录到 spec/

**场景**：今天做了大量重构和对比，需要把关键结论沉淀到 spec/ 目录

**给 Claude Code 的指令**：
```
刚才我们完成了 Knowledge Lab 的目录重构和 RAG Pipeline 对比。
把以下内容分别写入 spec/ 下的 Markdown 文件：
1. 目录新旧结构对比 → spec/STRUCTURE_MIGRATION.md
2. 五产品 RAG Pipeline 对比结论 → spec/RAG_PIPELINE_BENCHMARK.md
3. 本文档 → spec/prompts.md

每份文件要求：状态标注、日期、关键结论、后续待办。
STRUCTURE_MIGRATION 里要标注每项变更的设计依据（从哪个竞品学的）。
```

**实际效果**：三份 spec 文档一次性生成，STRUCTURE_MIGRATION 含 8 项变更明细 + 8 条设计依据 + 对标项目列。

**关键经验**："把对话上下文中的结论沉淀为文档"——这个 prompt 模式适用于任何需要"收尾"的场景。关键是把需要的内容分条列出，AI 才知道每份文件该写什么。

---

## Prompt 模板总结

| # | 模板模式 | 适用场景 |
|---|---------|---------|
| 1 | "参考 X 的 Y 设计，在我的项目里做 Z，约束是 A/B/C" | 任何需要参考竞品代码的重构 |
| 2 | "用对抗式求解器跑：任务描述 + 实际项目信息 + 具体约束 + 输出格式" | 需要两个模型对齐确认的设计决策 |
| 3 | "先探索 X → 基于探索结果对比 Y → 输出 HTML 放桌面" | 任何竞品/技术对比场景 |
| 4 | "场景前提 + 待评估项 + ROI 维度 + 关键约束" | 任何需要"做不做"决策的评估 |
| 5 | "把对话上下文中的关键结论沉淀到文件，分条列出每份文件该写什么" | 收尾/文档化 |

## 原则

- **参考代码路径永远具体到目录**（如 `tmp/pipeline/dify/api/core/rag/`，而不是 `tmp/dify`）
- **约束条件写到"不要做什么"比"要做什么"更有效**（AI 不会自作主张）
- **输出格式提前约定**（表格/JSON/HTML/Mermaid），避免 AI 自由发挥
- **场景前提必须明确**（个人 vs 企业、单用户 vs 多用户），否则 AI 按最通用标准判断
