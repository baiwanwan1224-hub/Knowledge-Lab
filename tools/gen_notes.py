#!/usr/bin/env python3
"""Generate AI PM study notes from skill decomposition."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')

NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vault', '00_学习笔记')
os.makedirs(NOTES_DIR, exist_ok=True)

date = '2026-07-26'

notes = {
    'agent_architect': {
        'title': 'AI Agent 系统架构设计方法论',
        'topics': ['AI Agent', '系统架构', '产品设计'],
        'content': '''# AI Agent 系统架构设计方法论

## 五阶段架构访谈

### Phase 1: Strategy
- 问题定义：Agent 要解决什么
- ROI 计算和成功指标量化

### Phase 2: Team
- 子 Agent 分解（2-10+ 个）
- 职责边界和协作模式

### Phase 3: Orchestration
- ReAct / Planner / Combined 三种模式
- 确定性路由 vs LLM 路由
- Handoff 和 Gatekeeper 模式

### Phase 4: Production Ready
- Guardrails、Observability
- Human-in-the-Loop 节点
- 成本和延迟预算

### Phase 5: Code Generation
- 架构→代码脚手架
- MCP 工具集成'''
    },
    'prompt_engineering': {
        'title': 'Prompt Engineering 系统化方法论',
        'topics': ['Prompt工程', 'LLM', 'AI开发'],
        'content': '''# Prompt Engineering 系统化方法论

## 五阶段流程

1. **结构化访谈**：明确任务目标和约束
2. **技术选择**：CO-STAR / RISEN / XML-First / Persona / CoT / Few-Shot
3. **Prompt 构建**：选择技术组合 + 参数设定
4. **质量审核**：Prompt Quality Checklist
5. **交付迭代**：A/B 测试 + 持续优化

## 六大 Prompt 技术

| 技术 | 适用场景 | 关键特征 |
|------|---------|---------|
| CO-STAR | 结构化输出 | Context-Objective-Style-Tone-Audience-Response |
| RISEN | 复杂推理 | Role-Instruction-Steps-End goal-Narrowing |
| XML-First | 数据提取 | XML 标签标注结构化数据 |
| Persona | 角色扮演 | 特定角色视角 |
| Chain-of-Thought | 推理任务 | 逐步推理过程 |
| Few-Shot | 格式控制 | 示例引导输出格式 |

## 核心原则
- 结构化 > 模糊
- 示例驱动 > 纯文字描述
- Prompt 是改出来的，不是一次写成的'''
    },
    'spec_driven_dev': {
        'title': 'Spec-Driven Development 产品规格方法论',
        'topics': ['产品管理', '开发流程', '规格设计'],
        'content': '''# Spec-Driven Development

## 四阶段门控流程

### SPECIFY
- 问题定义、目标用户、成功标准
- 显式列出所有假设
- Not Doing 清单

### PLAN
- 架构设计、技术选型
- Top 3 风险 + 缓解方案
- 依赖关系图

### TASKS
垂直切片原则：

| 尺寸 | 工时 | 示例 |
|------|------|------|
| XS | 分钟级 | 修改文案 |
| S | 小时级 | 添加验证 |
| M | 半天 | API 端点 |
| L | 一天 | 完整功能 |
| XL | 一周+ | 需拆分 |

### IMPLEMENT
- 按依赖顺序执行
- 每个 Phase 需人工审核

## 核心理念
- 假设显式化
- 成功标准前置
- Spec 是活文档'''
    },
    'idea_refine': {
        'title': '创意精炼：从模糊到可执行',
        'topics': ['产品思维', '创意方法', '需求分析'],
        'content': '''# 创意精炼方法论

## 三阶段流程

### Divergent（发散）
五种思维透镜：
- HMW（How Might We）
- 反转思维
- 约束移除
- 受众切换
- 类比迁移

### Convergent（收敛）
问题分类：
- 慢性 / 急性 / 潜在 / 市场转移 / 流程

评估矩阵：Impact x Feasibility x Alignment

### Sharpen & Ship（打磨交付）
- 假设显式化
- MVP 范围定义
- Not Doing 清单

## 核心理念
- 说不比说是更重要
- MVP 的核心是「最小」不是「可用」'''
    },
    'customer_research': {
        'title': 'Jobs to Be Done 框架实战',
        'topics': ['用户研究', 'JTBD', '需求分析'],
        'content': '''# Jobs to Be Done 框架实战

## 两种研究模式

### 分析现有资产
- 用户访谈、调查问卷、客服记录、评论

### Digital Watering Hole
- Reddit、G2、行业论坛、社交媒体

## JTBD 三类 Job

| 类型 | 定义 | 示例 |
|------|------|------|
| Functional | 功能性任务 | 「快速生成周报」 |
| Emotional | 情感体验 | 「不想显得不专业」 |
| Social | 社会认同 | 「被团队认可」 |

## 置信度标注
- High：多个独立来源
- Medium：1-2 个来源
- Low：推测待验证

## 反模式
- Frankenpersona：缝合怪
- Feature List Persona：只有需求
- Demographics-Only：只有统计'''
    },
    'icp_research': {
        'title': '理想客户画像（ICP）构建方法',
        'topics': ['用户研究', '市场定位', '增长策略'],
        'content': '''# 理想客户画像（ICP）构建

## 八步工作流

1. Product Context：核心解决的问题
2. Market Definition：TAM/SAM/SOM
3. Persona：人口统计+行为+目标+痛点
4. Pain Mapping：Frequency x Intensity = Priority
5. Objections：价格/切换/信任/够用
6. Buying Triggers：触发事件和窗口期
7. Community Research：用户活跃在哪
8. Messaging Angles：不同 Persona 不同话术

## Pain Score = Frequency x Intensity

- 频率：问题多久发生一次
- 强度：问题造成多大影响
- 按 Priority Score 排序'''
    },
    'pricing_strategy': {
        'title': '定价策略与价值度量方法论',
        'topics': ['定价', '商业化', '产品策略'],
        'content': '''# 定价策略与价值度量

## 三大定价轴

### Packaging
Good-Better-Best 框架：
- Good：核心功能入门
- Better：进阶功能主力
- Best：全部功能锚定

### Pricing Metric

| 模式 | 适用 | 案例 |
|------|------|------|
| Per-Seat | 协作工具 | Slack |
| Usage-Based | API/基础设施 | OpenAI |
| Tiered | SaaS | Figma |
| Freemium | 消费者 | Dropbox |
| Flat-Rate | 简单价值 | Basecamp |
| Hybrid | 复杂产品 | GitHub |

### Price Point
Van Westendorp 价格敏感度测试

## 竞争定位
- Premium / Competitive / Penetration / Value'''
    },
    'launch_strategy': {
        'title': '产品发布策略：ORB 框架',
        'topics': ['产品发布', 'GTM', '增长策略'],
        'content': '''# 产品发布策略：ORB 框架

## 三渠道模型

| 渠道 | 类型 | 示例 |
|------|------|------|
| Owned | 完全控制 | 博客/Email/产品内 |
| Rented | 借用不拥有 | PR/Podcast/社区 |
| Borrowed | 合作获取 | 伙伴/集成/联盟/KOL |

## 五阶段发布
1. Internal → 2. Alpha → 3. Beta → 4. Early Access → 5. Full

## Product Hunt 策略
- 提前2周准备，选周二至周四发布
- 首小时投票至关重要
- Maker Comment 要真诚有料

## 发布优先级
- Major：Full ORB
- Medium：Owned + Rented
- Minor：Owned only'''
    },
    'context_engineering': {
        'title': 'AI Agent 上下文工程方法论',
        'topics': ['AI Agent', 'RAG', '系统设计'],
        'content': '''# AI Agent 上下文工程

## 五层上下文架构

| 层级 | 内容 | 加载策略 |
|------|------|---------|
| L1 Rules | 规则/宪法/SOP | 始终加载 |
| L2 Spec | 架构/API/设计 | 任务相关加载 |
| L3 Source | 源代码 | 按需检索 |
| L4 Error | 运行时错误 | 自动注入 |
| L5 Conversation | 对话历史 | 窗口管理 |

## 打包策略
- Slot-Based：固定任务 → 高效可预测
- Layered：复杂项目 → 按需加载
- State-Based：多步骤 → 自动适应

## 常见问题
- 上下文衰减：早期信息被稀释
- 上下文污染：无关信息干扰
- 信息过载：关键信息被忽略

## 最佳实践
1. 关键指令放最前面
2. 明确 section 分隔
3. 定期总结压缩
4. 切换任务清上下文'''
    },
    'retention_metrics': {
        'title': '用户留存与流失预警体系',
        'topics': ['用户留存', '数据分析', '增长策略'],
        'content': '''# 用户留存与流失预警

## 三种流失

| 类型 | 原因 | 策略 |
|------|------|------|
| Voluntary | 主动取消 | 挽留+优惠 |
| Involuntary | 支付失败 | Dunning流程 |
| Silent | 不用不取消 | 重新激活 |

## 健康评分（加权）

| 信号 | 权重 |
|------|:--:|
| 产品使用量 | 25% |
| 功能采纳率 | 20% |
| 支持情绪 | 15% |
| 账单健康 | 15% |
| 参与度 | 15% |
| NPS/CSAT | 10% |

## 预警时间线
T-90 → T-60 → T-30 → T-14 → T-7 → T-0

## 挽回响应率
- 0-7天：15-25%
- 90天+：<3%

**前7天是黄金窗口**'''
    },
    'ab_testing': {
        'title': 'A/B 测试与增长实验方法论',
        'topics': ['增长实验', '数据分析', '产品优化'],
        'content': '''# A/B 测试与增长实验

## 假设框架
Because → We Believe → Will Cause → We'll Know

## ICE 优先级

| 维度 | 评分 |
|------|:--:|
| Impact | 1-10 |
| Confidence | 1-10 |
| Ease | 1-10 |

ICE = I x C x E

## 统计原则
- 置信度：95%（p<0.05）
- 统计功效：80%
- 最小检测效应

## 十大陷阱
1. Peeking（偷看）
2. Early Stopping（提前停）
3. Simpson's Paradox（辛普森悖论）
4. Multiple Comparisons（多重比较）
5. Novelty Effect（新鲜感）
6. Selection Bias（选择偏差）
7. Survivorship Bias（幸存者偏差）
8. Network Effects（网络效应）
9. Seasonality（季节性）
10. Small Sample（样本不足）'''
    },
    'ai_seo_geo': {
        'title': 'AI 搜索可见性优化（AEO/GEO）',
        'topics': ['AI SEO', 'GEO', '内容策略'],
        'content': '''# AI 搜索可见性优化（AEO/GEO）

## 三支柱框架

### Structure（让AI能提取）
- /llms.txt, /pricing.md 机器可读
- JSON-LD Schema, FAQ Schema
- 清晰标题层级 H1→H2→H3

### Authority（让AI愿引用）
- 引用来源 +40% 可见度
- 数据统计 +37% 可见度
- 外部验证和定期更新

### Presence（让AI能找到）
- Wikidata 条目
- Reddit 提及
- 行业媒体报道
- GitHub 开源

## GEO Checklist
- [ ] /llms.txt 存在？
- [ ] JSON-LD Schema？
- [ ] 引用数据和来源？
- [ ] FAQ Schema？
- [ ] Wikidata 条目？
- [ ] Reddit 社区活跃讨论？'''
    },
}

count = 0
for key, note in notes.items():
    filename = f'{date}_{key}.md'
    filepath = os.path.join(NOTES_DIR, filename)

    frontmatter = f'---\ntitle: {note["title"]}\ntopics: [{", ".join(note["topics"])}]\nstatus: imported\nsource: SKILL\ndate: {date}\n---\n\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + note['content'])

    print(f'Created: {filename}')
    count += 1

print(f'Total: {count} notes')
