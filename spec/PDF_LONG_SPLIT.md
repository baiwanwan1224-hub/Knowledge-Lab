# 长 PDF 分篇功能 · 排查与修复方案

> P2 · 预估 1-2h · 2026-07-28 记录 · 待排查

## 现象

导入长 PDF（如教材、论文）后只生成一篇笔记，未按 30000 字阈值自动拆分。

## 代码位置

`server/blueprints/notes.py` → `upload_file()` → PDF 处理分支（~265 行）

```python
# 当前逻辑
if len(raw_text) > SPLIT_AT:   # SPLIT_AT = 30000
    # 按段落边界拆分成 parts[]
    ...
else:
    parts = [raw_text]  # ← 不足 30000 字不拆分
```

## 排查步骤

### Step 1：确认实际提取字数

在 upload 端点加日志：

```python
raw_text = ''
for page in reader.pages:
    raw_text += page.extract_text() or ''
logger.info(f'[PDF] {safe_name}: {len(reader.pages)} pages, {len(raw_text)} chars extracted')
```

导入一份已知很长的 PDF，观察日志输出的字数和页数。

### Step 2：判断原因

| 情况 | 根因 | 修复 |
|------|------|------|
| 页数对但字数 < 30000 | PyPDF2 提取不完整 | 换 PyMuPDF (fitz) |
| 字数 > 30000 但未拆分 | 段落边界分割 bug | 检查 `\n\n` 分割逻辑 |
| 页数不对 | PDF 本身页数少 | 非 bug，正常行为 |

### Step 3：替换 PyPDF2 → PyMuPDF（如果 Step 2 确认）

```python
# 安装
pip install PyMuPDF

# 替换代码
import fitz  # PyMuPDF
doc = fitz.open(tmp.name)
raw_text = ''
for page in doc:
    raw_text += page.get_text() or ''
doc.close()
```

PyMuPDF 文字提取质量显著优于 PyPDF2，尤其对中文 PDF。

### Step 4：验证拆分逻辑

```python
# 测试：构造超长文本，确认拆分生效
test_text = ('测试段落。' * 10000)  # ~50000 字
parts = split_by_paragraphs(test_text, 30000)
assert len(parts) > 1, f'Expected >1 parts, got {len(parts)}'
```

## 边界情况

- 拆分点正好在标题处 → 应该避免在 `# ` 开头的行切分
- 英文 PDF → 单词可能被截断，应在空格处切分
- 混合中英文 → 统一按段落边界切分

## 关联改动

- 拆分后每篇笔记需标注 `[1/N]` 和 `本文档共 N 篇`
- 导入成功提示需显示 "已拆分为 N 篇"
- 前端结果提示已支持 `data.total_parts`

## 状态

2026-07-28：代码已写（拆分逻辑 + 前端提示），但未生效。待排查 PyPDF2 提取字数。
