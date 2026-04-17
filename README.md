# 工科实验室 - 可视化学习平台

一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，提供数学、物理、化学、算法、生物五大学科共 **60 个可视化实验**，全面覆盖人教版（2019 新课标）高中必修及选择性必修核心知识点。  
内置 C++ 后端服务器，支持静态文件托管和 REST API。

## 📁 项目结构

```
工科实验室/
├── index.html              # 单页入口（含所有页面结构）
├── sw.js                   # Service Worker（离线缓存 + stale-while-revalidate）
├── deploy.ps1              # Windows 一键部署脚本
├── doc/                    # 项目文档
│   ├── DEVELOPER_GUIDE.md  # 完整开发者文档
│   ├── UPDATE_PLAN.md      # 后续更新计划
│   └── DEPLOY.md           # 服务器部署文档
├── shared/                 # 全局共享资源
│   ├── css/                # 设计系统（tokens → base → components → responsive）
│   └── js/                 # 核心框架（config / router / module-selector / main）
├── pages/                  # 按学科分类的实验模块
│   ├── home/               # 首页（星空 + HUD + 卫星系统 + 加载屏）
│   ├── mathematics/        # 数学（13 个实验）
│   ├── physics/            # 物理（14 个实验）
│   ├── chemistry/          # 化学（11 个实验）
│   ├── algorithms/         # 算法（8 个实验）
│   └── biology/            # 生物（13 个实验）
└── server/                 # C++ httplib 后端服务器
```

## 🚀 快速开始

### 方式一：Python 开发服务器（推荐开发用）

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```

### 方式二：C++ 服务器（生产部署）

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 910 -r ..
# 访问 http://localhost:910
```

### 方式三：Windows 云服务器一键部署

```powershell
.\deploy.ps1
# 详见 doc/DEPLOY.md
```

## ✨ 功能特性

### 首页
- 科幻风格星空主题，5 颗 3D 卫星轨道对应 5 个学科
- 粒子连线网络、HUD 数据框架、Glitch 标题效果
- 内联 CSS 加载屏，首帧即可渲染
- 循环打字机动画、鼠标追踪眼球

### 学科页面
- 模块选择器画廊（点击卡片进入具体实验）
- 每个学科独有的 Hero 区域和配色
- "更多实验" 卡片直接跳转至对应模块
- ARIA 无障碍支持 + 键盘导航

### 60 个交互实验

| 数学 (13) | 物理 (14) | 化学 (11) | 算法 (8) | 生物 (13) |
|-----------|-----------|-----------|----------|-----------|
| 函数图像 | 力学模拟 | 元素周期表 | 桶排序 | 细胞结构 |
| 微积分 | 匀变速运动 | 分子结构 | 搜索算法 | DNA 双螺旋 |
| 几何变换 | 抛体运动 | 化学反应 | 图算法 | 光合作用 |
| 复数运算 | 圆周运动 | 化学键 | 数据结构 | 遗传学 |
| 三角函数 | 万有引力 | 离子反应 | 排序对比 | 有丝分裂 |
| 集合运算 | 机械能守恒 | 氧化还原 | 递归可视化 | 减数分裂 |
| 概率统计 | 电磁场 | 化学平衡 | 动态规划 | 基因表达 |
| 向量运算 | 电路分析 | 电化学 | 字符串匹配 | 细胞呼吸 |
| 不等式 | 电磁感应 | 有机化学 | | 物质运输 |
| 圆锥曲线 | 交变电流 | 反应速率 | | 基因突变 |
| 立体几何 | 波动演示 | 溶液与电离 | | 神经调节 |
| 排列组合 | 光学 | | | 免疫系统 |
| 数列 | 流体力学 | | | 生态系统 |
| | 相对论 | | | |

### 技术亮点
- GSAP 驱动的径向裁剪转场动画
- Canvas 2D 实时绘图引擎 + DPR 高分屏适配
- 60 个实验 defer 加载 + 分阶段初始化，首屏无阻塞
- Service Worker 离线缓存 + localStorage 回访用户加速
- 纯 CSS 星球渲染（渐变 + 动画）
- C++ httplib 高性能静态服务器
- ARIA 无障碍属性 + focus-visible 样式

## 🔧 技术栈

- **HTML5 / CSS3 / ES6+** — 前端核心
- **GSAP 3.12.7** + ScrollTrigger — 动画引擎
- **Lucide Icons 0.454** — 图标库
- **Canvas 2D API** — 可视化渲染（ResizeObserver + DPR 适配）
- **cpp-httplib 0.18.3** — C++ HTTP 服务器
- **CMake 3.14+** — C++ 构建系统

## 📝 更新日志

### v4.0.2 — 2026-04-17
- 🐛 修复 FuncProps/ExpLog 浏览器卡死（ResizeObserver 隐藏时 W=0 → 无限循环）
- 🔤 数学实验 Canvas 字体放大 1.5-2×（15 个文件）
- 🔤 生物实验 Canvas 字体标准化重构（13 个文件）
- 🔤 全项目 Canvas 字体统一使用 CSS 变量（`--font-sans` / `--font-mono`）
- 📄 新增 `doc/UI_TEMPLATES.md` 各学科 UI 基准模板文档

### v4.0.1 — 2026-04-17
- 🐛 修复生物模块语法错误（cell-structure.js / gene-mutation.js）
- ⚡ 回访用户加载加速（localStorage 检测 + 加载屏缩短）
- 🌐 新增 Service Worker 离线缓存（stale-while-revalidate）
- 📁 文档迁移至 `doc/` 目录

### v4.0.0 — 2026-04-15
- 🚀 60 个实验全部完成，覆盖人教版高中五大学科核心知识点
- ✅ 12 个模块深度 v2 重写，质量提升至 11-12/12
- ✅ Bug 修复 BF-01~11（DPR 适配、ARIA 无障碍、防抖锁等）
- ✅ 首页加载优化（内联 CSS 加载屏 + defer 脚本 + 分阶段初始化）
- ✅ Windows 云服务器部署（deploy.ps1 + doc/DEPLOY.md，端口 910）

### v3.0 — 2026-04-14
- 全部 P0/P1/P2 实验完成
- 全面功能测试 + Bug 修复

### v2.7 — 2026-04-13
- 6 个核心模块深度重写（波动、电磁、复数、微积分、几何、遗传、光合）

### v2.1 — 优化网页交互逻辑
- 新增生物学模块
- 优化字体加载与模块选择器

## 📄 许可证

本项目仅供学习使用。
