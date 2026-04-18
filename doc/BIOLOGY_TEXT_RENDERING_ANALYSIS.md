# 生物实验 Canvas 文本渲染分析报告

> 分析日期: 2026-04-17 | 文件数: 15 | ctx.font 总行数: 171  
> 全局字体常量: `CF` (shared/js/config.js) — 通过 `getComputedStyle` 解析 CSS 变量 `--font-sans` / `--font-mono`

---

## 1. 全局字体基础设施

```javascript
// shared/js/config.js
const CF = {
    _s: null, _m: null,
    get sans() { return this._s || (this._s = getComputedStyle(document.documentElement)
                 .getPropertyValue('--font-sans').trim() || 'sans-serif'); },
    get mono() { return this._m || (this._m = getComputedStyle(document.documentElement)
                 .getPropertyValue('--font-mono').trim() || 'monospace'); }
};
```

所有生物实验统一通过 `CF.sans` 和 `CF.mono` 引用字体，不再有硬编码字体名。

---

## 2. 逐文件详细清单

### 2.1 biology.js — 引导模块

- **ctx.font 行数**: 0
- **Canvas**: 无
- **渲染方式**: 无 — 仅调用子模块 `init` 函数

### 2.2 biology-zoom.js — 放大浮层

- **ctx.font 行数**: 0
- **Canvas**: 不创建，仅移动已有 canvas 到 modal
- **渲染方式**: 纯 DOM (`createElement`, `innerHTML`, `textContent`)
- **特殊**: 放大视图时通过 CSS `transform: scale()` 缩放已有 canvas

### 2.3 cell-structure.js — 细胞结构

| 行号 | ctx.font 值 | 字号 | 字族 |
|------|-----------|------|------|
| 223 | `'500 24px ' + CF.sans` | 24 | sans |
| 255 | `` `${hov?'600 22':'500 22'}px ${CF.sans}` `` | 22 | sans |
| 486 | `'bold 30px ' + CF.sans` | 30 | sans |
| 489 | `'19px ' + CF.sans` | 19 | sans |
| 511 | `'500 19px ' + CF.sans` | 19 | sans |
| 847 | `'500 19px ' + CF.sans` | 19 | sans |
| 883 | `'500 19px ' + CF.sans` | 19 | sans |
| 902 | `'bold 30px ' + CF.sans` | 30 | sans |
| 904 | `'24px ' + CF.sans` | 24 | sans |

- **Canvas**: `getElementById('cell-canvas')` | DPR + ResizeObserver
- **Helper**: `_label()` (L509) — 通用标签绘制 + `_injectInfoPanel()` (L912)
- **字号范围**: 19–30px | **字族**: 仅 CF.sans

### 2.4 dna-helix.js — DNA双螺旋

| 行号 | ctx.font 值 | 字号 | 字族 |
|------|-----------|------|------|
| 440 | `'bold ' + this._fs + 'px ' + CF.mono` | **动态** | mono |
| 496 | `this._fs + 'px ' + CF.sans` | **动态** | sans |
| 507 | `this._fsSm + 'px ' + CF.sans` | **动态-3** | sans |
| 520 | `'600 ' + this._fs + 'px ' + CF.sans` | **动态** | sans |
| 536 | `'bold ' + this._fsSm + 'px ' + CF.mono` | **动态-3** | mono |
| ... | _(共 22 处)_ | | |
| 843 | `'600 ' + this._fs + 'px ' + CF.sans` | **动态** | sans |

- **响应式计算**: `this._fs = Math.max(16, Math.min(19, W * 0.028)); this._fsSm = this._fs - 3;`
- **Canvas**: `getElementById('dna-canvas')` | DPR + ResizeObserver
- **Helper**: `_drawLegend()` + `_injectInfoPanel()` (L853)
- **字号范围**: 13–19px (响应式) | **字族**: CF.sans + CF.mono

### 2.5 photosynthesis.js — 光合作用

| 字号 | 字族 | 出现次数 |
|------|------|---------|
| 16px | sans | ~16 |
| 16px | mono | 4 |
| 19px | sans | ~7 |
| 19px | mono | 2 |
| 22px | sans (600w) | 2 |
| 24px | sans (600w) | 3 |

