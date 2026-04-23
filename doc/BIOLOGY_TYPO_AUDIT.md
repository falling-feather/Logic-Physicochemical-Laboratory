# 生物模块文字排版审视报告 (BIOLOGY_TYPO_AUDIT)

> 任务 7（v4.2.x 续）·只读审视，不改代码 · 2026-04-22  
> 范围：`pages/biology/*.js`（13 文件） · 同时参考 `doc/BIOLOGY_TEXT_RENDERING_ANALYSIS.md` 与 `/memories/repo/font-convention.md`

---

## 一、审视方法

通过 `grep_search` 全量统计 `ctx.font = ...`（172 处）与 `const fs = Math.max(...)`（41 处）调用点，结合关键章节代码阅读，从以下维度评估：

1. **字体常量统一性**：是否使用项目标准 `CF.sans` / `CF.mono`
2. **响应式字号**：宽屏 / 小屏端是否会过大或过小
3. **字号叠加上限**：`fs + N` 模式是否有 `Math.min(...)` 上限保护
4. **大屏 vs 小屏对比**：基准系数推导（如 W * 0.012 在 W=1920 → 23px，W=800 → fallback 13px）
5. **HTML 面板内联样式**：是否硬编码 font-size / font-family
6. **化学/生物式排版**：下标（C₆H₁₂O₆、CO₂）、上标（O²⁻）、箭头（→/⇌/⟶）一致性

---

## 二、统计概览

| 维度 | 数量 / 状态 |
| --- | --- |
| 文件数 | 13 |
| `ctx.font` 调用总数 | 172 |
| 字体常量统一 (`CF.sans`/`CF.mono`) | 13/13 ✅（无硬编码 `'sans-serif'`） |
| 响应式系数为 `W * 0.012`（偏小） | 7 文件（cellular-respiration、ecosystem、gene-expression、gene-mutation、immune-system、meiosis、substance-transport） |
| 响应式系数为 `W * 0.019`（中等） | 5 文件（cell-structure、dna-helix、genetics、photosynthesis、+ cell-structure 副基准） |
| 响应式系数为 `W * 0.024+`（合理） | 4 处（mitosis、neural-regulation 部分、cell-structure 部分） |
| 含 `Math.min(...)` 字号上限保护 | **1/13**（仅 dna-helix 的 `_fs` 体系，但 `fs = Math.max(11, W*0.019)` 主线仍无上限） |
| HTML 面板含内联 `style` 字号 | **0** ✅（已迁移到 CSS 类） |
| HTML 面板含内联 `style="--c:...` 颜色变量传值 | 部分文件（不影响排版，规范允许） |

---

## 三、按文件审视

### 1. cell-structure.js [P1 中度]
- L237/265/518：`const fs = Math.max(11, W * 0.019)` — 三段函数共用，**无上限** → 1920px 屏 fs ≈ 36.5px，叠加 `+11`（L522）= **47px** 可能过大
- L290：`fs - 3` 在 1920px = 33.5px ✓ 合理
- L884/920/939：`Math.max(13, this.W * 0.024)` 系数较高，1920px = 46px，叠加 `+11` = **57px** 严重偏大
- 建议：`Math.max(11, Math.min(20, W * 0.019))` 加上限钳制

### 2. cellular-respiration.js [P0 严重]
- L106/193/279/382：`Math.max(13, W * 0.012)` — 系数过小，1280px 屏 = 15.4px，800px 屏 = 13px（fallback），1920px 屏仅 23px，**全屏区间字号几乎不变化**（13~23），失去响应式意义
- L370/385：`fs + 5` / `fs + 8` 标题，1280px = 20/23px，**小屏过小**
- L134/161/180/186/259/339/353/365/376：化学式/反应式用 `CF.mono`，但 `fs - 3` 在 1280px = 12.4px **非常拥挤**，可读性差
- L370 `★ ATP ★` 等装饰字符与 mono 字体宽度不匹配
- 建议：与 ecosystem 一起统一升级到 `Math.max(14, Math.min(22, W * 0.018))`

