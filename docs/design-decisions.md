# SoC 集成工具（soc_itg）— 结论纪要

> 版本：v0.1（方案梳理阶段）
> 日期：2026-10-22
> 状态：数据模型 + 解析层方向已基本定稿；仍有个别开放问题待拍板

---

## 1. 项目定位

构建一套以 **Python 为核心、Tcl 为工具手脚**的 SoC 集成平台，把
「描述 → 生成 → 编排 → 检查 → 版本管理」串成闭环。

### 1.1 能力边界

| 能力 | 归属 | 交付物 |
|------|------|--------|
| IP 生成 / 寄存器配置 / IP-XACT 产出 | 第三方（Magillem、Arteris） | IP-XACT、IP 交付件 |
| RTL/IP 自动组装 + top 生成 | **自研** | top RTL、连接网表 |
| CSR 集成生成 | **自研** | CSR RTL + C header + UVM RAL + 文档 |
| 流程编排 / 自动化 | **自研** | 统一的 lint/CDC/综合/DFT 调度 |
| IP catalog / 配置组合 / 版本管理 | **自研** | catalog、config matrix、lock file |

核心原则：第三方是「IP 供应商」，本工具是「集成与流程方」。
**消费标准接口（IP-XACT），不重复造 IP 零件。**

---

## 2. 环境事实（本机勘察）

- 完整数字 IC 流程：Synopsys（VCS / Verdi / SpyGlass / DC / Formality / PrimeTime）、
  Mentor、Xilinx、ARM（AMBA Designer、Socrates）
- 现成商用 SoC 集成类工具：
  - `arteris/FlexNoc5.3` + `Ncore` — NoC 互联自动生成
  - `arteris/Magillem_516` — 基于 IP-XACT 的 IP/寄存器/SoC 组装平台
  - `ARM/AMBA_Designerr_r3p5` — AMBA 互联/SoC 组装
- 脚本环境：Tcl 8.6.8、Python 3.6.8（偏老，需 conda 隔离或升级）

### 2.1 本机真实 IP-XACT 文件（用于验证模型）

| 类型 | 路径 |
|------|------|
| IP 组件 | `/home/server/armSocrates/workspace/ip/logical/Uart/PL011_VC/uart_pl011/ipxact/Uart.xml` |
| 总线定义 | `/home/server/armSocrates/workspace/ip/logical/shared/ipxact/busdefs/amba.com/...`（APB/AXI5/ACE5 等） |
| 顶层 design | `.../CLUSTER/Neoverse_N2_DSU_110_Cluster_1_Integration_Example_Design.xml` |
| Magillem 样例 | `/soft/eda/arteris/Magillem_516/documentation/ipxact_examples/` |

**关键事实：本机 IP-XACT 为 `SPIRIT 1685-2009`**
（命名空间 `http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009`）。
按时模式用 `<spirit:master>` / `<spirit:slave>` **子元素**表达，
而非 2014/2022 的 `interfaceMode` **属性**。

---

## 3. 关键决策记录（Decision Log）

| # | 决策点 | 结论 |
|---|--------|------|
| D1 | 自研范围 | 组装 + top 生成 + CSR 生成 + 流程编排 + IP/配置/版本管理；IP 生成与配置用第三方 |
| D2 | 技术栈 | **Python + Tcl 结合**（Python 决策，Tcl 驱动工具） |
| D3 | IP-XACT 获取 | **读文件**（消费第三方导出件） |
| D4 | 互联 | 仅做**装配接线**；NoC 互联交给 Arteris |
| D5 | 版本管理 | **git** |
| D6 | CI / 多用户 | **暂缓**，先本地单机跑通 |
| D7 | GUI | **可以有**，列为后期 |
| D8 | 跨层连接 | **自动穿端口**（= 标准 *bus interface propagation*） |
| D9 | 实例命名 | **局部唯一 + 路径消歧** |
| D10 | bundle 语义 | `inst.a` 中 `a` 是一个 **bundle**，可含混合 in/out，由 IP-XACT 定义 |
| D11 | 方向推断 | `=` 为**对称语法**，方向由工具从 IP-XACT 端口/接口元数据**推断** |
| D12 | 存放 | hierarchy 与 connections **放同一份文件** |
| D13 | 标准版本 | **支持全部版本：SPIRIT 1.4 / 1.5 + IEEE 1685-2009 / 2014 / 2022**（见 §6.3） |
| D14 | 解析层 | **已定：lxml + pydantic 自研多版本适配层** |

---

## 4. 数据模型（定稿草案）

### 4.1 心智模型

一份 SoC 描述 ≈ **先列元件，再列连线**：

