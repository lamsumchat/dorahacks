# AI Awakening 黑客松 — 讨论归档

## 比赛概况

- **名称**: AI Awakening (Mantle 主办, DoraHacks 平台)
- **主题**: AI × Web3
- **核心要求**: 部署在 Mantle Network 上，开源 repo + 可运行 demo

## 关键概念梳理

### Mantle & L2
- Mantle 是以太坊 L2 (Optimistic Rollup)，EVM 兼容
- 交易更便宜更快，安全性继承自以太坊 L1
- 用 $MNT 作 gas（不是 ETH）
- 开发体验和以太坊几乎一样，只是 RPC 端点不同
- 开发阶段用 Testnet（免费水龙头），主网部署成本极低
- 背后是 Bybit/BitDAO，在 L2 中属中上游（TVL 数亿美元级别）
- 定位面向机构和 TradFi

### L1 vs L2
- L1 自己负责共识、执行、存储、安全（但慢且贵）
- L2 把交易在自己链上执行，只把结果/证明提交回 L1
- L2 有自己的区块链结构，但信任根在 L1 上
- 挑战期是 L2 (Optimistic Rollup) 的机制，裁决在 L1 执行
- "回滚"不是篡改 L1，而是 L1 合约里标记 L2 状态无效（新交易更新变量）

### Bybit vs Mantle
- Bybit = CEX（链下交易所），提供市场数据和交易 API
- Mantle = L2 链，链上 DEX/DeFi
- 两者互补：Bybit 提供数据 + CEX 交易能力，Mantle 提供链上执行和可验证性

### 价格数据来源
- Bybit API: CEX 价格，实时性好，免费
- DEX 合约: 链上池子价格，去中心化但可能有偏差
- Oracle (Chainlink/Pyth): 聚合多源价格，合约可直接读取
- 第三方索引 (The Graph, Dune): 历史数据查询

### Mantle 生态核心资产
- $MNT (原生代币), mETH (质押ETH), fBTC (合成BTC), MI4 (指数资产), COOK (治理代币)
- 桥接资产: WETH, USDT, USDC, WBTC 等
- 合作资产: USDe (Ethena), USDY (Ondo)
- 主要 DEX: Agni Finance, FusionX, Merchant Moe, iZiSwap

## 赛道分析

### 所有赛道一览
1. **AI Trading & Strategy** — AI quant bot, macro-driven 合约 (BGA 赞助)
2. **AI Alpha & Data** — 链上数据分析, smart money 追踪 (Mirana Ventures 赞助)
3. **AI x RWA** — 动态收益策略, 自动风控 (USDY, mETH)
4. **Consumer & Viral DApps** — 游戏化交易界面, 病毒式消费应用
5. **AI DevTools** — gas 优化工具, 审计助手
6. **Agentic Wallets & Economy** — AI agent 钱包 (Byreal 赞助)

### Trading 赛道四类策略对比
| | AI Quant Bot | Macro-Driven | Arbitrage | AI MM |
|---|---|---|---|---|
| 外部资源需求 | 最低 | 高 | 高 | 最高 |
| AI 角色 | 核心(预测) | 核心(判断) | 边缘(优化) | 中等(调参) |
| 金融知识需求 | 高 | 中高 | 中高 | 最高 |
| 黑客松适合度 | 较高 | 中等 | 较低 | 较低 |

### 出成果难度排名（AI 辅助 coding 条件下）
1. Consumer & Viral DApps（最容易）
2. Alpha & Data 路线A
3. AI DevTools
4. AI Quant Bot
5. Agentic Wallets
6. AI x RWA
7. 其他 Trading 子方向

## 参赛者技术背景

- Python 基础 + AI Agent 核心设计原理
- 区块链广泛了解但深度不足（知道成分，不熟具体机制/协议）
- 金融概念和交易机制大致了解，量化策略/因子未深入
- 神经网络知道原理，未专门训练过
- 有股票市场 TradingAgents 经验（输出投研报告）
- 偏好完整且相对硬核的项目
- UI/UX taste 不足

## 最终决定：Alpha & Data 赛道

### 方案：Smart Money 分析 + 信号 Agent

**三阶段架构：**

```
阶段一：数据层（路线A）
  监控 Mantle 链上大户钱包行为
  → 谁在买/卖什么？资金流向？

阶段二：分析层（核心优势）
  AI Agent 综合链上数据，生成投研级别的分析
  → 多 Agent 架构: data collector → analyzer → signal generator → risk assessor

阶段三：信号层（路线B 可验证性）
  分析结论 → 具体交易信号 → 信号上链记录（Mantle 合约）
  → 事后可验证信号准确率
```

