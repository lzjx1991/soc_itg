# 层级集成与自动穿端口(设计)

> 关联:`architecture.md`、`flow.md`、`repository.md`(待写)

## 1. 目标

在实例层级(可嵌套、可跨 repo)中,支持**跨层信号连接**,由工具**自动生成中间层**并完成连线(feed-through / 自动穿端口)。

```
insta
 └ instb
    └ instc
连接：insta.a = instc.c      # 跨过 instb
```

工具自动:
- 给 **instb** 加/生成**透传端口**,内部接到 `instc.c`;
- 在 **insta** 侧把 `insta.a` 接到 instb 的该端口。

生成结果:
```verilog
module instb ( input c_pass, ... );     // 透传端口
  instc u_instc ( .c(c_pass), ... );
endmodule

module insta ( input a, ... );
  instb u_instb ( .c_pass(a), ... );
endmodule
```

## 2. 两种中间层都要支持

| 情况 | instb 是 | 工具行为 |
|------|----------|----------|
| **① 纯结构容器** | 无自有逻辑,只含子实例(如仅 instc) | **整体生成 instb wrapper**(端口 + 例化子 + 穿线) |
| **② 已有内容** | 有自有 RTL/胶合/其它实例 | **加透传端口** + 内部连线(保留原有内容) |

**纯容器判定**:该 repo/实例**无自有 rtl/glue/逻辑**,只含子实例与连线 → 视为①,可全生成。

## 3. 解析算法

1. **建实例树**:由 `soc.yaml`(嵌套/`parent`)+ repo 引用,构建层级。
2. **每条连接**:两端用**路径**定位(`insta.a`、`instc.c`)。
3. **求 LCA**:两端的最低公共祖先。
4. **沿路径插端口**:从各端向上到 LCA 的每一中间层,插一个透传端口(名如 `c_pass`),并生成内部连线(端口 ↔ 子端口)。
5. **生成**:①全生成 wrapper;②在已有模块上加端口 + 连线。
6. **方向/位宽**:沿信号(源/汇方向、宽度)传播;位宽不符 → 报错/告警。

## 4. 跨 repo:顶层一次 integrate,自底向上

- 顶层执行一次 **`soc-itg integrate`**,递归完成整棵树,**每层在各自 repo 目录 build**,产物留各自 repo。
- **是否集成由 `repo.yaml` 决定**(显式指定):
  - `integrate: true` → 收集其集成信息(soc.yaml/连接/依赖/Excel)→ 递归集成;
  - `integrate: false` → **直接用现成 `ipxact/*.xml`**(黑盒,不递归)。
- **顺序:自底向上**(叶子先,父层用子层"已集成/复用"的边界)。
- 透传需求由 integrate 分析后**注入**该 repo(如 `build/feedthrough.yaml`),其 build 时加端口/生成 wrapper。

## 5. 与"逐 repo 局部 build"的关系

- 平时各 repo `soc-itg build`(局部,无跨层穿端口);
- 最终集成跑一次 **`soc-itg integrate`**(顶层),自动递归;
- 若子层 `integrate: false`,则其边界取自现成 XML。

## 6. 待实现清单

- 实例树/路径解析(LCA、跨层端点)
- feed-through 端口生成 + 内部连线
- 纯容器判定与 wrapper 全生成(①)
- 已有模块加端口(②)
- `integrate` 命令:递归、repo.yaml 标志、注入 feedthrough、自底向上
- 位宽/方向校验