- `hierarchy:` — 结构树（实例层次）；实例名在其父作用域内唯一
- `connections:` — 网表；用 `inst.port` / `inst.bundle` 引用实例
- 端点语法统一；工具按「端点是 bundle 还是物理端口」分派到两种内部表示

### 4.2 示例

```yaml
# soc.yaml —— 一份文件
hierarchy:                          # ① 结构树（局部唯一名）
  top:
    cluster0: {design: cpu_cluster}
    pll0:     {ip: pll_pll}
    cpu0:     {ip: cortex_a55}
    noc0:     {ip: arteris_flexnoc}

connections:                        # ② 统一 `=` 语法，工具按端点分派
  # bundle 互联 → interconnection
  - cluster0.l2.m_axi = noc0.s_axi[0]
  # 裸线 → adHocConnection（方向由端口元数据推断，自动广播）
  - noc0.clk = pll0.out
  - cpu0.clk = pll0.out
```

### 4.3 寻址语法

| 形式 | 含义 |
|------|------|
| `inst.port` | 实例的物理端口 |
| `inst.bundle` | 实例的接口/bundle |
| `inst.bundle[i]` | 数组接口的第 i 个 |
| `parent/child` | 跨作用域路径（消歧） |

### 4.4 与 IP-XACT 的映射

| 本工具语法 | IP-XACT 元素 |
|------------|--------------|
| `inst.bundle` | `activeInterface @componentInstanceRef + @busRef` |
| `insta.bundle = instb.bundle` | `interconnection`（两个 `activeInterface`） |
| `a.port = b.port`（裸线） | `adHocConnection` + `portReferences` |
| `hierarchy` | `componentInstance` 树 |
| 对外接口 | 层次化组件的 `busInterface`（可透传） |

**验证结论：`insta.axi = instb.axi` 可无损映射为标准 `interconnection`。**

---

## 5. 连接语义（与标准对齐）

### 5.1 两种连接构造

| 连接对象 | 内部表示 | 方向来源 |
|----------|----------|----------|
| bundle / 总线 | `interconnection` | interfaceMode + abstractionDefinition |
| 裸线（clk/rst/irq） | `adHocConnection` | component 的 `model/ports` 方向 |

### 5.2 方向推断算法

- **裸线**：读 component `spirit:model/spirit:ports` 的 `direction`。
  例：`pll0.out` 是 `out` → 判定为 driver；多个 `in` 端 → 自动广播。✓
- **bundle**：由 interfaceMode（initiator/target，2009 为 master/slave）
  + abstractionDefinition 的 `onMaster`/`onSlave`（2022：`onInitiator`/`onTarget`）
  逐信号判定 driver/load。
- **镜像模式反转**：`mirroredInitiator` / `mirroredTarget` 下每个逻辑信号方向 `in↔out` 反转。

### 5.3 自动穿端口（核心能力）

= 标准 **bus interface propagation**：层次化组件暴露一个 bus interface，
直接与内部实例接口相连，**无需逐层建端口**。

实现要点：穿透 bundle 时须**保留 abstractionType + portMap**，
并**逐信号处理方向**（master 侧 out ↔ slave 侧 in），不可整包当一根线。

### 5.4 纯连线子系统可自动化

| 子系统类型 | 内部内容 | connections 谁写 |
|------------|----------|------------------|
| 纯容器/透传 | 1 个孩子 + 暴露接口 | 自动，人写 0 行 |
| 结构化包装 | N 个孩子，1:1 暴露 | 规则生成，只写例外 |
| 真拓扑 | mux/解码/汇聚 | 人写（接口级） |

原则：**「有选择的地方」人写，「没得选的地方」自动。**

---

## 6. 解析层选型结论

### 6.1 候选库对比

| 库 | 2009 | 2014 | 2022 | busInterface/portMap | 层次设计 | 维护 |
|----|:---:|:---:|:---:|:---:|:---:|:---:|
| `ipyxact` | ✅ | ✅ | ❌ | ❌ | ❌ | 🟡 停更 |
| `peakrdl-ipxact` | ✅ | ✅ | ❌ | ⚠️ 经 SystemRDL，有损 | ✅ | 🟢 |
| `pyEDAA.IPXACT` | ✅ | ✅ | ✅ | ❌ | ⚠️ | 🟢 |
| `ipxact-compiler` | ❌ | ❌ | ✅ | ✅ 完整 | ✅ 完整 | 🟢（很新） |

### 6.2 结论

本机是 **2009**，而唯一完整支持 busInterface/portMap/层次设计的库
（`ipxact-compiler`）**仅支持 2022**；支持 2009 的库又都不支持 busInterface/portMap。

