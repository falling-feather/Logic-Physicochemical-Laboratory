# 实验 UI 基准模板

> 基于各学科第 1 号实验提炼的标准化 UI 规范。新实验开发时应以本文档为参考基准。

---

## 1. 全局设计系统

### 1.1 学科主题色

| 学科 | 主题色变量 | 色值 | Wash 变体 |
|------|-----------|------|----------|
| 数学 | `--accent-blue` | `#5b8dce` | `rgba(91,141,206,0.08)` |
| 物理 | `--accent-purple` | `#8b6fc0` | `rgba(139,111,192,0.08)` |
| 化学 | `--accent-green` | `#4d9e7e` | `rgba(77,158,126,0.08)` |
| 算法 | `--accent-orange` | `#c4793a` | `rgba(196,121,58,0.08)` |
| 生物 | `--accent-teal` | `#3a9e8f` | `rgba(58,158,143,0.08)` |

### 1.2 Canvas 字体规范（v4.0.1+）

所有 Canvas 文字通过全局 `CF` 对象引用字体族（定义在 `config.js` 顶部），禁止硬编码字体名或使用 `var()` CSS 变量（Canvas API 无法解析 CSS 自定义属性）。

```javascript
// ✅ 正确 — 使用 CF 全局对象
ctx.font = '16px ' + CF.sans;
ctx.font = 'bold 18px ' + CF.mono;
ctx.font = `${fs}px ${CF.sans}`;

// ❌ 禁止 — var() 在 Canvas 中不工作
ctx.font = '16px var(--font-sans, sans-serif)';

// ❌ 禁止 — 硬编码字体
ctx.font = '10px "Noto Sans SC", sans-serif';
```

**字体大小基准**（Canvas 2D 绘制）：

| 用途 | 最小尺寸 | 推荐尺寸 | 字重 |
|------|---------|---------|------|
| 标题/模式名 | 20px | 22-24px | bold / 600 |
| 标签/名称 | 16px | 17-18px | normal / 500 |
| 数值/公式 | 15px | 16-18px | normal（mono） |
| 辅助说明 | 14px | 15-16px | normal |
| 微型注释 | 12px | 14px | normal |

**动态字体大小**（响应式）：

```javascript
// 推荐模式：基于画布宽度的线性缩放 + 最小值保护
const fs = Math.max(15, W * 0.016);
ctx.font = `${fs}px ${CF.sans}`;
```

### 1.3 表面/背景色

```
Canvas 背景: var(--surface-0) = #08090e  或  #0c100f（生物偏绿）
面板背景:   var(--surface-1) = #0e1019
卡片背景:   var(--surface-2) = #151822
悬停高亮:   var(--surface-3) = #1c1f2e
```

---

## 2. 学科基准模板

### 2.1 数学 — 基准：`FuncProps`（函数性质探究）

**架构特征：**
- Canvas 全宽渲染 + 右侧/底部动态信息面板
- 控件由 JS 动态生成（`_buildControls()`）
- 单一 `draw()` 调用（无 RAF 循环）

**Canvas 配置：**
```javascript
resize() {
    const r = this.wrap.getBoundingClientRect();
    const dpr = devicePixelRatio || 1;
    if (r.width <= 0 || r.height <= 0) return;  // 必须！防止隐藏时触发
    this.W = r.width; this.H = r.height;
    this.canvas.width = this.W * dpr;
    this.canvas.height = this.H * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.draw();
}
```

**字体尺寸参考：**
- 坐标轴标签: `17px var(--font-sans)`
- 函数名称: `bold 20px var(--font-sans)`
- 刻度值: `16px var(--font-mono)`
- 标题: `bold 22px var(--font-sans)`

**面板模式：** 单一 `updateInfo()` 方法直接操作已有 DOM 元素

**生命周期：**
```javascript
const FuncProps = {
    init() { /* canvas 创建、事件绑定、ResizeObserver */ },
    destroy() { /* observer.disconnect, removeEventListener, DOM 清理 */ }
};
function initFuncProps() { FuncProps.init(); }
```

---

### 2.2 物理 — 基准：`Kinematics`（匀变速运动）