### 3. dna-helix.js [P2 轻度]
- 5 段 `const fs = Math.max(11, W * 0.019), fsSm = fs - 3` 一致（L378/515/558/680/803），是当前最规范的样本
- 全 23+ 处 `ctx.font` 全部基于 `fs`/`fsSm`，无叠加 `+N`，字号变化收敛
- 仍**缺上限**：1920px 屏 fs = 36.5px，碱基对标签可能过大
- 建议：仅需在 fs 计算处加 `Math.min(20, ...)` 即可全文受益

### 4. ecosystem.js [P0 严重]
- L206/494：`Math.max(13, W * 0.012)` 同病
- L367/505：标题 `(fs + 5)px` / `(fs + 8)px` — 1280px = 20/23px
- L453/597/608：`(fs + 5)px` 用于坐标轴/ODE 方程式，**未对方程截断**，长公式（如 `dN/dt = rN(1-N/K)`）在窄屏溢出 canvas
- L539/608：`CF.mono` 用于公式 ✓ 合理
- 建议：抽取一个 `_fs` 实例方法供 4 段统一调用，增加上限钳制 + 公式裁剪

### 5. gene-expression.js [P1 中度]
- L112/223：`Math.max(13, W * 0.012)`
- L121/233：标题 `(fs + 8)` — 1280px = 23px ✓
- L127：`(fs + 5)` 标签 — 1920px = 28px，狭窄气泡内会**溢出气泡边缘**
- L195/276/300/327/341/363：`(fs - 3)` 大量小字号 mono 显示密码子表，1280px = 12px **拥挤**
- 建议：调整密码子表 `fs - 1`，标签加上限

### 6. gene-mutation.js [P2 轻度]
- L84/134/180/234：`Math.max(13, W * 0.012)`
- L118：单独有 `Math.max(16, boxes[0].w * 0.24)` — **基于盒子尺寸**而非屏宽，更灵活 ✓ 推荐做法
- L93/182：`(fs + 5)` / `(fs + 8)` 标题
- L203：`'bold ' + (fs + 5) + 'px '` 嵌套字符串拼接，可读性低（其他文件类似），可统一为模板字符串
- 建议：minor clean-up，整体可读性已较好

### 7. genetics.js [P1 中度]
- 4 段 `const fs = Math.max(11, W * 0.019)`（L735/845/964/1040）
- 字号变体最多：`fs + 8` (L741/1043)、`fs + 5` (L768)、`fs + 3` (L762/783/794/1056)、`fs - 3` (L987/1023)、`pctFs`（百分比专用）、`labelFs`（标签专用）、`cellFs`（单元格专用）
- L860 三元 `(many ? labelFs + 2 : fs)` — 逻辑分支让字号难以追踪
- HTML 面板 `style="--c:..."` 颜色变量传递（L795 等）✓ 规范允许
- 建议：抽取 `_typo()` 方法返回 `{title, body, small, mono}` 字号组，避免分支

### 8. immune-system.js [P0 严重]
- L309：仅 1 处 `const fs = Math.max(13, W * 0.012)`
- L362/364/371/410/474/481/495/513：8+ 处 `ctx.font` 调用，但 **3 处直接重新计算** `Math.max(13, this.W * 0.012)` 而非引用上层 `fs` —— 重复逻辑
- L362：`fs + 'px ' + CF.sans` 浅色背景叠加 `rgba(255,255,255,0.25)` 文本 — **对比度过低**，浅色 canvas 上几乎不可读
- L371：`(fs + 8)px` 中央大字 `rgba(77,158,126,0.5)` 同样对比度问题
- L410：`(Math.max(13, this.W * 0.012) - 3)` 在 1280px = 12.4px **过小**
- 建议：统一 fs 计算，提升透明度到至少 0.5+（白底）/0.7+（深底），或改用更深色

