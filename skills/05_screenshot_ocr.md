---
skill_id: SKILL-005
name: 截图 OCR 多模态识别
category: 内容处理
status: production
model: MiniMax M3 多模态
created: 2026-07-28
---

# 截图 OCR 多模态识别 · Screenshot OCR

## 做什么

用户选择多张截图 → 逐张发送给多模态 LLM → 识别并提取文字 → 按截图顺序合并成一篇 Markdown 笔记。

## OCR Prompt

```
请识别并提取这张截图中的所有文字内容。输出 Markdown 格式，保留标题层级和列表结构。
```

## 工作流程

1. 前端多选图片文件（PNG / JPG / WebP）
2. 批量打包为 FormData + `mode=ocr_batch`
3. 后端逐张 Base64 编码 → 调用 MiniMax M3 多模态 API
4. 每张截图标注 `## 截图 N`
5. 合并结果 → 保存为 `截图_{N}张.md`

## API 调用

```
POST https://api.minimaxi.com/v1/text/chatcompletion_v2
Model: MiniMax-M3
Input: data:{mime};base64,{img_b64}
Temperature: 0.1（低温度保证准确提取）
Timeout: 120s
```

## 依赖

- `MINIMAX_API_KEY` 需在 `.env` 中配置
- 不填则 OCR 功能不可用，不影响其他功能
- 推荐支持多模态的 LLM（当前仅适配 MiniMax M3）

## 代码入口

`server/blueprints/notes.py` → `upload_file()` → mode=ocr_batch 分支
