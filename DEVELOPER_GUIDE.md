# 工科实验室 — 开发者文档

> **版本**: v2.3 | **最后更新**: 2026-04-13 | **维护者团队**: EngLab Dev Team

---

## 目录

1. [项目概览](#1-项目概览)
2. [技术架构](#2-技术架构)
3. [目录结构详解](#3-目录结构详解)
4. [前端架构](#4-前端架构)
5. [后端架构](#5-后端架构)
6. [各模块功能说明](#6-各模块功能说明)
7. [路由与页面转场系统](#7-路由与页面转场系统)
8. [模块选择器系统](#8-模块选择器系统)
9. [首页系统](#9-首页系统)
10. [实验模块开发指南](#10-实验模块开发指南)
11. [CSS 设计系统](#11-CSS-设计系统)
12. [构建与部署](#12-构建与部署)
13. [维护指南](#13-维护指南)
14. [维护计划](#14-维护计划)
15. [更新日志](#15-更新日志)

---

## 1. 项目概览

**工科实验室**是一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，面向高中阶段学生，涵盖**数学、物理、化学、算法、生物**五大学科，提供 **20+ 个可视化交互实验**。

### 核心理念
- **玩中学** (Learn by Play)：所有实验均可实时交互操作
- **从抽象到直觉**：将公式和理论转化为可视化动画
- **低门槛高上限**：从基础概念到深入原理的分层教学

### 技术特点
- 纯前端渲染，无框架依赖（Vanilla JS + Canvas 2D）
- GSAP 驱动的丝滑页面转场
- C++ httplib 高性能静态服务器
- 单页应用 (SPA) 架构，hash 路由

---

## 2. 技术架构

```
┌───────────────────────────────────────────────┐
│                  浏览器端                       │
│                                               │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Router  │──│ Module   │──│ Experiment   │ │
│  │ (hash)  │  │ Selector │  │ Modules      │ │
│  └────┬────┘  └────┬─────┘  └──────┬───────┘ │
│       │            │               │          │
│  ┌────┴────────────┴───────────────┴───────┐  │
│  │           index.html (SPA 入口)          │  │
│  │  所有页面 <section> 以 display 切换       │  │
│  └──────────────────────────────────────────┘  │
│                                               │
│  CSS 层:  tokens → base → components → pages  │
│  JS 层:   config → common → modules → main   │
└───────────────────────┬───────────────────────┘
                        │ HTTP
┌───────────────────────┴───────────────────────┐
│         C++ httplib 服务器 (端口 9527)          │
│  - 静态文件托管                                 │
│  - REST API (/api/health, /api/info)          │
│  - CORS 支持                                   │
└───────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端核心 | HTML5 / CSS3 / ES6+ | — | 页面结构与交互 |
| 动画引擎 | GSAP | 3.12 | 页面转场、元素动画 |
| 图标库 | Lucide Icons | 0.454 | UI 图标（CDN） |
| 字体 | Inter + Noto Sans SC + JetBrains Mono | — | UI/中文/代码字体 |
| 后端 | cpp-httplib | 0.18.3 | HTTP 服务器 |
| 构建 | CMake | 3.14+ | C++ 构建 |
| 可视化 | Canvas 2D API | — | 所有实验渲染 |

---

## 3. 目录结构详解

```
工科实验室/
├── index.html                  # 【核心】单页入口，包含所有页面 HTML 结构
├── README.md                   # 项目简介
├── DEVELOPER_GUIDE.md          # 本文档
├── UPDATE_PLAN.md              # 后续更新计划
│
├── shared/                     # 全局共享资源
│   ├── css/
│   │   ├── tokens.css          # 设计令牌（CSS 变量：颜色、间距、字体、阴影等）
│   │   ├── base.css            # 基础样式（reset、页面系统 .page/.page.active）
│   │   ├── typography.css      # 排版样式
│   │   ├── navbar.css          # 顶部导航栏
│   │   ├── page-layout.css     # Hero 区域布局
│   │   ├── cards.css           # 实验推荐卡片组件
│   │   ├── module-selector.css # 模块选择器画廊
│   │   └── responsive.css      # 响应式断点（必须最后加载）
│   └── js/
│       ├── config.js           # 【关键】全局配置（页面元数据 + 实验列表）
│       ├── router.js           # 路由系统 + GSAP 径向裁剪转场
│       ├── module-selector.js  # 模块选择器（画廊 ↔ 实验内容切换）
│       ├── cards.js            # "更多实验"推荐卡片
│       ├── common.js           # 公共工具函数
│       ├── scroll-animations.js # 滚动动画
│       └── main.js             # 应用启动入口（initApp）
│
├── pages/                      # 各学科页面资源
│   ├── home/                   # 首页
│   │   ├── home.css            # 首页样式（星空、卫星、HUD）
│   │   └── home.js             # 首页逻辑（粒子网络、卫星轨道、打字机等）
│   │
│   ├── mathematics/            # 数学模块
│   │   ├── mathematics.css     # 数学页面样式
│   │   ├── mathematics.js      # 算筹演示 + 函数图像
│   │   ├── calculus.js         # 微积分可视化（导数切线 + 定积分面积）
│   │   ├── geometry.js         # 几何变换（平移、旋转、缩放、剪切、镜像）
│   │   └── complex-numbers.js  # 复数运算（复平面可视化）
│   │
│   ├── physics/                # 物理模块
│   │   ├── physics.css         # 物理页面样式
│   │   ├── physics.js          # 力学模拟（重力、碰撞、弹簧）
│   │   ├── electromagnetic.js  # 电磁场可视化（电场线、磁场）
│   │   ├── waves.js            # 波动演示（声波、光波、干涉）
│   │   └── relativity.js       # 相对论（时间膨胀、长度收缩）
│   │
│   ├── chemistry/              # 化学模块
│   │   ├── chemistry.css       # 化学页面样式
│   │   ├── periodic-table.js   # 交互式元素周期表（118个元素完整数据）
│   │   ├── molecular-structure.js # 3D 分子结构（8种分子模型）
│   │   └── chemical-reactions.js  # 化学反应动画（5种反应）
│   │
│   ├── algorithms/             # 算法模块
│   │   ├── algorithms.css      # 算法页面样式
│   │   ├── algorithms.js       # 桶排序动画
│   │   ├── search-algorithms.js # 二分查找 + 图遍历 (BFS/DFS)
│   │   ├── graph-algo.js       # 图算法 (Dijkstra/Prim)
│   │   └── data-structures.js  # 数据结构可视化（栈、队列、树）
│   │
│   └── biology/                # 生物模块
│       ├── biology.css         # 生物页面样式
│       ├── biology.js          # 生物模块初始化入口
│       ├── cell-structure.js   # 细胞结构（动物/植物细胞）
│       ├── dna-helix.js        # DNA 双螺旋 + 复制模拟
│       ├── photosynthesis.js   # 光合作用（光反应可视化）
│       └── genetics.js         # 遗传学（孟德尔杂交 Punnett Square）
│
└── server/                     # C++ 后端服务器
    ├── CMakeLists.txt          # CMake 构建配置
    ├── main.cpp                # httplib 服务器源码
    ├── README.md               # 服务器文档
    └── build/                  # CMake 构建输出目录
```

---

## 4. 前端架构

### 4.1 SPA 页面系统

所有页面内容均嵌入 `index.html` 中的 `<section>` 标签：

```html
<section id="page-home" class="page active home-page">...</section>
<section id="page-mathematics" class="page">...</section>
<section id="page-physics" class="page">...</section>
<section id="page-chemistry" class="page">...</section>
<section id="page-algorithms" class="page">...</section>
<section id="page-biology" class="page">...</section>
```

**页面切换机制**：通过 CSS 类 `.active` 控制显隐，结合 GSAP 实现径向裁剪转场动画。

### 4.2 JS 加载顺序

```html
<!-- 1. 外部库 -->
<script src="gsap.min.js"></script>
<script src="ScrollTrigger.min.js"></script>
<script src="lucide.min.js"></script>

<!-- 2. 全局配置与工具 -->
<script src="shared/js/config.js"></script>       <!-- CONFIG 对象 -->
<script src="shared/js/common.js"></script>        <!-- 公共工具 -->
<script src="shared/js/module-selector.js"></script>
<script src="shared/js/router.js"></script>
<script src="shared/js/scroll-animations.js"></script>
<script src="shared/js/cards.js"></script>

<!-- 3. 页面模块 -->
<script src="pages/home/home.js"></script>
<script src="pages/mathematics/mathematics.js"></script>
<!-- ... 各学科模块 ... -->

<!-- 4. 启动入口（必须最后） -->
<script src="shared/js/main.js"></script>
```

### 4.3 全局配置 (CONFIG)

`shared/js/config.js` 定义核心配置：

```javascript
CONFIG = {
    pages: {         // 页面元数据（标签、颜色、图标、标题、描述）
        mathematics: { label: '数学', accent: 'blue', ... },
        // ...
    },
    experiments: {   // 实验卡片列表（id、标题、描述、图标、变体、锚点）
        mathematics: [
            { id: 'function-graph', title: '函数图像', variant: 'featured', ... },
            // ...
        ],
        // ...
    },
    accentColors: {  // 颜色映射
        mathematics: 'blue',
        physics: 'purple',
        // ...
    }
};
```

**新增实验时**：在对应学科的 `experiments` 数组中添加条目，`variant` 为 `'featured'` 或 `'upcoming'`。

### 4.4 Canvas 渲染模式

所有实验均使用 Canvas 2D API 进行绘制：
- **坐标系转换**：通过 `ctx.translate()` 和 `ctx.scale()` 建立数学坐标系
- **动画循环**：`requestAnimationFrame` 驱动的实时渲染
- **交互检测**：鼠标/触摸位置映射到画布坐标，几何碰撞检测
- **3D 投影**：Y-X 旋转矩阵 + perspective 透视投影（分子结构、DNA 螺旋）

---

## 5. 后端架构

### 5.1 C++ 服务器

基于 `cpp-httplib` 的轻量级 HTTP 服务器。

**启动命令**：
```bash
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 9527 -r ..
```

**参数**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-p PORT` | 监听端口 | 9527 |
| `-r ROOT` | 静态文件根目录 | `..` |
| `-h` | 显示帮助 | — |

### 5.2 API 端点

| 方法 | 路径 | 响应 |
|------|------|------|
| GET | `/api/health` | `{"status":"ok","server":"englab-cpp"}` |
| GET | `/api/info` | 服务器信息、根目录、时间戳 |
| POST | `/api/eval` | 数学表达式求值（占位符，未实现） |

### 5.3 替代方案

```bash
# Python 临时服务器
python -m http.server 9527

# Node.js
npx serve -p 9527
```

---

## 6. 各模块功能说明

### 6.1 数学模块 (Mathematics)

| 实验 | 文件 | 功能 | 交互方式 |
|------|------|------|----------|
| 算筹演示 | `mathematics.js` | 中国古代算筹加减法 | 输入框 + 按钮 |
| 函数图像 | `mathematics.js` | 实时绘制数学函数 | 表达式输入 + 预设 + 范围调整 |
| 微积分 | `calculus.js` | 导数切线 + 定积分面积 | 滑块拖动 + 动画播放 |
| 几何变换 | `geometry.js` | 平移/旋转/缩放/剪切/镜像 | 参数滑块 + 形状切换 |
| 复数运算 | `complex-numbers.js` | 复平面可视化 | 拖拽 + 运算选择 |

### 6.2 物理模块 (Physics)

| 实验 | 文件 | 功能 | 交互方式 |
|------|------|------|----------|
| 力学模拟 | `physics.js` | 重力、碰撞、弹簧系统 | 参数调整 + 实时模拟 |
| 电磁场 | `electromagnetic.js` | 电场线/磁场分布可视化 | 电荷拖拽 + 参数调整 |
| 波动演示 | `waves.js` | 声波/光波/干涉 | 频率振幅调整 |
| 相对论 | `relativity.js` | 时间膨胀/长度收缩 | 速度滑块 |

### 6.3 化学模块 (Chemistry)

| 实验 | 文件 | 功能 | 交互方式 |
|------|------|------|----------|
| 元素周期表 | `periodic-table.js` | 118 元素交互式周期表 | 点击元素/分类过滤 |
| 分子结构 | `molecular-structure.js` | 8 种分子 3D 模型 | 鼠标拖拽旋转/滚轮缩放 |
| 化学反应 | `chemical-reactions.js` | 5 种反应过程动画 | 反应选择/速度控制/播放 |

### 6.4 算法模块 (Algorithms)

| 实验 | 文件 | 功能 | 交互方式 |
|------|------|------|----------|
| 排序算法 | `algorithms.js` | 桶排序动画 | 速度滑块/数据重置 |
| 搜索算法 | `search-algorithms.js` | 二分查找 + BFS/DFS | 图遍历起点选择 |
| 图算法 | `graph-algo.js` | Dijkstra/Prim | 图节点选择/参数调整 |
| 数据结构 | `data-structures.js` | 栈/队列/树可视化 | 入栈/出栈/遍历操作 |

### 6.5 生物模块 (Biology)

| 实验 | 文件 | 功能 | 交互方式 |
|------|------|------|----------|
| 细胞结构 | `cell-structure.js` | 动物/植物细胞对比 | 器官悬停/点击/类型切换 |
| DNA 结构 | `dna-helix.js` | 双螺旋 3D 旋转 + 复制 | 旋转/复制/重置按钮 |
| 光合作用 | `photosynthesis.js` | 光反应粒子模拟 | 光强度滑块/播放控制 |
| 遗传学 | `genetics.js` | 孟德尔杂交 Punnett Square | 亲本基因型选择 |

---

## 7. 路由与页面转场系统

### 7.1 路由器 (`Router`)

**核心对象**：`shared/js/router.js`

```javascript
Router = {
    currentPage: 'home',
    isTransitioning: false,
    transitionOrigin: { x: 50, y: 50 },  // 转场起始点（百分比）
    
    init()          // 初始化：绑定导航点击、监听 hashchange
    navigateTo()    // 页面切换（带/不带动画）
    handleHash()    // 处理 URL hash 变化
    updateNav()     // 更新导航栏高亮
    onPageEnter()   // 页面进入回调
}
```

### 7.2 转场动画流程

```
1. 当前页面淡出 (opacity→0, scale→0.97, blur→6px)  [0.18s]
2. 径向裁剪遮罩展开 (circle 0% → 150%)             [0.3s]
3. 切换 .active 类 + 滚动到顶部
4. 遮罩淡出 + 目标页面淡入 (opacity→1, y→0)        [0.3s]
5. Hero 区域子元素逐个入场 (stagger 50ms)
6. 触发 onPageEnter() 回调
```

### 7.3 导航方式

- **URL Hash**：`#home`、`#mathematics`、`#physics` 等
- **导航栏点击**：顶部 nav 中每个 `.nav-item[data-page]`
- **首页卫星点击**：`selectModule('target')` → 自定义动画 → Router
- **实验卡片点击**：`openExperiment(id)` → 路由切换 + 模块展开

---

## 8. 模块选择器系统

### 8.1 工作原理

每个学科页面分为两种视图：
- **画廊视图** (Gallery)：显示所有实验卡片
- **实验视图** (Module)：显示单个实验的完整内容

```
┌─────────────────────────────┐
│ 学科 Hero 区域               │
├─────────────────────────────┤
│ ┌───┐ ┌───┐ ┌───┐ ┌───┐   │  ← 画廊视图（ModuleSelector）
│ │ 01│ │ 02│ │ 03│ │ 04│   │
│ └───┘ └───┘ └───┘ └───┘   │
├─────────────────────────────┤
│ ← 返回                      │  ← 实验视图（点击卡片后展开）
│ [完整实验内容]               │
│                             │
├─────────────────────────────┤
│ 更多实验（推荐卡片）          │
└─────────────────────────────┘
```

### 8.2 关键方法

- `ModuleSelector.openModule(page, moduleId)`：隐藏画廊 → 显示实验 → 添加返回按钮
- `ModuleSelector.closeModule(page)`：隐藏实验 → 恢复画廊

### 8.3 HTML 结构约定

实验内容必须用 `data-module` 属性标记：

```html
<div class="content-section" data-module="function-graph">
    <!-- 实验内容 -->
</div>
```

`data-module` 值必须与 `CONFIG.experiments` 中的 `id` 一致。

---

## 9. 首页系统

### 9.1 视觉组件

| 组件 | 类/ID | 说明 |
|------|-------|------|
| 粒子网络 | `#particle-network` | Canvas 粒子连线 + 鼠标吸引 |
| 三层星空 | `.star-layer-far/mid/near` | CSS 闪烁星星 + 鼠标视差 |
| 星云 | `.nebula-1/2/3` | CSS 模糊渐变漂浮 |
| 流星 | `#shooting-stars` | JS 随机生成 + CSS 动画 |
| HUD 框架 | `.hud-frame` | 四角装饰 + 扫描线 + 数据流 |
| 主星 | `#main-star` | 脉冲动画 + 表面纹理滚动 |
| 眼睛 | `.star-eyes` | 瞳孔跟随鼠标 + 眨眼 |
| 打字机标语 | `#tagline-text` | 循环 6 段文案 |
| 卫星轨道 | `#satellites-orbit` | 5 颗行星独立 3D 轨道 |

### 9.2 卫星系统

5 个卫星分别对应 5 个学科，各有独立轨道参数（半径、倾角、周期、旋转方向）：

| 卫星 | 学科 | 颜色 | 轨道半径X/Y | 周期 |
|------|------|------|-------------|------|
| satellite-1 | 数学 | 蓝色 | 320/200 | 18s |
| satellite-2 | 物理 | 紫色 | 420/260 | 25s |
| satellite-3 | 化学 | 绿色 | 520/320 | 32s |
| satellite-4 | 算法 | 橙色 | 450/280 | 22s |
| satellite-5 | 生物 | 青色 | 380/240 | 28s |

**点击卫星动画流程**：
1. 粒子喷发效果
2. 主星摇晃 + 淡出
3. 其他卫星缩小消失
4. 选中卫星放大至屏幕中心（4倍）
5. 背景渐变为学科主题色
6. 路由切换至对应学科页面
7. 重置所有状态（延迟 300ms）

---

## 10. 实验模块开发指南

### 10.1 新增实验步骤

1. **注册实验**：在 `config.js` 的 `CONFIG.experiments[学科]` 中添加条目

```javascript
{ id: 'new-exp', title: '新实验', description: '实验描述', icon: 'icon-name', variant: 'featured' }
```

2. **编写 HTML**：在 `index.html` 对应学科 `<section>` 内添加

```html
<div class="content-section" data-module="new-exp">
    <div class="demo-section">
        <div class="section-header">
            <h2>实验标题</h2>
            <p>实验说明</p>
        </div>
        <div class="demo-layout">
            <div class="demo-controls-panel">
                <!-- 控制面板 -->
            </div>
            <div class="demo-visualization">
                <canvas id="new-exp-canvas"></canvas>
            </div>
        </div>
    </div>
</div>
```

3. **编写 JS**：创建 `pages/学科/new-exp.js`

```javascript
const NewExp = {
    canvas: null, ctx: null,
    init() {
        this.canvas = document.getElementById('new-exp-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.loop();
    },
    resize() { /* 响应式 canvas 尺寸 */ },
    draw() { /* 渲染逻辑 */ },
    loop() { requestAnimationFrame(() => this.loop()); this.draw(); }
};
function initNewExp() { NewExp.init(); }
```

4. **注册到 main.js**：

```javascript
if (typeof initNewExp === 'function') initNewExp();
```

5. **引入 JS**：在 `index.html` 中添加 `<script>` 标签

6. **测试**：启动服务器，访问对应学科页面 → 点击卡片进入实验

### 10.2 编码规范

- 每个实验封装为独立对象（如 `Calculus`、`ChemReaction`）
- 初始化函数命名：`initXxx()`，全局暴露
- Canvas 使用 `requestAnimationFrame` 驱动
- 响应式：监听 `resize` 事件调整 canvas 尺寸
- 交互：绑定 `mousemove`/`click`/`touchstart` 事件
- 清理：在页面离开时可通过 `Router.onPageEnter()` 暂停动画

### 10.3 样式规范

- 使用 `tokens.css` 中的 CSS 变量
- 学科主题色：`--accent-blue`(数学)、`--accent-purple`(物理)、`--accent-green`(化学)、`--accent-orange`(算法)、`--accent-teal`(生物)
- 间距：`--space-1` 到 `--space-8`
- 字体大小：`--text-xs` 到 `--text-3xl`
- 圆角：`--radius-sm`/`--radius-md`/`--radius-lg`

---

## 11. CSS 设计系统

### 11.1 加载顺序（严格遵守）

```
1. tokens.css      → 设计令牌（变量定义）
2. base.css        → 全局重置 + 页面系统
3. typography.css   → 排版
4. navbar.css      → 导航栏
5. page-layout.css → Hero 区域
6. cards.css       → 卡片组件
7. module-selector.css → 模块选择器
8. [各页面 CSS]     → 页面特有样式
9. responsive.css  → 响应式（必须最后）
```

### 11.2 断点

```css
@media (max-width: 768px)  { /* 平板 */ }
@media (max-width: 480px)  { /* 手机 */ }
```

---

## 12. 构建与部署

### 12.1 开发环境

```bash
# 方式 1: Python 开发服务器
python -m http.server 9527

# 方式 2: VS Code Live Server 插件
# 右键 index.html → Open with Live Server

# 方式 3: C++ 服务器（需要 CMake + C++ 编译器）
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 9527 -r ..
```

### 12.2 部署

项目为纯静态网站，可部署到任何静态文件服务器：
- **GitHub Pages**：直接推送到 `gh-pages` 分支
- **Vercel / Netlify**：连接仓库自动部署
- **Nginx**：指向项目根目录
- **C++ 服务器**：编译后直接运行

---

## 13. 维护指南

### 13.1 常见任务

| 任务 | 操作 |
|------|------|
| 修改实验内容 | 编辑对应 `pages/学科/xxx.js` |
| 新增实验 | 见 §10.1 |
| 修改导航 | 编辑 `index.html` 的 `<nav>` + `config.js` |
| 调整主题色 | 编辑 `tokens.css` |
| 新增学科 | 见 §13.2 |

### 13.2 新增学科

1. 在 `CONFIG.pages` 和 `CONFIG.experiments` 中添加学科配置
2. 在 `index.html` 中添加导航项 + 页面 `<section>`
3. 创建 `pages/新学科/` 目录
4. 在首页添加卫星（HTML + CSS + JS 轨道配置）
5. 在 `SatelliteSystem.orbits` 中添加轨道数据
6. 在 `home.css` 中添加卫星样式
7. 更新 `selectModule()` 中的颜色映射

### 13.3 调试技巧

- **路由问题**：在控制台输入 `Router.currentPage` 查看当前页面
- **模块选择器**：`ModuleSelector.activeModule` 查看当前展开的模块
- **Canvas 问题**：在实验对象中添加临时 `console.log` 或使用 Canvas Inspector 浏览器扩展
- **动画问题**：GSAP DevTools（`gsap.globalTimeline`）

---

## 14. 维护计划

### 14.1 短期计划 (1-2 周)

- [ ] 修复首页生物卫星跳转（已完成 ✅）
- [ ] 优化化学反应交互质量（添加化学键可视化）
- [ ] 审查所有页面交互逻辑 Bug
- [ ] 完善响应式布局断点
- [ ] 添加 404/错误状态页面

### 14.2 长期计划 (1-3 月)

- [ ] 对齐人教版课标，扩展各科实验内容
- [ ] 实现 `/api/eval` 安全数学表达式求值
- [ ] 添加用户学习进度追踪（localStorage）
- [ ] 国际化 (i18n) 支持
- [ ] 性能优化：Canvas OffscreenCanvas、Web Worker
- [ ] PWA 支持：离线访问、安装
- [ ] 无障碍 (a11y)：ARIA 属性、键盘导航

---

## 15. 更新日志

### v2.7 — 2026-04-13
- ✅ 重写：波动演示模块（waves.js，342→560+行）
  - 三模式切换：叠加 | 驻波分析 | 多普勒效应
  - **叠加模式**（增强）：
    - 保留原有两波叠加 + 探针 + 预设
    - 新增：拍频包络线（当 |f₁−f₂| 在 0.05~1.5 范围内自动显示虚线包络）
    - 新增：能量密度可视化（底部薄条，∝ y²）
  - **驻波分析模式**（全新）：
    - 谐波次数滑块 n=1..8
    - 入射波（淡红右行）+ 反射波（淡蓝左行）+ 驻波合成（紫色）
    - 振幅包络 ±2A sin(kx) 虚线绘制
    - 波节（N，绿色圆圈）自动标注，共 n+1 个
    - 波腹（A，金色虚线）自动标注，共 n 个
    - 两端固定点标记
    - 信息面板：λ = 2L/n、y = 2A sin(nπx/L) cos(ωt) 公式
  - **多普勒效应模式**（全新）：
    - 2D 波前同心圆动画（声源移动，波前中心不同）
    - 声源速度滑块 vs/v = 0~1.5（支持超音速）
    - 声源频率滑块 0.5~5 Hz
    - 来回弹跳运动 + 速度箭头可视化
    - 两侧观测者 O：实时计算并显示接收频率 f'
    - 超音速马赫锥：自动绘制锥角线（θ = arcsin(1/M)）
    - 信息面板：亚/近/超音速判定、f' 公式、马赫数 & 锥角
  - 模式切换自动隐藏/显示相应控件面板
  - 波动原理说明新增"驻波"和"多普勒效应"条目
  - index.html 描述更新

### v2.6 — 2026-04-13
- ✅ 重写：电磁场可视化模块（electromagnetic.js，400→520+行）
  - 三显示模式切换：电力线 | 等势线 | 电势图
  - **电力线模式**（保留并增强）：场线 + 矢量场叠加
  - **等势线模式**（全新）：
    - 基于 Marching Squares 的等势线绘制
    - 关于 V=0 对称的 12 条等势线
    - 正势红色、负势蓝色、零势黄色
    - 叠加淡化场线方便对比
  - **电势热图模式**（全新）：
    - 1/3 分辨率 offscreen canvas + ImageData 像素级渲染
    - Blue(-1)→Dark(0)→Red(+1) 发散色谱
    - 叠加淡化等势线轮廓
    - dirty flag 缓存，仅电荷移动时重算
  - **测量探针**（全新）：
    - 鼠标悬停实时显示 |E|、V、θ 三项数据
    - E 向量箭头可视化（金色）
    - 半透明数值标签面板
  - **预设配置**（全新）：偶极子、四极子、平行板、三角形
  - **双击删除**电荷
  - potentialAt() 标量电势计算函数
  - 修复 const 变量重赋值 bug（potentialAt）
  - 原理说明新增"等势线"和"电势"两节
  - index.html 描述更新

### v2.5 — 2026-04-13
- ✅ 重写：复数可视化模块（complex-numbers.js，570→680+行）
  - 三模式切换：运算 | 单位根 | 域着色
  - **运算模式**（增强）：
    - 乘法/除法增加模长圆（虚线圆弧可视化 |z₁|×|z₂| 关系）
    - 角度弧标注度数
    - 幂运算增加公式说明 z₁^z₂ = exp(z₂·ln z₁)
    - 滚轮缩放（viewRange 1~50 自适应）
  - **单位根模式**（全新）：
    - z^n = 1 的 n 个根可视化（n=2..12 滑块）
    - 正多边形连接 + 辐射线 + 填充
    - 旋转角标注（360°/n）
    - 动画演示：根依次高亮旋转
    - 信息面板显示通式 z_k = e^(i·2πk/n)
  - **域着色模式**（全新）：
    - 6 种复变函数：z², z³, 1/z, eᶻ, sin(z), z³−1
    - 像素级域着色：色相=辐角，亮度=对数模长等高线
    - 半分辨率 offscreen canvas 缓存，仅 dirty 时重算
    - 零点（白圆圈）/ 极点（红叉）自动标注
    - 函数特性描述面板
  - 自适应网格步长（nice-number 算法，任意缩放级别保持 8~15 条网格线）
  - ResizeObserver 替代 window.resize
  - DPR 正确处理
  - 模式按钮与面板动态注入 DOM

### v2.4 — 2026-04-13
- ✅ 重写：微积分模块（calculus.js，445→620+行）
  - 三模式切换：导数/切线、定积分、Taylor 级数
  - **导数模式**：f(x) + f'(x) + f''(x) 曲线，切线（虚线）+ 斜率标注
  - **临界点检测**：自动扫描 f'(x)=0（bisection），菱形标记极大/极小/驻点
  - **拐点检测**：自动扫描 f''(x)=0，三角形标记
  - **定积分模式**：Riemann 和可视化（左/右/中/梯形 4 种类型），N=2..200 滑块
  - Riemann 误差实时显示（与精确 Simpson 积分对比）
  - **Taylor 级数模式**：可调阶数 n=1..20 + 展开中心 a，多项式字符串公式
  - 自适应步长数值微分（`h = ε^(1/(k+2))`），解决高阶导数灾难性消去问题
  - Taylor 零系数过滤（不显示 "0x^6" 等噪声项）
  - 收敛半径可视区域着色
  - 缩放（鼠标滚轮，焦点感知）+ 平移（右键拖拽）
  - ResizeObserver 替代 window.resize
  - Y 轴刻度标签补全
- ✅ 重写：几何变换模块（geometry.js，385→540+行）
  - 双模式切换：仿射变换 + 三角形几何
  - **仿射变换模式**：增加行列式（面积缩放因子）、特征值/特征向量显示
  - **三角形几何模式**（全新）：
    - 拖拽 3 个顶点交互
    - 外接圆 + 外心
    - 内切圆 + 内心
    - 重心、垂心
    - 欧拉线（外心-重心-垂心共线，OG:GH=1:2）
    - 角度弧线显示 + 边长标注
    - 中线、高线可选显示
    - 面积/周长实时计算
  - ResizeObserver 替代 debounced resize

### v2.3 — 2026-04-13
- ✅ 重写：遗传学模块（genetics.js，150→280行）
  - 对象化 Genetics 模块，DPR + ResizeObserver 适配
  - 新增双基因模式（AaBb 等 9 种组合），动态切换按钮注入 DOM
  - Punnett 方格可视化 + 表现型柱状图统计
  - GCD 化简比例显示（如 9:3:3:1）
  - 双基因表现型分类（A_B_ / A_bb / aaB_ / aabb）
- ✅ 重写：光合作用模块（photosynthesis.js，178→425行）
  - 对象化 Photosynthesis 模块，DPR + ResizeObserver 适配
  - 光反应/暗反应分区可视化（左侧类囊体膜区 + 右侧 Calvin 循环基质区）
  - 3 组基粒（类囊体堆叠）在光反应区
  - Calvin 循环圆圈带旋转标记点
  - ATP+NADPH 粒子从光反应区转移至暗反应区
  - CO₂ 粒子 → 暗反应区固定 → 葡萄糖计数
  - H₂O 粒子 → 光反应区光解 → O₂ 气泡释放
  - 光合速率条随光照强度动态变化
  - 底部完整化学方程式（6CO₂ + 6H₂O ──光──▶ C₆H₁₂O₆ + 6O₂）

### v2.2 — 2026-04-13
- ✅ 新增：首页生物卫星跳转（第 5 轨道）
- ✅ 新增：完整开发者文档 & 项目后续更新计划
- ✅ 重写：化学反应模块（chemical-reactions.js，430→870行）
  - 化学键可视化：单键、双键（C=O）、三键（N≡N）、离子键（Na-Cl 紫色虚线）
  - 5 阶段动画：反应物完整分子 → 键断裂（虚线 + 震动） → 自由原子重排 → 键形成 → 产物分子
  - 内嵌能量曲线图（显示 Ea 活化能 + ΔH 焓变）
  - 反应信息面板新增：活化能数值、反应历程文字说明
  - ResizeObserver 修复隐藏 section 初始化时 canvas 尺寸为 0 的问题
  - DPR 适配（devicePixelRatio）
- 🔒 安全：mathematics.js / calculus.js 表达式编译加固（`"use strict"` + 白名单校验）
- 🔧 修复：router.js 导航竞态条件（`isTransitioning` 提前设置）

### v2.1 — 优化网页交互逻辑
- 优化模块选择器
- 新增生物模块（细胞、DNA、光合作用、遗传学）

### v2.0 — 项目重构
- SPA 架构 + hash 路由
- GSAP 径向裁剪转场
- 模块化实验系统
