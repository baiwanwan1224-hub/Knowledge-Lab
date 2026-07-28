# 多用户隔离方案

> P2 · 近期 30min（API Key）· 远期 1-2 天（OAuth）· 2026-07-28 编写

## 阶段一：API Key 认证（30min · 立即可做）

### 后端（已就绪）

`server/middleware/auth.py` 已实现轻量 API Key 认证：

```python
# .env 中设置
API_KEY=your-random-key-here
```

启用后，所有 `/v1/*` 请求需带 `X-API-Key` header，否则返回 401。

### 前端（需改动）

1. 在 `apiFetch()` 中自动附加 API Key：

```javascript
async function apiFetch(url, options = {}) {
  const headers = { ...options.headers };
  if (window.API_KEY) headers['X-API-Key'] = window.API_KEY;
  // ... existing timeout logic
}
```

2. 启动时从 localStorage 读取或弹出输入框让用户输入 Key：

```javascript
function initAuth() {
  let key = localStorage.getItem('api_key');
  if (!key) {
    key = prompt('请输入 API Key（本地 dev 模式留空）:');
    if (key) localStorage.setItem('api_key', key);
  }
  window.API_KEY = key;
}
```

3. `.env` 设好 `API_KEY`，重启服务，前端输 Key 即可。

### 局限

- 只有一个全局 Key，所有人用同一个 Key 看到同一份数据
- 无法区分用户 A 和用户 B
- 适合：个人使用 / 给 PM 临时体验（告诉他 Key 即可）

---

## 阶段二：多用户隔离（远期 · 1-2 天）

### 方案：Vault 目录隔离

```
vault/
├── shared/           ← 共享模板和标准
├── users/
│   ├── alice/
│   │   ├── 00_学习笔记/
│   │   └── 01_错题本/
│   └── bob/
│       ├── 00_学习笔记/
│       └── 01_错题本/
```

### 后端改动

1. **生成用户 API Key**：`secrets.token_hex(32)`，存入 `.env` 或 JSON 文件
2. **Key → 用户映射**：`API_KEYS = {"key1": "alice", "key2": "bob"}`
3. **动态 Vault 路径**：根据请求中的 API Key 定位到对应用户目录
4. **管理接口**：`POST /v1/admin/users` 创建用户（需 admin Key）

```python
# server/middleware/auth.py 扩展
USERS = {"sk-alice-xxx": {"name": "alice", "vault": "users/alice"},
         "sk-bob-xxx":   {"name": "bob",   "vault": "users/bob"}}

def get_user_vault(request):
    key = request.headers.get('X-API-Key', '')
    user = USERS.get(key)
    return user['vault'] if user else 'shared'
```

### 前端改动

- 登录页：输入 Key → 存入 localStorage → 后续请求自动带 Key
- 导航栏显示当前用户名

### 更远：GitHub OAuth

- 用 GitHub OAuth App 做登录
- 用户授权后拿到 GitHub username → 自动创建 vault 目录
- 无需手动管理 Key

---

## 当前建议

先做阶段一（30min），给 PM 体验时把 Key 发他就行。多用户隔离等功能验证有真实需求再做。
