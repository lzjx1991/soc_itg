# Issues / 决策记录(无人值守执行,待明日对齐)

> 本轮在无人值守下完成:文档落盘 + 代码骨架 + 可运行 demo。
> 下面是**遇到的问题**、**我做的决定**、**待你拍板项**。

## A. 已完成

- 文档:`architecture.md`、`flow.md`、`pinmux-spec.md`、`design-decisions.md`(§11 第二轮决策)
- 代码骨架(`src/soc_itg/`):model / ipxact / design / assemble / checkers / generators / cli
- 工具链:`pyproject.toml`、`environment.yml`、`requirements.txt`、`tests/`
- Demo:`examples/demo_soc/`(2 个 IP-XACT 2009 + soc.yaml + pinmux.xlsx)→ 全链路 + pinmux reader 跑通
- **Pinmux Excel reader**(`src/soc_itg/pinmux/`):4 sheet → Pinmux 模型 + 校验;CLI `soc-itg pinmux`
- **连接文件 + 统一连线器**:`connectivity.json` + `netlist_emit`;top 端口=pads
- **top-CSR**:Excel(`type`/`bind`)→ `u_top_regs` 接入;`regtypes` 类型映射
- **CRG 引擎合入**:`crg_gen` 迁移为 `src/soc_itg/crg/`(parser/validate/generate + templates + 叶子 lib);`soc-itg crg` 读 `crg/*.xlsx` → `generated/crg/<mod>/`(+ rtl/sdc 汇总 + `build/crg.json`);原包已删除

## B. 环境问题与决定

| # | 问题 | 决定 |
|---|------|------|
| E1 | 本机无 conda | 用 **Python 3.11 venv**(`/home/server/.local/bin/python3.11`) |
| E2 | lxml/jinja2/typer 安装超时(网络慢) | demo 改用 **stdlib**:`xml.etree` 解析、`argparse` 做 CLI、字符串拼模板 |
| E3 | 未 `pip install -e .`(hatchling 未装) | demo 用 `PYTHONPATH=src python -m soc_itg.cli.main` 运行 |
| E4 | 依赖仅装 pydantic 2.14 + PyYAML 6.0.3 | 够 demo;lxml/jinja2/typer 计划后续补 |

**待拍板**:生产是否切回 **lxml + Jinja2 + typer**?(docs 计划是它们;当前 demo 用 stdlib 替代)

## C. 功能缺口(demo 未实现,按实现顺序)

| # | 缺口 | 说明 |
|---|------|------|
| I1 | 仅实现 IP-XACT **2009** 解析 | 1.4/1.5/2014/2022 抛 NotImplementedError |
| I2 | 无短名→路径 / 自动穿端口 / 子系统递归 | assemble 仅单层 |
| I3 | top RTL 生成简化 | 仅按 portMap 连同名逻辑信号;未连端口输出空 `.port()`;无位宽检查;无时钟复位到顶层端口 |
| I4 | 未套**文件头模板** + 未做完整 flatten 规范 | B1 要求 |
| I5 | 未实现 SDC 合并 / filelist / verify / docs / release | **CRG 生成已合入**;SDC(filelist/verify/docs/release)待补 |
| I6 | 未实现 `ipgen`(Excel→IP-XACT)与 Excel reader | 设计已定 |
| I7 | CSR 只出 OFFSET/MSK/POS 宏;无 struct 访问器 / RAL / security 标记 | 精简 demo |
| I8 | check 仅 连接存在性 + 地址冲突;无位宽/security 检查 | |

## D. 本轮修的问题

| # | 问题 | 处理 |
|---|------|------|
| F1 | 生成信号名含大写(`net_cpu0_PCLK`)违反"全小写" | 已改 `net = ...lower()` |

## E. 设计层面待对齐(影响大)

1. ~~top 的对外端口~~ → **已定:top 对外端口 = pads**(来自 pinmux `pads` 表,数字+模拟)。top 顶层端口就是 pad;数字 pad 经 pinmux,模拟 pad 直通。实现待 pinmux reader。
2. **未连接端口策略**:当前输出空 `.port()`;真实应 tie0/tie1/open?按方向区分?
3. **时钟/复位布线**:CRG 未实现,demo 只把 PCLK/PRESETn 在 master-slave 间直连。真实要接 CRG 输出。
4. **security 传播**:寄存器模型有 `security`,但 C 头/生成未体现;需定 C 头怎么写 secure 寄存器。
5. **`--top` 语义**:骨架暂无 `--top`(多 sub-top);需补。
6. **中间契约**:`ipdb.json`/`soc.json` 字段目前是 demo 最小集;随功能扩展需定 schema_version 迁移策略。

## G. Pinmux reader 实现约定(已实现,待确认)

- Sheet 名(大小写不敏感):`pads` / `function_share` / `padshare` / `bist_share`
- `pads` 列:`pad / type / wrapper / security` + 配置列 `NAME[WIDTH]`(如 `DS[3]`)
- 合并单元格:key 列(pad / group)向下填充
- 配置默认值格式:支持 `3`、`0x3`、`0b011`、`"011"`(长度=位宽)、`"0,1,1"`
- 模拟 pad:不进模式表;无 cfg
- `bist_share` 的 `[BIST_ENTRY]` 段:标记行 `BIST_ENTRY` → 表头 `bist_mode/pad/value` → 数据行
- type 缺省→digital;security 缺省→nonsecure
- 依赖新增:**openpyxl**(已装 3.1.5)

## H. CSR / pinmux 生成器约定(已实现,待确认)