**架构特征：**
- Canvas + RAF 动画循环（`performance.now()` dt 驱动）
- HTML 预设 Slider 控件 + JS 绑定
- 分离的信息面板（`kin-info` 数值 + `kin-edu` 教育）

**Canvas 配置：**
```javascript
resize() {
    const rect = this.wrap.getBoundingClientRect();
    const dpr = devicePixelRatio || 1;
    this.W = rect.width; this.H = rect.height;
    this.cvs.width = this.W * dpr;
    this.cvs.height = this.H * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
```

**字体尺寸参考：**
- 使用 CSS 变量: `var(--font-mono)`, `var(--font-sans)`
- 标签: `11px var(--font-mono)`（物理标准偏小，因信息密度高）
- 数值: `10px var(--font-mono)`

> **注意**: 物理实验因数据密集，字体尺寸可适当偏小（10-11px），但不应低于 10px。

**面板模式：**
- 预设 HTML 元素: `<div id="kin-info">`, `<div id="kin-edu">`
- JS 中通过 `getElementById` 获取并更新 `innerHTML`

**动画循环模板：**
```javascript
_loop(now) {
    if (!this._running) return;
    const dt = Math.min((now - (this._prev || now)) / 1000, 0.05);
    this._prev = now;
    // 物理更新 + 绘制
    this._raf = requestAnimationFrame(t => this._loop(t));
},
destroy() {
    this._running = false;
    cancelAnimationFrame(this._raf);
}
```

---

### 2.3 化学 — 基准：`PeriodicTable`（元素周期表）

**架构特征：**
- **纯 DOM 渲染**（无 Canvas）— 化学实验允许 DOM/Canvas 混合
- 模式切换 + 搜索功能
- 复杂教育面板（多 Tab 切换）

**布局特征：**
- 18 列 CSS Grid 布局
- 元素卡片 hover 放大 + 详情弹出
- 底部教育面板固定高度

**面板模式：** `_injectInfoPanel()` 创建 + `_updateInfo()` 更新
- 面板包含多个 Tab（元素详情/趋势图/知识卡）

**生命周期：**
```javascript
const PeriodicTable = {
    init() { /* DOM 生成、事件绑定 */ },
    destroy() { /* DOM 清理、事件移除 */ }
};
function initPeriodicTable() { PeriodicTable.init(); }
```

---

### 2.4 算法 — 基准：`SortingVis`（排序可视化）

**架构特征：**
- **纯 HTML/CSS** 柱状图 + JS 动态操作
- 异步 `async/await` 驱动排序步骤
- 简洁控件（速度、数组大小、算法选择）

**面板模式：** 内联 HTML，步骤说明动态更新

**动画模式：**
```javascript
async sort() {
    // 每步操作后 await delay(speed)
    // 通过 CSS class 标记 比较/交换/完成 状态
}
```

---

### 2.5 生物 — 基准：`CellStructure`（细胞结构）

**架构特征：**
- Canvas 全宽 + 缩放平移交互（`biology-zoom.js` 混入）
- 两步面板注入：`_injectInfoPanel()` 创建结构 → `_updateInfo()` 更新内容
- 悬停高亮 + 标签动态显示

**Canvas 配置：**
```javascript
resize() {
    const dpr = devicePixelRatio || 1;
    const w = this.wrap.clientWidth, h = this.wrap.clientHeight;
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.W = w; this.H = h;
}
```

**字体尺寸参考（v4.0.1+ 标准化后）：**
- 结构名称: `500 18px var(--font-sans)`
- 悬停标签: `600 20px var(--font-sans)`
- 描述文字: `17px var(--font-sans)`
- 标题: `bold 24px var(--font-sans)`

**面板模式：**
```javascript
_injectInfoPanel() {
    // 创建面板 DOM 结构（标题、内容区、知识点列表）
    // 插入到 section 容器中
},
_updateInfo(organelle) {
    // 更新面板内容为当前选中的细胞器信息
}
```

**缩放交互混入（biology-zoom.js）：**
```javascript
// 提供 wheel 缩放 + 拖拽平移
// 通过 transform matrix 控制 Canvas 视图
```

---

## 3. 通用代码模式

### 3.1 实验模块标准结构

