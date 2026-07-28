# Knowledge Lab · 新用户完整配置指南

> 5 分钟从零开始搭建你的自测学习平台

---

## 一、环境要求

| 要求 | 说明 |
|------|------|
| Python | 3.10 或更高版本 |
| 操作系统 | Windows / macOS / Linux |
| 磁盘空间 | 100MB（代码 + 依赖），笔记按需 |
| 网络 | 需访问 DeepSeek API（出题+批改） |

**检查 Python 版本：**
```bash
python --version
# 应显示 Python 3.10.x 或更高
```

如果没装 Python：https://www.python.org/downloads/ （安装时勾选 "Add Python to PATH"）

---

## 二、获取 API Key

### DeepSeek（必填 — 出题和批改）

1. 打开 https://platform.deepseek.com
2. 注册/登录 → 左侧菜单 "API Keys"
3. 点击 "创建 API Key" → 复制 `sk-xxx` 开头的密钥
4. 充值 ¥10 即可使用（按量计费，每次出题约 ¥0.02）

### MiniMax M3（可选 — 截图 OCR）

1. 打开 https://platform.minimaxi.com
2. 注册/登录 → API Keys → 创建
3. 复制 Key 填入 `.env`
4. 不填不影响出题/批改/知识库功能

---

## 三、安装步骤

### Windows
```bash
# 1. 下载项目
git clone https://github.com/baiwanwan1224-hub/Knowledge-Lab.git
cd Knowledge-Lab

# 2. 配置
copy .env.example .env
# 用记事本打开 .env，填入 DeepSeek API Key

# 3. 启动
双击 start.bat
```
浏览器自动打开 http://localhost:5050

### Mac / Linux
```bash
git clone https://github.com/baiwanwan1224-hub/Knowledge-Lab.git
cd Knowledge-Lab
cp .env.example .env
# 编辑 .env，填入 API Key
bash start.sh
```

### 手动安装（如果自动脚本失败）
```bash
pip install -r requirements.txt
python -c "import sys; sys.path.insert(0,'.'); from server.app import create_app; create_app().run(host='127.0.0.1',port=5050)"
```
打开浏览器访问 http://localhost:5050

---

## 四、常见问题

| 问题 | 解决方法 |
|------|------|
| `python: command not found` | Python 未安装或未加入 PATH。重装 Python 并勾选 "Add to PATH" |
| `pip install` 报错 | 尝试 `python -m pip install -r requirements.txt` |
| 端口 5050 被占用 | 修改 `server/config.py` 中的 `DEFAULT_PORT` |
| API Key 不生效 | 确认 `.env` 文件在项目根目录，Key 格式为 `sk-xxx` |
| 仪表盘显示"API 离线" | 检查 API Key 是否有效，DeepSeek 余额是否 > 0 |
| OCR 功能不可用 | 需在 `.env` 中配置 `MINIMAX_API_KEY` |
| 知识库是空的 | 先导入一篇笔记：知识库 tab → 粘贴文本或上传文件 |

---

## 五、Vault 存储模式

| 模式 | `.env` 配置 | 适用场景 |
|------|------|------|
| 本地模式（默认） | `VAULT_PATH=./vault` | 开箱即用，笔记存在项目目录下 |
| Obsidian 联动 | `VAULT_PATH=C:/Users/.../Obsidian Vault` | 笔记与 Obsidian 双向同步 |
| 自定义路径 | `VAULT_PATH=/your/path` | 任意目录 |

Obsidian 联动模式的优势：可以用 Obsidian 编辑笔记、Obsidian Sync 云端备份、手机端查看。

---

## 六、功能导览

打开 http://localhost:5050 后：

| Tab | 功能 | 首次使用 |
|------|------|------|
| 📊 仪表盘 | 学习数据总览：笔记数、错题数、能力雷达 | 暂无数据，需先导入笔记 |
| 📚 知识库 | 浏览、搜索、管理所有笔记 | 点 "📝 粘贴文本" 导入第一篇文章 |
| 🧪 出题测验 | 从笔记自动生成测验题 | 选主题 → 生成测验 → 答题 → 批改 |
| ❌ 错题本 | 按 SM-2 算法排期的错题复习 | 做完测验后自动生成 |
| 📈 历史记录 | 历次测验成绩和详情 | 做完测验后自动记录 |

**3 分钟快速体验流程：**
1. 知识库 tab → 粘贴一段文章 → AI 自动结构化
2. 出题测验 tab → 选主题 → 生成测验 → 答题 → 提交
3. 查看批改结果 → 错题自动入错题本