→ **没有现成库完美覆盖。** 现实路径二选一：

- **A（推荐）自研解析层**：`lxml` + `pydantic`，针对 Magillem 2009 输出；
  XSD 校验可借用 `pyEDAA.IPXACT` 的 schema。可控、不被不成熟库绑架。
- **B 统一到 2022**：让 Magillem 导出 2022，直接用 `ipxact-compiler`。
  省解析层，但依赖很新的库，且要改上游产出格式。

### 6.3 多版本支持架构（决策 D13）

目标：**支持全部版本：SPIRIT 1.4 / 1.5 + IEEE 1685-2009 / 2014 / 2022**。

采用 **适配器 + 归一化**（防腐层 / anti-corruption layer）：

```
IP-XACT 文件 ──检测版本──▶ 版本适配器(reader) ──▶ 统一内部模型(IR) ──▶ 生成器
                                2009 / 2014 / 2022
```

- **版本差异只允许存在于解析层**；生成器只认 IR。
- IR 为版本无关模型：`BusInterface` / `Port` / `Interconnection` /
  `AdHocConnection` / `ComponentInstance`。

**版本差异对照**

| 维度 | 2009 (SPIRIT) | 2014 | 2022 |
|------|---------------|------|------|
| 命名空间 | `spiritconsortium.org/.../SPIRIT/1685-2009` | `accellera.org/.../IPXACT/1685-2014` | `accellera.org/.../IPXACT/1685-2022` |
| 接口模式 | `<master>/<slave>` **元素** | `interfaceMode` **属性**（initiator/target…） | 同 2014 |
| 角色命名 | master / slave | initiator / target | initiator / target |
| 抽象定义 | `onMaster`/`onSlave` | `onInitiator`/`onTarget` | 同 2014 |
| 电源域 | 无 | 有 | 有 |

**归一化规则**：`master→initiator`、`slave→target`、
`mirroredMaster→mirroredInitiator`、`mirroredSlave→mirroredTarget`；
`system` / `monitor` 不变。

**实现要点**
- 命名空间感知解析：按**命名空间 URI** 匹配，不依赖前缀。
- 版本检测：读根元素命名空间 URI → 版本枚举。
- 每版本 XSD 校验（schema 可借用 Accellera / pyEDAA.IPXACT）。
- 每版本独立测试样例；缺失特性 → IR 可选字段置 `None`。
- 新增一个版本 = 新增一个 adapter + 一套测试集，不动生成器。

**版本与命名空间（本机实测）**

| 版本 | 命名空间 | 本机文件数 |
|------|----------|-----------:|
| SPIRIT 1.4 | `.../XMLSchema/SPIRIT/1.4` | 602 |
| SPIRIT 1.5 | `.../XMLSchema/SPIRIT/1.5` | 0（需另找样例） |
| IEEE 1685-2009 | `.../XMLSchema/SPIRIT/1685-2009` | 4904 |
| IEEE 1685-2014 | `.../XMLSchema/IPXACT/1685-2014` | 2788 |
| IEEE 1685-2022 | `.../XMLSchema/IPXACT/1685-2022` | 0 |

> 版本**只能靠命名空间 URI 判定**，不能靠目录名/前缀
> （例：本机 `samples/ipxact1.5/` 目录里其实是 1685-2009 文件）。

**额外成本**：1.5 ≈ 2009（差异小）；**1.4 更老、差异更大**
（`directConnection` / `isAddressable` / `maxMasters` / `systemGroupNames`），
需独立 adapter，工作量高于 2009→2014。

**路线**：2009（主力）→ 2014 → 2022 → 1.5 → 1.4（由易到难）。

---

## 7. 架构（分层）

```
[输入]   SoC 组装描述 (YAML)  +  第三方 IP-XACT (2009) 交付件
   │
[模型层]  SoC 对象模型：instance / net / addr / clk / rst / power     (Python + Pydantic)
   │
[引擎层]  Generators (top/addr/csr)  +  Checkers (冲突/连接/CDC)      (Python + Jinja2)
   │
[适配层]  VCS / SpyGlass / DC / PT / Formality 封装                    (Tcl 驱动 + Python 解析)
   │
[接口层]  CLI  +  Python API  +  CI hooks                              (Python)
   │
[管理层]  IP catalog / 配置组合 / 版本锁定 (lock file)                  (Python + git)
```

Python 负责数据与逻辑；Tcl 只负责驱动工具与采集结果。
铁律：**不让 Tcl 承担业务逻辑。**

---

## 8. 迭代路线图