### 选择理由
1. TradingAgents 经验直接复用（换数据源到链上）
2. AI 角色核心且有深度（多 Agent 架构）
3. 不需要执行交易，只输出+记录信号
4. 技术栈友好：Python 抓数据 + AI agent 分析 + 简单 Solidity 记录
5. Mantle 生态贡献度天然高（分析的就是 Mantle 数据）
6. 可量力而行（路线A → 路线B 灵活调整）

### 评分标准
- General (60%): 数据源质量 / AI 分析深度 / 技术完整度 / 可持续性
- Track-Specific (40%): Insight 独特性 + 可视化质量 / 策略复杂度 + 可验证性

### 待后续讨论
- [ ] 具体技术架构设计
- [ ] 数据源选择和获取方案
- [ ] Agent 系统设计细节
- [ ] 智能合约设计（信号记录）
- [ ] 开发计划和时间线

---

## 第二轮脑暴：Agent 架构与验证模式

### 时间预期与目标修正
- 初期投入 2-3 天，后续视状态延伸
- 目标改为：**先做出一个能通过某种模式验证的完整产品**，拿奖优化放后期
- Demo 形态：**Streamlit/Gradio 简单 Web Dashboard**
- 赛道路径：Path A（数据分析）+ Path B（信号验证）融合，**A 为主、B 为锦上添花**

### Agent 架构选型：从多 Agent 图 → ReAct + Harness

**否决的方案**：照搬 TradingAgents 的"角色扮演 + 文本辩论"流水线（偏 2024 范式，多 Agent handoff 时 context loss 严重）

**最终选定：ReAct 主 Agent + 关键节点 Sub-Agent（对齐 Claude Code / Cursor / Devin 范式）**

```
[Research Analyst Agent] (ReAct 主循环, 单一连贯上下文)
   │
   ├── 数据访问工具（预定义）：whale_track / dex_flows / price_oracle / hedge_lookup ...
   ├── 基础分析工具（预定义）：calc_concentration / detect_breakout / compute_correlation ...
   ├── run_python（自由探索逃生口）：让 Agent 自己写 Pandas 做新分析
   └── Sub-Agent 工具（独立上下文）：
         · spawn_critic_agent（魔鬼代言人，主动查反向证据）
         · spawn_self_reviewer（事后回看历史信号）
   ↓
[最终结构化输出]：{asset, direction, confidence, reasoning_summary} → 上链 hash
```

### 关键设计原则
1. **数据 + 常用分析做成工具** = 稳定、快、可单测
2. **run_python 做成"逃生口"** = 应对 Web3 alpha 分析的探索性本质
3. **Critic 必须有独立上下文 + 工具调用能力**，不是单纯"嘴硬质疑"
4. **Reflexion loop 必须有界**（max 2 轮），超出则降低置信度输出
5. **沙盒选型**：黑客松阶段用 LangChain `PythonREPLTool` 即可（项目唯一用户，无需防御外部攻击），上线阶段再换 E2B / Modal 等托管沙盒

### 验证模式：B + D（实时前向追踪 + Agent 自评）
- **放弃严谨历史回测**：archive node / Mantle 历史索引覆盖弱、未来函数泄漏难处理、统计显著性需大量样本
- **采用方案**：
  - 实时跑信号 → 链上写 hash + timestamp → 等 N 小时后用真实价格回填
  - Agent 自我反思（回看自己过去判断的对错并解释）
- **可拿出的验证证据**：架构合理性 + 真实跑出的信号上链记录 + 自我反思报告
- **窄回测留 v2**：选 5-10 个已知历史鲸鱼移动事件做手工验证

---

## 第三轮脑暴：Smart Money 定义 + 数据源 + 工具集 + 合约 + Dashboard

### Smart Money 定义
- **核心引擎：行为异常检测**（不依赖预置名单，实时发现"谁在做不寻常的事"）
- **补充层：已知身份标注**（发现异动后查 Blockscout 标签，提升可解释性）
- 否决方案：纯历史表现筛选（Mantle 历史浅，数据不够）、纯大户 top N（噪音大，很多是合约/桥/死地址）

### 异常检测维度（按优先级）
1. **大额异动** — 单笔超过 7 天均值 N 倍（MVP 必做）
2. **桥接资金流入** — L1→Mantle 大额充值（MVP 必做）
3. 地址聚集 — 多地址同时段同方向操作（run_python 探索）
4. 新钱包首次大额操作（run_python 探索）
5. 时间异常 — 低流动性时段大额操作（v2）

### 数据源选定
| 数据源 | 接口 | 用途 |
|---|---|---|
| Mantle RPC (`rpc.mantle.xyz`) | JSON-RPC | 实时区块/交易监控 |
| Blockscout Explorer API (`explorer.mantle.xyz/api`) | REST (Etherscan 兼容) | Token 转账、地址历史、已知标签 |
| FusionX Subgraph | GraphQL | DEX swap 数据、池子状态 |
| Agni Finance SDK/Contracts | SDK + 合约调用 | DEX 数据补充 |
| Covalent API | REST | 批量历史数据备选 |
| Bybit API | REST/WebSocket | CEX 价格参考基准 |
| Bridge 合约 event logs | RPC | L1→L2 资金流入监控 |

