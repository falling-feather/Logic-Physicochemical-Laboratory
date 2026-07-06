# 星序 Astra · 多学科可视化学习平台

「星序 Astra」是一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，当前由三个星系构成：

- 🌌 **工科试验室星系**（主站）：数学、物理、化学、算法、生物五大学科共 **88 个可视化实验**，覆盖高中核心知识与扩展演示
- 💻 **代码空间星系**（[子站 `/codevis/`](codevis/README.md)）：多语言代码执行追踪播放器（JavaScript / Python / C / C++），含 Runtime 抽象层与三沙箱后端
- ✨ **未来星系**（主站内 `frontier` 星系）：地球与宇宙、工程、数据科学、信息技术、材料、人文可视化六个跨学科探索方向

星序总览页负责承载一级星系入口；进入某个星系后，才显示该星系自己的二级学科或知识目录。内置 C++ httplib 后端服务器，支持静态文件托管。

> **当前状态**: v6.5（2026-07-03 起）— `houduan` 分支已接入 Python 后端骨架、健康检查、部署预检、部署 smoke 门禁、API no-store 缓存边界、工科试验室内容协议持久化样例、内容 seed 启动初始化与读取无副作用边界、正式内容初始化入口、ContentDraft 草稿与脚本审核、脚本静态分析风险等级、脚本 sandbox 契约、公开 render 脚本 manifest 脱敏、草稿编辑、草稿提交/退回/撤回工作流、active 草稿数据库唯一约束、内容发布/版本记录/回滚、脚本历史版本 rollback 重审门禁、内容页 current 指针、草稿 base version/hash、版本 previous 链、发布元数据回填、管理端版本 JSON path diff 与富语义摘要、本地账号认证安全基线、学校/班级最小闭环与加入申请审批、课程/作业/学习事件/提交批改/作业只读复盘/跨班级提交唯一性/积分统计、知识状态/班级规则统计、个人/班级知识快照、知识快照周期重算脚本、运行记录与进程内调度器、管理端 API、学校/班级深度统计、管理端加入申请队列、管理端列表分页搜索、管理端内容页数据库侧分页、待批改队列、审计元数据与认证事件审计、学校/班级/课程访问控制服务层、跨范围权限矩阵测试，以及前端 opt-in schema 渲染试点
> **Review 回流状态**: 2026-07-06，`review` 分支已交付代码审查报告（审查基线 `V6.5.23 Review 前基线快照`，范围 `re1` 至 `re17`）。本 `houduan` 分支未合并 review 代码修复；后续仅按 `02` / `07` 中记录的优先级在 `houduan` 上选择性吸收。
> **下一阶段规划**: Python + MySQL 后端化、内容协议、登录用户体系与管理员 / 教师 / 学生三端平台设计，详见 [`doc/07-后端优化与设计.md`](doc/07-后端优化与设计.md)
> **当前分支**: `houduan` — 后端化设计与重构开发分支；`main` 保持主线维护
> **v6.4 主线**：未来星系产品内容保留，比赛提交/评审/截图临时层清理 + `20260630mainV64` 资产版本同步
> **v6.0 主线**：多星系架构正式确立 + muban UI 模板扩充 + 开发者手册 §0/§6.6/§17 新增星系开发指南
> **v5.1 主线**：Codevis 独立为子站 + Runtime 抽象层 + JS-Interpreter / Skulpt / JSCPP 三后端沙箱
> **v5.0 主线**：planets 多星系顶层导航 + 全局主题系统精简（移除亮色主题）

## 🪐 大版本里程碑速览

