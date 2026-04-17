# 工科实验室 — AI 协作指南

## 项目简介

「工科实验室」是一个**纯前端交互式科学学习平台**，面向中国高中生，涵盖数学、物理、化学、算法、生物五大学科，共 **60 个 Canvas 2D 可视化实验**，全面对齐人教版（2019 新课标）高中必修及选择性必修核心知识点。

- **架构**：Vanilla JS 单页应用（SPA），hash 路由，无框架依赖
- **渲染**：所有实验使用 Canvas 2D API + requestAnimationFrame + performance.now() dt 驱动
- **动画**：GSAP 3.12.7 驱动页面转场（径向裁剪遮罩）
- **服务器**：C++ httplib 静态文件服务器（生产端口 910）；开发用 `python -m http.server 8080`
- **当前版本**：v4.0.2

## 快速了解项目必读

| 文档/文件 | 内容 | 何时阅读 |
|-----------|------|----------|
| `doc/DEVELOPER_GUIDE.md` | **完整开发者文档**（~940 行）：架构、目录结构、60 个实验清单、JS 加载顺序、路由/模块选择器/首页系统、加载屏优化、开发指南、CSS 设计系统、部署、更新日志 | 首次接触项目时通读 |
| `doc/UPDATE_PLAN.md` | 后续更新计划：已完成实验汇总、人教版课标覆盖度分析、Phase 2 待开发实验列表、架构优化路线图、Bug 审查清单 | 规划新功能/新实验时 |
| `README.md` | 项目简介 + 快速开始 + 60 个实验一览表 | 快速概览 |
| `doc/DEPLOY.md` + `deploy.ps1` | Windows 云服务器一键部署文档与脚本 | 部署相关工作时 |

## 关键文件速查

```
index.html                      → 唯一 HTML 入口，所有页面 <section> + 全部 <script> 引用
shared/js/config.js             → 全局配置（5 学科元数据 + 60 个实验条目）
shared/js/router.js             → hash 路由 + GSAP 页面转场 + onPageEnter 实验初始化
shared/js/module-selector.js    → 画廊↔实验视图切换
shared/js/main.js               → 应用启动入口（lucide.createIcons → Router.init → initHome）
sw.js                            → Service Worker（离线缓存 + stale-while-revalidate）
pages/home/home.js              → 首页逻辑（粒子网络、卫星轨道、打字机、分阶段初始化）
pages/{学科}/{实验}.js           → 各实验模块（独立对象，init/destroy 生命周期）
shared/css/tokens.css           → CSS 设计令牌（颜色/间距/字体变量）
```

## 代码约定

1. **实验模块模式**：每个实验封装为全局对象（如 `Calculus`、`RedoxReaction`），暴露 `initXxx()` 全局函数，由 `router.js` 的 `onPageEnter()` 按需调用
2. **Canvas 标准**：DPR 适配（`canvas.width = rect.width * dpr`）+ `ResizeObserver` 监听容器 + `ctx.setTransform(dpr, 0, 0, dpr, 0, 0)`
3. **脚本加载**：CDN 库 + 框架脚本（同步）→ home.js（同步）→ main.js（同步）→ 60 个实验模块（全部 `defer`）
4. **教育面板**：多数实验通过 `_injectXxxPanel()` 方法动态注入 DOM（不需要预设 HTML 元素）
5. **无障碍**：Canvas 需 `role="img"` + `aria-label`；交互按钮需 `role`/`tabindex`/键盘事件；导航栏支持 `aria-current`
6. **新增实验流程**：`config.js` 注册 → `index.html` 添加 `data-module` section → 编写 JS 模块 → `index.html` 添加 `<script defer>` → `router.js` 注册 init/destroy

## 学科与实验分布

- **数学** (`pages/mathematics/`)：13 个实验 — 函数、微积分、几何、复数、三角、集合、概率、向量、不等式、圆锥曲线、立体几何、排列组合、数列
- **物理** (`pages/physics/`)：14 个实验 — 力学、运动学、抛体、圆周、万有引力、能量、电磁、电路、电磁感应、交变电流、波动、光学、流体、相对论
- **化学** (`pages/chemistry/`)：11 个实验 — 周期表、分子结构、化学反应、化学键、离子反应、氧化还原、化学平衡、电化学、有机化学、反应速率、溶液电离
- **算法** (`pages/algorithms/`)：8 个实验 — 排序、搜索、图算法、数据结构、排序对比、递归、DP、KMP
- **生物** (`pages/biology/`)：13 个实验 — 细胞、DNA、光合、遗传、有丝/减数分裂、基因表达、呼吸、物质运输、突变、神经、免疫、生态

## 注意事项

- `index.html` 是 **2400+ 行的单文件 SPA**，所有学科页面内容都在其中，修改时注意定位到正确的 `<section>`
- 实验 JS 中大量 DOM 元素由 JS 动态创建（`innerHTML` / `createElement`），不要在 HTML 中预设这些元素
- `router.js` 中的 `destroy` 调用对象名必须与实验 JS 导出的全局对象名严格匹配
- CSS 加载顺序严格：`tokens → base → typography → navbar → page-layout → cards → module-selector → [页面CSS] → responsive`
