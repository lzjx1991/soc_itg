# soc-itg 命令设计

> 所有命令带 `soc-itg` 前缀。flow / create 等实现对多项目共享,封装在工具内(公共库)。

## 1. 运行上下文

- 命令在**某个 repo 目录下**执行(cwd = 当前 repo)。
- 工具向上找到 **workspace(superproject)**,取得所有**平级 sibling repo** 作为依赖池。
- 无 `--repo`;要操作哪个 repo 就 `cd` 进去。
- 目标 top:`--top <design>`(`soc.yaml` 的 `design.name`),不写用 `default_top`。

## 2. 仓库创建:`create`

```bash
# 1) 创建 top 的 project repo(workspace / superproject)
soc-itg create --prj <project_name>

# 2) 创建子 repo,并加入 project 作为 submodule + 初始化
soc-itg create --prj <project_name> --sub <repo_name> --init
```

行为:
- `--prj P`:在 GitLab 创建项目 `P`;初始化 workspace 容器结构(`name/default_top/repos`、`.gitignore`、README);初始提交 + push。
- `--prj P --sub S --init`:创建子 repo `S`(GitLab + 按 `repository.md` 脚手架化 + push);在 `P` 里 `git submodule add S`;`git submodule update --init`;在 `P` 提交 submodule 引用。

选项:

| 选项 | 说明 |
|------|------|
| `--prj <name>` | project(workspace)名 |
| `--sub <name>` | 子 repo 名(可选) |
| `--init` | 添加后执行 `git submodule update --init` |
| `--group <g>` | GitLab 组/命名空间(默认 `GITLAB_GROUP`) |
| `--visibility` | private(默认)/internal/public |
| `--gitlab-url` | GitLab 地址(默认 `GITLAB_URL`);token 取 `GITLAB_TOKEN` |
| `--no-git` | 只本地脚手架,不建 GitLab / 不 push |

## 3. 主命令:`itg`(集成入口)

```bash
soc-itg itg [--top <design>]
```

- 单一集成入口(替代 `build`/`integrate`)。
- 从 `--top` 起解析实例树;每个子实例按**父 `soc.yaml` 的 `integrate`**:
  - `true` → 递归在该子 repo 目录集成(parse→…→generate→filelist);
  - `false` → 用其现成 `ipxact/*.xml`。
- **自底向上**;产物写各自 repo 的 `generated/`。
- **包含最后一步 filelist**。

## 4. 子阶段命令(保留,调试/单步)

在当前 repo 上执行:

| 命令 | 作用 | 读写 |
|------|------|------|
| `parse` | IP-XACT → 归一 | `ipxact/`、`*/ipxact/*.xml` → `build/ipdb.json` |
| `assemble` | 组装 SoC 模型 | `ipdb.json`+`soc.yaml` → `build/soc.json` |
| `pinmux` | pinmux 模型 | `pinmux/*.xlsx` → `build/pinmux.json` |
| `crg` | CRG 模型 | `crg/*.xlsx` → `build/crg.json` |
| `topcsr` | 顶层寄存器 | `csr/*.xlsx` → `build/topcsr.json` |
| `check` | 完整性/地址/位宽/安全 | `soc.json` → `build/findings.json` |
| `connect` | 连接/netlist | 上述 → `build/connectivity.json` |
| `generate -g <gen>` | 生成产物 | → `generated/**` |

`-g`:`top / csr / regblock / pinmux / crg / sdc / filelist / verify / docs / all`。

## 5. 信息

| 命令 | 作用 |
|------|------|
| `soc-itg status` | workspace / repo / default_top / 集成状态 |
| `soc-itg repos` | 列出所有 repo + integrate 状态 |
| `soc-itg tops` | 列出可用 top |

## 6. 自研 IP(押后)

| 命令 | 作用 |
|------|------|
| `soc-itg ipgen --top <ip>` | 寄存器 Excel + RTL 端口 → IP-XACT |
| `soc-itg ipgen --init` | 生成 `ip.yaml` / `portmap` 草稿 |

## 7. EDA flow

| 命令 | 作用 |
|------|------|
| `soc-itg flow <syn\|cdc_check\|upf_check\|lint_check\|sdc_check> [--top]` | 按 `<repo>_info.yaml` 跑对应 flow |
| `soc-itg verdi --top [..]` | 打开 verdi(多 top) |
| `soc-itg vcs --top [..]` | 跑 vcs |

> flow 的脚本/工具适配(Tcl driver、tool 封装、parser)是 `soc-itg` 工具的**公共库**,多项目共享,不放进项目 repo;项目只提供 `<repo>_info.yaml`。

## 8. 其他

| 命令 | 作用 |
|------|------|
| `soc-itg clean` | 清 `build/`(临时产物) |
| `soc-itg report` | 汇总报告 |
| `soc-itg version` | 版本 |

## 9. 典型流程

```bash
# 创建 workspace 与子 repo
soc-itg create --prj my_soc
soc-itg create --prj my_soc --sub repo_cpu --init
soc-itg create --prj my_soc --sub repo_uart --init

# 集成(在某 repo 下)
cd repo_top
soc-itg itg --top my_top

# 跑 flow
soc-itg flow syn --top core_top
soc-itg verdi --top core_top dma_top
```
