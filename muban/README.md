# 实验模板参考 — 基于「匀变速直线运动」

本文件夹提供标准实验页面的 **UI 布局、字号设置、控件调度** 参考模板。
后续新建实验时，请以此为基础参考。

---

## 1. 整体布局结构

```
.content-section[data-module="xxx"]
  └─ .demo-section
       ├─ .section-header          ← 标题 + 描述
       │     ├─ h3 / h2            ← 实验名称（含 lucide icon）
       │     └─ p                  ← 一行描述文案
       ├─ .xxx-controls            ← 控件区（滑块 + 按钮）
       │     ├─ .xxx-param × N     ← 参数滑块行
       │     └─ .xxx-action-row    ← 按钮行
       ├─ .xxx-canvas-wrap         ← Canvas 容器
       │     └─ canvas#xxx-canvas  ← Canvas 元素
       ├─ .xxx-info                ← 实时数据面板
       └─ .xxx-edu / #xxx-edu     ← 教育面板（知识点说明）
```

### 关键 CSS 容器

| 类名 | 来源 | 说明 |
|------|------|------|
| `.content-section` | `page-layout.css` | 最大宽度 1100px，居中，上下留白 `--space-12`/`--space-8` |
| `.demo-section` | `page-layout.css` | 背景 `--surface-1`，圆角 `--radius-lg`(8px)，内边距 `--space-10`(2.5rem)，边框 `--border-subtle` |
| `.section-header` | `typography.css` | 下边距 `--space-10`，标题 h2/h3 下 `--space-2`，描述 p 颜色 `--text-tertiary`、字号 `--text-sm` |

---

## 2. 控件区（Controls）

### 2.1 参数滑块

```html
<div class="kin-controls">
  <div class="kin-param">
    <label>v₀ = <span id="kin-v0-val">2.0</span> m/s</label>
    <input type="range" id="kin-v0" min="-5" max="10" step="0.5" value="2">
  </div>
  <!-- 更多 .kin-param ... -->
  <div class="kin-action-row">
    <button class="btn btn--primary btn--sm" id="kin-play-btn">▶ 播放</button>
    <button class="btn btn--ghost btn--sm" id="kin-reset-btn">↺ 重置</button>
  </div>
</div>
```

### 2.2 控件 CSS 模式

```css
.xxx-controls {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);           /* 0.75rem */
    align-items: center;
    margin-bottom: var(--space-4); /* 1rem */
}

.xxx-param {
    display: flex;
    align-items: center;
    gap: var(--space-2);           /* 0.5rem */
    font-size: var(--text-sm);     /* clamp(0.8rem, ..., 0.875rem) */
    color: var(--text-secondary);  /* #8a90a0 */
    min-width: 200px;
}

.xxx-param label {
    white-space: nowrap;
    font-family: var(--font-mono);
    color: var(--accent-purple);   /* 学科主色，物理=#8b6fc0 */
    min-width: 120px;
}

.xxx-param input[type="range"] {
    flex: 1;
    accent-color: var(--accent-purple);
}

.xxx-action-row {
    display: flex;
    gap: var(--space-2);
}
```

### 2.3 按钮规范

| 类名组合 | 用途 | 外观 |
|----------|------|------|
| `btn btn--primary btn--sm` | 主操作（播放/开始） | 实心蓝底白字 `--accent-blue` |
| `btn btn--ghost btn--sm` | 次要操作（重置/切换） | 透明底描边，hover 时填充 `--surface-2` |
| `btn btn--orange` | 强调操作 | 实心橙底白字 |

**btn--sm** 样式:
```css
.btn--sm {
    font-size: var(--text-xs);     /* clamp(0.7rem, ..., 0.8rem) */
    padding: var(--space-1) var(--space-2);  /* 0.25rem 0.5rem */
}
```

---

## 3. Canvas 标准

### 3.1 DPR 适配 + ResizeObserver

```javascript
resize() {
    const wrap = this.canvas.parentElement;
    if (!wrap) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = wrap.getBoundingClientRect();
    const w = rect.width;
    const h = Math.min(w * 0.55, 500);  // 宽高比约 16:9，最大 500px
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.W = w;
    this.H = h;
}
```