### 9. meiosis.js [P2 轻度]
- L168：仅 1 处 fs 定义，0.012 系数同病
- 仅 6 处 `ctx.font` 调用，逻辑简单
- L330/334/340/354 同 cellular-respiration 风格
- 建议：与同基准文件批量统一升级即可

### 10. mitosis.js [P2 轻度]
- L333：`const fs = Math.max(13, this.W * 0.024)` ✓ 系数合理
- 仅 1 处 `ctx.font`，复杂度极低
- 唯一问题：fs 在循环内定义，可移到方法顶部减少重复计算
- 建议：保持现状或微调

### 11. neural-regulation.js [P1 中度]
- L238/431/535/592 各自定义 fs，系数不一致（0.014 / 0.013 / 0.024 / 0.015）—— **同一文件内 4 套基准**
- 大量模板字符串 ` `${fs}px ${CF.sans}` ` ✓ 现代写法
- L468/522：`fs - 1` 极小字号，1280px = 13px ✓ 合理
- 标签颜色多用 `rgba(255,255,255,0.35)` — 对比度仍偏低
- 建议：统一 4 段 fs 计算到 `this._fs(panel)` 实例方法

### 12. photosynthesis.js [P1 中度]
- 3 段 `const fs = Math.max(11, W * 0.019)`（L332/555/719），系数一致 ✓
- **字号变体最多**：23+ 处 `ctx.font`，含 `(fs - 3)` (大量) / `fs` / `(fs + 3)` / `(fs + 5)` / `'600 ' + fs` / `'bold ' + (fs - 3) + 'px ' + CF.mono`
- 化学式 `6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂` 用 `CF.mono` ✓ 规范
- L478/484/497/509：4 段循环渲染光反应/暗反应方程，可抽取为辅助方法
- 建议：统一抽取「方程式渲染」复用函数

### 13. substance-transport.js [P1 中度]
- 5 段 `Math.max(13, W * 0.012)`（L104/139/164/193/232）— **5 处重复计算**
- L131/157/174/184/212/234/238：`fs ± N` 系列
- L184/238：bold mono 用于膜蛋白标签 ✓ 合理
- 建议：fs 计算可上提为 `_drawX(W, ...)` 共享参数

---

## 四、Top 10 待修问题汇总（跨实验最优先）

| 排名 | 问题 | 涉及文件 | 严重度 |
| ---: | --- | --- | :---: |
| 1 | `Math.max(13, W * 0.012)` 系数过小，宽屏字号几乎不变化（13~23px 全区间） | cellular-respiration、ecosystem、gene-expression、gene-mutation、immune-system、meiosis、substance-transport（共 7 文件） | **P0** |
| 2 | 所有 `fs + N` 模式**无 `Math.min` 上限**，1920px 宽屏可达 47~57px 过大 | cell-structure、dna-helix、ecosystem、gene-expression、genetics、photosynthesis | **P0** |
| 3 | 浅透明度 `rgba(255,255,255,0.25~0.35)` 文本对比度不足 WCAG AA | immune-system、neural-regulation | **P0** |
| 4 | 同一文件内 fs 公式多次复制，难以全局调整 | substance-transport（5 处）、cellular-respiration（4 处）、neural-regulation（4 处）、genetics（4 处） | **P1** |
| 5 | 同一文件内 fs 系数不一致（0.013/0.014/0.015/0.024 混用） | neural-regulation | **P1** |
| 6 | `(fs - 3)` 在 W * 0.012 基准下小屏字号 12px 拥挤 | cellular-respiration、gene-expression、photosynthesis | **P1** |
| 7 | 字号嵌套字符串拼接 `'bold ' + (fs + N) + 'px ' + CF.x` 可读性低 | 全部 13 文件混用 | P2 |
| 8 | ODE 方程/化学式渲染逻辑重复 | ecosystem (3 处)、photosynthesis (4 处)、cellular-respiration (3 处) | P2 |
| 9 | `★ ATP ★` 装饰字符与等宽字体宽度不匹配 | cellular-respiration | P2 |
| 10 | mitosis 单点 fs 定义在循环内（性能微影响） | mitosis | P2 |

