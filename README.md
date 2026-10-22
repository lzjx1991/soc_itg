# soc_itg — SoC 集成工具

以 **Python 为核心、Tcl 为工具手脚**的 SoC 集成平台：
把「描述 → 生成 → 编排 → 检查 → 版本管理」串成闭环。

## 定位

- **第三方**：IP 生成、寄存器配置、IP-XACT 产出（Magillem / Arteris）
- **本工具自研**：RTL/IP 自动组装、top 生成、CSR 生成、流程编排、IP/配置/版本管理

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/design-decisions.md`](docs/design-decisions.md) | **结论纪要**：决策记录、数据模型、连接语义、解析层选型、架构、路线图 |
| [`docs/requirements.md`](docs/requirements.md) | 需求细项与开放问题清单 |

## 当前状态

方案梳理阶段（v0.1）。数据模型与解析层方向已基本定稿，
个别开放问题待拍板（见 design-decisions 第 9 节）。

## 快速背景

- 本机 IP-XACT 格式为 **SPIRIT 1685-2009**
- 连接语法：`insta.bundle = instb.bundle`（对标 IP-XACT `interconnection`）
- 关键能力：bundle 混合方向、方向自动推断、跨层自动穿端口
