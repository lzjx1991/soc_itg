# soc_itg 流程与数据契约

> 关联:`architecture.md`、`pinmux-spec.md`

## 1. 核心思想:阶段脚本 + 规范化中间数据

工具由一串**阶段脚本**组成,每个阶段是 **输入(文件) → 输出(文件)** 的纯函数。阶段之间通过 **JSON + Pydantic 契约**传递,契约带 `schema_version`。

```
ipgen → parse → assemble → check → generate → release → (flow)
```

## 2. 阶段定义

| 阶段 | 子命令 | 读 | 写 |
|:---:|--------|-----|-----|
| 0 | `ipgen` | Excel + RTL + ip.yaml | `ip/*.xml`(IP-XACT) |
| 1 | `parse` | `*.xml`(IP-XACT) | `build/ipdb.json` |
| 2 | `assemble` | `ipdb.json` + `soc.yaml` + pinmux + crg | `build/soc.json` |
| 3 | `check` | `soc.json` | `build/findings.json` |
| 4 | `generate` | `soc.json` | `generated/**` |
| 5 | `release` | `generated/**` + `soc.json` | `release/<ver>/` |
| 6 | `run`(Phase B) | `generated/**` | 工具结果 |

## 3. 数据契约

### 3.1 `build/ipdb.json`(parse 产出)
```json
{
  "schema_version": 1, "tool_version": "0.1.0",
  "components": {
    "acme.com:CPU:cpu_core:1.0.0": {
      "vlnv": "acme.com:CPU:cpu_core:1.0.0",
      "ports": [{"name": "pclk", "direction": "in", "width": 1}],
      "bus_interfaces": [{"name": "apb", "mode": "slave", "bus_type": "APB",
                          "port_maps": {"PCLK": "pclk"}}],
      "memory_maps": [{"name": "APB_Slave_MM",
                       "registers": [{"name": "CTRL", "offset": "0x0",
                         "fields": [{"name": "EN", "msb": 0, "lsb": 0,
                                     "access": "rw", "reset": 0, "security": "nonsecure"}]}]}]
    }
  },
  "bus_defs": {}, "abstraction_defs": {}
}
```

### 3.2 `build/soc.json`(assemble 产出,中枢)
```json
{
  "schema_version": 1, "tool_version": "0.1.0",
  "top": "my_soc",
  "designs": {},
  "instances": [{"name": "cpu0", "vlnv": "acme.com:CPU:cpu_core:1.0.0", "params": {}}],
  "connections": [
    {"type": "interconnection", "from": "cpu0.apb", "to": "uart0.apb"},
    {"type": "adhoc", "net": "clk", "driver": "pll0.out", "loads": ["cpu0.pclk"]}
  ],
  "address_map": [{"region": "uart0", "base": "0x10000000", "size": "0x1000"}],
  "pads": [], "clocks": {}, "resets": {}, "pinmux": {}, "crg": {},
  "register_models": {"cpu0": {"block": "cpu0", "registers": []}}
}
```

### 3.3 `build/findings.json`(check 产出)
```json
{"schema_version": 1,
 "findings": [{"level": "error", "code": "ADDR_CONFLICT", "msg": "...", "location": "..."}]}
```

## 4. 调用方式:单独跑 + 串联

```bash
soc-itg parse
soc-itg assemble
soc-itg check
soc-itg generate -g csr
soc-itg build            # 一键串联 parse→assemble→check→generate
```

## 5. 数据格式与稳定性

- 中间文件 **JSON**(YAML 仅 `--format yaml` 调试)。
- 每个契约带 `schema_version` + `tool_version` → 阶段间兼容性校验。
- 契约由 Pydantic 模型**单一来源**定义。

## 6. 增量与缓存

- 每阶段按输入文件哈希判断是否跳过;缓存记 `.soc_itg/cache/`。
- `soc.json` 未变则复用 `findings.json` 与生成产物。

## 7. 目录:输入 / 中间 / 产物分离

```
my_soc/
├── .soc_itg/{cache,lock.yaml}
├── build/          # ipdb.json / soc.json / findings.json
├── generated/      # rtl/ csr/ sdc/ filelist/ verify/ docs/
├── release/
├── ip/  soc.yaml  pinmux.xlsx  crg.xlsx
```

## 8. 各生成器输入依赖

| 生成器 | 输入 | 说明 |
|--------|------|------|
| rtl/top | soc.json | 实例+已展开连接 |
| rtl/pinmux | soc.json.pinmux | 4 表规则 |
| rtl/crg | soc.json.crg | 时钟复位生成 |
| csr | soc.json.register_models | APB4,含 security |
| sdc | soc.json.crg + IP SDC | 自动骨架 + 人工参数 |
| filelist | 全部 RTL 文件 + 依赖 | 拓扑排序,分 sim/syn/fpga |
| verify | soc.json + RAL | 初版 TB/UVM |
| docs | soc.json + 寄存器 | IP/reg 文档 |