> **注意**: 生物实验使用 `Math.min(Math.max(w * 0.48, 300), 420)` 作为高度。
> 各学科可微调比例，但核心模式不变。

### 3.2 Canvas 容器 CSS

```css
.xxx-canvas-wrap {
    position: relative;
    width: 100%;
    border-radius: var(--radius-md);  /* 6px */
    background: var(--surface-1);
    border: 1px solid var(--border);
    overflow: hidden;
}

.xxx-canvas {
    display: block;
    width: 100%;
}
```

---

## 4. Canvas 字号设置

### 4.1 全局字体配置对象 `CF`

```javascript
// shared/js/config.js 中定义
const CF = {
    get sans() { /* 解析 CSS --font-sans 变量 */ },
    get mono() { /* 解析 CSS --font-mono 变量 */ }
};
```

Canvas 中 `ctx.font` 不支持 CSS `var()`，必须通过 `CF.sans` / `CF.mono` 获取实际字体名。

### 4.2 字号参考（匀变速直线运动实验）

| 场景 | 字号 | 字体 | 代码示例 |
|------|------|------|----------|
| 图表标题 | `16px` | `CF.sans` | `ctx.font = '16px ' + CF.sans` |
| 轨迹标签 | `15px` | `CF.sans` | `ctx.font = '15px ' + CF.sans` |
| 坐标轴数值 | `14px` | `CF.mono` | `ctx.font = '14px ' + CF.mono` |
| 坐标轴标签 | `14px` | `CF.mono` | `ctx.font = '14px ' + CF.mono` |
| RNA聚合酶等小标注 | `fs-3` | `CF.sans` | `ctx.font = (fs-3)+'px '+CF.sans` |

**匀变速直线运动用了固定 px 值**（14px/15px/16px），而部分生物实验采用响应式：

```javascript
// 生物实验 7-13 的响应式字号
const fs = Math.max(13, W * 0.012);  // W=1920 → ~23px, W=800 → ~13px

// 生物实验 1-4 的响应式字号
const fs = Math.max(11, W * 0.019);  // W=1920 → ~36px, W=800 → ~15px
```

> **建议**: 物理/数学/化学/算法实验推荐使用固定 px 字号（14-16px）。
> 生物实验因绘图密度高，需要响应式字号。

---

## 5. 教育面板（知识点说明）

### 5.1 面板 HTML（由 JS `updateInfo()` 动态注入）

```html
<div id="kin-edu" class="kin-edu">
  <div class="ac-hd">
    <span class="ac-tag">加速</span>匀变速直线运动
  </div>
  <div class="ac-row">
    <span class="ac-key">速度公式</span>v = v₀ + at — 当前 v₀=2.0 m/s, a=1.0 m/s²
  </div>
  <div class="ac-row">
    <span class="ac-key ac-key--purple">位移公式</span>s = v₀t + ½at² ...
  </div>
  <div class="ac-note">💡 人教版必修1：调整滑块观察粒子运动和图像变化...</div>
</div>
```

### 5.2 教育面板 CSS 模式

教育面板的样式类前缀按学科不同而变化（`ac-` 表示物理通用、`chem-` 表示化学、等），但整体结构一致：

```css
.xxx-edu {
    margin-top: 10px;
    padding: 12px 16px;
    border-radius: var(--radius-md, 8px);
    background: rgba(主色, 0.06);
    border: 1px solid rgba(主色, 0.12);
    font-size: 0.85rem;
    line-height: 1.65;
}

/* 标题行 */
.ac-hd {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* 标签 */
.ac-tag {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    background: rgba(主色, 0.18);
    color: rgba(主色, 0.9);
}

/* 属性行 */
.ac-row {
    display: flex;
    gap: 8px;
    margin: 3px 0;
    color: var(--text-secondary);
}

/* 键名 */
.ac-key {
    flex-shrink: 0;
    font-weight: 600;
    color: rgba(主色, 0.85);
}

/* 注释 */
.ac-note {
    margin-top: 8px;
    padding-top: 6px;
    border-top: 1px dashed rgba(255,255,255,0.06);
    font-size: 0.8rem;
    color: var(--text-tertiary);
}
```

