# soc_itg 架构

> 版本 v0.2 · 状态:已确定主体架构,骨架搭建中
> 关联:`design-decisions.md`(决策记录)、`flow.md`(流程与数据契约)、`pinmux-spec.md`(pinmux 规格)

## 1. 定位

以 **Python 为核心、Tcl 为工具手脚**的 SoC 集成工具(ITG)。第三方负责 IP 生成与配置(Magillem/Arteris),本工具负责:
集成描述 → 校验 → 生成 RTL/CSR/SDC/filelist/验证环境/文档 → 流程编排。

## 2. 分层

```
   CLI / Python API
        │
  ┌─────┴───────────────────────────────────────┐
  │ generators · checkers · design · ipgen · release  │  应用层
  └─────┬─────────────┬───────────────┬──────────┘
        │             │               │
     design        eda(PhaseB)     templates
        │
  ┌─────┴─────────────┐
  │ ipxact(多版本解析) │
  └─────┬─────────────┘
        │
     model(IR,无依赖基座)
```

**依赖只允许自上而下;model 是基座,不反向依赖。**

## 3. 主包结构

```
src/soc_itg/
├── model/            # 版本无关 IR(Pydantic):component/design/connection/register/clock_reset/pinmux/crg
├── ipxact/           # 多版本解析 + 写出
│   ├── detect.py     #   命名空间 URI → 版本
│   ├── reader.py     #   统一读取入口
│   ├── busdef.py     #   busDefinition / abstractionDefinition 加载
│   ├── resolve.py    #   VLNV 引用解析
│   └── adapters/     #   spirit14/spirit15/v2009/v2014/v2022
├── design/           # 用户描述加载与解析(连接/pinmux/crg)
├── ipgen/            # 自研 IP:Excel + RTL 端口 + portmap → IP-XACT
├── generators/
│   ├── rtl/          #   top + pinmux 逻辑 + crg 逻辑
│   ├── csr/          #   寄存器块 RTL + C头 + RAL + 文档
│   ├── sdc/          #   CRG→SDC + 合入 IP SDC
│   ├── filelist/     #   sim / syn / fpga
│   ├── verify/       #   初版验证环境
│   └── docs/         #   IP 文档 + reg 文档
├── checkers/         # 完整性:连接/pinmux/crg/地址/位宽
├── registers/        # 寄存器源:ipxact(memoryMap) / excel(自研)
├── io/               # 通用 IO:excel 读取(合并单元格 forward-fill)
├── release/          # 版本发布
├── deps/             # 依赖(submodule,L0)
├── eda/              # (Phase B) Tcl 适配:tools/<tool>/{tool.py,driver.tcl.j2,parser.py}
├── templates/        # Jinja2 模板(随包发布)
├── cli/              # 命令行
└── utils/
```

## 4. 生成流水线

```
输入: IP-XACT + soc.yaml(连接) + pinmux(Excel) + crg(Excel)
  ① parse     → build/ipdb.json     (归一化 IP 库)
  ② assemble  → build/soc.json      (已解析 SoC 模型)
  ③ check     → build/findings.json (完整性/地址/位宽/安全)
  ④ generate  → generated/**        (RTL/CSR/SDC/filelist/verify/docs)
  ⑤ release   → release/<ver>/
  ⑥ (Phase B) flow → EDA 工具
```

top 对外端口 = **pads**(来自 pinmux `pads` 表,数字+模拟);数字 pad 经 pinmux、模拟 pad 直通。

详见 `flow.md`。

## 5. 生成产物(对应需求 1~8)

| # | 产物 | 生成器 |
|---|------|--------|
| 3 | RTL(top/pinmux/crg,Verilog-2001,flatten) | `generators/rtl` |
| 4 | SDC(CRG→SDC + 合入 IP SDC) | `generators/sdc` |
| 5 | 各 IP reg header | `generators/csr`(C 头) |
| 6 | 初版验证环境 | `generators/verify` |
| 7 | sim/syn/fpga filelist | `generators/filelist` |
| 8 | IP 文档 + reg 文档 + 版本发布 | `generators/docs` + `release/` |
| — | pinmux RTL + pinmux reg Excel | `generators/rtl` + `generators/csr` |

## 6. Python ↔ Tcl 边界(Phase B)

- Python 决策/生成;Tcl 只驱动工具 + 采集结果。
- 桥接:Python 渲染 `.tcl.j2` → `tclsh`/工具执行 → 解析输出 → 结构化回流。
- 参数开放(`TaskSpec.params: dict`),per-tool 可选 schema;**不预定义**,接工具时再补。
- 逃生舱:project 可覆盖驱动脚本(`<project>/scripts/<tool>_driver.tcl.j2`)。

## 7. 插件机制

Generator / Checker 统一基类 + 注册表,核心不认识具体实现;新增能力 = 加文件,不动核心。

## 8. 版本支持(IP-XACT)

支持 SPIRIT 1.4/1.5 + IEEE 1685-2009/2014/2022。适配器 + 归一化 IR,版本差异**只在解析层**。
实现路线:2009(主力)→ 2014 → 2022 → 1.5 → 1.4。

## 9. 编码/输出规范

- **Verilog-2001**,接口 **flatten** 成信号。
- 命名**全小写**;缩进 **4 空格**;统一文件头模板(人工填字段)。
- 生成**确定、幂等**;产物与源分离(生成物禁止手改)。

## 10. 两个 Phase

| | Phase A(现在) | Phase B(以后) |
|--|----------------|----------------|
| 范围 | parse→assemble→check→generate→release | 跑 EDA 工具 |
| EDA | 生成后仅 lint 验证 | 综合/lint/CDC/RDC/VCLP/Palladium/FPGA |