### 工具集设计（四层）

**Layer 1 — 数据访问工具**
- `get_recent_large_transfers(token, min_value_usd, hours)`
- `get_dex_swaps(pool_or_token, hours)`
- `get_bridge_deposits(hours, min_value_usd)`
- `get_address_profile(address)` → 余额、历史、标签
- `get_token_top_holders(token, limit)`
- `get_price(token, source)` → Bybit 或 DEX

**Layer 2 — 基础分析工具**
- `detect_volume_anomaly(token, window_hours, threshold_sigma)`
- `detect_address_cluster(tx_list)` → 同时段同方向聚类
- `calc_net_flow(token, hours)` → 净流入/流出
- `check_address_age(address)` → 新钱包识别
- `enrich_with_labels(address_list)` → 批量标签查询

**Layer 3 — 自由探索**
- `run_python(code)` → 预装 pandas/numpy/web3.py，可调用 Layer 1 helpers
- 沙盒：黑客松阶段 PythonREPLTool，上线换 E2B

**Layer 4 — Sub-Agent 工具**
- `spawn_critic(hypothesis, evidence)` → 独立上下文 Critic
- `spawn_self_reviewer(signal_id)` → 事后反思

### Critic Sub-Agent 设计
- **独立上下文**：只接收 hypothesis + evidence，不看主 Agent 推理过程
- **结构化找茬清单**：对冲检查 / 身份检查 / 资金来源检查 / 时间窗口偏差 / 基准对比
- **有工具调用权限**：Layer 1 数据工具子集（无 run_python）
- **输出**：PASS 或 CHALLENGE(reason, counter_evidence)
- **循环上界**：max 2 轮，超出则降低置信度

### 信号上链合约 (AlphaSignalRegistry)
- **存储**：contentHash (bytes32) + timestamp + emitter + asset + direction (int8) + confidence (uint8) + timeHorizon
- **方法**：`emitSignal()` 写入 + `verifySignal()` 验证 hash
- **设计原则**：链上只存 hash，链下存完整推理 JSON。极简、低 gas、可验证
- **v2 扩展**：`resolveSignal()` 回填实际结果

### Dashboard (Streamlit, 4 页)
1. **Live Anomaly Feed** — 实时异常事件流（让评委看到"系统在跑"）
2. **Signal Dashboard** — 信号列表 + 方向/置信度/Critic 结果 + 上链 proof 链接
3. **Agent Reasoning Trace** — 选中信号后展示完整推理链（核心展示 AI 深度）
4. **Mantle Ecosystem Overview** — 核心资产状态 + 近期关注地址概览（满足生态贡献度评分）

---

## 第四轮：技术栈 + LLM + 命名 + 开发计划

### 项目名：Mantis（Mantle + Intelligence + Signal，螳螂=精准捕猎）

### 技术栈
- **主框架**：LangGraph 最小化（`create_react_agent` 预构建 + 自定义 tools）
- **Critic sub-agent**：独立 LLM call with tools（不走 LangGraph）
- **工具组件**：LangChain 个别工具（PythonREPLTool 等）
- **合约**：Solidity ^0.8.20，Hardhat/Foundry 部署
- **前端**：Streamlit
- **链交互**：web3.py

### LLM 选型：可配置多 provider
```
main_agent:  anthropic/claude-sonnet-4（默认，强推理 + tool calling）
critic:      anthropic/claude-haiku（默认，轻量省钱）
reviewer:    anthropic/claude-haiku（默认）
# 支持切换：openai, deepseek, google 等
```
统一接口：LangChain `init_chat_model(model, provider)`

### 开发计划（每个 Milestone 结束都有可运行产物）
- **M0（半天）脚手架**：repo 结构 + 配置系统 + API 连接验证
- **M1（1 天）数据层**：Layer 1 全部数据工具 + Layer 2 核心分析工具 + smoke test
- **M2（1 天）主 Agent**：LangGraph ReAct agent + 全部工具注册 + system prompt + 端到端信号输出
- **M3（半天）Critic**：spawn_critic + 反思循环（max 2 轮）
- **M4（半天）上链**：AlphaSignalRegistry 部署 Testnet + web3.py 封装
- **M5（1 天）Dashboard**：Streamlit 4 页
- **M6（弹性）打磨**：self_reviewer + 代码清理 + README + demo 视频
- **关键路径**：M0→M1→M2 是核心（做完有可跑的 Agent），M3/M4 互不依赖可灵活调整