---

## 五、全局优化建议（非本轮任务，供后续 v4.3+ 参考）

### 建议 A：抽取统一 `BiologyTypo` 工具
新建 `pages/biology/_typo.js`：
```js
window.BiologyTypo = {
  // 主基准：14~22px 自适应
  primary: (W) => Math.max(14, Math.min(22, W * 0.018)),
  // 副基准（小字）
  small: (W) => Math.max(11, Math.min(16, W * 0.014)),
  // 标题
  title: (W) => Math.max(18, Math.min(28, W * 0.022)),
  // 等宽（公式、密码子）
  mono: (W) => Math.max(12, Math.min(20, W * 0.016)),
  // 模板字符串助手
  font: (size, weight, mono) => `${weight ? weight + ' ' : ''}${size}px ${mono ? CF.mono : CF.sans}`
};
// 使用：ctx.font = BiologyTypo.font(BiologyTypo.primary(W), 'bold');
```

### 建议 B：分阶段修复（不必一次完工）
- **Phase 1（P0 修复，~3 文件/轮）**：cellular-respiration / ecosystem / immune-system 升级 fs 系数 + 上限 + 透明度
- **Phase 2（P0 余下）**：gene-expression / gene-mutation / meiosis / substance-transport 同步基准
- **Phase 3（P1）**：cell-structure / dna-helix / genetics / photosynthesis 添加 `Math.min` 上限
- **Phase 4（P2 + neural-regulation）**：统一 fs 计算 + 装饰字符清理

### 建议 C：可访问性增强
- WCAG AA 对比度要求 4.5:1（正文）/ 3:1（大字）
- `rgba(255,255,255,0.25~0.35)` 在浅色 canvas 上对比度约 1.5~2.0:1，**远低于 AA 标准**
- 建议最低透明度提升到 0.55（深色背景）/ 0.7（浅色背景）

### 建议 D：化学式语义化
所有化学式（`C₆H₁₂O₆` 等）建议在 HTML 面板用 `<sub>`：
```html
<span>C<sub>6</sub>H<sub>12</sub>O<sub>6</sub></span>
```
Canvas 内可保持 Unicode 下标（`₆`），因 ctx 不支持 sub 标签。

---

## 六、修复工作量估算

| 阶段 | 文件数 | 预计改动行数 | 预计耗时 | 风险 |
| --- | ---: | ---: | --- | --- |
| Phase 1 | 3 | ~50 | 1 轮 | 低（仅字号常量替换） |
| Phase 2 | 4 | ~40 | 1 轮 | 低 |
| Phase 3 | 4 | ~30 | 1 轮 | 中（需视觉回归） |
| Phase 4 | 1 + cleanup | ~50 | 1 轮 | 中 |
| **合计** | **12 文件** | **~170 行** | **4 轮** | — |

> 注：mitosis 只需 1 行调整，可并入 Phase 4。

---

## 七、参考链接

- [shared/css/typography.css](../shared/css/typography.css) — 全局排版令牌
- [shared/css/tokens.css](../shared/css/tokens.css) — 设计令牌（颜色、间距）
- [doc/BIOLOGY_TEXT_RENDERING_ANALYSIS.md](BIOLOGY_TEXT_RENDERING_ANALYSIS.md) — 历史分析（前置）
- [doc/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#125-移动端开发规范) — §12.5 移动端排版规范

---

> 本审视仅诊断，不改源码。下一步建议执行 Phase 1（cellular-respiration / ecosystem / immune-system 三件套），或由用户指定其他优先级。
