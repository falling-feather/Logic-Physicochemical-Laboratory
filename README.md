# 工科实验室 - 可视化学习平台

一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，提供数学、物理、化学、算法、生物五大学科共 20 个可视化实验。  
内置 C++ 后端服务器，支持静态文件托管和 REST API。

## 📁 项目结构

```
工科实验室/
├── index.html              # 单页入口（含所有页面结构）
├── shared/                 # 全局共享资源
│   ├── css/
│   │   ├── tokens.css      # 设计令牌（颜色、间距、字体等）
│   │   ├── base.css        # 基础样式、页面系统
│   │   ├── typography.css  # 排版
│   │   ├── navbar.css      # 导航栏
│   │   ├── page-layout.css # 页面 Hero 区域布局
│   │   ├── cards.css       # 实验卡片组件
│   │   ├── module-selector.css # 模块选择器画廊
│   │   └── responsive.css  # 响应式断点
│   └── js/
│       ├── config.js       # 实验配置（CONFIG.experiments）
│       ├── module-selector.js # 模块选择器逻辑
│       ├── router.js       # 路由 + GSAP 页面转场
│       ├── scroll-animations.js
│       ├── cards.js        # 实验推荐卡片（更多实验）
│       ├── common.js       # 公共工具函数
│       └── main.js         # 应用启动入口（initApp）
├── pages/                  # 按页面分类的资源
│   ├── home/               # 首页（星空 + HUD + 卫星系统）
│   ├── mathematics/        # 数学（函数图像、微积分、几何变换、复数运算）
│   ├── physics/            # 物理（力学、电磁场、波动、相对论）
│   ├── chemistry/          # 化学（元素周期表、分子结构、化学反应）
│   ├── algorithms/         # 算法（排序、搜索、图算法、数据结构）
│   └── biology/            # 生物（细胞结构、DNA螺旋、光合作用、遗传学）
├── server/                 # C++ 后端服务器
│   ├── CMakeLists.txt      # CMake 构建配置
│   ├── main.cpp            # httplib 服务器（静态托管 + API）
│   └── README.md           # 服务器文档
└── README.md
```

## 🚀 快速开始

### 方式一：C++ 服务器（推荐）

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 9527 -r ..
# 访问 http://localhost:9527
```

### 方式二：Python 临时服务器

```bash
python -m http.server 9527
# 访问 http://localhost:9527
```

## ✨ 功能特性

### 首页
- 科幻风格星空主题，3D 卫星轨道系统
- 粒子连线网络、HUD 数据框架、Glitch 标题效果
- 循环打字机动画、鼠标追踪眼球

### 学科页面
- 模块选择器画廊（点击卡片进入具体实验）
- 每个学科独有的 Hero 区域和配色
- "更多实验" 卡片直接跳转至对应模块

### 20 个交互实验
| 数学 | 物理 | 化学 | 算法 | 生物 |
|------|------|------|------|------|
| 算筹演示 | 力学模拟 | 交互式周期表 | 桶排序动画 | 细胞结构 |
| 函数图像 | 电磁场可视化 | 3D 分子结构 | 二分查找 | DNA 双螺旋 |
| 微积分可视化 | 波动演示 | 化学反应模拟 | 图遍历 (BFS/DFS) | 光合作用 |
| 几何变换 | 狭义相对论 | — | 图算法 (Dijkstra/Prim) | 遗传学 |
| 复数运算 | — | — | 数据结构可视化 | — |

### 技术亮点
- GSAP 驱动的径向裁剪转场动画
- Canvas 2D 实时绘图引擎
- 纯 CSS 星球渲染（渐变 + 动画）
- C++ httplib 高性能静态服务器
- 非阻塞字体加载 + 关键资源预加载优化

## 🔧 技术栈

- **HTML5 / CSS3 / ES6+** — 前端核心
- **GSAP 3.12** + ScrollTrigger — 动画引擎
- **Lucide Icons 0.454** — 图标库
- **cpp-httplib 0.18.3** — C++ HTTP 服务器
- **CMake 3.14+** — C++ 构建系统

## 📝 更新日志

### v2.1 — 优化网页交互逻辑
- **修复** "更多实验" 卡片点击后正确跳转至对应实验模块（不再显示"正在开发中"）
- **修复** 算法页面 "更多算法" 区域位置错误（从中间移至页面底部）
- **新增** 生物学模块（细胞结构、DNA 螺旋、光合作用、遗传学 Punnett 方格）
- **优化** 字体非阻塞加载，GSAP preload，iframe lazy loading
- **修复** `openExperiment()` 不再使用隐式 `event` 全局变量

## 📄 许可证

本项目仅供学习使用。
