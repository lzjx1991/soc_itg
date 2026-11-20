# Repository 结构规范

> 关联:`hierarchy-integration.md`、`architecture.md`

## 1. 总体:扁平 superproject + 平级 repo

- 一个 **git superproject**(工作区)下,所有 repo 都是**平级 submodule**(无嵌套)。
- repo **内部不再放 repo**;层级关系靠 `soc.yaml` 的**实例引用**表达(逻辑层级,非目录嵌套)。
- 每个 repo 结构**一致**;角色(top / 子系统 / IP)由**位置与引用**决定,不由目录区分。

```
my_soc/                     # superproject
├── repo.yaml               # default_top + repos 列表
├── repo_top/               # submodule(顶层设计之一)
├── repo_subsys_a/          # submodule
├── repo_ip_x/              # submodule
├── build/  generated/      # (superproject 级可选,一般不用)
└── .soc_itg/
```

## 2. 统一 repo 内部结构

```
<repo>/
├── <repo>_info.yaml # 元数据(name/vlnv)+ EDA flow 配置(per-tool 多 top=harden)
├── soc.yaml         # 设计:实例引用 + 连接 + 地址(叶子可无)
├── pinmux/          # pinmux 表(*.xlsx,可多个)
├── crg/             # CRG 表(*.xlsx,可多个)
├── csr/             # 寄存器表(*.xlsx,可多个;top/IP 寄存器)
├── rtl/             # 源 RTL(IP RTL / glue)
├── glue/            # 胶合 RTL(人工写;可 ipgen 抽 XML)
├── ipxact/          # 对外 IP-XACT 组件(叶子:第三方/手写;组合:生成)
├── filelist/        # 可选:自带 .f
├── generated/       # 生成产物(★提交):rtl/ csr/ sdc/ filelist/ verify/ docs/
├── build/           # 中间契约(gitignore)
├── release/         # 版本发布(可选)
└── README.md
```

## 3. 目录角色

| 类别 | 目录 | 提交? |
|------|------|:---:|
| 源 | `rtl/ glue/ ipxact/ filelist/ pinmux/ crg/ csr/ <repo>_info.yaml soc.yaml` | ✅ |
| 生成产物 | `generated/**` | ✅ **提交**(供他人作 submodule 消费) |
| 临时产物 | `build/**`、`.soc_itg/**` | ❌ **不上传 git** |

> 注:组合仓的 `ipxact/` 是**生成物**(design→component),但与叶子放同目录、同样提交,父层按它连线。

## 4. `<repo>_info.yaml`(元数据 + flow)

```yaml
name: repo_subsys_a
vlnv: acme.com:Subsys:subsys_a:1.0.0   # 对外标识(叶子必填;组合可生成)
description: 可选
# 其余为 EDA flow 配置(见 §8)
```

> **`integrate`(是否重新集成)不在这里**——由**上层在 `soc.yaml` 的实例上决定**(见 §5)。

workspace(superproject)的容器配置(非统一 repo):
```yaml
name: my_soc
default_top: repo_top
repos: [repo_top, repo_subsys_a, repo_ip_x]
```

## 5. `soc.yaml`(设计描述)

```yaml
design:
  name: subsys_a
  instances:
    - { name: cpu0,  repo: repo_cpu, integrate: true }                    # 上层决定:重新集成
    - { name: uart0, vlnv: acme.com:PERIPH:uart:1.0.0, integrate: false } # 用现成 ipxact
    - { name: gl0,   ipxact: glue/glue.xml }                             # 直接引用本地 ipxact
  connections:
    - cpu0.APB_Master = uart0.APB_Slave     # interconnection
    - insta.a = instc.c                     # 跨层路径(自动穿端口)
    - cpu0.halt = 1'b0                      # tie
    - cpu0.dbg  = none                      # 悬空
  address_map:
    - { region: uart0, base: 0x10000000, size: 0x1000 }
```

## 6. 层级表达(逻辑,非目录嵌套)