| 阶段 | 目标 | 验收 |
|------|------|------|
| P0 | 打通最小闭环 | 单 IP：描述 → CSR 生成 → VCS lint 通过 |
| P1 | top 组装 | top RTL + 地址映射 + 冲突/连接检查 |
| P2 | 流程编排 | 接 VCS lint / SpyGlass，确定性 + 增量 |
| P3 | 管理体系 | IP catalog + 版本锁定（CI 后续） |
| P4 | 进阶 | CDC/RDC、多级 top、电源域（UPF）、GUI |

---

## 9. 开放问题

> 已解决：版本路线（全版本）、解析层（lxml+pydantic 自研）、F1、C1、B1~B7、流程与数据契约、pinmux、安全 —— 见 §11。

1. **GUI 功能范围**：只读可视化 / 可视化编辑 / 触发流程？（后期）
2. **CRG**：等用户提供 Excel→CRG 脚本后合入。
3. 其余细项（`docs/requirements.md`）。

---

## 10. 下一步

1. 落地文档（architecture / flow / pinmux-spec）与骨架
2. 合入 CRG 脚本（待提供）
3. 细化验证环境 / 文档发布 / Phase B flow

---

## 11. 第二轮决策（C1/B/F/流程/pinmux/安全）

### 11.1 依赖与仓库（F1）
- **结构**：全多仓 —— 工具仓 + 设计仓 + 每子系统一仓 + 每 IP 一仓。
- **引用**：**L0 极简 + git submodule**。`soc.yaml` 的依赖写 `repo + ref`；commit 由 submodule 原生钉住。
- 不用 catalog/lock（L1/L2 留待需要时再加）。每仓都是工程根（cwd 上下文）。

### 11.2 输入（C1）
- 第三方 IP → **IP-XACT**；自研 IP → **Excel**。
- **集成工具只读 IP-XACT**；自研 IP 由 `soc-itg ipgen --top <ip>` 生成完整 IP-XACT。
- `ipgen`：Excel(寄存器) + RTL(端口自动提取) + `ip.yaml`/`portmap.yaml`(接口) → IP-XACT。
  portmap 采用「脚本生成草稿 + 人工确认一次」。
- 寄存器入口统一=IP-XACT；pinmux/CRG 仍用 Excel（各自 reader）。

### 11.3 RTL 生成（B1~B7）
- **Verilog-2001**，接口 **flatten** 成信号。
- 命名全小写；缩进 4 空格；统一文件头模板（人工填）。
- B3 位宽/协议：**只检查不转换**。
- B4 层次：**多级**（递归）。
- B5 top 文件：**按域拆分**。
- B7 输出：**全量**（RTL + SDC + 综合脚本 + filelist）。
- CSR 从端：**APB4**。

### 11.4 流程与数据契约
- 阶段：`ipgen → parse → assemble → check → generate → release →(flow)`。
- 中间契约：**JSON + Pydantic**，带 `schema_version`；中枢 `build/soc.json`。
- 子命令单独跑 + `build` 串联；增量按输入哈希。
- 详见 `docs/flow.md`。

### 11.5 SDC / filelist
- **SDC**：CRG→SDC 骨架 + **合入 IP SDC** + 人工时序预算（false path/IO delay 等不可自动）。
- **filelist**：依赖图 + 拓扑排序 → 中性 JSON → 分 **sim / syn / fpga** 三套（语法不同，须分工具出）。详见 `docs/flow.md`。

### 11.6 Pinmux（详见 `docs/pinmux-spec.md`）
- 输入 **4 表**：`pads`(模拟+数字,单一来源,含 wrapper+security+配置字段) / `function_share`(按 group 的 sel) / `padshare`(按 pad 的 sel) / `bist_share`(覆盖所有数字 pad + BIST_ENTRY)。
- Pad **wrapper** 隔离工艺；8/16bit cfg(≤8→8,否则16)，每 pad 一个 cfg 寄存器。
- 空 cell → 输入 + tie0；bist_mode → 全数字 pad 切 BIST。
- 寄存器：**独立 APB4 从端**，只定 offset；输出寄存器模板格式 Excel。

### 11.7 安全属性（全局）
- 与 APB4 `PPROT` 一致；覆盖 secure pad 的 cfg+sel。
- 门控 `PPROT[1]==0`；非安全写忽略、读 **PSLVERR + error interrupt**。
- 寄存器 IR 全局带 `security` 字段（不止 pinmux）。

### 11.8 环境
- 本机无 conda；使用 **Python 3.11 venv**（`/home/server/.local/bin/python3.11`）。
- 依赖：pydantic / pyyaml / lxml / jinja2 / typer / pytest。