```javascript
const ExperimentName = {
    // === 状态 ===
    canvas: null, ctx: null, W: 0, H: 0,
    _raf: 0, _running: false,
    _ro: null,  // ResizeObserver

    // === 生命周期 ===
    init() {
        const sec = document.getElementById('module-xxx');
        const wrap = sec.querySelector('.canvas-wrap');
        this.canvas = wrap.querySelector('canvas');
        this.ctx = this.canvas.getContext('2d');
        
        this._ro = new ResizeObserver(() => this.resize());
        this._ro.observe(wrap);
        this.wrap = wrap;
        
        this._injectInfoPanel(sec);
        this.resize();
        this._running = true;
        this._loop(performance.now());
    },
    
    destroy() {
        this._running = false;
        cancelAnimationFrame(this._raf);
        this._ro?.disconnect();
        // 移除事件监听、清理 DOM
    },
    
    // === Canvas ===
    resize() {
        const r = this.wrap.getBoundingClientRect();
        const dpr = devicePixelRatio || 1;
        if (r.width <= 0 || r.height <= 0) return;
        this.W = r.width; this.H = r.height;
        this.canvas.width = this.W * dpr;
        this.canvas.height = this.H * dpr;
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    },
    
    _loop(now) {
        if (!this._running) return;
        const dt = Math.min((now - (this._prev || now)) / 1000, 0.05);
        this._prev = now;
        this._update(dt);
        this._draw();
        this._raf = requestAnimationFrame(t => this._loop(t));
    },
    
    // === 面板 ===
    _injectInfoPanel(sec) { /* 动态创建教育面板 DOM */ },
    _updateInfo(data) { /* 更新面板内容 */ }
};

function initExperimentName() { ExperimentName.init(); }
```

### 3.2 resize 安全守卫（必须）

```javascript
resize() {
    const r = this.wrap.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;  // ← 关键！
    // ...
}
```

**原因**：当通过路由切换离开实验页面时，`ResizeObserver` 可能在 section 已隐藏（宽高为 0）时触发回调。如果不做此守卫，可能导致：
- 除以零（`step = range / W` → `Infinity`）
- 无限循环（`for` 循环的 `step=0`）
- 浏览器卡死

### 3.3 destroy 清理清单

```javascript
destroy() {
    // 1. 停止动画
    this._running = false;
    cancelAnimationFrame(this._raf);
    
    // 2. 断开观察器
    this._ro?.disconnect();
    
    // 3. 移除事件监听（必须用具名函数引用）
    this.canvas.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('resize', this._onResize);
    
    // 4. 清理动态注入的 DOM
    this._panel?.remove();
    
    // 5. 重置状态
    this.canvas = null; this.ctx = null;
}
```

---

## 4. CSS 布局约定

### 4.1 实验容器

```css
.module-experiment {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
}

.canvas-wrap {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;        /* 数学/物理/算法 */
    /* aspect-ratio: 4 / 3;  */   /* 生物/化学（信息密集型） */
    max-height: 520px;
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--surface-0);
}

.canvas-wrap canvas {
    display: block;
    width: 100%;
    height: 100%;
}
```

### 4.2 控件区

```css
.experiment-controls {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: center;
    padding: var(--space-3) var(--space-4);
    background: var(--surface-1);
    border-radius: var(--radius-default);
    border: 1px solid var(--border-subtle);
}

.experiment-controls button {
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
    border-radius: var(--radius-default);
    border: 1px solid var(--border-default);
    background: var(--surface-2);
    color: var(--text-primary);
    cursor: pointer;
    transition: all var(--duration-fast) ease;
}

.experiment-controls button:hover {
    background: var(--surface-3);
    border-color: var(--border-hover);
}
```

### 4.3 教育面板

```css
.experiment-info {
    padding: var(--space-4);
    background: var(--surface-1);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.6;
}

.experiment-info h3 {
    font-size: var(--text-base);
    color: var(--text-primary);
    margin-bottom: var(--space-2);
}
```

---

## 5. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v4.0.1 | 2025-01 | 初版：统一 Canvas 字体为 CSS 变量，生物/数学字体放大 1.5-1.7× |