各学科主色参考：
- **物理**: `--accent-purple` (#8b6fc0)，`rgba(139,111,192,...)`
- **化学**: `--accent-green` (#4d9e7e)，`rgba(77,158,126,...)`
- **数学**: `--accent-blue` (#5b8dce)，`rgba(91,141,206,...)`
- **算法**: `--accent-orange` (#c4793a)，`rgba(196,121,58,...)`
- **生物**: `--accent-teal` (#3a9e8f)，`rgba(58,158,143,...)`

---

## 6. 实时数据面板（Info）

```css
.xxx-info {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    padding: var(--space-3) 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
}

/* 数据项 */
.ki-item { display: flex; gap: var(--space-2); align-items: baseline; }
.ki-label { color: var(--accent-purple); font-weight: 600; }
.ki-formula { color: rgba(255,255,255,0.4); font-size: var(--text-xs); }
```

---

## 7. 实验 JS 模块标准结构

```javascript
const ExperimentName = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,

    // 参数
    param1: defaultValue,

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('xxx-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.bindEvents();
        this.draw();
        this.updateInfo();
    },

    destroy() {
        this.stopAnim();
        for (const l of this._listeners) l.el.removeEventListener(l.evt, l.fn, l.opts);
        this._listeners = [];
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    },

    resize() {
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const dpr = window.devicePixelRatio || 1;
        const rect = wrap.getBoundingClientRect();
        const w = rect.width;
        const h = Math.min(w * 0.55, 500);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => { this.resize(); this.draw(); });
            this._resizeObs.observe(this.canvas.parentElement);
        } else {
            this._on(window, 'resize', () => { this.resize(); this.draw(); });
        }
        // 绑定滑块、按钮等...
    },

    draw() {
        const { ctx, W, H } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);
        // ... 绘制逻辑
    },

    updateInfo() {
        // 更新实时数据 + 教育面板
    },

    startAnim() { /* requestAnimationFrame 循环 */ },
    stopAnim()  { /* cancelAnimationFrame */ },
    toggleAnim(){ this.animating ? this.stopAnim() : this.startAnim(); }
};

function initExperimentName() { ExperimentName.init(); }
window.ExperimentName = ExperimentName;
window.initExperimentName = initExperimentName;
```

### 生命周期

1. 路由匹配 → `router.js` 调用 `initXxx()` → `ExperimentName.init()`
2. 页面离开 → `router.js` 调用 `ExperimentName.destroy()`

### 新增实验清单

1. `shared/js/config.js` — 添加实验条目
2. `index.html` — 添加 `data-module` section + HTML
3. 编写 JS 模块 → `pages/{学科}/{实验名}.js`
4. `index.html` — 添加 `<script defer src="pages/{学科}/{实验名}.js">`
5. `router.js` — 注册 `init`/`destroy` 函数

---

## 8. 响应式断点

```css
@media (max-width: 768px) {
    .xxx-controls { flex-direction: column; align-items: flex-start; }
    .xxx-param { min-width: 100%; }
    .xxx-info { flex-direction: column; gap: var(--space-2); }
}
```

---

## 9. 设计令牌速查

| 变量 | 值 | 用途 |
|------|-----|------|
| `--surface-0` | `#08090e` | 最深背景 |
| `--surface-1` | `#0e1019` | demo-section 背景 |
| `--surface-2` | `#151822` | 按钮/卡片背景 |
| `--text-primary` | `#d8dce6` | 主文本色 |
| `--text-secondary` | `#8a90a0` | 次要文本/数据 |
| `--text-tertiary` | `#5a5f70` | 辅助文本 |
| `--font-sans` | Noto Sans SC, Inter, ... | 正文字体 |
| `--font-mono` | JetBrains Mono, ... | 代码/数据字体 |
| `--text-xs` | clamp(0.7rem,...,0.8rem) | 最小字号 |
| `--text-sm` | clamp(0.8rem,...,0.875rem) | 小字号 |
| `--radius-sm` | 2px | 小圆角 |
| `--radius-default` | 4px | 默认圆角 |
| `--radius-md` | 6px | 中圆角 |
| `--radius-lg` | 8px | 大圆角 |
