# 星序 Astra — AI 协作指南

## 项目简介

「**星序 Astra**」是一个**纯前端交互式多学科可视化学习平台**，面向中国高中生与自学者，由两大并列子站构成：

- 🌌 **工科实验室星系**（主站，本仓库根目录）：数学、物理、化学、算法、生物五大学科，共 **63 个 Canvas 2D 可视化实验**，对齐人教版 2019 新课标
- 💻 **代码空间星系**（子站 `codevis/`）：多语言代码执行追踪播放器（JS / Python / C / C++），含 Runtime 抽象层 + 三沙箱后端（JS-Interpreter / Skulpt / JSCPP）

后续将延伸更多"星系"（智能 / 历史 / 宇宙等方向），新增星系开发流程详见 [doc/01-开发者手册.md §17](../doc/01-开发者手册.md)。

- **架构**：Vanilla JS 双 SPA（主站 + codevis 子站独立 `index.html`），hash 路由，无框架依赖
- **渲染**：所有实验使用 Canvas 2D API + requestAnimationFrame + performance.now() dt 驱动
- **动画**：GSAP 3.12.7 驱动页面转场（径向裁剪遮罩）
- **顶层导航**：`pages/planets/` 多星系大屏（双层状态机 galaxies ↔ galaxy）
- **命名空间隔离**：codevis 子站 CSS 类一律 `cv-` 前缀，JS 全局一律 `Cv*` 前缀
- **服务器**：C++ httplib 静态文件服务器（生产端口 910）；开发用 `python -m http.server 8080`
- **当前版本**：v6.0.0（项目层级调整 + 正式更名为「星序 Astra」）

## 快速了解项目必读

| 文档/文件 | 内容 | 何时阅读 |
|-----------|------|----------|
| `doc/01-开发者手册.md` | **完整开发者文档**（~940 行，v4.0.4 基线，待 v5.1.x 修订）：架构、目录结构、63 个实验清单、JS 加载顺序、路由/模块选择器/首页系统、加载屏优化、开发指南、CSS 设计系统、部署、更新日志 | 首次接触项目时通读 |
| `doc/02-更新规划.md` | 后续更新计划：已完成实验汇总、人教版课标覆盖度分析、Phase 2 待开发实验列表、架构优化路线图、Bug 审查清单 | 规划新功能/新实验时 |
| `doc/03-发布历史.md` | 已完成沉淀（Historical Snapshot）：大版本里程碑、阶段性实验汇总、历史 Bug 修复记录 | 回溯历史决策时 |
| `doc/04-部署指南.md` + `deploy.ps1` | Windows 云服务器一键部署文档与脚本 | 部署相关工作时 |
| `doc/05-UI规范模板.md` | 各学科 UI 基准模板、Canvas 字体规范、面板注入模式 | 新增/重构实验 UI 时 |
| `doc/99-历史审视报告归档.md` | v4.0.5 ~ v4.2.x 一次性只读审视报告归档（UI / 移动端 / 生物 Canvas 文本 / 生物文字排版） | 排查历史问题或参考评估方法时 |
| `README.md` | 项目简介 + 快速开始 + 63 个实验一览表 | 快速概览 |

## 关键文件速查

```
index.html                      → 唯一 HTML 入口，所有页面 <section> + 全部 <script> 引用
shared/js/config.js             → 全局配置（5 学科元数据 + 63 个实验条目）
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
3. **脚本加载**：CDN 库 + 框架脚本（同步）→ home.js（同步）→ main.js（同步）→ 63 个实验模块（全部 `defer`）
4. **教育面板**：多数实验通过 `_injectXxxPanel()` 方法动态注入 DOM（不需要预设 HTML 元素）
5. **无障碍**：Canvas 需 `role="img"` + `aria-label`；交互按钮需 `role`/`tabindex`/键盘事件；导航栏支持 `aria-current`
6. **新增实验流程**：`config.js` 注册 → `index.html` 添加 `data-module` section → 编写 JS 模块 → `index.html` 添加 `<script defer>` → `router.js` 注册 init/destroy

## 学科与实验分布

- **数学** (`pages/mathematics/`)：13 个实验 — 函数、微积分、几何、复数、三角、集合、概率、向量、不等式、圆锥曲线、立体几何、排列组合、数列
- **物理** (`pages/physics/`)：17 个实验 — 力学、运动学、抛体、圆周、万有引力、能量、电磁、电路、电磁感应、交变电流、波动、光学、流体、相对论、力的合成与分解、动量守恒、带电粒子运动
- **化学** (`pages/chemistry/`)：11 个实验 — 周期表、分子结构、化学反应、化学键、离子反应、氧化还原、化学平衡、电化学、有机化学、反应速率、溶液电离
- **算法** (`pages/algorithms/`)：8 个实验 — 排序、搜索、图算法、数据结构、排序对比、递归、DP、KMP
- **生物** (`pages/biology/`)：13 个实验 — 细胞、DNA、光合、遗传、有丝/减数分裂、基因表达、呼吸、物质运输、突变、神经、免疫、生态

## Git 版本管理规则（自 V4.3.0 起）

- main 分支只接受**每个 0.1 大版本（如 V4.3 / V4.4 / V5.0）的合并提交**；微版本（v4.x.y, x 不变）必须在专属分支进行，不直接打到 main
- 当前迭代分支命名：`feature/v{大版本}` 例如 `feature/v4.3`
- 历史细节分支命名：`legacy/v{大版本}-detail` 例如 `legacy/v4.2-detail` 保留被合并的细碎提交
- 大版本 commit 信息：`V{大版本}.0（汇总 v{起} ~ v{终}，N 个细节提交；详细历史保留在 legacy/v{大版本}-detail 分支）`
- 仅给大版本（V4.3.0 / V4.4.0 ...）打 annotated tag 并推送到远程

## 注意事项

- `index.html` 是 **2400+ 行的单文件 SPA**，所有学科页面内容都在其中，修改时注意定位到正确的 `<section>`
- 实验 JS 中大量 DOM 元素由 JS 动态创建（`innerHTML` / `createElement`），不要在 HTML 中预设这些元素
- `router.js` 中的 `destroy` 调用对象名必须与实验 JS 导出的全局对象名严格匹配
- CSS 加载顺序严格：`tokens → base → typography → navbar → page-layout → cards → module-selector → [页面CSS] → responsive`
