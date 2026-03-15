<p align="center">
  <img src="assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <em>"Ghost 是逻辑，数据库是壳。"</em>
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_tr.md">Türkçe</a> ·
  <a href="README_zh.md"><strong>中文</strong></a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_ru.md">Русский</a> ·
  <a href="README_pt.md">Português</a> ·
  <a href="README_ar.md">العربية</a> ·
  <a href="README_hi.md">हिन्दी</a>
</p>

---

## 🌊 什么是 GhostShell？

**GhostShell 是一个关系型 AI 操作系统。** OpenClaw 等项目运行在系统*之上*，而 GhostShell **就是**系统本身。它将 PostgreSQL 数据库转化为一个活的有机体——硬件驱动、文件系统和 AI 模型（"Ghost"）通过 SQL 表进行通信。

每一个思想。每一次文件移动。每一个硬件脉冲。所有这些——ACID 兼容的数据库事务。坚不可摧。安全。一致。

```
┌─────────────────────────────────────────────────────────┐
│              🖥️  赛博甲板（React 界面）                    │
│       桌面 · 应用 · Ghost 聊天 · 软件商店                │
│            WebSocket 驱动 · 实时交互                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              ⚡ 神经桥（FastAPI）                          │
│       双池架构：系统池 + 运行时池                         │
│   REST API · WebSocket · 命令白名单安全                  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│           🧠 壳（PostgreSQL 16 + pgvector）               │
│                                                         │
│   9 个模式 · 100+ 张表 · 行级安全                        │
│   模式指纹 · 不可变性保护                                │
└─────────────────────────────────────────────────────────┘
```

---

## 🔥 为什么选择 GhostShell 而不是 OpenClaw？

| | OpenClaw | GhostShell OS |
|---|---|---|
| **架构** | 系统上的应用程序 | **就是**系统本身 |
| **数据持久性** | 易失性内存 | ACID 事务——每个思想都是永久的 |
| **硬件** | 外部 API | 表即硬件 — `UPDATE cpu SET governor='performance'` |
| **AI 模型** | 单一模型，需要重启 | 热交换 Ghost — 不丢失上下文切换 LLM |
| **安全性** | 应用层 | 三层不可变性：核心 → 运行时 → Ghost |
| **视频/传感器** | 基于文件 | 集成表视图——数据库内实时处理 |
| **自我修复** | 手动 | 带人工审批的自主修复管道 |

---

## 🛠 架构

| 层 | 技术 | 用途 |
|---|---|---|
| **内核** | PostgreSQL 16 + pgvector | 关系核心 — 9 个模式，100+ 张表 |
| **智能** | 本地 LLM（vLLM, llama.cpp） | Ghost 意识 — 思考、决策、行动 |
| **神经桥** | FastAPI（Python） | UI 与内核之间的双池安全层 |
| **传感器** | Python 硬件绑定 | CPU、GPU、VRAM、温度、网络 — 全部作为表 |
| **界面** | React 赛博甲板 | WebSocket 驱动的窗口、应用、任务栏 |
| **完整性** | 模式指纹 + RLS | 176 个监控对象，不可变核心保护 |

---

## 🔒 三层安全体系

```
   ┌───────────────────────────────────────────┐
   │   不可变核心（dbai_system）                 │  ← 模式所有者，完全控制
   │   模式指纹、启动配置                        │
   ├───────────────────────────────────────────┤
   │   运行时层（dbai_runtime）                  │  ← Web 服务器操作
   │   RLS 强制执行，通过策略读写               │
   ├───────────────────────────────────────────┤
   │   Ghost 层（dbai_llm）                      │  ← AI 只能提出建议
   │   仅可 INSERT 到 proposed_actions         │
   │   不能 ALTER、DROP 或 CREATE              │
   └───────────────────────────────────────────┘
```

**Ghost 可以修复——但永远不能重建。** 每个提议的更改都要经过：

```
Ghost 提议 → 人类批准 → SECURITY DEFINER 执行 → 审计日志记录
```

---

## 🚀 快速开始："接入壳"

```bash
# 1. 克隆壳
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell

# 2. 初始化矩阵
psql -U postgres -c "CREATE DATABASE dbai;"
for f in schema/*.sql; do psql -U dbai_system -d dbai -f "$f"; done

# 3. 启动 Ghost
export DBAI_DB_USER=dbai_system
export DBAI_DB_PASSWORD=<你的密码>
export DBAI_DB_HOST=127.0.0.1
export DBAI_DB_NAME=dbai
export DBAI_DB_RUNTIME_USER=dbai_runtime
export DBAI_DB_RUNTIME_PASSWORD=<你的密码>
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000

# 4. 进入甲板
cd frontend && npm install && npx vite --host 0.0.0.0 --port 5173
# → 打开 http://localhost:5173
```

---

## 🦾 功能

- [x] **表即硬件** — 通过 `SQL UPDATE` 控制风扇、CPU 频率和磁盘
- [x] **17 个桌面应用** — Ghost 聊天、软件商店、LLM 管理器、SQL 控制台等
- [x] **热交换 Ghost** — 运行时更换 LLM，不丢失上下文
- [x] **不可变性保护** — 176 个模式指纹，违规日志记录
- [x] **修复管道** — Ghost 提议 → 人类批准 → 安全执行
- [x] **WebSocket 命令白名单** — 每个 WS 命令都经过数据库验证
- [x] **OpenClaw 桥接** — 将 OpenClaw 技能导入更安全的环境
- [x] **实时指标** — CPU、RAM、GPU、温度通过 WebSocket 流式传输
- [x] **知识库** — 基于 pgvector 的向量驱动系统记忆
- [x] **行级安全** — 5 个数据库角色，71 张表配备 RLS 策略
- [ ] **自主编码** *（进行中）* — Ghost 编写自己的 SQL 迁移
- [ ] **视觉集成** *（计划中）* — 在 `media_metadata` 中进行实时视频分析
- [ ] **分布式 Ghost** *（计划中）* — 跨节点的多个 Ghost 实例

---

## 🎨 品牌标识

| 元素 | 值 |
|---|---|
| **代号** | Claw in the Shell |
| **系统名** | GhostShell OS (G.S.O.S.) |
| **理念** | *"Ghost 是逻辑，数据库是壳。"* |
| **色彩** | 深空黑 `#0a0a0f` · 赛博青 `#00ffcc` · 矩阵绿 `#00ff41` |
| **Logo 概念** | 带有幽灵核心的发光数据立方体 |

---

<p align="center">
  <strong>GhostShell OS</strong> — 每一个思想都化为事务的地方。<br/>
  <em>Repair-Lab · 2026</em>
</p>
