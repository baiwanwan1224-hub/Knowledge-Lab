# 移动端响应式适配方案

> P1 · 预估 2-3h · 2026-07-28 编写 · 待实施

## 目标

手机端（< 768px）能完成核心操作：看笔记、出题、批改、查看错题本。

## 改动点

### 1. 侧边栏 → 顶部导航条

**现状**：240px 固定侧边栏，占满手机全屏。

**改为**：顶部横条导航，每个 tab 显示图标即可。

```css
@media (max-width: 768px) {
  .sidebar {
    position: static;
    width: 100%;
    min-width: unset;
    height: auto;
    flex-direction: row;
    justify-content: space-around;
    padding: 8px 4px;
    overflow-y: visible;
  }
  .sidebar-nav a {
    flex-direction: column;
    font-size: 10px;
    padding: 6px 4px;
    gap: 2px;
  }
  .sidebar-nav .icon { font-size: 18px; }
  .sidebar-nav .nav-en { display: none; }
  .main { margin-left: 0; }
}
```

### 2. 表格 → 卡片列表

**现状**：7 列表格，手机屏幕根本放不下，横向溢出。

**改为**：每条笔记渲染为一张卡片，竖排堆叠。

```css
@media (max-width: 768px) {
  .note-table, .note-table thead { display: none; }
  .note-table tbody, .note-table tr, .note-table td {
    display: block;
    width: 100%;
  }
  .note-table tr {
    margin-bottom: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    background: var(--card);
  }
  .note-table td { padding: 4px 0; border: none; }
  .col-title { font-size: 15px; font-weight: 600; max-width: unset !important; white-space: normal !important; }
  .col-source, .col-time, .col-status { font-size: 12px; display: inline-block; margin-right: 8px; }
}
```

### 3. 按钮和输入框

```css
@media (max-width: 768px) {
  .form-row { flex-direction: column; gap: 8px; }
  .form-group { width: 100%; }
  .btn { width: 100%; padding: 12px; }
  input, select, textarea { width: 100%; font-size: 16px; }  /* 16px 防止 iOS 缩放 */
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .flex-between { flex-direction: column; gap: 8px; }
}
```

### 4. 弹窗适配

```css
@media (max-width: 768px) {
  .modal { max-width: 95vw; max-height: 85vh; padding: 16px; }
  .modal-overlay { padding: 10px; align-items: flex-start; }
}
```

### 5. 测验区域

```css
@media (max-width: 768px) {
  #quizArea .flex-between { flex-wrap: wrap; }
  #quizArea button { flex: 1; min-width: 80px; }
}
```

## 验证清单

- [ ] 手机竖屏打开页面，导航在顶部横条显示
- [ ] 知识库 tab → 笔记以卡片形式堆叠，无横向滚动
- [ ] 能正常点击笔记打开详情弹窗
- [ ] 出题 → 选题 → 答题 → 批改 → 查看结果，全部在手机上完成
- [ ] 错题本和历史记录正常显示
- [ ] 仪表盘统计卡片 2 列排列
- [ ] 导入按钮和输入框不溢出
