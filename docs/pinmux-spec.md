# Pinmux 规格

> 关联:`architecture.md`、`flow.md`

## 1. 概述

Pinmux 把芯片引脚(pad)与 IP 内部 pin 复用连接。输入为 **4 张表(一个 Excel 的 4 个 sheet)**,输出 **pinmux RTL + pinmux 寄存器规格(Excel)+ 引脚清单**。

## 2. 工艺隔离:Pad Wrapper

- 每个 pad 包一个 **wrapper**(工艺相关,人工提供 RTL)。
- wrapper 固定接口 + **8bit / 16bit 配置**(cfg);ITG 只**例化 + 传 cfg + 连线**。

## 3. 输入:4 张表

### Sheet 0 `pads`(总表:模拟 + 数字,单一来源)
| pad | type | wrapper | security | DS[3] | PULL[2] | SCHMITT[1] | … |
|-----|------|---------|----------|-------|---------|-----------|----|
| PAD_GPIO0 | digital | IO_BIDIR_WRAP | secure | 011 | 10 | 0 | |
| PAD_VDDA | analog | ANA_PAD_WRAP | — | — | — | — | |

- `type`:digital / analog
- `security`:与 APB4 PPROT 一致(secure / nonsecure)
- 配置字段:列头带位宽 `DS[3]/PULL[2]/SCHMITT[1]`,**表格驱动,自动解析**
- 模拟 pad:有 wrapper,无 cfg,不进模式表

### Sheet 1 `function_share`(仅数字 pad)
| group | pad | function0 | function1 | … |
|:---:|-----|-----------|-----------|----|
| A | PAD_GPIO0 | insta.uart_tx | insta.gpio0 | |

- `group`:同组共用一个 `sel_<group>`;单组 = 全局
- `sel` 选一列 → 该列各 cell 接本行 pad

### Sheet 2 `padshare`(仅数字 pad)
| pad | pin0 | pin1 | … |
|-----|------|------|----|
| PAD_SPI0 | insta.spi_clk | insta.gpio2 | |

- 每 pad 一个 `sel_<pad>`,独立选择自己行内候选 pin
- 默认 pin0

### Sheet 3 `bist_share`(覆盖所有数字 pad)
| pad | bist_func0 | bist_func1 | … |
|-----|------------|------------|----|
| PAD_TM0 | insta.bist_in0 | insta.jtag_tck | |

BIST 入口(本表下方单独几行):
```
[BIST_ENTRY]
bist_mode | pad | value
0 | PAD_TM0 | 1
0 | PAD_TM1 | 0
0 | PAD_TM2 | 1
```

- `bist_mode` 有效 → **所有数字 pad 切 BIST**
- BIST 功能列同 function share(可分组)

## 4. 规则

| 规则 | 说明 |
|------|------|
| 空单元格 | **输入模式 + tie0** |
| 模式唯一 | 每个数字 pad 只进 function_share **或** padshare |
| BIST 覆盖 | bist_share 覆盖所有数字 pad |
| 模拟排除 | 模拟 pad 不进模式表 |
| 属性来源 | 物理属性只认 `pads` 表 |
| 引用存在性 | 模式表引用的 pad 必须在 `pads` 且 digital |

## 5. cfg 位宽

- 配置字段总和 **≤8 → 8bit;否则 16bit**。
- 每 pad **一个 cfg 寄存器**(不打包);默认值 = 表格值。

## 6. 寄存器规格输出

- 与**寄存器模板格式**一致:
  `block_name | reg_name | offset | field | msb | lsb | access | reset_value | security | description`
- **只含 offset**(base 由顶层地址映射分配)。
- pinmux 用**独立 APB4 从端**(self-contained 寄存器块)。

## 7. 安全属性(全局能力)

| 项 | 定案 |
|----|------|
| 取值 | APB4 PPROT 一致 |
| 覆盖 | secure pad 的 cfg + sel |
| 门控 | `PPROT[1]`(secure = `PPROT[1]==0`) |
| 非安全写 | 忽略 |
| 非安全读 | **PSLVERR + error interrupt** |
| 适用 | 寄存器 IR 全局支持 security |

## 8. 生成产物

1. **pinmux RTL**:sel mux + `reg→wrapper.cfg` + wrapper 例化(Verilog,flatten)
2. **pinmux reg Excel**:模板格式,offset-only,APB4,含 security
3. **引脚清单**:pad / wrapper / 方向
4. (引脚约束 → 后端/FPGA,Phase B)

## 9. 自动生成的寄存器

```
pinmux_regs:
  sel_<group>   # function_share,每 group 一个
  sel_<pad>     # padshare,每 pad 一个
  cfg_<pad>     # 每 pad 一个(cfg 字段,含默认值)
  bist_mode     # 全局,由 [BIST_ENTRY] 派生
```