**CSR(`generators/regblock.py`)** — APB4 寄存器块:
- 端口:PCLK/PRESETn/PADDR/PSEL/PENABLE/PWRITE/PWDATA/PSTRB/PRDATA/PREADY/PSLVERR/PPROT/err_irq
- **访问类型**:rw / ro / wo / rw1(只写一次)/ w1(只写一次)
- **写副作用**(modifiedWriteValue):w1c / w1s / w1t / w0c / w0s / w0t / clear / set / modify
- **读副作用**(readAction):rc(读清)/ rs(读置)
- **字节写使能**:按 PSTRB 逐字节更新(wmask)
- **写一次**:rw1/w1 用 `done_*` 标志,首次后忽略
- rw/wo → `o_*`;ro → `i_*`(读输入);wo 读返回 0
- security:寄存器任一字段 secure → `PPROT[1]==0` 才可写;非安全读 → PSLVERR + err_irq
- `generate -g csr` 每个有寄存器模型的实例生成 `<inst>_regs.v` + 汇总 C 头(含 `_SECURE` 标记)

**解析归一化(v2009)**:`read-write/read-only/write-only/read-writeOnce/writeOnce` + `modifiedWriteValue` + `readAction` → 规范枚举。

**Pinmux(`generators/pinmux.py` + `pinmux/registers.py`)**:
- 寄存器模型:每数字 pad 一个 `cfg_<pad>`(字段=配置列,≤8→8bit 否则 16bit);每组一个 `sel_<group>`;每 padshare pad 一个 `sel_<pad>`;一个 `bist_mode`
- cfg 拼接:字段按列序打包,不足 8/16 左补 0
- mux:`~bist_active ? (normal_sel==i)` / `bist_active ? (bist_mode==k)`;输出候选驱动 pad `dout/oe`;输入候选 `ip_* = sel ? pad_din : z`;空选 → oe=0/ie=1/dout=0(输入+tie0)
- `bist_active`:由 `[BIST_ENTRY]` 的 pad 组合(`pad_din == value`)与项派生
- wrapper 接口假设:`pad / data_i / data_o / oe / ie / cfg`;模拟 wrapper 仅 `pad`
- 内嵌寄存器块:pinmux 模块内部实例化 `<top>_pinmux_regs`(独立 APB4 slave)

**已知简化(待后续)**:
- pad 假定 **1-bit**;多比特 pad / 总线 pad 未处理(演示数据里 pad↔多比特 pin 存在位宽 mismatch,仅为结构演示)
- analog pad 只例化 wrapper,直通路径未连
- 影子寄存器 / 锁 / 计数器 / 硬件写(hw=w)语义未做;位宽检查、RAL 未做

## I. 连接文件 + 统一连线器(已实现)

- 新增 **`build/connectivity.json`**(netlist):`ports`(顶层 pads)/ `instances`(含各自 port 列表)/ `nets`(endpoints 列表,含方向/宽度/tri_state)
- 新增命令 **`soc-itg connect`** → 生成连接文件
- `generate -g top` 改为**统一 emitter**(`generators/netlist_emit.py`)消费连接文件,**不再就地"谁该连就连"**
- 连接来源:pads→顶层端口、IP 内部总线(`portMap` 展开)、pinmux↔IP
- 规则:记录方向/位宽;**单驱动校验**(tri-state 除外)

**已知限制**:
- pinmux 的 APB4 端口尚未接总线(top 里留空)
- pinmux↔IP:若该 IP pin 已被内部总线占用 → **跳过以避免多驱动**
- pinmux 模块内 pad(1-bit)↔多比特 pin 存在位宽 mismatch(demo 数据;建议映射到 1-bit pin)

## J. top-CSR 与 glue logic

**top-CSR(已实现)**:
- 输入 `top_csr.xlsx`(寄存器模板 + **`type`** 列 + **`bind`** 列;另有 `type_ref` 参考 sheet)
- **`type` 列**:rw/ro/wo/w1c/w1s/w1t/w0c/w0s/w0t/rc/rs/rw1/w1;经 `regtypes.resolve_type` 展开成 access+write_action+read_action
- `type_ref` sheet:type→access/write_action/read_action 映射 + 中文含义(供人参考)
- `soc-itg topcsr` → `build/topcsr.json`(MemoryMap + bindings)
- `generate -g csr` → `<top>_top_regs.v`(regblock,全类型 + security)
- `connect` → 实例 `u_top_regs` + 每 bind 一条 net:
  - **rw/wo 字段 → 驱动 `inst.port`**(字段输出为 driver)
  - **ro 字段 → 读 `inst.port`**(实例输出为 driver)
  - bind 逗号分隔 = 多目标;空 = 不建连接
- demo:`SYS_CTRL.EN→uart0.test_en`(rw)、`STATUS.BUSY←uart0.irq`(ro)

**glue logic(设计,未实现)**:
- 复杂:用户写 `top_glue.v` → 作为实例 `u_glue`,由 netlist 连
- 简单(tie/mux/assign):connectivity 增加 `assigns` 段,emitter 出 `assign`

## K. 连接语义扩展 + glue 定案

**tie / 悬空(soc.yaml connections 语法)**:
- `inst.port = inst.port` → interconnection
- `inst.port = 1'b0` / `1'b1` → tie 0/1
- `inst.port = none` → 悬空(不建连接)
- netlist 记录 `ties`;emitter 出 `.port(1'b0/1'b1)`;`none` 留 `.port()`

**glue logic(定案)**:
- 人工写 glue RTL → `ipgen` **抽取 IP-XACT** → 当**普通 IP 实例**接入(不做独立 assigns 机制)
- ipgen 待实现

## F. git

- **未提交**(遵守"未明确要求不提交")。待你确认后统一提交。
