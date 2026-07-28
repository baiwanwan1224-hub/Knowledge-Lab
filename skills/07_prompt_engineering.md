---
skill_id: SKILL-007
name: Vibe Coding Prompt 工程
category: 开发方法论
status: documented
created: 2026-07-27
---

# Vibe Coding Prompt 工程 · Prompt Engineering for AI-Assisted Development

## 5 条实战 Prompt 模板

### 模板 1：参考代码重构

```
参考 tmp/architecture/{project} 的目录组织方式，
将 {source_path} 迁移到 {target_path}，
不动 {keep_path} 的业务逻辑。
输出的代码要遵循 {standards_path} 规范。
```

**实例**："参考 tmp/architecture/openclaw 的目录组织方式，将 dashboard/ 迁移到 apps/web/，不动 server/ 业务逻辑。输出代码要遵循 standards/ 命名规范。"

### 模板 2：功能实现 + 参考设计

```
实现 {feature_name} 功能，参考 tmp/pipeline/{project} 的设计模式。
需要生成：
1. 数据模型（{schema_format}）
2. API 端点（{method} {path}）
3. 前端组件（{component_type}）
错误处理使用 errors.py 统一错误码。
```

### 模板 3：Bug 修复 + 回归保护

```
修复 {bug_description}：
1. 定位根因（为什么 {input} 导致 {error}）
2. 最小改动修复（不改动无关代码）
3. 加自动化测试覆盖这个场景（pytest）
同时检查是否有类似的潜在问题。
```

### 模板 4：代码审查

```
审查 {filename} 的代码：
1. 安全检查（注入、认证、数据泄漏）
2. 错误处理（是否所有异常都有处理）
3. 性能瓶颈（N+1 查询、不必要的循环）
4. 代码可读性（命名、注释、函数长度）
输出结构化的审查报告，标注严重程度。
```

### 模板 5：文档生成

```
为 {component} 生成文档：
1. 功能说明（一句话 + 使用场景）
2. API 参考（输入/输出/错误码）
3. 代码示例（最小可用示例）
4. 注意事项（边界情况、限制）
格式参考 docs/api.md 的风格。
```

## 6 种协作模式

| 模式 | 指令特征 | 适用场景 |
|------|------|------|
| **参考驱动** | "参考 tmp/X 的设计" | 有成熟参考项目时 |
| **规范驱动** | "遵循 standards/X" | 有不可变规则时 |
| **增量式** | "只改 X，不动 Y" | 大项目的局部修改 |
| **对抗式** | "你审查一下这个方案" | 需要第二意见时 |
| **文档驱动** | "先写 spec，再写代码" | 新功能开发 |
| **测试驱动** | "先写测试，再实现" | Bug 修复 |

## 5 条原则

1. **上下文 > 指令字数**：给 AI 提供参考代码和规范文档，比写长指令更有效
2. **增量 > 一次性**：把大任务拆成 AI 能精准执行的小步骤
3. **约束 > 自由**：明确告诉 AI "不能做什么"，比告诉它"做什么"更有效
4. **验证 > 信任**：每次 AI 输出都要有自动化检查（QA Gate、测试、Linter）
5. **记录 > 遗忘**：成功的 prompt 记录下来，下次复用

## 代码入口

`spec/prompts.md`（完整版）