- **Canvas**: `getElementById('photosynthesis-canvas')` | DPR + ResizeObserver
- **面板**: `_injectInfoPanel()` (L874) + `_updateInfo()` 三模式切换（simulation/curve/comparison）
- **字号范围**: 16–24px | **特点**: ctx.font 最多（34处），三种模式 Canvas 绘制完全不同

### 2.6 genetics.js — 遗传学

| 行号 | 字号 | 字族 | 说明 |
|------|------|------|------|
| 698 | 27 | sans | 大标题 |
| 718 | 22 | sans | 副标题 |
| 724 | 24 | mono | 基因型 |
| 782 | **≤24 动态** | mono | `Math.min(24, cellSize*0.48)` |
| 804–1077 | 16–19 | 混合 | 标签/图例 |

- **Canvas**: `getElementById('genetics-canvas')` | DPR + ResizeObserver
- **面板**: `_injectInfoPanel()` (L605) — 三种模式 (punnett/population/pedigree)
- **字号范围**: 16–27px

### 2.7 cellular-respiration.js — 细胞呼吸

| 字号 | 字族 | 次数 |
|------|------|------|
| 16px | sans | 2 |
| 16px | mono | 3 |
| 19px | sans | 5 |
| 19px | mono | 4 |
| 24px | mono (bold) | 1 |
| 27px | sans (bold) | 1 |

- **Canvas**: `getElementById('cell-resp-canvas')` | DPR + ResizeObserver ✅ (已修复)
- **字号范围**: 16–27px

### 2.8 gene-expression.js — 基因表达

| 字号 | 字族 | 次数 |
|------|------|------|
| 16px | sans | 2 |
| 16px | mono | 4 |
| 19px | sans | 2 |
| 19px | mono (bold) | 5 |
| 24px | sans | 1 |
| 27px | sans (bold) | 2 |

- **Canvas**: `getElementById('gene-expression-canvas')` | DPR + ResizeObserver ✅ (已修复)
- **字号范围**: 16–27px

### 2.9 substance-transport.js — 物质运输

| 行号 | 字号 | 字族 |
|------|------|------|
| 123 | 19 | sans |
| 148, 164, 201 | 16 | sans |
| 174 | 16 (bold) | mono |
| 222 | 27 (bold) | sans |
| 226 | 19 | sans |

- **Canvas**: `getElementById('substance-transport-canvas')` | DPR + ResizeObserver ✅ (已修复)
- **字号范围**: 16–27px

### 2.10 gene-mutation.js — 基因突变 (IIFE 模式)

| 行号 | 字号 | 字族 |
|------|------|------|
| 92 | 24 (bold) | sans |
| 118 | **动态 fs** | sans |
| 133 | 19 | sans |
| 179 | 27 (bold) | sans |
| 200 | 24 (bold) | sans |
| 207, 213, 231 | 19 | sans |

- **动态计算**: `fs = Math.max(9, boxes[0].w * 0.28)`
- **Canvas**: `getElementById('gene-mutation-canvas')` | DPR + ResizeObserver
- **架构**: `const GeneMutation = (() => { ... })()` IIFE

### 2.11 neural-regulation.js — 神经调节 ✅ 最现代化

| 行号 | 字号 | 字族 |
|------|------|------|
| 285 | 19 | mono |
| 390, 396, 472, 520, 592 | **动态 fs** | sans |
| 456, 503 | **动态 fs** | mono |
| 468, 522 | **动态 fs-1** | mono |
| 547, 562 | 19 | mono |
| 550, 565 | 19 | sans |

- **动态计算**: `fs = Math.max(10, W * 0.011)`
- **Canvas**: `getElementById('neural-canvas')` | DPR + ResizeObserver
- **特点**: 大量动态响应式字体

### 2.12 immune-system.js — 免疫系统

| 行号 | 字号 | 字族 |
|------|------|------|
| 361, 494, 512 | 19 | sans |
| 363 | 19 | mono |
| 370 | 27 | sans |
| 409, 473, 480 | 16 | mono |

- **Canvas**: `getElementById('immune-canvas')` | DPR + ResizeObserver
- **Helper**: `_drawTip()` — 工具提示气泡

### 2.13 mitosis.js — 有丝分裂

| 行号 | 字号 | 字族 |
|------|------|------|
| 334 | 19 | sans |

- **Canvas**: `getElementById('mitosis-canvas')` | DPR + ResizeObserver
- **特点**: Canvas 仅 1 处文本，以 DOM 面板为主

### 2.14 meiosis.js — 减数分裂

