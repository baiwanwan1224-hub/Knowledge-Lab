# 🔧 Knowledge Lab · RED SKill 打包说明

> RED 平台 Skill 提交文件（Markdown 格式）
> 代码仓库：https://github.com/baiwanwan1224-hub/Knowledge-Lab

---

## Skill 信息

| 字段 | 内容 |
|------|------|
| **名称** | Knowledge Lab · RAG 知识库搭建系统 |
| **作者** | Reforox AI Team |
| **版本** | v0.2.0 |
| **分类** | AI 工具 / 学习 / 知识管理 |
| **定价** | 免费开源 (AGPL v3.0) / 商用授权另议 |
| **GitHub** | https://github.com/baiwanwan1224-hub/Knowledge-Lab |
| **演示视频** | YouTube · Bilibili（见 README） |

---

## 一句话

**把 Obsidian Vault 变成个性化 AI 测验生成器。** 导入任意内容（网页/PDF/视频/截图），自动清洗→结构化→去重→分类，一键生成测验题。

---

## 适合谁

- 用 Obsidian 做知识管理的 AI 学习者
- 需要自测检验的产品经理 / 开发者
- 想搭建个人 AI 知识库的研究者

---

## 3 步启动

```bash
# 1. 克隆
git clone https://github.com/baiwanwan1224-hub/Knowledge-Lab.git
cd knowledge-lab

# 2. 配置
cp .env.example .env
# 编辑 .env: 填入 LLM_API_KEY (DeepSeek), 设置 VAULT_PATH

# 3. 运行
pip install -r requirements.txt
python server/app.py
# 打开 http://localhost:5050
```

---

## 核心工作流（5 步）

```
导入 → 审核 → 出题 → 答题 → 回顾
  │       │       │       │       │
  │       │       │       │       └─ 错题本 + 能力雷达
  │       │       │       └─ AI 评分 + 来源引用
  │       │       └─ 按主题生成测验
  │       └─ draft → ready（人工确认）
  └─ URL/PDF/YouTube/截图/粘贴
```

---

## 数据清洗管线（7 层）

| 层 | 功能 |
|:--:|------|
| 1 | HTML 清洗 — 去 script/style/nav/footer，提取正文 |
| 2 | 转录降噪 — 去时间戳/填充词/重复行，段落分段 |
| 3 | 空源检测 — 内容 <100 字符直接拒收，防止 LLM 编造 |
| 4 | LLM 结构化 — 原始文本 → 结构化 Markdown |
| 5 | 去重检测 — SHA-256 + Jaccard 相似度 |
| 6 | 自动分类 — 15 主题标签 (DeepSeek + M3 + GLM 三模型) |
| 7 | 质量门禁 — L0-003 标准 · 仅 `ready` 笔记用于出题 |

---

## 与网页端 LLM 的差异

| 能力 | ChatGPT/Claude 网页 | Knowledge Lab |
|------|:--:|:--:|
| 单篇格式化 | ✅ | ✅ |
| HTML 自动清洗 | ❌ | ✅ |
| 去重检测 | ❌ | ✅ |
| 批量处理 | ❌ | ✅ |
| 增量管理 | ❌ | ✅ |
| 知识库检索 | ❌ | ✅ |
| 本地存储 | ❌ | ✅ (Obsidian) |
| 空源防幻觉 | ❌ | ✅ |
| AI 测验生成 | ❌ | ✅ |
| 错题本 + SM-2 | ❌ | ✅ |
| 能力雷达图 | ❌ | ✅ |

---

## 技术栈

- **后端**: Python 3.10+ · Flask · DeepSeek V4 Pro · MiniMax M3
- **前端**: 单文件 SPA (Vanilla JS · 零框架)
- **存储**: Markdown + YAML frontmatter (Obsidian 兼容)
- **质量**: 32 自动化测试 · CI (GitHub Actions)
- **防丢**: WAL (预写日志) + SHA-256 完整性快照

---

## 配置项

| 环境变量 | 说明 | 默认值 |
|------|------|------|
| `LLM_API_KEY` | DeepSeek API Key | (必填) |
| `LLM_MODEL` | 模型名 | deepseek-v4-pro |
| `VAULT_PATH` | Obsidian Vault 路径 | ./vault |
| `MINIMAX_API_KEY` | OCR 多模态 (可选) | — |
| `DEDUP_THRESHOLD` | 去重相似度阈值 | 0.85 |
| `API_KEY` | 访问密码 (可选) | — |

---

## 常见问题

**Q: 会修改我的 Obsidian 笔记吗？**
仅写入 `Knowledge Lab/00_学习笔记/` 子目录，原始文件永不修改。所有写入使用原子操作。

**Q: 需要多少笔记才能开始？**
5-10 篇同主题笔记即可。50+ 篇效果最佳。

**Q: 支持其他 LLM 吗？**
任何 OpenAI 兼容接口均可。设置 `LLM_API_URL` + `LLM_MODEL`。

**Q: 不用 Obsidian 能用吗？**
可以。`VAULT_PATH` 指向任意包含 Markdown 的目录即可。

---

*打包日期：2026-08-01 · 代码版本 v0.2.0*