| 版本 | 发布日期 | 主题 | 详情 |
|------|---------|------|------|
| **v6.5（规划中）** | 2026-07-03 起 | Python + MySQL 后端化 + 三端教学平台设计 | [→](doc/07-后端优化与设计.md) |
| **v6.4.0** | 2026-06-30 | 已结束赛事材料清理 + future 分支主线合并 + 底栏恢复 + 缓存版本同步 | [→](#v640--2026-06-30) |
| **v6.1 ~ v6.2** | 2026-05-26 ~ 2026-06 | 工科试验室内容扩充、未来星系 MVP 接入、可信学习框架推进 | [→](doc/03-发布历史.md) |
| **v6.0.0** | 2026-05-26 | 项目层级调整 · 正式更名为「星序 Astra」· 多星系架构确立 | [→](#v600--2026-05-25--2026-05-26) |
| **v5.1.0 ~ v5.1.3** | 2026-05-24 | Codevis 独立子站 + Runtime 抽象层 + 三沙箱（JS/Python/C/C++） | [→](#v51x--2026-05-24) |
| **v5.0.0 / v5.0.1** | 2026-05-24 | 多星系顶层导航大屏 + 全局主题精简（移除亮色） | [→](#v50x--2026-05-24) |
| **v4.6.0** | 2026-04-24 | 物理 5 实验深度升级（机翼升力 / 开普勒 / 2D 动量等） | [→](#v460--2026-04-24合并-5-个-alpha--legacyv46-detail) |
| **v4.5.0** | 2026-04-24 | 全局体验升级（Ctrl+K 搜索 / 快捷键 / 跨学科推荐）+ 化学 5 项优化 | [→](#v450--2026-04-24合并-9-个-alpha--legacyv45-detail) |
| **v4.4.0** | 2026-04-24 | 星系导航升级为正式目录入口（进入↔浏览↔跳转↔返回完整动画） | [→](#v440--2026-04-24合并-8-个-alpha--legacyv44-detail) |
| **v4.3.0** | 2026-04-24 | FAB 折叠菜单系统 + Git 工作流规则确立 | [→](#v430--2026-04-24合并-v4229--v4245--legacyv43-detail) |
| **v4.2.0** | 2026-04-22 | 镜空科技风首页（全息 HUD）+ 生物排版预审 | [→](#v420--2026-04-22合并-v420-alpha1--v4228-共-30-提交--legacyv42-detail) |
| **v4.1.0** | 2026-04-22 | 5 学科测验题库扩充 63/63 + 移动端适配审视 | [→](#v410--2026-04-22合并-v410--v4121-共-22-提交--legacyv41-detail) |
| **v4.0.0** | 2026-04-15 | **63 个实验全部完成** · 12 模块 v2 重写 · 云服务器部署 | [→](#v40x--2026-04-15--2026-04-22) |
| **v3.0** | 2026-04-14 | 全部 P0/P1/P2 实验完成（60 个）+ 全面功能测试 | [→](#v3x-及更早) |
| **v2.7** | 2026-04-13 | 6 个核心模块深度重写（波动 / 电磁 / 复数 / 微积分 / 几何 / 遗传 / 光合） | [→](#v3x-及更早) |

## 📁 项目结构

```
星序 Astra/
├── index.html              # 主站 SPA 入口（含所有页面结构）
├── sw.js                   # Service Worker（离线缓存 + stale-while-revalidate）
├── deploy.ps1              # Windows 一键部署脚本
├── backend/                 # Python FastAPI 业务后端（v6.5 首切片）
│   ├── app/                 # API、配置、数据库探针、内容协议与服务层
│   └── tests/               # pytest 后端回归测试
├── doc/                    # 项目文档（v5.1.4 中文化重组）
│   ├── 01-开发者手册.md            # 完整开发者文档
│   ├── 02-更新规划.md              # 后续更新计划
│   ├── 03-发布历史.md              # 已完成沉淀
│   ├── 04-部署指南.md              # 服务器部署文档
│   ├── 05-UI规范模板.md            # UI 基准模板
│   ├── 06-实验体验与信度审查报告-20260606.md  # 实验体验与事实口径审查
│   ├── 07-后端优化与设计.md        # Python 后端化与三端平台设计
│   ├── 08-前端页面实现索引.md      # 页面/路由/模块到实现文件的定位索引
│   └── 99-历史审视报告归档.md      # v4.x 一次性审视报告归档
├── codevis/                # 代码可视化独立子站（v5.1 升级：独立 SPA + 多语言沙箱）
│   ├── index.html          # 子站入口
│   ├── shared/             # codevis 专用 css/js（与主站隔离）
│   │   └── js/runtimes/    # JS-Interpreter / Skulpt / JSCPP 三个后端
│   └── pages/              # home + code-trace
├── shared/                 # 主站全局共享资源
│   ├── css/                # 设计系统（tokens → base → components → responsive）
│   └── js/                 # 核心框架（config / router / module-selector / main）
├── pages/                  # 主站页面与实验模块
│   ├── home/               # 首页（星空 + HUD + 卫星系统 + 加载屏）
│   ├── planets/            # 星系大屏（v5.0 升级为多星系顶层导航）
│   ├── mathematics/        # 工科试验室：数学（20 个实验）
│   ├── physics/            # 工科试验室：物理（20 个实验）
│   ├── chemistry/          # 工科试验室：化学（17 个实验）
│   ├── algorithms/         # 工科试验室：算法（12 个实验）
│   ├── biology/            # 工科试验室：生物（19 个实验）
│   ├── cosmos/             # 未来星系：地球与宇宙
│   ├── engineering/        # 未来星系：工程应用
│   ├── datascience/        # 未来星系：数据科学与 AI
│   ├── infotech/           # 未来星系：信息技术
│   ├── materials/          # 未来星系：材料与微观结构
│   └── humanities/         # 未来星系：语言与人文可视化
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
# 详见 doc/04-部署指南.md
```

### 方式四：Python 业务后端（v6.5 开发中）

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
# 访问 http://127.0.0.1:8000/api/health
# 内容协议样例：http://127.0.0.1:8000/api/render/page/physics/energy-conservation

# 部署 smoke（生产 MySQL 门禁，需先配置 ASTRA_DATABASE_URL 并执行迁移）
python -m scripts.deploy_smoke --require-mysql

# 正式内容初始化（迁移和预检通过后执行，建议先 dry-run）
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts

# 前端 schema smoke（另开终端启动静态服务）
node server/dev-static-server.mjs --port 8766
# 访问：
# http://localhost:8766/?backendSchema=1&apiBase=http%3A%2F%2F127.0.0.1%3A8000#physics/energy-conservation
```

## ✨ 功能特性

### 星序总览与多星系入口
- 星序总览页承载一级星系入口，避免把学科目录混入全局一级菜单
- 工科试验室、代码空间、未来星系拥有独立页面品牌和导航语境
- 加载屏根据当前入口识别星系语境，首帧即可反馈正在进入的区域

### 工科试验室
- 数学、物理、化学、算法、生物五大学科共 **88 个交互实验**
- 模块选择器画廊支持点击卡片进入具体实验
- 每个学科保留独立 Hero、配色、实验推荐和键盘可访问性

| 数学 | 物理 | 化学 | 算法 | 生物 |
| ---- | ---- | ---- | ---- | ---- |
| 20 个实验 | 20 个实验 | 17 个实验 | 12 个实验 | 19 个实验 |

### 代码空间
- 独立 `/codevis/` 子站，使用 `cv-` 命名空间隔离 UI
- 支持 JavaScript / Python / C / C++ 代码执行追踪
- 变量、指针、数据结构与执行步骤以时间轴方式回放

### 未来星系
- 已接入未来星系总览页，承载六个二级方向入口
- 六个方向分别为地球与宇宙、工程应用、数据科学与 AI、信息技术、材料与微观结构、语言与人文可视化
- 学习框架已包含任务、模型边界、来源索引、页内学习路径和实验台状态读数
- 当前仍处于持续深化阶段，后续重点是二级总览、主题拆分、视觉素材与内容可信度

### 技术亮点
- GSAP 驱动的径向裁剪转场动画
- Canvas 2D 实时绘图引擎 + DPR 高分屏适配
- 页面脚本与实验脚本按需加载，首屏只启动最小 Router shell
- 星系级 support 生命周期治理：进入星系加载增强层，离开页面清理 Observer / RAF / 定时器 / 事件监听
- Service Worker 最小壳缓存 + 当前星系资源预热
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
- **Python 3 / FastAPI / SQLAlchemy** — v6.5 业务后端骨架、API、MySQL 连接、部署预检、部署 smoke、API no-store 缓存边界、内容协议、内容 seed 初始化与只读查询边界、正式内容初始化入口、ContentDraft 草稿与脚本审核、脚本静态分析风险等级、脚本 sandbox 契约、公开 render 脚本 manifest 脱敏、草稿编辑、active 草稿数据库唯一约束、内容发布/版本记录/追加式回滚、脚本历史版本 rollback 重审门禁、内容页 current 指针、草稿 base version/hash、版本 previous 链、管理端版本 JSON path diff 与富语义摘要、本地认证安全基线、学校/班级加入申请审批、学校/班级/课程访问控制服务层、作业提交/批改/学生侧只读复盘、跨班级提交唯一性、知识状态/班级规则统计、个人/班级知识快照、周期重算运行记录与进程内调度器、管理端学校/班级统计、加入申请治理、列表分页搜索、内容页数据库侧分页、待批改队列和审计元数据

## 📝 更新日志

> 完整的细碎微版本详见 [doc/03-发布历史.md](doc/03-发布历史.md)。当前主线在 `main` 分支维护。

### v6.5 — 2026-07-05（houduan）
- 2026-07-06 已在 `houduan` 落地 REV-04 第二批后端修复：`/api/admin/content/pages` 改为数据库侧状态过滤、关键字搜索、计数和分页，并转义 `%/_` 查询通配符。
- 2026-07-06 已在 `houduan` 落地 REV-04 首批后端修复：作业提交唯一性从 `assignment_id + student_id` 收窄为 `assignment_id + student_id + class_id`，同一作业挂到多个班级时学生可按班级分别提交。
- 2026-07-06 已在 `houduan` 明确班级加入双路径口径：`/join` 保留为 legacy/direct join 兼容入口，`/join-requests` 承担教师/admin 审批流。
- 2026-07-06 已在 `houduan` 落地 closed/archived 作业学生侧只读复盘入口：学生可继续查看题目、本人提交、成绩和反馈，但不可再次提交；教师/admin 提交列表与批改视角保持不变。
- 2026-07-06 已在 `houduan` 落地 active 草稿数据库级抗并发：新增 `active_key` 与唯一约束，同作者同目标页只能有一个 active 草稿，撤回/发布后可重新创建。
- 2026-07-06 已读取 `review` 分支代码审查报告并回流规划：本次只同步文档和后续任务，不合并 review 分支代码；后续开发继续在 `houduan` 上推进。
- 已保存 review 前基线快照：`houduan@c9a2b41` 工作区干净，可作为团队整体代码 review 的冻结点；剩余大块集中在真实 MySQL/部署、脚本真实运行隔离、三端 UI、多 worker 调度锁和审计治理。
- 正式内容初始化新增 `scripts.init_content_pages`，迁移和部署预检通过后可显式创建/修复内置内容页版本，并要求管理员归因与脚本引用确认。
- 内容草稿已支持管理员发布到公开 `content_pages`、写入不可变 `content_page_versions`、按历史版本追加式回滚，并保留审计与 schema hash。
- 内容版本生命周期已补齐 `content_pages.current_version_id`、草稿 `base_version_id/base_schema_hash` 和版本 `previous_version_id`，发布/回滚不再只依赖时间顺序推断当前态。
- 管理端内容版本 diff 在保留兼容 `changes` 列表的同时新增 `semantic` 摘要，覆盖 metadata、courseUnit、sections 和 sources 的增删改移。
- 内容脚本能力已新增静态策略分析和 `scriptSandbox` 契约；公开 render 会剥离原始脚本引用并返回不可执行 manifest，脚本历史版本 rollback 需走新草稿重审。
- 内容草稿已支持作者或管理员在 `draft` / `changes_requested` 状态编辑 schema；编辑会重算 schema hash 与脚本风险、清空旧脚本审核，并保留原始 base 版本保护。

### v6.4.0 — 2026-06-30
- 清理已结束赛事相关提交文档、预检脚本、临时依赖和预览日志，保留未来星系作为正式产品内容。
- 移除材料页中的临时展示导览、路径矩阵、取景点和编号来源展示，恢复为普通学习与可信审查路径。
- 恢复主站底栏署名显示，并让未来星系总览页使用未来星系底栏。
- 入口、Router、main 和 Service Worker 统一推进到 `20260630mainV64`。

### v6.1.0-alpha 系列
- **v6.1.0-alpha3** — 2026-05-26 — 协调工科实验室实验控件（统一面板/按钮交互口径）
- **v6.1.0-alpha2** — 2026-05-26 — 优化代码空间（Codevis）子站交互与更新规划口径
- **v6.1.0-alpha1** — 2026-05-26 — 修复 CodeSpace 跳转与文档口径偏差

### v6.0.0 — 2026-05-25 / 2026-05-26
- 🪐 项目顶层正式更名为「**星序 Astra**」，确立多星系架构（工科试验室星系 + 代码空间星系）
- 🏗️ 项目层级调整：`muban/` UI 模板扩充，开发者手册新增 §0 / §6.6 / §17 多星系开发指南
- 📚 文档体系重组完成：`doc/` 五大主文档 + `99-历史审视报告归档.md`

### v5.1.x — 2026-05-24
- **v5.1.3** — Code-trace 子站交互打磨：复制/重置、关键步骤时间轴、面板可折叠
- **v5.1.2** — 代码空间子站交互优化：文案对齐、控件分区、键盘快捷、首访引导、卡片光晕
- **v5.1.0** — **Codevis 独立为子站** `/codevis/`，引入 Runtime 抽象层 + JS-Interpreter / Skulpt / JSCPP 三后端沙箱（覆盖 JS / Python / C / C++）

### v5.0.x — 2026-05-24
- **v5.0.1** — 多星系导航打磨 + 主题系统精简（移除亮色主题）
- **v5.0.0** — 多星系顶层导航大屏（`planets`，galaxies ↔ galaxy 双层状态机）

### v4.6.0 — 2026-04-24（合并 5 个 alpha · `legacy/v4.6-detail`）
- **alpha5** — 物理 `fluid-dynamics` 新增「✈️ 机翼升力」第 4 模式（NACA 4 位翼型 + 上下流线分割 + 升力公式推导）
- **alpha4** — 物理 `gravitation` 新增「开普勒」+「三宇宙速度」两模式（椭圆轨道 + 三星同发对比）
- **alpha3** — 物理 `momentum-conservation` 升级为 1D + 2D 双模式（2D 沿连心线碰撞 + 鼠标/触屏拖拽）
- **alpha2** — 物理 `energy-conservation` 升级为「能量总量守恒」（KE/PE/Q/Σ 四列柱 + 守恒检验）
- **alpha1** — 物理 `force-composition` 升级为「多力合成」（2-6 力 + 首尾相接虚线链 / 平行四边形双法切换）

### v4.5.0 — 2026-04-24（合并 9 个 alpha · `legacy/v4.5-detail`）
- **alpha1-3** — 全局体验升级：Ctrl+K 全局搜索（63 实验跨学科模糊匹配）、Ctrl/Alt+1~5 快捷键、实验底部跨学科推荐 4 卡片
- **alpha4-5** — 化学 `molecular-structure`：移除 NaCl、新增键参数表 + HCHO/H₂S/CH₃COOH（对比 H₂O 键参）
- **alpha6-7** — 化学 `chemical-reactions`：中和反应离子方程式重做 + redox（Fe+Cu²⁺）+ NaCl 溶解三反应
- **alpha8** — 化学 `chemical-bond`：三键型微粒 +「构成微粒 / 本质静电作用」分区强调
- **alpha9** — 化学 `organic-chemistry`：去重 methane，新增乙烯（sp²）/ 乙炔（sp）/ 乙烷（sp³），σ 键可旋转交互

### v4.4.0 — 2026-04-24（合并 8 个 alpha · `legacy/v4.4-detail`）
- 🪐 **核心**：星系导航从纯视觉装饰升级为正式的目录入口，闭环「进入→浏览→跳转→返回」完整动画体系
- **alpha1-2** — 主题换色（绿→蓝）+ FAB 折叠菜单重构 + 星系大屏隐藏顶栏
- **alpha3-4** — 星系作为目录：学科子星系视图（实验作为双环卫星）+ 轨道半径 / 卫星尺寸 / 转场调优
- **alpha5-6** — `zoom-into-satellite` 联动（点击卫星 480ms ease-out 飞向中心 + 10x 放大 + hash 跳转）+ 首页 CTA「进入星系目录」入口
- **alpha7-8** — 子星系顶部面包屑 + zoom-out 退出动画（ESC / 中央 / 面包屑统一触发）

### v4.3.0 — 2026-04-24（合并 v4.2.29 ~ v4.2.45 · `legacy/v4.3-detail`）
- 🎛️ FAB 折叠菜单系统：默认收起 + 三点菜单展开 4 个功能 FAB（主题 / 收藏 / 帮助 / 返回顶部）
- 🎨 默认黑夜模式 + 主题/收藏 FAB 配色、tooltip 气泡、ripple 水波动画细节打磨
- 📋 **Git 工作流规则确立**：main = 大版本合并 · feature 分支 = 微版本迭代 · legacy 分支 = 历史细节

### v4.2.0 — 2026-04-22（合并 v4.2.0-alpha1 ~ v4.2.28 共 30+ 提交 · `legacy/v4.2-detail`）
- 🎨 **镜空科技风首页**：主星球 + 5 卫星球 + 全屏背景青绿化全息 HUD（经纬网格 / 准星十字 / 双层扫描环）
- 📋 任务7：生物 13 实验文字排版预审 + Top10 待修问题汇总
- 🎛️ FAB 折叠菜单基础（v4.2.29+ 在 v4.3 大版本完成）

### v4.1.0 — 2026-04-22（合并 v4.1.0 ~ v4.1.21 共 22 提交 · `legacy/v4.1-detail`）
- 📚 5 学科测验题库扩充：数学 / 物理 / 化学 / 生物 / 算法各加 5 步定制引导，目标 63/63 实验全覆盖
- 🔧 复核 Batch3 全部 `injectInfoPanel` / `injectEduPanel` 用 innerHTML 覆盖确保天然幂等
- 📱 移动端适配审视产出 `MOBILE_AUDIT` 报告并完成全触控配套

### v4.0.x — 2026-04-15 ~ 2026-04-22
- **v4.0.10** — 2026-04-22 — 复核 Batch3 物理化学 7 个 `injectEduPanel` 幂等性
- **v4.0.9** — 2026-04-22 — 顺手修复「力的合成与分解」残留 11px 字号抬升至 12px
- **v4.0.5 ~ v4.0.8** — 2026-04-22 — 移除首页 `home-progress-widget`、UI 排版审视输出 29 项问题、动量守恒 Canvas 字号统一至 12px、CF.sans 接入
- **v4.0.4** — 2026-04-18 — 新增化学实验：原子结构与电子排布（轨道形状 / 电子排布 / 玻尔模型三模式）
- **v4.0.2** — 2026-04-17 — 修复 FuncProps/ExpLog 浏览器卡死（ResizeObserver 隐藏时 W=0 → 无限循环）；Canvas 字体全项目统一使用 CSS 变量（`--font-sans` / `--font-mono`）；新增 `doc/05-UI规范模板.md`
- **v4.0.1** — 2026-04-17 — 生物模块语法错误修复；回访用户加载加速（localStorage 检测）；新增 Service Worker 离线缓存（stale-while-revalidate）；文档迁移至 `doc/`
- **v4.0.0** — 2026-04-15 — 63 个实验全部完成；12 个模块深度 v2 重写；BF-01~11 Bug 修复（DPR 适配 / ARIA 无障碍 / 防抖锁）；首页加载优化；Windows 云服务器一键部署（端口 910）

### v3.x 及更早
- **v3.0.2** — 2026-02 — 一致性审计 + DPR 适配 + ARIA 无障碍
- **v3.0.1** — 全面功能测试 + Bug 修复
- **v3.0** — 2026-04-14 — 全部 P0/P1/P2 实验完成（60 个）
- **v2.7** — 2026-04-13 — 6 个核心模块深度重写（波动 / 电磁 / 复数 / 微积分 / 几何 / 遗传 / 光合）
- **v2.2** — 生物卫星 + 化学反应重写 + 文档
- **v2.0** — SPA 架构 + hash 路由 + 初始实验

## 📄 许可证

本项目仅供学习使用。
