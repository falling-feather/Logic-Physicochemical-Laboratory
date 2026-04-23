# 工科实验室 UI 排版审视报告（v4.0.5 基线）

> **审视日期**: 2026-04-22 (v4.0.6) | **方法**: 正则扫描 + 模板对照 | **范围**: 60 个实验文件（pages/{mathematics,physics,chemistry,algorithms,biology}/*.js，排除学科主页与 *-zoom.js）
>
> 本文档是 **只读审视产出**，未对代码做任何修改。修复执行将在后续版本（v4.1+）按 Batch 推进。

---

## 一、概览

- **扫描方法**：正则 grep 五维度 — Canvas 字号 / 硬编码字体 / `_inject*` 幂等性 / Canvas 高度计算 / `ctx.font` 字体回退
- **基准**：[muban/README.md](../muban/README.md) + [doc/UI_TEMPLATES.md](UI_TEMPLATES.md)
- **发现问题**：**29 项**（高 15 / 中 13 / 低 1）

| 维度 | 物理 | 化学 | 数学 | 生物 | 算法 | 合计 |
|------|------|------|------|------|------|------|
| Canvas 字号过小 | 8 | 2 | 0 | 0 | 0 | 10 |
| _inject 幂等缺失 | 3 | 1 | 0 | 9 | 0 | 13 |
| 硬编码字体 | 24 处 / 3 文件 | — | — | — | — | 24 |
| Canvas 高度复制 | 0 | 0 | 0 | 0 | 0 | 0 |

---

## 二、高优先级问题

### A. Canvas 字号严重过小（需立即修复）

| 文件 | 行号 | 当前 | 建议 |
|------|------|------|------|
| `pages/physics/momentum-conservation.js` | 540 | `'8px system-ui, sans-serif'` | ≥ 12px + `CF.sans` |
| `pages/physics/momentum-conservation.js` | 533 | `'9px system-ui, sans-serif'` | ≥ 12px + `CF.sans` |
| `pages/physics/momentum-conservation.js` | 364 | `'10px system-ui, sans-serif'` | 12px + `CF.sans` |
| `pages/physics/momentum-conservation.js` | 407, 424, 443, 455 | `'11px system-ui, sans-serif'` ×4 | 12px + `CF.sans` |
| `pages/physics/force-composition.js` | 630 | `'11px "Noto Sans SC"'` | 12px + `CF.sans` |
| `pages/chemistry/atomic-structure.js` | 326, 418 | `'11px ' + CF.sans` ×2 | 12px |

### B. `_inject*` 面板幂等防护复查结果（v4.0.10 复核后修正）

> **v4.0.10 复核结论**：本表 13 项需逐个核实实际面板实现模式。以 [`pages/physics/optics.js`](../pages/physics/optics.js#L161) 为代表的 `appendChild` 动态追加模式才需“`document.getElementById('xxx') return;`”去重防护；而 **使用 `el.innerHTML = '...'` 覆盖固定容器的实现是天然幂等的**（重复调用仅重绘相同 HTML，不会累积节点、不会泄漏监听器）。

| 文件 | 行号 | 方法 | 实际实现 | 核实结果 |
|------|------|------|----------|----------|
| `pages/physics/atomic-structure.js` | 617 | `_injectEduPanel` | `el.innerHTML = '...'` | ✅ 幂等误报 |
| `pages/physics/charged-particle.js` | 200 | `_injectEduPanel` | `wrap.innerHTML = '...'` | ✅ 幂等误报 |
| `pages/physics/force-composition.js` | 690 | `_injectEduPanel` | `edu.innerHTML = content[mode]` | ✅ 幂等误报（模式切换需覆盖是必要行为） |
| `pages/physics/momentum-conservation.js` | 594 | `_injectEduPanel` | `edu.innerHTML = '...'` | ✅ 幂等误报 |
| `pages/biology/*.js` × 9 | 多 | `_injectInfoPanel` | 全部为 `el.innerHTML = '...'` | ✅ 幂等误报（v4.1.0 复核完成） |

> **判定准则**：面板实现中出现 `appendChild` / `insertAdjacentHTML` 且未以 `getElementById` 检查唯一性才是真问题。**纯 `innerHTML = ...` 赋值不是问题**。

#### 原表（保留以备查阅，4 项物理化学条目已于 v4.0.10 关闭为误报）

| 文件 | 行号 | 方法 | 当前守卫 | 建议补丁 |
|------|------|------|----------|----------|
| `pages/biology/cell-structure.js` | 913 | `_injectInfoPanel` | `if (!el) return;` | 追加 `\|\| document.getElementById('cellstr-info-panel')` |
| `pages/biology/dna-helix.js` | 855 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/cellular-respiration.js` | 399 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/gene-expression.js` | 384 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/meiosis.js` | 373 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/mitosis.js` | 521 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/genetics.js` | 644 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/photosynthesis.js` | 873 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/biology/substance-transport.js` | 302 | `_injectInfoPanel` | 同上 | 同上模式 |
| `pages/physics/charged-particle.js` | 200 | `_injectEduPanel` | `if (!wrap) return;` | 追加 `\|\| document.getElementById('cp-edu-panel')` |
| `pages/physics/force-composition.js` | 690 | `_injectEduPanel` | `if (!edu) return;` | 同上模式 |
| `pages/physics/momentum-conservation.js` | 594 | `_injectEduPanel` | `if (!edu) return;` | 同上模式 |
| `pages/chemistry/atomic-structure.js` | 617 | `_injectEduPanel` | `if (!el) return;` | 同上模式 |

> **参考实现**：[`pages/physics/optics.js`](../pages/physics/optics.js) 与 [`pages/physics/fluid-dynamics.js`](../pages/physics/fluid-dynamics.js) 中已有正确的幂等模式（v4.0.0 维护增量已修复）。

---

## 三、中优先级问题

### 硬编码字体名残留（应统一为 `CF.sans` / `CF.mono`）

| 文件 | 出现行号 | 模式 | 数量 |
|------|----------|------|------|
| `pages/physics/charged-particle.js` | 448, 473, 489, 499, 520, 529, 566, 573, 587, 596, 666 | `"Noto Sans SC"` | 11 |
| `pages/physics/force-composition.js` | 338, 493, 553, 593, 630 | `"Noto Sans SC"` | 5 |
| `pages/physics/relativity.js` | 1850, 1859, 1868, 1883, 1888, 1903, 1932, 1935 | `'JetBrains Mono'`（HTML inline style） | 8 |

**合计**：24 处硬编码字体（v4.0.2 FONT-03 修复时遗漏的 3 个文件）

---

## 四、低优先级问题

| 项 | 发现 | 处置 |
|----|------|------|
| Canvas 高度复制（`canvas.height = rect.height`） | 0 命中 | ✅ 已彻底修复，无需跟进 |

---

## 五、建议修复批次

### Batch 1 · 紧急（建议下个 patch v4.0.7 完成）
- **Momentum-Conservation Canvas 字号修复**：将 8px/9px/10px/11px 全部提升到 12px，同时把 `system-ui, sans-serif` 改为 `CF.sans`（统一字体源）。
- **影响**：1 个文件，约 8 行编辑。

### Batch 2 · 一次性脚本（v4.0.8）
- **硬编码字体统一替换**：写一个 Python/Node 脚本，对 3 个文件做正则替换：
  - `"Noto Sans SC"` → `' + CF.sans` 或字符串拼接
  - `'JetBrains Mono'`（inline style）→ `var(--font-mono)`
- **影响**：3 个文件，24 处替换。
- **风险**：HTML inline style 与 JS ctx.font 替换语法不同，需分别处理。

### Batch 3 · 手工逐个（v4.1.0）
- **`_inject*` 幂等防护补全**：13 个方法分别添加 `document.getElementById(...)` 唯一性检查。
- **影响**：4 个学科，13 个文件，每处 1-2 行。
- **建议**：按文件批次提交，每次 3-4 个文件 + 浏览器回归（连续打开 / 关闭 / 重开 同一实验，观察 DOM Inspector 中面板节点数）。

### Batch 4 · 提升一致性（v4.1.x）
- **Canvas 字号下限统一为 12px**（除生物允许响应式 ≥11px）
- 涉及 `chemistry/atomic-structure.js` 2 处 11px → 12px

---

## 六、不在审视范围（已知良好）

- 数学 13 个实验 / 算法 8 个实验 — 字号、字体、幂等性均符合规范，本轮 0 问题
- 生物 13 个实验的字号 — v4.0.2 FONT-02 已统一放大 1.5-1.7×，本轮仅在 _inject 幂等性维度发现问题
- 化学 11 个实验 — 仅 atomic-structure.js 有 4 处问题，其余 10 个文件干净

---

## 七、不进入清单的发现

- 部分实验（如 `pages/physics/electromagnetic.js`）有 `ctx.font = '13px ' + CF.sans` 的最小字号，落在 12-13px 边界，视为合规（密度高的辅助标注允许 13px）
- 教育面板的 CSS 类前缀（`ac-` / `chem-` / `bio-` / `algo-`）按学科差异化是有意设计，无需统一
