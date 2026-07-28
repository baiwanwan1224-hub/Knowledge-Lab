---
skill_id: SKILL-006
name: Vault 防丢架构
category: 基础设施
status: production
created: 2026-07-26
---

# Vault 防丢架构 · Anti-Loss Storage Engine

## 做什么

保证用户笔记永不丢失——原子写入保护写入过程、WAL 日志保护崩溃恢复、完整性快照检测文件丢失。

## 三层保护

### 1. 原子写入（Atomic Write）

```
写入流程：内容 → 临时文件(.tmp) → flush → fsync → os.rename → 正式文件
```

- 写入过程中崩溃：临时文件残留，正式文件完好
- rename 是操作系统原子操作：要么是旧文件，要么是新文件，不存在半写状态

### 2. 预写日志（WAL）

- 每次写入前，先追加一行记录到 `vault/.vault-meta/wal.log`
- 启动时回放 WAL：检测最后一次写入是否成功完成
- 未完成的写入从临时文件恢复

### 3. 完整性快照（Integrity Snapshot）

- 启动时计算所有笔记文件的 SHA256 哈希
- 与上次快照对比 → 检测文件丢失、变更
- `.gitignore` 保护笔记不入 Git，但备份脚本可做云端同步

## 文件命名规范（L0-004）

```
{YYYYMMDD}_{HHMMSS}_{TYPE}_{SLUG}_{HASH4}.md
```

例：`20260726_201403_WHISPER_rick-astley-never-gonna-give-you-up_a3f2.md`

## 为什么需要

7/25 曾发生 34 篇笔记全部丢失（vault 目录被 gitignore 排除 + 服务器不自建目录）。防丢架构是事后复盘建立的。

## 代码入口

`server/vault_core.py` → `atomic_write()` | `wal_append()` / `wal_replay()` | `save_integrity_snapshot()` / `verify_integrity()` | `safe_save_note()`
