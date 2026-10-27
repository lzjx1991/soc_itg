# soc_itg — SoC 集成工具

以 **Python 为核心、Tcl 为工具手脚**的 SoC 集成平台：
把「描述 → 生成 → 编排 → 检查 → 版本管理」串成闭环。

## 定位

- **第三方**：IP 生成、寄存器配置、IP-XACT 产出（Magillem / Arteris）
- **本工具自研**：RTL/IP 自动组装、top 生成、CSR 生成、流程编排、IP/配置/版本管理

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/design-decisions.md`](docs/design-decisions.md) | 结论纪要：决策记录 D1~D14 + 第二轮决策 |
| [`docs/architecture.md`](docs/architecture.md) | 架构：分层、模块、生成流水线 |
| [`docs/flow.md`](docs/flow.md) | 流程与数据契约（ipdb/soc/findings） |
| [`docs/pinmux-spec.md`](docs/pinmux-spec.md) | pinmux 规格（4 表 + 规则 + 安全 + APB4） |
| [`docs/requirements.md`](docs/requirements.md) | 需求细项与开放问题 |
| [`docs/issues.md`](docs/issues.md) | 无人值守执行的问题 / 决策记录 |

## 当前状态

v0.2 —— **骨架 + 可运行 demo**：`parse → assemble → check → generate` 已跑通
（IP-XACT 2009 → top RTL + CSR 头）。其余域（pinmux/CRG/SDC/filelist/verify/docs/ipgen）按设计待补。

## 快速开始（demo）

环境：Python 3.11

```bash
python3.11 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cd examples/demo_soc
../../.venv/bin/python make_pinmux_xlsx.py
PYTHONPATH=../../src ../../.venv/bin/python -m soc_itg.cli.main pinmux
PYTHONPATH=../../src ../../.venv/bin/python -m soc_itg.cli.main build
```

产物：`build/ipdb.json`、`build/soc.json`、`build/pinmux.json`、`generated/rtl/demo_soc.v`、`generated/csr/demo_soc_csr.h`。

单步执行：`soc-itg parse | assemble | check | generate -g top|csr | pinmux <xlsx> | build`（加 `-C <工程目录>`）。

## 测试

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## 目录

```
src/soc_itg/
├── model/       IR（Component / SoC）
├── ipxact/      多版本解析（当前 2009）
├── design/      soc.yaml 加载
├── assemble.py  组装 → build/soc.json
├── checkers/    连接 / 地址检查
├── generators/  top_rtl / csr
├── pinmux/      Excel reader + 校验
└── cli/         命令行
examples/demo_soc/   demo 工程
tests/               冒烟测试
```

## 快速背景

- 本机 IP-XACT 格式为 **SPIRIT 1685-2009**（支持路线 2009→2014→2022→1.5→1.4）
- 连接语法：`insta.bundle = instb.bundle`（对标 IP-XACT `interconnection`）
- 关键能力：bundle 混合方向、方向自动推断、跨层自动穿端口