| 行号 | 字号 | 字族 |
|------|------|------|
| 192, 346 | 19 | sans |
| 312, 332 | 19 | mono |
| 322 | 27 (bold) | sans |
| 326 | 24 | sans |

- **Canvas**: `getElementById('meiosis-canvas')` | DPR + ResizeObserver ✅ (已修复)
- **字号范围**: 19–27px

### 2.15 ecosystem.js — 生态系统

| 行号 | 字号 | 字族 |
|------|------|------|
| 366 | 24 (bold) | sans |
| 392, 406, 521, 526, 626 | 19 | sans |
| 423 | 19 (bold) | sans |
| 452, 595 | 24 | sans |
| 503 | 27 (bold) | sans |
| 537 | 19 | mono |
| 606 | 24 | mono |

- **Canvas**: `getElementById('ecosystem-canvas')` | DPR + ResizeObserver
- **字号范围**: 19–27px

---

## 3. 总对比表

| 文件 | ctx.font | 字号范围 | ResizeObserver | 渲染方式 | 响应式字号 |
|------|---------|---------|:-:|---------|:-:|
| biology.js | 0 | — | — | 无 | — |
| biology-zoom.js | 0 | — | — | 纯 DOM | — |
| cell-structure.js | 9 | 19–30 | ✅ | 混合 | ✅ (hover) |
| dna-helix.js | 22 | 13–19 | ✅ | 混合 | ✅ (W*0.028) |
| photosynthesis.js | 34 | 16–24 | ✅ | 混合(重) | ❌ |
| genetics.js | 17 | 16–27 | ✅ | 混合 | ✅ (cellSize) |
| cellular-respiration.js | 18 | 16–27 | ✅ | 混合 | ❌ |
| gene-expression.js | 16 | 16–27 | ✅ | 混合 | ❌ |
| substance-transport.js | 7 | 16–27 | ✅ | 混合 | ❌ |
| gene-mutation.js | 9 | 19–27+动态 | ✅ | 混合(IIFE) | ✅ (fs) |
| neural-regulation.js | 15 | 19+动态 | ✅ | 混合 | ✅ (W*0.011) |
| immune-system.js | 9 | 16–27 | ✅ | 混合 | ❌ |
| mitosis.js | 1 | 19 | ✅ | DOM 为主 | ❌ |
| meiosis.js | 6 | 19–27 | ✅ | 混合 | ❌ |
| ecosystem.js | 12 | 19–27 | ✅ | 混合 | ❌ |

---

## 4. 标准字号档位

| 档位 | 字号 | 语义 | 典型使用 |
|------|------|------|---------|
| sm | 16px | 详细/小标签 | 图例项、groove 标签、分子简写 |
| base | 19px | 正文/标签 | 方向标记、面板文本、通用标签 |
| md | 22px | 中等标题 | 副标题、悬停状态 |
| lg | 24px | 重要标签 | 基因型、方程式、区域标题 |
| xl | 27px | 主标题 | 模块标题、大标题 |
| hero | 30px | 最大标题 | cell-structure 专用 |

---

## 5. dna-helix vs cell-structure 对比

| 维度 | cell-structure | dna-helix |
|------|---------------|-----------|
| ctx.font 次数 | 9 | 22 |
| 字号范围 | 19–30px | 13–19px (响应式) |
| mono 字族 | 不使用 | 大量（碱基字母） |
| Helper | `_label()` 通用标签 | `_drawLegend()` 图例块 |
| 信息面板 | `_injectInfoPanel()` + `_updateInfo()` | `_injectInfoPanel()` + 4 模式 |
| 响应式字体 | 悬停 500→600 weight | `_fs/_fsSm` 基于 W*0.028 |
| Canvas sizing | `parentElement.client*` | `parentElement.getBoundingClientRect()` |

---

## 6. 后续优化建议

1. **已完成**: 4 个文件添加 ResizeObserver (cellular-respiration, gene-expression, substance-transport, meiosis)
2. **已完成**: 字号统一 (21→22px, 26→27px)
3. **已完成**: dna-helix 添加响应式字体 (`_fs`/`_fsSm`)
4. **待做**: photosynthesis、ecosystem、genetics 等高频文件添加响应式字体
5. **待做**: 统一 Panel 注入模式（当前有 `_injectInfoPanel()` / `updateInfo()` / IIFE 闭包 三种变体）
