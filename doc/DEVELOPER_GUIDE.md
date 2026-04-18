# 工科实验室 — 开发者文档

> **版本**: v4.0.3 | **最后更新**: 2026-04-17 | **维护者团队**: EngLab Dev Team

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
10. [加载屏与启动优化](#10-加载屏与启动优化)
11. [实验模块开发指南](#11-实验模块开发指南)
12. [CSS 设计系统](#12-CSS-设计系统)
13. [构建与部署](#13-构建与部署)
14. [维护指南](#14-维护指南)
15. [维护计划](#15-维护计划)
16. [更新日志](#16-更新日志)

---

## 1. 项目概览

**工科实验室**是一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，面向高中阶段学生，涵盖**数学、物理、化学、算法、生物**五大学科，提供 **61 个可视化交互实验**，全面覆盖人教版（2019 新课标）高中必修及选择性必修核心知识点。

### 核心理念

- **玩中学** (Learn by Play)：所有实验均可实时交互操作
- **从抽象到直觉**：将公式和理论转化为可视化动画
- **低门槛高上限**：从基础概念到深入原理的分层教学

### 技术特点

- 纯前端渲染，无框架依赖（Vanilla JS + Canvas 2D）
- GSAP 驱动的丝滑页面转场
- C++ httplib 高性能静态服务器（部署端口 910）
- 单页应用 (SPA) 架构，hash 路由
- 首屏加载优化：内联 CSS 加载屏 + defer 脚本分阶段初始化
- ARIA 无障碍支持 + DPR 高分屏适配

---

## 2. 技术架构

```
┌───────────────────────────────────────────────┐
│                  浏览器端                       │
│                                               │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Router  │──│ Module   │──│ Experiment   │ │
│  │ (hash)  │  │ Selector │  │ Modules (60) │ │
│  └────┬────┘  └────┬─────┘  └──────┬───────┘ │
│       │            │               │          │
│  ┌────┴────────────┴───────────────┴───────┐  │
│  │           index.html (SPA 入口)          │  │
│  │  所有页面 <section> 以 display 切换       │  │
│  └──────────────────────────────────────────┘  │
│                                               │
│  CSS 层:  tokens → base → components → pages  │
│  JS 层:   CDN → config → shared → home →      │
│           main(sync) → 60 modules(defer)      │
└───────────────────────┬───────────────────────┘
                        │ HTTP
┌───────────────────────┴───────────────────────┐
│      C++ httplib 服务器 (部署端口 910)          │
│  - 静态文件托管                                 │
│  - REST API (/api/health, /api/info)          │
│  - CORS 支持                                   │
└───────────────────────────────────────────────┘
```

### 技术栈

| 层级     | 技术                                  | 版本   | 用途               |
| -------- | ------------------------------------- | ------ | ------------------ |
| 前端核心 | HTML5 / CSS3 / ES6+                   | —     | 页面结构与交互     |
| 动画引擎 | GSAP                                  | 3.12.7 | 页面转场、元素动画 |
| 图标库   | Lucide Icons                          | 0.454  | UI 图标（CDN）     |
| 字体     | Inter + Noto Sans SC + JetBrains Mono | —     | UI/中文/代码字体   |
| 后端     | cpp-httplib                           | 0.18.3 | HTTP 服务器        |
| 构建     | CMake                                 | 3.14+  | C++ 构建           |
| 可视化   | Canvas 2D API                         | —     | 所有实验渲染       |

---

## 3. 目录结构详解

```
工科实验室/
├── index.html                  # 【核心】单页入口，包含所有页面 HTML 结构
├── sw.js                       # Service Worker（离线缓存 + stale-while-revalidate）
├── README.md                   # 项目简介
├── deploy.ps1                  # Windows 一键部署脚本（端口 910）
│
├── doc/                        # 项目文档
│   ├── DEVELOPER_GUIDE.md      # 本文档
│   ├── UPDATE_PLAN.md          # 后续更新计划
│   └── DEPLOY.md               # 服务器部署文档
│
├── shared/                     # 全局共享资源
│   ├── css/
│   │   ├── tokens.css          # 设计令牌（CSS 变量：颜色、间距、字体、阴影等）
│   │   ├── base.css            # 基础样式（reset、页面系统 .page/.page.active、focus-visible）
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
│       ├── cards.js            # "更多实验"推荐卡片（含防抖锁）
│       ├── common.js           # 公共工具函数
│       ├── scroll-animations.js # 滚动动画
│       └── main.js             # 应用启动入口（initApp + 分阶段初始化）
│
├── pages/                      # 各学科页面资源
│   ├── home/                   # 首页
│   │   ├── home.css            # 首页样式（星空、卫星、HUD、加载屏）
│   │   └── home.js             # 首页逻辑（粒子网络、卫星轨道、打字机等）
│   │
│   ├── mathematics/            # 数学模块（13 个实验）
│   │   ├── mathematics.css     # 数学页面样式
│   │   ├── mathematics.js      # 算筹演示 + 函数图像
│   │   ├── calculus.js         # 微积分（导数切线 + 定积分面积 + Taylor 级数）
│   │   ├── geometry.js         # 几何变换（仿射变换 + 三角形几何）
│   │   ├── complex-numbers.js  # 复数运算（运算 + 单位根 + 域着色）
│   │   ├── trigonometry.js     # 三角函数（单位圆联动正弦曲线）
│   │   ├── set-operations.js   # 集合运算（韦恩图交互）
│   │   ├── probability.js      # 概率统计（频率收敛 + 直方图）
│   │   ├── vector-ops.js       # 向量运算（加减 + 数量积 + 投影）
│   │   ├── inequality.js       # 不等式（线性规划可行域）
│   │   ├── conic-sections.js   # 圆锥曲线（椭圆/双曲线/抛物线）
│   │   ├── solid-geometry.js   # 立体几何（5 形体 + 截面 + 3D 旋转）
│   │   ├── permutation-combination.js  # 排列组合（树状图 + 杨辉三角）
│   │   └── sequences.js        # 数列可视化（等差/等比 + 前 n 项和）
│   │
│   ├── physics/                # 物理模块（15 个实验）
│   │   ├── physics.css         # 物理页面样式
│   │   ├── physics.js          # 力学模拟（重力、碰撞、弹簧）
│   │   ├── kinematics.js       # 匀变速运动（v-t/s-t 图联动）
│   │   ├── projectile.js       # 抛体运动（斜抛轨迹分解）
│   │   ├── circular-motion.js  # 圆周运动（向心力可视化）
│   │   ├── gravitation.js      # 万有引力（卫星轨道模拟）
│   │   ├── energy-conservation.js  # 机械能守恒（过山车能量条）
│   │   ├── electromagnetic.js  # 电磁场（电力线 + 等势线 + 电势图）
│   │   ├── circuit-analysis.js # 电路分析（串并联 + 欧姆定律）
│   │   ├── electromagnetic-induction.js  # 电磁感应（法拉第定律）
│   │   ├── alternating-current.js  # 交变电流（波形 + 相量图 + 变压器）
│   │   ├── waves.js            # 波动演示（叠加 + 驻波 + 多普勒）
│   │   ├── optics.js           # 光学（折射/反射/全反射/干涉/色散/偏振）
│   │   ├── fluid-dynamics.js   # 流体力学（势流叠加 + 伯努利方程）
│   │   └── relativity.js       # 相对论（时间膨胀/长度收缩）
│   │
│   ├── chemistry/              # 化学模块（11 个实验）
│   │   ├── chemistry.css       # 化学页面样式
│   │   ├── periodic-table.js   # 交互式元素周期表（118 元素）
│   │   ├── molecular-structure.js  # 3D 分子结构（8 种分子模型）
│   │   ├── chemical-reactions.js   # 化学反应动画（5 种 + 化学键可视化）
│   │   ├── chemical-bond.js    # 化学键（离子键/共价键/金属键）
│   │   ├── ionic-reaction.js   # 离子反应（方程式拆分 + 电离可视化）
│   │   ├── redox.js            # 氧化还原（电子转移 + 双线桥法）
│   │   ├── chemical-equilibrium.js  # 化学平衡（勒夏特列原理）
│   │   ├── electrochemistry.js # 电化学（原电池/电解池）
│   │   ├── organic-chemistry.js    # 有机化学（3D 碳链 + 6 种分子）
│   │   ├── reaction-rate.js    # 反应速率（Maxwell-Boltzmann + 碰撞理论）
│   │   └── solution-ionization.js  # 溶液与电离（6 种物质 + pH 计算）
│   │
│   ├── algorithms/             # 算法模块（8 个实验）
│   │   ├── algorithms.css      # 算法页面样式
│   │   ├── algorithms.js       # 桶排序动画
│   │   ├── search-algorithms.js    # 搜索算法（二分查找 + BFS/DFS）
│   │   ├── graph-algo.js       # 图算法（Dijkstra/Prim）
│   │   ├── data-structures.js  # 数据结构（栈/队列/树）
│   │   ├── sorting-compare.js  # 排序对比（5 种排序动画对比）
│   │   ├── recursion-vis.js    # 递归可视化（Fibonacci 树 + 汉诺塔）
│   │   ├── dynamic-programming.js  # 动态规划（0/1 背包 DP 表）
│   │   └── string-matching.js  # 字符串匹配（KMP 逐步动画）
│   │
│   └── biology/                # 生物模块（13 个实验）
│       ├── biology.css         # 生物页面样式
│       ├── biology.js          # 生物模块初始化入口
│       ├── cell-structure.js   # 细胞结构（动物/植物细胞）
│       ├── dna-helix.js        # DNA 双螺旋 + 复制模拟
│       ├── photosynthesis.js   # 光合作用（光反应 + 暗反应 Calvin 循环）
│       ├── genetics.js         # 遗传学（孟德尔杂交 + 双基因 + 系谱图）
│       ├── mitosis.js          # 有丝分裂（前/中/后/末期动画）
│       ├── meiosis.js          # 减数分裂（同源染色体联会 + 交叉互换）
│       ├── gene-expression.js  # 基因表达（转录 + 翻译全过程）
│       ├── cellular-respiration.js  # 细胞呼吸（糖酵解 + 柠檬酸循环 + 电子传递链）
│       ├── substance-transport.js   # 物质运输（自由扩散/协助扩散/主动运输/胞吞胞吐）
│       ├── gene-mutation.js    # 基因突变（碱基替换/插入/缺失 + 密码子表）
│       ├── neural-regulation.js    # 神经调节（突触传递 + 动作电位）
│       ├── immune-system.js    # 免疫系统（固有免疫 + 适应性免疫）
│       └── ecosystem.js        # 生态系统（能量流动 + 种群动态）
│
├── server/                     # C++ 后端服务器
│   ├── CMakeLists.txt          # CMake 构建配置
│   ├── main.cpp                # httplib 服务器源码
│   ├── README.md               # 服务器文档
│   └── build/                  # CMake 构建输出目录
│
└── test-screenshots/           # 测试截图目录
```

---

## 4. 前端架构

### 4.1 SPA 页面系统

所有页面内容均嵌入 `index.html` 中的 `<section>` 标签：

```html
<section id="page-home" class="page active home-page" role="region" aria-label="首页">...</section>
<section id="page-mathematics" class="page" role="region" aria-label="数学">...</section>
<section id="page-physics" class="page" role="region" aria-label="物理">...</section>
<section id="page-chemistry" class="page" role="region" aria-label="化学">...</section>
<section id="page-algorithms" class="page" role="region" aria-label="算法">...</section>
<section id="page-biology" class="page" role="region" aria-label="生物">...</section>
```

**页面切换机制**：通过 CSS 类 `.active` 控制显隐，结合 GSAP 实现径向裁剪转场动画。

### 4.2 JS 加载顺序

采用**同步 + defer 分层加载**策略，优化首屏体验：

```html
<!-- ① 内联加载屏 CSS（<head> 内，首帧可见） -->
<style>/* 加载动画关键帧 + 遮罩层样式 */</style>

<!-- ② CDN 外部库（同步） -->
<script src="lucide.min.js"></script>
<script src="gsap.min.js"></script>
<script src="ScrollTrigger.min.js"></script>

<!-- ③ 框架脚本（同步） -->
<script src="shared/js/config.js"></script>
<script src="shared/js/module-selector.js"></script>
<script src="shared/js/router.js"></script>
<script src="shared/js/scroll-animations.js"></script>
<script src="shared/js/cards.js"></script>
<script src="shared/js/common.js"></script>

<!-- ④ 首页逻辑（同步） -->
<script src="pages/home/home.js"></script>

<!-- ⑤ 启动入口（同步，必须在 home.js 之后、defer 之前） -->
<script src="shared/js/main.js"></script>

<!-- ⑥ 60 个实验模块（全部 defer，不阻塞首屏） -->
<script defer src="pages/mathematics/mathematics.js"></script>
<script defer src="pages/mathematics/calculus.js"></script>
<!-- ... 共 60 个 defer 脚本 ... -->
<script defer src="pages/biology/gene-mutation.js"></script>
```

**加载时序**：

1. 浏览器解析 `<head>`，内联 CSS 立即渲染加载屏
2. CDN + 框架脚本同步执行，建立 `CONFIG`、`Router`、`ModuleSelector` 等核心对象
3. `home.js` 同步加载，注册 `initHome()` 函数
4. `main.js` 同步执行：`lucide.createIcons()` → `Router.init()` → 分阶段 `initHome()`
5. 60 个 defer 脚本在文档解析完成后异步执行，各自调用 `initXxx()` 初始化
6. 首页渲染完成后，加载屏淡出消失

### 4.3 全局配置 (CONFIG)

`shared/js/config.js` 定义核心配置：

```javascript
CONFIG = {
    pages: {         // 页面元数据（标签、颜色、图标、标题、描述）
        mathematics: { label: '数学', accent: 'blue', ... },
        physics:     { label: '物理', accent: 'purple', ... },
        chemistry:   { label: '化学', accent: 'green', ... },
        algorithms:  { label: '算法', accent: 'orange', ... },
        biology:     { label: '生物', accent: 'teal', ... }
    },
    experiments: {   // 实验卡片列表（id、标题、描述、图标、变体、锚点）
        mathematics: [ /* 13 条 */ ],
        physics:     [ /* 14 条 */ ],
        chemistry:   [ /* 11 条 featured + 1 upcoming */ ],
        algorithms:  [ /* 8 条 */ ],
        biology:     [ /* 13 条 */ ]
    },
    accentColors: {  // 学科颜色映射
        mathematics: 'blue',
        physics: 'purple',
        chemistry: 'green',
        algorithms: 'orange',
        biology: 'teal'
    }
};
```

### 4.4 Canvas 渲染模式

所有实验均使用 Canvas 2D API 进行绘制：

- **DPR 适配**：`canvas.width = rect.width * dpr`，`ctx.setTransform(dpr, 0, 0, dpr, 0, 0)`
- **动画循环**：`requestAnimationFrame` + `performance.now()` dt 驱动
- **交互检测**：鼠标/触摸位置映射到画布坐标，几何碰撞检测
- **3D 投影**：Y-X 旋转矩阵 + perspective 透视投影（分子结构、DNA 螺旋、立体几何）
- **响应式**：`ResizeObserver` 监听容器尺寸变化（替代 window.resize）
- **教育面板**：多数实验通过 `_injectXxxPanel()` 动态注入 DOM

---

## 5. 后端架构

### 5.1 C++ 服务器

基于 `cpp-httplib` 的轻量级 HTTP 服务器。

**启动命令**：

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 910 -r ..
```

**参数**：

| 参数        | 说明           | 默认值 |
| ----------- | -------------- | ------ |
| `-p PORT` | 监听端口       | 9527   |
| `-r ROOT` | 静态文件根目录 | `..` |
| `-h`      | 显示帮助       | —     |

### 5.2 API 端点

| 方法 | 路径            | 响应                                      |
| ---- | --------------- | ----------------------------------------- |
| GET  | `/api/health` | `{"status":"ok","server":"englab-cpp"}` |
| GET  | `/api/info`   | 服务器信息、根目录、时间戳                |

### 5.3 替代方案（开发用）

```bash
# Python 临时服务器（推荐开发使用）
python -m http.server 8080
# 访问 http://localhost:8080

# Node.js
npx serve -p 8080
```

---

## 6. 各模块功能说明

### 6.1 数学模块 (Mathematics) — 13 个实验

| 实验     | 文件                           | 对应教材        | 功能                                | 交互方式                     |
| -------- | ------------------------------ | --------------- | ----------------------------------- | ---------------------------- |
| 算筹演示 | `mathematics.js`             | 文化拓展        | 中国古代算筹加减法                  | 输入框 + 按钮                |
| 函数图像 | `mathematics.js`             | 必修一 第3章    | 实时绘制数学函数                    | 表达式输入 + 预设 + 范围调整 |
| 微积分   | `calculus.js`                | 选必二 第4章    | 导数切线 + 定积分面积 + Taylor 级数 | 模式切换 + 滑块 + 缩放平移   |
| 几何变换 | `geometry.js`                | 必修二 第6章    | 仿射变换 + 三角形几何（欧拉线）     | 参数滑块 + 顶点拖拽          |
| 复数运算 | `complex-numbers.js`         | 必修二 第5章    | 运算 + 单位根 + 域着色三模式        | 拖拽 + 缩放 + 函数选择       |
| 三角函数 | `trigonometry.js`            | 必修一 第5章    | 单位圆联动正弦曲线                  | 角度拖拽 + 参数调整          |
| 集合运算 | `set-operations.js`          | 必修一 第1章    | 韦恩图交互                          | 元素拖拽 + 运算选择          |
| 概率统计 | `probability.js`             | 必修二 第9-10章 | 频率→概率收敛 + 直方图             | 实验选择 + 次数调整          |
| 向量运算 | `vector-ops.js`              | 必修二 第6章    | 加减法/数量积/投影                  | 向量拖拽 + 运算选择          |
| 不等式   | `inequality.js`              | 必修一 第2章    | 线性规划可行域 + 最优解             | 约束条件编辑                 |
| 圆锥曲线 | `conic-sections.js`          | 选必一 第3章    | 椭圆/双曲线/抛物线焦点轨迹          | 参数滑块 + 类型切换          |
| 立体几何 | `solid-geometry.js`          | 选必一 第1章    | 5 形体 + 截面 + 法线光照            | 鼠标拖拽旋转 + 截面滑块      |
| 排列组合 | `permutation-combination.js` | 选必二 第5章    | 树状图 + 杨辉三角                   | n/r 调整 + hover 详情        |
| 数列     | `sequences.js`               | 选必二 第3章    | 等差/等比数列 + 前 n 项和面积       | 类型切换 + 参数调整          |

### 6.2 物理模块 (Physics) — 15 个实验

| 实验           | 文件                             | 对应教材       | 功能                                | 交互方式                 |
| -------------- | -------------------------------- | -------------- | ----------------------------------- | ------------------------ |
| 力学模拟       | `physics.js`                   | 必修一 第3-4章 | 重力、碰撞、弹簧系统                | 参数调整 + 实时模拟      |
| 匀变速运动     | `kinematics.js`                | 必修一 第1-2章 | v-t/s-t 图联动，自由落体/竖直上抛   | 初始参数 + 播放控制      |
| 抛体运动       | `projectile.js`                | 必修二 第1章   | 斜抛轨迹分解（水平+竖直）           | 角度/速度滑块            |
| 圆周运动       | `circular-motion.js`           | 必修二 第2章   | 向心力/向心加速度                   | 半径/速度调整            |
| 万有引力       | `gravitation.js`               | 必修二 第3章   | 卫星轨道模拟 + 引力场               | 质量调整                 |
| 机械能守恒     | `energy-conservation.js`       | 必修二 第4章   | 过山车 PE/KE 能量条                 | 轨道编辑 + 播放          |
| 力的合成与分解 | `force-composition.js`         | 必修一 第3章   | 平行四边形定则/正交分解/斜面分析   | 箭头拖拽 + 模式切换 + 滑块 |
| 电磁场         | `electromagnetic.js`           | 必修三 第1-3章 | 电力线 + 等势线 + 电势热图          | 电荷拖拽 + 预设 + 探针   |
| 电路分析       | `circuit-analysis.js`          | 必修三 第2章   | 串并联电路 + 欧姆定律               | 组件拖拽 + 参数调整      |
| 电磁感应       | `electromagnetic-induction.js` | 选必二 第1章   | 法拉第电磁感应定律                  | 磁通量滑块               |
| 交变电流       | `alternating-current.js`       | 选必二 第2章   | 波形 + 相量图 + 变压器              | 模式切换 + 参数调整      |
| 波动演示       | `waves.js`                     | 选必一 第2-3章 | 叠加 + 驻波分析 + 多普勒效应        | 模式切换 + 频率/振幅调整 |
| 光学           | `optics.js`                    | 选必一 第4章   | 折射/反射/全反射/双缝干涉/色散/偏振 | 光源拖拽 + 参数调整      |
| 流体力学       | `fluid-dynamics.js`            | 课外拓展       | 势流叠加、圆柱绕流 + 伯努利方程     | 流场参数 + 模式切换      |
| 相对论         | `relativity.js`                | 课外拓展       | 时间膨胀/长度收缩                   | 速度滑块                 |

### 6.3 化学模块 (Chemistry) — 11 个实验

| 实验       | 文件                        | 对应教材     | 功能                                  | 交互方式              |
| ---------- | --------------------------- | ------------ | ------------------------------------- | --------------------- |
| 元素周期表 | `periodic-table.js`       | 必修一 第4章 | 118 元素交互式周期表                  | 点击元素 + 分类过滤   |
| 分子结构   | `molecular-structure.js`  | 选必二 第2章 | 8 种分子 3D 模型                      | 鼠标拖拽旋转 + 缩放   |
| 化学反应   | `chemical-reactions.js`   | 必修二 第1章 | 5 种反应 + 化学键断裂/形成 + 能量曲线 | 反应选择 + 速度控制   |
| 化学键     | `chemical-bond.js`        | 必修一 第4章 | 离子键/共价键/金属键                  | 键型切换 + 参数调整   |
| 离子反应   | `ionic-reaction.js`       | 必修一 第2章 | 离子方程式拆分 + 旁观离子             | 反应选择              |
| 氧化还原   | `redox.js`                | 必修一 第2章 | 电子转移 + 双线桥法 + 5 种反应        | 反应选择 + 速度/暂停  |
| 化学平衡   | `chemical-equilibrium.js` | 选必一 第2章 | 勒夏特列原理                          | 浓度/温度/压强调整    |
| 电化学     | `electrochemistry.js`     | 选必一 第4章 | 原电池/电解池电子流向                 | 类型切换 + 参数调整   |
| 有机化学   | `organic-chemistry.js`    | 必修二 第2章 | 3D 碳链 + 6 种分子 + 官能团高亮       | 拖拽旋转 + 分子选择   |
| 反应速率   | `reaction-rate.js`        | 选必一 第2章 | Maxwell-Boltzmann 分布 + 碰撞理论     | 温度/浓度/催化剂调整  |
| 溶液与电离 | `solution-ionization.js`  | 选必一 第3章 | 6 种物质 + pH 计算 + 离子计数         | 物质选择 + hover 详情 |

### 6.4 算法模块 (Algorithms) — 8 个实验

| 实验       | 文件                       | 功能                         | 交互方式               |
| ---------- | -------------------------- | ---------------------------- | ---------------------- |
| 排序算法   | `algorithms.js`          | 桶排序动画                   | 速度滑块 + 数据重置    |
| 搜索算法   | `search-algorithms.js`   | 二分查找 + BFS/DFS           | 图遍历起点选择         |
| 图算法     | `graph-algo.js`          | Dijkstra/Prim                | 图节点选择 + 参数调整  |
| 数据结构   | `data-structures.js`     | 栈/队列/树可视化             | 入栈/出栈/遍历操作     |
| 排序对比   | `sorting-compare.js`     | 冒泡/选择/插入/快排/归并对比 | 同时播放对比           |
| 递归可视化 | `recursion-vis.js`       | Fibonacci 递归树 + 汉诺塔    | 参数调整 + 单步/连续   |
| 动态规划   | `dynamic-programming.js` | 0/1 背包 DP 表填充           | 物品/容量配置 + 单步   |
| 字符串匹配 | `string-matching.js`     | KMP 算法逐步动画             | 文本/模式串输入 + 单步 |

### 6.5 生物模块 (Biology) — 13 个实验

| 实验     | 文件                        | 对应教材     | 功能                                  | 交互方式                  |
| -------- | --------------------------- | ------------ | ------------------------------------- | ------------------------- |
| 细胞结构 | `cell-structure.js`       | 必修一 第3章 | 动物/植物细胞对比                     | 器官 hover + 类型切换     |
| DNA 结构 | `dna-helix.js`            | 必修二 第3章 | 双螺旋 3D 旋转 + 复制                 | 旋转/复制/重置按钮        |
| 光合作用 | `photosynthesis.js`       | 必修一 第5章 | 光反应 + 暗反应(Calvin 循环)          | 光强度滑块 + 播放控制     |
| 遗传学   | `genetics.js`             | 必修二 第1章 | 单/双基因 Punnett + 种群遗传 + 系谱图 | 基因型选择 + 模式切换     |
| 有丝分裂 | `mitosis.js`              | 必修一 第6章 | 前/中/后/末期动画                     | 自动/手动步进             |
| 减数分裂 | `meiosis.js`              | 必修二 第2章 | 减数 Ⅰ/Ⅱ + 联会 + 交叉互换          | 阶段控制 + 速度调整       |
| 基因表达 | `gene-expression.js`      | 必修二 第4章 | 转录(DNA→mRNA) + 翻译(mRNA→蛋白质)  | 步骤控制                  |
| 细胞呼吸 | `cellular-respiration.js` | 必修一 第5章 | 糖酵解 + 柠檬酸循环 + 电子传递链      | 阶段切换 + 播放           |
| 物质运输 | `substance-transport.js`  | 必修一 第4章 | 自由扩散/协助扩散/主动运输/胞吞胞吐   | 模式切换 + 浓度调整       |
| 基因突变 | `gene-mutation.js`        | 必修二 第5章 | 碱基替换/插入/缺失 + 64 密码子表      | 突变类型选择 + hover 详情 |
| 神经调节 | `neural-regulation.js`    | 选必一 第2章 | 突触传递 + 动作电位                   | 模式切换 + 速度/暂停      |
| 免疫系统 | `immune-system.js`        | 选必一 第4章 | 固有免疫 + 适应性免疫(B/T 细胞)       | 速度/暂停 + hover 详情    |
| 生态系统 | `ecosystem.js`            | 选必二 第3章 | 能量流动 + 种群动态                   | 4 参数滑块 + hover 详情   |

---

## 7. 路由与页面转场系统

### 7.1 路由器 (`Router`)

**核心对象**：`shared/js/router.js`

```javascript
Router = {
    currentPage: 'home',
    isTransitioning: false,
    transitionOrigin: { x: 50, y: 50 },
  
    init()          // 初始化：绑定导航点击、监听 hashchange、创建图标
    navigateTo()    // 页面切换（带/不带动画）
    handleHash()    // 处理 URL hash 变化
    updateNav()     // 更新导航栏高亮 + aria-current
    onPageEnter()   // 页面进入回调（init 各实验模块）
}
```

### 7.2 转场动画流程

```
1. 当前页面淡出 (opacity→0, scale→0.97, blur→6px)  [0.18s]
2. 径向裁剪遮罩展开 (circle 0% → 150%)             [0.3s]
3. 切换 .active 类 + 滚动到顶部
4. 遮罩淡出 + 目标页面淡入 (opacity→1, y→0)        [0.3s]
5. Hero 区域子元素逐个入场 (stagger 50ms)
6. 触发 onPageEnter() 回调（初始化目标页面实验模块）
```

### 7.3 导航方式

- **URL Hash**：`#home`、`#mathematics`、`#physics` 等
- **导航栏点击**：顶部 nav 中每个 `.nav-item[data-page]`（支持 Tab 键盘导航）
- **首页卫星点击**：`selectModule('target')` → 自定义动画 → Router
- **实验卡片点击**：`openExperiment(id)` → 路由切换 + 模块展开（含防抖锁）
- **Skip Navigation**：`#skip-nav` 链接，键盘用户可跳过导航栏直达内容

---

## 8. 模块选择器系统

### 8.1 工作原理

每个学科页面分为两种视图：

- **画廊视图** (Gallery)：显示所有实验卡片（支持键盘 Enter/Space 激活）
- **实验视图** (Module)：显示单个实验的完整内容

```
┌─────────────────────────────┐
│ 学科 Hero 区域               │
├─────────────────────────────┤
│ ┌───┐ ┌───┐ ┌───┐ ┌───┐   │  ← 画廊视图（ModuleSelector）
│ │ 01│ │ 02│ │ 03│ │ 04│   │     role="button" tabindex="0"
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

| 组件       | 类/ID                        | 说明                       |
| ---------- | ---------------------------- | -------------------------- |
| 粒子网络   | `#particle-network`        | Canvas 粒子连线 + 鼠标吸引 |
| 三层星空   | `.star-layer-far/mid/near` | CSS 闪烁星星 + 鼠标视差    |
| 星云       | `.nebula-1/2/3`            | CSS 模糊渐变漂浮           |
| 流星       | `#shooting-stars`          | JS 随机生成 + CSS 动画     |
| HUD 框架   | `.hud-frame`               | 四角装饰 + 扫描线 + 数据流 |
| 主星       | `#main-star`               | 脉冲动画 + 表面纹理滚动    |
| 眼睛       | `.star-eyes`               | 瞳孔跟随鼠标 + 眨眼        |
| 打字机标语 | `#tagline-text`            | 循环 6 段文案              |
| 卫星轨道   | `#satellites-orbit`        | 5 颗行星独立 3D 轨道       |

### 9.2 卫星系统

5 个卫星分别对应 5 个学科，各有独立轨道参数（半径、倾角、周期、旋转方向）：

| 卫星        | 学科 | 颜色 | 轨道半径X/Y | 周期 |
| ----------- | ---- | ---- | ----------- | ---- |
| satellite-1 | 数学 | 蓝色 | 320/200     | 18s  |
| satellite-2 | 物理 | 紫色 | 420/260     | 25s  |
| satellite-3 | 化学 | 绿色 | 520/320     | 32s  |
| satellite-4 | 算法 | 橙色 | 450/280     | 22s  |
| satellite-5 | 生物 | 青色 | 380/240     | 28s  |

**点击卫星动画流程**：

1. 粒子喷发效果
2. 主星摇晃 + 淡出
3. 其他卫星缩小消失
4. 选中卫星放大至屏幕中心（4倍）
5. 背景渐变为学科主题色
6. 路由切换至对应学科页面
7. 重置所有状态（延迟 300ms）

---

## 10. 加载屏与启动优化

### 10.1 加载屏系统

为解决 60+ 个脚本首次加载时的白屏/卡顿问题，实现了**内联 CSS 加载屏**：

```html
<head>
  <style>
    /* 加载屏样式直接内联在 <head> 中 */
    #loading-screen { /* 全屏遮罩 + 旋转动画 */ }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }
  </style>
</head>
<body>
  <div id="loading-screen">
    <div class="loading-spinner"></div>
    <p class="loading-text">正在加载实验室…</p>
  </div>
  <!-- 页面内容 -->
</body>
```

**特点**：

- CSS 内联在 `<head>` 中，**首帧即可渲染**，无需等待任何外部资源
- 加载屏位于 DOM 顶层 (`z-index: 99999`)
- 旋转动画 + 脉冲文字提供视觉反馈

### 10.2 分阶段初始化 (initHome)

`main.js` 中的 `initHome()` 采用三阶段 `requestAnimationFrame` 分帧执行，避免长任务阻塞：

```javascript
function initHome() {
    // Phase 1: 粒子网络 + 卫星系统
    requestAnimationFrame(() => {
        initParticleNetwork();
        SatelliteSystem.init();
      
        // Phase 2: 星空 / 流星 / HUD
        requestAnimationFrame(() => {
            StarField.init();
            initShootingStars();
            initHUD();
          
            // Phase 3: 打字机 + 视差 + 交互绑定
            requestAnimationFrame(() => {
                initTypewriter();
                initParallax();
                // ... 其他初始化
            });
        });
    });
}
```

### 10.3 回访用户优化（localStorage + Service Worker）

v4.0.1 新增两层缓存优化，显著提升回访用户加载体验：

#### 第一层：localStorage 回访检测

`index.html` 内联脚本在解析早期读取 `englab-cache-meta`（JSON），判断是否为回访用户：

```javascript
// 存储结构
{ visitCount: number, lastVisit: ISO_string, hasSeenSplash: boolean }
```

- **回访用户标识**：`html.return-visit` CSS 类 + `window.__englabCache.returning = true`
- **加载屏加速**：回访用户使用更短的过渡动画（0.26s vs 0.5s）、更小的 loader
- **`main.js` 自适应**：回访用户的轮询间隔更短（60ms vs 90ms）、fallback 超时更短（900ms vs 1800ms）
- **`home.js` 自适应**：回访用户减少星星数量，延迟加载粒子网络/流星等非关键动画

#### 第二层：Service Worker 离线缓存

`sw.js` 实现完整的缓存策略：

- **安装阶段**：预缓存 APP_SHELL（index.html、核心 JS/CSS、首页资源）
- **激活阶段**：清理旧版本缓存，立即接管所有客户端
- **请求策略**：
  - 导航请求：network-first + cache fallback
  - 静态资源（.js/.css/.png/.jpg/.svg/.woff2）：stale-while-revalidate
- **缓存命名**：`englab-static-v{版本号}`，更新代码时需同步更新
- **注册时机**：`main.js` 中通过 `requestIdleCallback` 延迟注册，不阻塞首屏

#### 版本管理

更新代码后需同步更新以下位置的版本号：

1. `sw.js` 中的 `CACHE_NAME`（如 `englab-static-v20260416b`）
2. `index.html` 中 `<script>` 标签的 `?v=` 查询参数

### 10.4 加载屏消除

加载屏在以下条件满足后淡出移除：

1. `main.js` 执行完毕（`Router.init()` + `initHome()` 调度完成）
2. 通过 `setTimeout + rAF` 确保至少一帧渲染完成
3. 加载屏 `opacity` 过渡到 0，`transitionend` 后从 DOM 移除

---

## 11. 实验模块开发指南

### 11.1 新增实验步骤

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
                <canvas id="new-exp-canvas" role="img" aria-label="实验画布"></canvas>
            </div>
        </div>
    </div>
</div>
```

3. **编写 JS**：创建 `pages/学科/new-exp.js`

```javascript
const NewExp = {
    canvas: null, ctx: null, dpr: 1, raf: null,
    init() {
        this.canvas = document.getElementById('new-exp-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.dpr = window.devicePixelRatio || 1;
        // 使用 ResizeObserver 监听尺寸变化
        new ResizeObserver(() => this.resize()).observe(this.canvas.parentElement);
        this.resize();
        this._lastTime = performance.now();
        this.loop();
    },
    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width * this.dpr;
        this.canvas.height = rect.height * this.dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    },
    draw(dt) { /* 渲染逻辑，dt 为增量时间 */ },
    loop() {
        const now = performance.now();
        const dt = Math.min((now - this._lastTime) / 1000, 0.05);
        this._lastTime = now;
        this.draw(dt);
        this.raf = requestAnimationFrame(() => this.loop());
    },
    destroy() {
        if (this.raf) cancelAnimationFrame(this.raf);
    }
};
function initNewExp() { NewExp.init(); }
```

4. **在 index.html 中添加 `<script defer>`**：

```html
<script defer src="pages/学科/new-exp.js"></script>
```

5. **在 router.js 中注册 init/destroy 调用**
6. **测试**：启动服务器，访问对应学科页面 → 点击卡片进入实验

### 11.2 编码规范

- 每个实验封装为独立对象（如 `Calculus`、`ChemReaction`）
- 初始化函数命名：`initXxx()`，全局暴露
- Canvas 使用 `requestAnimationFrame` + `performance.now()` dt 驱动
- 响应式：`ResizeObserver` 监听容器尺寸（而非 window.resize）
- DPR 适配：`canvas.width = rect.width * dpr` + `ctx.setTransform(dpr, ...)`
- 交互：绑定 `mousemove`/`click`/`touchstart` 事件
- 教育面板：通过 `_injectXxxPanel()` 动态注入 DOM
- ARIA：Canvas 添加 `role="img"` + `aria-label`，按钮添加 `role`/`tabindex`/`aria-pressed`
- 清理：提供 `destroy()` 方法取消 rAF 和事件监听

### 11.3 样式规范

- 使用 `tokens.css` 中的 CSS 变量
- 学科主题色：`--accent-blue`(数学)、`--accent-purple`(物理)、`--accent-green`(化学)、`--accent-orange`(算法)、`--accent-teal`(生物)
- 间距：`--space-1` 到 `--space-8`
- 字体大小：`--text-xs` 到 `--text-3xl`
- 圆角：`--radius-sm`/`--radius-md`/`--radius-lg`

---

## 12. CSS 设计系统

### 12.1 加载顺序（严格遵守）

```
1. tokens.css      → 设计令牌（变量定义）
2. base.css        → 全局重置 + 页面系统 + focus-visible
3. typography.css   → 排版
4. navbar.css      → 导航栏
5. page-layout.css → Hero 区域
6. cards.css       → 卡片组件
7. module-selector.css → 模块选择器
8. [各页面 CSS]     → 页面特有样式
9. responsive.css  → 响应式（必须最后）
```

### 12.2 断点

```css
@media (max-width: 768px)  { /* 平板 */ }
@media (max-width: 480px)  { /* 手机 */ }
```

---

## 13. 构建与部署

### 13.1 开发环境

```bash
# 方式 1: Python 开发服务器（推荐）
python -m http.server 8080
# 访问 http://localhost:8080

# 方式 2: VS Code Live Server 插件
# 右键 index.html → Open with Live Server

# 方式 3: C++ 服务器（需要 CMake + C++ 编译器）
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 8080 -r ..
```

### 13.2 生产部署

项目为纯静态网站。推荐使用 C++ 服务器部署到云服务器。

#### Windows 云服务器一键部署

```powershell
# 使用项目提供的一键部署脚本
.\deploy.ps1
# 服务将在端口 910 启动
# 访问 http://服务器IP:910
```

详见 [DEPLOY.md](doc/DEPLOY.md) 获取完整部署指南，包括：

- 环境要求（Git、CMake、MSVC/MinGW）
- 一键部署 / 手动部署步骤
- 防火墙 & 安全组配置
- 运维命令（启动/停止/更新）
- 常见问题排查

#### 其他部署方式

- **GitHub Pages**：直接推送到 `gh-pages` 分支（不含 C++ 后端）
- **Vercel / Netlify**：连接仓库自动部署前端
- **Nginx**：指向项目根目录做反向代理

---

## 14. 维护指南

### 14.1 常见任务

| 任务         | 操作                                             |
| ------------ | ------------------------------------------------ |
| 修改实验内容 | 编辑对应 `pages/学科/xxx.js`                   |
| 新增实验     | 见 §11.1                                        |
| 修改导航     | 编辑 `index.html` 的 `<nav>` + `config.js` |
| 调整主题色   | 编辑 `tokens.css`                              |
| 新增学科     | 见 §14.2                                        |

### 14.2 新增学科

1. 在 `CONFIG.pages` 和 `CONFIG.experiments` 中添加学科配置
2. 在 `index.html` 中添加导航项 + 页面 `<section>`
3. 创建 `pages/新学科/` 目录
4. 在首页添加卫星（HTML + CSS + JS 轨道配置）
5. 在 `SatelliteSystem.orbits` 中添加轨道数据
6. 在 `home.css` 中添加卫星样式
7. 更新 `selectModule()` 中的颜色映射

### 14.3 调试技巧

- **路由问题**：在控制台输入 `Router.currentPage` 查看当前页面
- **模块选择器**：`ModuleSelector.activeModule` 查看当前展开的模块
- **Canvas 问题**：在实验对象中添加临时 `console.log` 或使用 Canvas Inspector 浏览器扩展
- **动画问题**：GSAP DevTools（`gsap.globalTimeline`）
- **加载问题**：检查 Network 面板中 defer 脚本加载顺序

---

## 15. 维护计划

### 15.1 已完成 ✅

- [X] 60 个实验全部实现并通过测试
- [X] 12 个模块 v2 重写（OPT-01~12），质量提升至 11-12/12
- [X] Bug 修复 BF-01~11（语法错误、DPR 适配、ARIA 无障碍、防抖锁等）
- [X] 首页加载优化（内联 CSS 加载屏 + defer 脚本 + 分阶段 initHome）
- [X] Windows 云服务器部署准备（deploy.ps1 + DEPLOY.md）
- [X] 生物模块语法修复（cell-structure.js / gene-mutation.js）
- [X] localStorage 回访用户检测 + 加载屏加速
- [X] Service Worker 离线缓存（stale-while-revalidate）

### 15.2 近期计划 (v4.1)

- [ ] 深化实验教育面板内容（补充人教版教材原文引用）
- [ ] 实验步骤引导系统（首次进入实验时显示操作提示）
- [x] 触控手势优化（移动端 pinch-zoom、swipe 返回）
- [ ] 键盘导航完善（Tab 切换实验控件、Esc 返回画廊）

### 15.3 中期计划 (v4.5)

- [ ] 学习进度系统（localStorage 记录已完成实验）
- [ ] 实验数据导出（截图/CSV 导出功能）
- [X] ~~PWA 离线支持（Service Worker + 缓存策略）~~ → v4.0.1 已完成基础实现
- [ ] Canvas OffscreenCanvas + Web Worker（复杂实验性能优化）

### 15.4 远期计划 (v5.0)

- [ ] 小测验模块（每个实验后附带概念检测题）
- [ ] 暗/亮主题切换（`prefers-color-scheme`）
- [ ] 实验分享功能（生成实验截图 + 配置链接）

---

## 16. 更新日志

### v4.0.3 — 2026-04-17

- 🎨 **基因表达按钮 UI 统一**：
  - `gene-expression.js`：自定义 `.genexp-btn` → 标准 `btn btn--primary/ghost btn--sm`，与全平台按钮风格一致
  - 模式切换按钮改为 primary/ghost 交替高亮
- 🪟 **周期表元素详情居中模态框**：
  - `chemistry.css`：底部滑出面板 → 屏幕居中模态，`scale` 缩放 + `opacity` 过渡动画
  - 新增 `.pt-detail-overlay` 暗色遮罩层（`rgba(0,0,0,0.45)`），点击关闭
  - `periodic-table.js`：overlay 点击关闭 + `showDetail()`/`closeDetail()` overlay 联动
  - `index.html`：移除 `.page` 内重复 `pt-detail` 面板（`will-change` 导致 `fixed` 定位失效）
- 📐 **实验侧边栏固定定位修复**：
  - `shared/css/base.css`：新增 `.sidebar-fixed` 样式体系，解决 `.page` 容器 `will-change` 创建新包含块导致 `position: fixed` 失效
  - `shared/js/router.js`：侧边栏动态挂载到 `document.body`，确保滚动时真正固定
- 🐛 **生物实验 Canvas 修复与优化**：
  - `genetics.js`：遗传学实验大幅重构（+164 行），修复 Punnett 方格绘制与数据逻辑
  - `dna-helix.js`：Canvas 下坠 bug 修复、字体大小进一步调优
  - `photosynthesis.js`：光合作用实验 Canvas 布局重新排版
  - `cellular-respiration.js`：细胞呼吸实验 Canvas 布局修复
  - 多个生物实验（cell-structure / ecosystem / meiosis / substance-transport）字体与布局微调
  - `biology.css`：侧边栏固定定位样式补充
- 🔤 **全实验字体进一步微调**：
  - 物理 14 个、化学 11 个、算法 7 个、数学 4 个实验文件字体与布局细节修正
  - `shared/js/module-selector.js`：模块选择器小修
- 🖼️ **UI 资源文件**：新增 `UI/` 目录（favicon、apple-touch-icon 等站点图标）

### v4.0.2 — 2025-07

- 🐛 **关键 Bug 修复 — FuncProps/ExpLog 浏览器卡死**：
  - `function-properties.js` / `exp-log.js`：当切换实验时 ResizeObserver 在 section 隐藏后触发 → `W=0` → `_plotFunc()` 中 `step=0` → 无限 `for` 循环冻结浏览器
  - 修复：`resize()` 添加 `W<=0 || H<=0` 提前返回守卫；`_plotFunc()` 添加 `W<=0` 和 `step<=0` 守卫
- 🔤 **数学实验 Canvas 字体放大 1.5-2×**：
  - 15 个数学实验文件全部更新字体大小（8→14, 9→15, 10→16, 11→17, 12→18, 13→20, 14→22）
  - 动态计算字体同步调整（如 `Math.max(9, W*0.009)` → `Math.max(15, W*0.015)`）
- 🔤 **生物实验 Canvas 字体标准化重构**：
  - 13 个生物实验文件全部消除硬编码字体族引用（`"Noto Sans SC"` → `var(--font-sans)`，`"JetBrains Mono"` → `var(--font-mono)`）
  - 字体大小统一放大 1.5-1.7×，与数学实验保持一致
  - 动态 `fs` 计算（neural-regulation、gene-mutation）同步调整
- 🔤 **全项目 Canvas 字体标准化**：
  - 消除物理、化学、算法所有实验 JS 文件中的硬编码字体族引用
  - 统一使用 CSS 变量 `var(--font-sans, sans-serif)` 和 `var(--font-mono, monospace)`
- 🐛 **ionic-reaction.js `_resize()` 安全守卫**：添加 `w<=0 || h<=0` 提前返回，防止 section 隐藏时 ResizeObserver 触发异常
- 📄 **新增 `doc/UI_TEMPLATES.md`**：各学科实验 UI 基准模板文档，包含 Canvas 字体规范、DPR 适配模板、面板注入模式、resize 安全守卫等标准化参考

### v4.0.1 — 2026-04-17

- 🐛 **生物模块语法修复**：
  - `cell-structure.js`：修复 `_detGeneric()` 与 `_injectInfoPanel()` 方法间缺少逗号导致的 SyntaxError
  - `gene-mutation.js`：修复 `updInfo()` 中模板字面量闭合引号不匹配（反引号误写为单引号）导致的 SyntaxError
  - 补充 `window.CellStructure` / `window.initCellStructure` / `window.initGeneMutation` 全局导出
  - 修正 `module-selector.js` 中生物模块 init 函数映射
- ⚡ **首页加载优化 — 回访用户加速**：
  - 新增 `index.html` 内联脚本：localStorage `englab-cache-meta` 检测回访用户
  - 回访用户加载屏过渡时间从 0.5s 降至 0.26s，loader 缩小
  - `main.js` 回访用户轮询间隔缩短（60ms vs 90ms），fallback 超时缩短（900ms vs 1800ms）
  - `home.js` 回访用户减少星星数量，延迟加载粒子网络/流星等非关键动画
  - 新增重复绑定防护（parallax / eye-tracking / shooting-stars）
- 🌐 **Service Worker 离线缓存**（`sw.js` 新增文件）：
  - 安装阶段预缓存 APP_SHELL（index.html、核心 JS/CSS、首页资源）
  - 导航请求 network-first + cache fallback
  - 静态资源 stale-while-revalidate（.js/.css/.png/.jpg/.svg/.woff2）
  - `main.js` 通过 `requestIdleCallback` 延迟注册 SW
  - 缓存版本 `englab-static-v20260416b`
- 📁 **文档整理**：所有文档（除 README.md）迁移至 `doc/` 目录

### v4.0.0 — 2026-04-15

- 🚀 **大版本更新**：知识点全面填充，60 个实验全部完成
- ✅ 12 个模块 v2 深度重写（OPT-01~12），质量全线提升：
  - **OPT-01** redox.js：ResizeObserver + dt 驱动 + 5 反应 + 3D 原子 + 电子trail + 教育面板
  - **OPT-02** sequences.js：lerp 过渡 + 面积填充 + 教育面板 + 配色区分
  - **OPT-03** ecosystem.js：dt 驱动 + 4 参数滑块 + hover tooltip + 分解者回路
  - **OPT-04** organic-chemistry.js：3D 拖拽旋转 + 透视投影 + 官能团高亮 + 6 分子 + 教育面板
  - **OPT-05** immune-system.js：8 种病原体 + 4 固有免疫细胞 + 适应性免疫(B/Th/Tc) + 细胞因子信号 + Y 形抗体
  - **OPT-06** neural-regulation.js：突触模式(Ca²⁺通道 + 小泡胞吐 + 6 步状态) + 动作电位(Na⁺/K⁺ 通道 + 6 相标注)
  - **OPT-07** solution-ionization.js：6 种物质 + Ka/Kb 精确 pH + 水分子背景 + 离子计数 + 9 种离子详解
  - **OPT-08** permutation-combination.js：动画展开树 + 缓存布局扁平数组 + 杨辉行高亮 + 教育面板
  - **OPT-09** alternating-current.js：3 模式(波形/相量图/变压器) + RMS + φ 相移 + 铁芯叠片 + 功率守恒
  - **OPT-10** solid-geometry.js：5 形体 + 法线光照 + 背面剔除 + 截面多边形 + 欧拉公式
  - **OPT-11** reaction-rate.js：Maxwell-Boltzmann 分布曲线 + 碰撞闪光 + Arrhenius 公式 + 催化剂降 Ea
  - **OPT-12** gene-mutation.js：完整 64 密码子表 + 模板链/编码链 + 氢键 + 突变前后对比 + 移码突变
- ✅ Bug 修复（BF-06~11）：
  - 4 个生物模块 `<script>` 标签缺失修复
  - 3 个物理实验 CONFIG 条目补充
  - 圆锥曲线错字修正
  - `openExperiment` 防抖锁
  - 10 个 Canvas 模块 DPR 高分屏适配
  - ARIA 无障碍属性全面添加（skip-nav、地标、键盘交互、focus-visible）
- ✅ 首页加载优化：
  - 内联 CSS 加载屏（首帧可见）
  - 60 个实验脚本全部改为 `defer` 加载
  - `main.js` 移至 defer 脚本之前同步执行
  - `initHome()` 三阶段 rAF 分帧初始化
- ✅ Windows 云服务器部署：
  - `deploy.ps1` 一键部署脚本（端口 910）
  - `DEPLOY.md` 完整部署文档

### v3.0.2 — 2026-04-14

- ✅ 一致性审计修复（BF-06~10）
- ✅ DPR 高分屏适配（10 个模块）
- ✅ ARIA 无障碍属性添加（BF-11）

### v3.0.1 — 2026-04-14

- ✅ 全面功能测试 + Bug 修复（BF-01~05）
- ✅ 57 个 `<script>` 引用验证
- ✅ 55 个 config 条目与 HTML `data-module` 一致性验证
- ✅ 58 个 router init/destroy 调用匹配验证

### v3.0 — 2026-04-14

- 🎉 **全部 P0/P1/P2 实验完成**，达到 60 个实验
- 新增数学实验 9 个：集合运算、三角函数、数列、概率统计、向量运算、不等式、圆锥曲线、立体几何、排列组合
- 新增物理实验 10 个：匀变速运动、抛体运动、万有引力、圆周运动、机械能守恒、电路分析、电磁感应、交变电流、光学、流体力学
- 新增化学实验 8 个：离子反应、氧化还原、化学平衡、电化学、化学键、有机化学、反应速率、溶液与电离
- 新增算法实验 4 个：排序对比、递归可视化、动态规划、字符串匹配
- 新增生物实验 9 个：有丝分裂、减数分裂、基因表达、细胞呼吸、物质运输、基因突变、神经调节、免疫系统、生态系统

### v2.7 — 2026-04-13

- ✅ 重写：波动演示模块（waves.js）— 三模式：叠加 + 驻波分析 + 多普勒效应
- ✅ 重写：电磁场可视化（electromagnetic.js）— 三模式：电力线 + 等势线 + 电势热图 + 测量探针
- ✅ 重写：复数可视化（complex-numbers.js）— 三模式：运算 + 单位根 + 域着色
- ✅ 重写：微积分模块（calculus.js）— 三模式：导数/切线 + 定积分 Riemann 和 + Taylor 级数
- ✅ 重写：几何变换（geometry.js）— 双模式：仿射变换 + 三角形几何（欧拉线）
- ✅ 重写：遗传学（genetics.js）— 双基因模式 + Punnett 方格 + 表现型统计
- ✅ 重写：光合作用（photosynthesis.js）— 光反应/暗反应分区 + Calvin 循环

### v2.2 — 2026-04-13

- ✅ 新增：首页生物卫星跳转（第 5 轨道）
- ✅ 重写：化学反应模块 — 化学键可视化 + 5 阶段动画 + 能量曲线
- 🔒 安全：mathematics.js / calculus.js 表达式编译加固
- 🔧 修复：router.js 导航竞态条件

### v2.1 — 优化网页交互逻辑

- 新增生物模块（细胞、DNA、光合作用、遗传学）
- 优化模块选择器

### v2.0 — 项目重构

- SPA 架构 + hash 路由
- GSAP 径向裁剪转场
- 模块化实验系统
