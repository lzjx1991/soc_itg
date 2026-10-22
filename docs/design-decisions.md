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
| D13 | 标准版本 | 当前为 **2009**；是否统一到 2022 **待定** |
| D14 | 解析层 | 推荐 **lxml + pydantic 自研**；待确认 |

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

## 9. 开放问题（待拍板）

1. **版本路线**：坚持 2009 自研解析（A），还是推动统一到 2022（B）？
2. **解析层**：接受 lxml + pydantic 自研吗？
3. **P0 切入点**：从 CSR 生成开始，还是从 top RTL 组装开始？
4. **GUI 功能范围**：只读可视化 / 可视化编辑 / 触发流程？（后期，但需先定范围）
5. 其余需求细项（见 `docs/requirements.md`）：IP-XACT 元数据、命名规范、
   编排步骤全集、仓库结构、SoC 规模量级等。

---

## 10. 下一步

1. 拍板「开放问题」前 3 项
2. 补全 `docs/requirements.md` 剩余细项
3. 设计「连接解析 + 自动穿端口」算法
4. 搭 P0 最小骨架（conda 环境 + 数据模型 + 一个生成器 demo）
