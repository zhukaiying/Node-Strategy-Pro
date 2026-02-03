# Node-Strategy-Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PTrade](https://img.shields.io/badge/Platform-PTrade-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Stars](https://img.shields.io/github/stars/your-username/Node-Strategy-Pro?style=social)

**专业量化交易策略库 | A股PTrade平台适配**

[English](#english) | [中文](#中文说明)

</div>



## 中文说明

### 📖 项目简介

Node-Strategy-Pro 是一个面向 A股市场 的量化交易策略开源项目，由 **节点量化 (Node Quant)** 开发维护。本项目提供多种经过验证的量化策略，已适配 **PTrade 交易终端**，可直接用于实盘交易或回测研究。

### ✨ 策略列表

| 策略文件 | 策略名称 | 核心逻辑 | 适用场景 |
|---------|---------|---------|---------|
| `01_dual_moving_average.py` | 双均线趋势追踪策略 | 短周期均线上穿/下穿长周期均线产生买卖信号 | 趋势明显的市场 |
| `02_four_stirrers_ptrade.py` | 四大搅屎棍策略 | 行业轮动+小市值+ROE/ROA财务筛选，规避银行/煤炭/钢铁/有色领涨的存量市场 | 存量博弈环境识别 |
| `03_multi_factor.py` | 多因子选股策略 | 小市值+ROE双因子等权打分排序 | 沪深300成分股 |

---

### 🚀 快速开始

#### 环境要求

- Python 3.8+
- PTrade 交易终端（实盘/回测）
- 依赖库：`pandas`, `numpy`, `talib`（部分策略）

#### 安装依赖

```bash
pip install pandas numpy ta-lib
```

#### 本地测试（双均线策略示例）

```python
from strategies.01_dual_moving_average import DualMovingAverageStrategy
import pandas as pd
import numpy as np

# 生成模拟数据
dates = pd.date_range('2025-01-01', periods=100)
df = pd.DataFrame(np.random.randn(100).cumsum() + 100, index=dates, columns=['Close'])

# 初始化策略
strategy = DualMovingAverageStrategy(short_window=5, long_window=20)

# 运行策略
results = strategy.generate_signals(df)
print(results[['short_mavg', 'long_mavg', 'positions']].tail())
```

#### PTrade 平台使用

1. 登录 PTrade 交易终端
2. 新建策略文件，将策略代码粘贴
3. 设置回测参数（起止日期、初始资金等）
4. 运行回测或实盘交易

---

### 📊 策略详解

#### 1️⃣ 双均线趋势追踪策略

**原理：** 经典的趋势跟踪策略，利用移动平均线的交叉产生交易信号。

- **金叉买入**：短期均线上穿长期均线
- **死叉卖出**：短期均线下穿长期均线

**参数配置：**
| 参数 | 默认值 | 说明 |
|------|-------|------|
| `short_window` | 20 | 短期均线周期 |
| `long_window` | 60 | 长期均线周期 |

---

#### 2️⃣ 四大搅屎棍策略

**原理：** 基于A股市场特有的行业轮动现象，当银行、煤炭、钢铁、有色四大板块领涨时，往往预示着市场进入存量博弈阶段，此时应降低仓位规避风险。

**核心逻辑：**
1. **市场环境判断**：识别"存量博弈"环境
2. **行业对冲**：当四大搅屎棍（银行/煤炭/钢铁/有色）领涨时，策略空仓
3. **选股因子**：小市值 + ROE/ROA双重财务筛选，优选质优小盘股

**回测表现：**
- 回测区间：2015-01-05 至 2026-01-07
- 初始资金：￥100,000
- 调仓频率：每周一
<img width="2109" height="677" alt="9e6f571f1d09b60a9f7864c7c465b415" src="https://github.com/user-attachments/assets/bb696958-2c4c-489c-8f01-345361a733cc" />

---

#### 3️⃣ 多因子选股策略

**原理：** 经典多因子模型，结合价值因子与成长因子进行综合打分选股。

**因子构成：**
| 因子 | 权重方向 | 说明 |
|------|---------|------|
| `total_value` | 正向(1) | 市值因子，小市值优先 |
| `roe` | 负向(-1) | 盈利因子，高ROE优先 |

**关键参数：**
| 参数 | 默认值 | 说明 |
|------|-------|------|
| `tc` | 15 | 调仓频率（天） |
| `yb` | 63 | 样本长度（天） |
| `N` | 20 | 持仓数目 |

**回测表现：**
- 回测区间：2005-01-01 至 2016-12-31
- 累计收益：450.95%
![Uploading image.png…]()

---

### 📁 项目结构

```
Node-Strategy-Pro/
├── README.md                           # 项目说明文档
├── strategies/                         # 策略目录
│   ├── 01_dual_moving_average.py       # 双均线趋势追踪策略
│   ├── 02_four_stirrers_ptrade.py      # 四大搅屎棍策略（PTrade版）
│   └── 03_multi_factor.py              # 多因子选股策略
└── __pycache__/                        # Python缓存文件
```

---

### ⚠️ 风险提示

> **本项目仅供学习研究使用，不构成任何投资建议！**

1. 历史回测表现不代表未来收益
2. 量化策略存在模型失效风险
3. 实盘交易请充分理解策略逻辑
4. 建议先在模拟环境充分测试

---

### 🔧 PTrade 适配说明

本项目已针对 PTrade 平台进行适配，主要修改包括：

| 原JoinQuant语法 | PTrade适配语法 |
|----------------|---------------|
| `.XSHG` / `.XSHE` | `.SS` / `.SZ` |
| `attribute_history()` | `get_history()` |
| `get_current_data()` | `get_snapshot()` |
| 聚宽财务API | `get_fundamentals()` |
| 行业代码无后缀 | 行业代码加`.XBHS`后缀 |

---

### 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

### 📜 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 👋 关于我

- **作者**：**节点量化**佳佳
- **邮箱**：[249859399@qq.com]
- **公众号**：节点量化
|   📞 联系方式 |
|:------:|:----------:|
微信：xiaojiulaoliu
 📱 18570347035（微信同号） 
------

 在这里与大家分享一些精心研发的量化交易策略。
![alt text](image.png)

如果您对策略有任何疑问，或想深入交流量化投资，欢迎添加我的微信！

---

## English

### 📖 Introduction

Node-Strategy-Pro is an open-source quantitative trading strategy library for the **A-share (Chinese stock) market**, developed by **Node Quant**. This project provides multiple verified quantitative strategies, adapted for the **PTrade trading terminal**, ready for live trading or backtesting research.

### ✨ Strategy List

| File | Strategy Name | Core Logic | Applicable Scenario |
|------|--------------|------------|-------------------|
| `01_dual_moving_average.py` | Dual MA Crossover | Buy/sell signals from short MA crossing long MA | Trending markets |
| `02_four_stirrers_ptrade.py` | Four Stirrers Strategy | Industry rotation + small cap + ROE/ROA screening | Stock market rotation |
| `03_multi_factor.py` | Multi-Factor Selection | Small cap + ROE dual factor scoring | CSI 300 constituents |

### 🚀 Quick Start

```bash
# Install dependencies
pip install pandas numpy ta-lib

# Run example
python strategies/01_dual_moving_average.py
```

### ⚠️ Disclaimer

> **This project is for educational and research purposes only. It does not constitute investment advice!**

### 📜 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**⭐ 如果觉得有帮助，请给个 Star 支持一下！**

**⭐ If this helps you, please give it a Star!**

</div>