- 实例引用 **sibling repo**(`repo:` / `vlnv:`)→ 逻辑层级;
- 跨层连接用**路径**(`insta.a = instc.c`),由 `integrate` 自动穿端口(见 `hierarchy-integration.md`);
- **无嵌套 submodule**。

## 7. 生成产物位置

- 都写进**当前 repo** 的 `generated/`(`cd <repo> && soc-itg build`);
- `soc-itg integrate`(顶层一次)递归、每层在**各自 repo 目录** build,产物留各自 repo。

## 8. EDA flow tops(harden 配置)

- **集成阶段不感知 harden**;harden 在 **EDA flow(Phase B)** 才体现 = **每个工具可配多组任务(多个 top/harden)**。
- 配置在 **`<repo>_info.yaml`**(文件名 = repo 名 + `_info`,放 repo 内)。
- **verdi / vcs 不在此文件**——通过集成 flow `verdi/vcs --top [...]` 打开。
- `waive` 取自文件,无其它字段。
- 每个工具 = **任务列表**;每条任务 = 一个 top + 关联文件(**多行书写**)。

```yaml
syn:
  - top: core_top
    sdc: ${CORE_SDC_DIR}/core.sdc
    upf: ${CORE_UPF_DIR}/core.upf
  - top: dma_top
    sdc: ${DMA_SDC_DIR}/dma.sdc
    upf: ${DMA_UPF_DIR}/dma.upf

cdc_check:
  - top: core_top
    sdc: ${CORE_SDC_DIR}/core.sdc
    waive: ${CORE_CDC_DIR}/cdc.waive
  - top: dma_top
    sdc: ${DMA_SDC_DIR}/dma.sdc
    waive: ${DMA_CDC_DIR}/cdc.waive

upf_check:
  - top: core_top
    upf: ${CORE_UPF_DIR}/core.upf
  - top: dma_top
    upf: ${DMA_UPF_DIR}/dma.upf

lint_check:
  - top: core_top
    waive: ${CORE_LINT_DIR}/lint.waive
  - top: dma_top
    waive: ${DMA_LINT_DIR}/lint.waive

sdc_check:
  - top: core_top
    sdc: ${CORE_SDC_DIR}/core.sdc
    waive: ${CORE_SDC_DIR}/sdc.waive
  - top: dma_top
    sdc: ${DMA_SDC_DIR}/dma.sdc
    waive: ${DMA_SDC_DIR}/sdc.waive

filelist:
  sim: ${CORE_FL_DIR}/sim.f
  syn: ${CORE_FL_DIR}/syn.f
  fpga: ${CORE_FL_DIR}/fpga.f
```

| 工具 | 参数 |
|------|------|
| `syn` | top, sdc, upf |
| `cdc_check` | top, sdc, waive |
| `upf_check` | top, upf |
| `lint_check` | top, waive |
| `sdc_check` | top, sdc, waive |

规则:
- **每个任务 `- top:` 开头**;`sdc/upf/waive` 是**缩进的单值**(不加 `-`),用 `${ENV}/绝对路径`,运行时展开。
- **多个 `- top:` = 多个 harden**;所有 check 工具都支持多 harden。
- **filelist 按类别**(sim/syn/fpga)单值,同样 `${ENV}` 路径。

## 9. 定稿要点

- 输入按类型分目录:`pinmux/ crg/ csr/`(各可多文件);原 `regs/` 并入 `csr/`。
- `generated/` **提交**;`build/` + `.soc_itg/` 为**临时产物,不上传 git**;源提交。
- 组合仓生成的 IP-XACT 放 `ipxact/`。
- 配置合并为 `<repo>_info.yaml`(元数据 + flow);`integrate` 在 `soc.yaml` 实例上由上层决定。
- **superproject 仅容器**(容器配置 + 平级 repo submodule + 可选根级 build),自身无设计内容。
- **EDA flow 脚本/工具适配是 `soc-itg` 工具公共库**,多项目共享,**不放进 repo**;repo 只有 `<repo>_info.yaml` 配置。