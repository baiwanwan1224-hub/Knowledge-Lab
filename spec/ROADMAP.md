# Knowledge Lab · Roadmap

> 版本：2026-07-28 · 状态：v0.1 持续迭代中
>
> **产品发展路径**：个人工具 → 开源项目 → 可项目化产品 → 商业/企业化落地

---

## v0.1.0 — MVP · 个人使用需求 ✅

> 自己做题自测，能用就行。功能优先，体验其次。

- [x] 单页 SPA 仪表盘（纯 HTML/CSS/JS，零框架）
- [x] Obsidian Vault 笔记导入（URL / YouTube / 粘贴 / PDF / 截图 OCR）
- [x] RAG 自动出题（LLM + 5 项 QA Gate）
- [x] LLM 智能评分 + SM-2 间隔重复 + 错题卡生成
- [x] 六维能力雷达图 + 学习方向建议
- [x] 知识库管理（浏览 / 搜索 / 审核 / 删除）
- [x] Flask + Blueprint + pydantic 架构重构
- [x] /v1 版本前缀 + Swagger 文档
- [x] LLM 响应缓存（SQLite · 三层失效 · 命中率统计）

---

## v0.2.0 — 发布就绪 · 开源需求 ⏳

> 别人能下载、能跑起来、能看懂。文档 + 测试 + CI + 截图 + 视频 + Release。

- [ ] GitHub Release v0.1.0（zip 打包 + 一键启动）
- [ ] Demo 视频（3-5 分钟核心流程演示）
- [ ] README 截图更新（匹配最新 UI）
- [x] 新用户配置指南（docs/SETUP.md）✅
- [x] 自动化测试（32 个 pytest 用例）✅
- [x] CI/CD（GitHub Actions · Python 3.10/3.12）✅ 待 push
- [x] 前端统一错误处理 + 超时保护 ✅
- [x] UI 全面翻新（Inter 字体 · Indigo 配色 · SVG 图标）✅
- [ ] 移动端响应式适配（方案已写，待实施）
- [ ] 多用户 API Key 认证（方案已写，待启用）

---

## v0.3.0 — 项目化 · 产品化需求 🔮

> 不只是"能跑"，而是可维护、可评测、可展示的完整项目。

- [x] 测试覆盖（pytest · 32 个测试）✅
- [x] CI/CD（GitHub Actions）✅
- [ ] 跨模型评测自动化（5 LLM 批量跑 benchmark + 对比报告）
- [ ] 评测 Dashboard 可视化（HTML 报告生成）
- [ ] 竞品 Feature Matrix（5 产品功能对比表）
- [ ] 数据流链路图（全链路 Mermaid）
- [ ] 项目级 AI 技能定义（skills/）
- [ ] 社区需求验证（Reddit r/Anki / r/PKMS）

---

## v0.5.0+ — 商业化/企业化 · 扩展需求

> 多用户、大规模、可运营。触发条件：有真实外部用户或商业机会。

- [ ] 语义检索（笔记 > 500 篇时启用 · bge-small-zh + sqlite-vec）
- [ ] 多用户支持（讲师场景 · 学员管理 + 班级数据）
- [ ] 社区版 vs 商业版（开源 AGPL + 商业许可）
- [ ] LLM 评测自动化流水线（定时跑 benchmark + 趋势报告）
- [ ] 知识图谱可视化（笔记间关联 + 能力维度间关系）
- [ ] 移动端 PWA / 独立 App
- [ ] API 商业化计费
