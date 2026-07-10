# 星序 Astra · 多学科可视化学习平台

「星序 Astra」是一个基于 HTML/CSS/JavaScript 的交互式科学学习平台，当前由三个星系构成：

- 🌌 **工科试验室星系**（主站）：数学、物理、化学、算法、生物五大学科共 **88 个可视化实验**，覆盖高中核心知识与扩展演示
- 💻 **代码空间星系**（[子站 `/codevis/`](codevis/README.md)）：多语言代码执行追踪播放器（JavaScript / Python / C / C++），含 Runtime 抽象层与三沙箱后端
- ✨ **未来星系**（主站内 `frontier` 星系）：地球与宇宙、工程、数据科学、信息技术、材料、人文可视化六个跨学科探索方向

星序总览页负责承载一级星系入口；进入某个星系后，才显示该星系自己的二级学科或知识目录。内置 C++ httplib 静态服务器负责静态文件托管，业务 API 由 Python/FastAPI 承担。

> **当前状态**: V6.6.63（2026-07-11）— `houduan` 分支已完成 V6.6.37-V6.6.63 后端阶段收束。首个 RC 不选入 Webhook、GitHub issue sync 或 audit anchor，三者保持默认关闭；只读范围门禁证明零网络请求/零副作用，生产 stage gate 15/15 通过。后续外部集成和 WORM/RFC3161 等能力必须另行立项。
> **Review 回流状态**: 2026-07-06，`review` 分支已交付代码审查报告（审查基线 `V6.5.23 Review 前基线快照`，范围 `re1` 至 `re17`）。本 `houduan` 分支未合并 review 代码修复；后续仅按 `02` / `07` 中记录的优先级在 `houduan` 上选择性吸收。
> **最新治理**: 2026-07-10，V6.6.53 将班级与课程权限拆成独立授权轴：学生软移除/双范围转班/逐项批量导入，`editor/content_editor/assessment_editor/viewer` 协作者和批量 upsert，以及班级 assignment/积分覆盖均有审计、幂等和越权回归；管理端加入审批使用内联二次确认、写入不重试并同步对账列表与 KPI。
> **最新学习分析**: `rule_version=v2` 以 effective active assignment-class pair 为分母，按提交/评分/事件/积分自身时间戳稳定输出 course/unit/knowledge_point/assignment 维度；hidden/draft/archived/closed/unassigned 资源不进入当前统计，v1 历史快照保持兼容读取。
> **最新外部治理**: 外部告警默认关闭，只在 admin 显式确认、plan/hash/due/expiry 再校验通过且 HTTPS URL/SecretStr token 安全注入后发送脱敏信封；真实 staging 目标、出口网络、接收端验签/幂等与回执仍待部署留证。
> **最新任务治理**: `background_tasks/background_task_attempts` 保存统一任务控制面，worker 以数据库租约竞争并复用知识快照/脚本扫描领域 run 去重；管理端只返回脱敏摘要，可查看队列和尝试记录并显式 retry/cancel。V6.6.61 已用真实 MySQL 验证 lease/cancel/retry、重复副作用防护及 API/worker 并发；V6.6.62 已验证独立 `AstraWorker` 服务重启后的包装/业务 PID 更替与自动恢复，最小权限进程拒绝普通用户强制终止。
> **最新审计可信边界**: `audit_chain_heads` 在 MySQL 使用行锁串行化链尾，SQLite 本地回归使用事务级进程锁；归档 Manifest v2 记录范围、文件 hash、导出人/导出时间和生命周期策略。V6.6.61 的 6 writer 实测无链分叉，并完成一致性备份和独立恢复；默认关闭的外部回执只有被选入 RC 时才在 V6.6.63 补 staging。
> **最新外部问题治理**: GitHub 是首个可执行 provider，Gitee/Jira 通过协议接口预留但尚未实现。同步仅允许管理员显式确认，创建/评论结果不确定时不盲重试；外发内容不含 evidence、notes、source 或凭据，不接收外部反向写入，本地 `BugRecord` 始终为权威记录。功能默认关闭，只有被选入 RC 时才在 V6.6.63 补真实 staging、token 权限、限流和人工歧义证据。
> **最新性能门禁**: `backend_performance_drill` 与管理端报告覆盖 11 个高频查询 profile，复核 10 个新增复合索引和既有任务 claim 索引；真实 MySQL 会执行不返回计划正文的 EXPLAIN ANALYZE，并输出 p50/p95/p99。V6.6.61 已完成代表性数据、0043 DDL、连接池耗尽恢复和 100 API + 100 worker 并发实证；深 offset、leading wildcard 和动态聚合继续作为已归属 P2。
> **最新隔离**: `physics/energy-conservation` 保持 `sandbox="allow-scripts"`、opaque origin、hash CSP/SRI、静态回退和 opt-in 接入；opaque iframe 的匿名 SRI 资产只在 hash-bound 资产端点使用资源级 CORS，全局凭据型 API 仍为精确 origin。V6.6.60 Edge proof 27/27。
> **最新缓存边界**: `/api` 与 `/api/*` 由 FastAPI 全状态 `no-store`，Service Worker 在路由最前面直接旁路 API；安装失败不再激活不完整静态缓存。桌面登录态/真实写入和外部 Chrome 390×844 的三端门禁、sandbox 交互、网络失败/恢复均已回归。
> **下一阶段规划**: Python + MySQL 后端化、内容协议、登录用户体系与管理员 / 教师 / 学生三端平台设计，详见 [`doc/07-后端优化与设计.md`](doc/07-后端优化与设计.md)
> **当前分支**: `houduan` — 后端化设计与重构开发分支；`main` 保持主线维护
> **v6.4 主线**：未来星系产品内容保留，比赛提交/评审/截图临时层清理 + `20260630mainV64` 资产版本同步
> **v6.0 主线**：多星系架构正式确立 + muban UI 模板扩充 + 开发者手册 §0/§6.6/§17 新增星系开发指南
> **v5.1 主线**：Codevis 独立为子站 + Runtime 抽象层 + JS-Interpreter / Skulpt / JSCPP 三后端沙箱
> **v5.0 主线**：planets 多星系顶层导航 + 全局主题系统精简（移除亮色主题）

## 🪐 大版本里程碑速览

| 版本 | 发布日期 | 主题 | 详情 |
|------|---------|------|------|
| **v6.6.63（houduan）** | 2026-07-11 | 首个 RC 外部通道范围冻结、长期证据确认与后端阶段完成 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.62（houduan）** | 2026-07-11 | 真实反代、四服务、Release 构建与回滚实证 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.61（houduan）** | 2026-07-10 | 真实 MySQL 迁移、并发、性能、连接池与备份恢复实证 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.60（houduan）** | 2026-07-10 | 发布候选本地总验收、风险/回滚总账与 RC 延期决策 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.59（houduan）** | 2026-07-10 | 安全、隐私和发布冻结审查 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.58（houduan）** | 2026-07-10 | 复合索引、性能报告、慢日志、MySQL 连接池和负载预算 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.57（houduan）** | 2026-07-10 | GitHub issue 最小同步、操作账本、歧义锁定与本地权威边界 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.56（houduan）** | 2026-07-10 | 审计链并发串行化、Manifest v2、HTTPS hash 回执锚定与生命周期审批边界 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.55（houduan）** | 2026-07-10 | DB-backed 任务控制面、租约重试、dead-letter 与领域幂等恢复 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.54（houduan）** | 2026-07-10 | 默认关闭的 Webhook 告警投递、状态机、幂等与审计 | [→](doc/09-后端阶段收束小版本开发安排.md) |
| **v6.6.53（houduan）** | 2026-07-10 | 复杂权限矩阵、班级作业策略与 v2 多维学习分析 | [→](doc/09-后端阶段收束小版本开发安排.md) |
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
├── deploy.ps1              # Windows 四服务演练包生成入口；不下载工具或安装服务
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
└── server/                 # C++ httplib 静态服务器与内部 health
```

## 🚀 快速开始

### 方式一：Python 开发服务器（推荐开发用）

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```

### 方式二：C++ 静态服务器（生产部署）

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
./build/Release/englab_server.exe -p 910 -r ..
# 访问 http://localhost:910
```

V6.6.59 起该服务默认只监听 `127.0.0.1`，且只公开审核过的前端资源目录；不要用 `--host 0.0.0.0` 绕过反向代理和防火墙边界。构建需 MSVC 2019+、GCC 9.1+ 或等效的完整 C++17 filesystem 工具链。

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

# 部署预检与 smoke（生产 MySQL 门禁，需先配置 ASTRA_DATABASE_URL 并执行迁移）
python -m scripts.deploy_preflight --require-mysql
python -m scripts.deploy_smoke --require-mysql

# 正式内容初始化（迁移和预检通过后执行，建议先 dry-run）
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts

# 审计归档候选导出与 Manifest 校验（只读，不删除源表）
python -m scripts.archive_audit_logs --retention-days 365 --output-dir audit-archives
python -m scripts.archive_audit_logs --verify audit-archives/audit-logs-archive-<stamp>.manifest.json

# 密码重置 token 留存清理（默认 dry-run；显式 --apply 才删除）
python -m scripts.cleanup_password_reset_tokens --retention-days 30
python -m scripts.cleanup_password_reset_tokens --retention-days 30 --apply

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
- **Python 3 / FastAPI / SQLAlchemy** — v6.5/v6.6 业务后端骨架、连续 Alembic/MySQL 门禁、内容/认证/教学/三端治理 API、脚本隔离与供应链观察、v2 学习分析、知识快照与告警 outbox、默认关闭的 Webhook 投递，以及 V6.6.55 DB-backed 统一后台任务控制面；任务具备租约、attempt、退避、dead-letter、人工恢复和领域 run 幂等，审计与 API 响应继续执行 payload/token 脱敏。

## 📝 更新日志

> 完整的细碎微版本详见 [doc/03-发布历史.md](doc/03-发布历史.md)。当前主线在 `main` 分支维护。

### v6.5 — 2026-07-05（houduan）
- 2026-07-11 已在 `houduan` 落地 V6.6.63 RC 范围冻结：首个 RC 不选入 Webhook/GitHub/audit anchor，新增只读范围门禁证明零网络请求/零副作用；最终 stage gate 15/15，全量后端 375 passed/5 skipped，V6.6.37-V6.6.63 后端阶段收束完成。
- 2026-07-10 已在 `houduan` 落地 V6.6.61 真实 MySQL 实证：Alembic head 前进到 0046，完成空库迁移、preflight/smoke、内容/知识快照/脚本扫描/统一任务/审计并发、11 个 EXPLAIN ANALYZE profile、0043 DDL 建撤、连接池压力和独立备份恢复；修复 MySQL 标识符、保留字、DATETIME 精度、降级外键顺序与健康探针连接池泄漏等真实方言问题。
- 2026-07-10 已在 `houduan` 落地 V6.6.55 统一任务执行治理：`background_tasks/background_task_attempts` 覆盖告警 plan、知识快照和内容脚本扫描，支持调度入队、优先级、数据库租约、指数退避、dead-letter、显式 retry/cancel、attempt 历史和重启接管；worker 默认关闭，脚本扫描外网执行另设 opt-in，管理 API 不返回 payload 或 lease token。
- 2026-07-09 已在 `houduan` 落地 BE-09/V6.6.48 浏览器隔离证明首轮：新增 Playwright/Edge drill，验证 iframe opaque origin 无法读取父页 DOM/storage/cookie，unknown sandbox/asset fail closed，sandbox HTML 的 `frame-ancestors` 和可执行资源 CORP 口径已同步收束。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容脚本沙箱执行契约：公开 `scriptManifest.sandbox` 返回 enforcement/capabilities，按 `network=none/same-origin` 派生 CSP，unsafe sandbox 防御性降级为 blocked，render API 返回 `X-Astra-Content-Script-*` 契约头。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容脚本资产校验证据：`script_integrity_verified` 与 `script_integrity_mismatch` finding 会携带资产 SHA-256、字节大小、SRI token 数量和匹配算法，用于管理员审核响应、stored analysis 和后续供应链审计。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容脚本资产下载校验：管理员批准外部脚本和发布已审核草稿时，后端会下载脚本资产并按声明 SRI 比对字节；下载失败、SRI mismatch 或发布前 CDN 字节漂移返回 `409`，默认下载器不跟随重定向。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容协议稳定身份：`sectionId/sourceId` 作为新写入必填契约进入草稿创建、编辑、发布和内置内容初始化；schema 对历史内容保持可选兼容，semantic diff 优先使用稳定 ID，避免章节重排、标题改名或来源 label/url 改动被误判为删除新增。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容 diff 稳定身份响应：管理端版本 semantic diff 的 section/source 变更项显式返回 `section_id_before/after` 与 `source_id_before/after`，保留旧 `key`、`field_changes`、`summary` 和 JSON path diff 兼容。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容 diff 敏感预览：管理端版本 diff 的 raw `changes` 和 semantic `field_changes/prop_changes` 会对 token/key/secret/script/sandbox/integrity/crossorigin 等敏感字段返回 redaction preview，非敏感字段保持原值。
- 2026-07-07 已在 `houduan` 落地 BE-02 内容脚本资产完整性静态门禁：外部脚本 URL 默认阻断，配置 `ASTRA_CONTENT_SCRIPT_ALLOWED_HOSTS` 后仍需 `https`、无 query/fragment、SRI 和 `crossorigin=anonymous`，并继续要求管理员脚本审核；公开 render 剥离脚本 URL、integrity、crossorigin 和 sandbox 原始字段，只保留不可执行 manifest。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照调度积压摘要：管理员可通过 `/api/admin/knowledge-snapshot-runs/queue` 查看 dispatchable now、claimable by lease rule、manual requeue 和 blocked runs，区分 pending requeue、当前 due window、retryable/exhausted failed、cancelled、active/stale/legacy running；响应和 `admin.knowledge_snapshot_run.queue_report` 审计均不暴露 lease token 或 metadata 明细。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照运行手动 requeue：管理员可通过 `/api/admin/knowledge-snapshot-runs/{id}/requeue` 将 failed、cancelled 或过期带租约 running run 重置为 pending；pending 幂等，active running、无租约 legacy running 和 success 返回 `409`；调度器会扫描 pending run 并抢占执行，响应和 `admin.knowledge_snapshot_run.requeue` 审计均不暴露 lease token。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照运行健康摘要：管理员可通过 `/api/admin/knowledge-snapshot-runs/health` 查看 stale running、lease expiring、claimable、retryable/exhausted failed、pending 与 problem runs 摘要；响应和 `admin.knowledge_snapshot_run.health_report` 审计均不暴露 lease token。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照运行取消：管理员可分页过滤 `knowledge_snapshot_runs`，并对 `pending` 或带 scheduler lease 的 `running` run 执行协作式取消；取消会标记 `cancelled`、清空 scheduler lease、写入 `admin.knowledge_snapshot_run.cancel` 审计且不返回 lease token。
- 2026-07-07 已在 `houduan` 落地 BE-03 密码重置 token 留存清理脚本：默认 dry-run，显式 `--apply` 才删除；按已用时间或过期时间命中 cutoff，摘要只返回计数、截断、策略和首尾 id，不暴露用户名、IP 哈希、user-agent 或 token hash。
- 2026-07-07 已在 `houduan` 落地 BE-03 用户自助密码重置令牌：请求接口泛化响应并按账号哈希/IP 哈希冷却，生产环境不回传 token；确认接口行锁消费一次性 token，重置密码后撤销会话、清理登录失败桶并写入脱敏审计。真实投递通道/MFA 暂列 P4 最低优先级；MySQL 并发压测仍待后续。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计链完整性校验：`GET /api/admin/audit-logs/chain-integrity` 按时间窗与扫描上限重算应用层 hash chain，报告 `current_hash_mismatch`、`prev_hash_mismatch`、历史空 hash 与截断状态，并以 `admin.audit.chain_integrity` 记录摘要；接口只读，不修复、不删除、不提供 WORM 或外部锚定。
- 2026-07-07 已在 `houduan` 落地 BE-12 本地审计归档包导出：`scripts.archive_audit_logs` 可按配置、`--retention-days` 或 `--before` 选择归档候选，输出 JSONL/CSV 数据文件和 Manifest，记录 SHA-256、导出数量、截断状态、链边界与 hash-chain 校验状态，并支持 `--verify`；脚本默认只读，不删除源表、不写管理端审计日志、不提供 WORM 或外部锚定。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计留存预检：`GET /api/admin/audit-logs/retention-plan` 复用审计筛选，按配置或查询参数计算 cutoff、归档候选、临期数量、聚合桶和哈希链边界，并以 `admin.audit.retention_plan` 记录不含候选明细的摘要；真实归档、删除、WORM、外部锚定和正式留存执行仍待后续。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计高频事件摘要：`GET /api/admin/audit-logs/high-frequency` 复用审计筛选与默认 24 小时时间窗，按 action、actor/action、ip/action、resource/action、failure_reason 聚合候选，并以 `admin.audit.high_frequency` 记录不含候选明细的摘要快照；正式告警、归档、外部锚定和 issue 自动化仍待后续。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照租约自动心跳：调度器和周期重算 CLI 会把 token-guard heartbeat callback 注入长重算循环，按配置间隔续租；失去租约时旧 worker 抛出 `SnapshotRunLeaseLost` 并停止，不标记 failed、不覆盖新 owner。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计日志链式哈希：`AuditLog` 新增 `prev_hash/current_hash`，写入时以规范化审计 payload 串联 SHA-256 摘要，查询与 JSON/CSV 导出返回哈希字段；旧记录不回填，空值表示历史兼容段或链起点。
- 2026-07-07 已在 `houduan` 落地 BE-08 知识快照调度租约：`KnowledgeSnapshotRun` 新增 scheduler lease owner/token/expires/heartbeat 字段，调度器和周期重算 CLI 通过数据库租约避免多 worker 重复执行同一窗口，过期 running 可被抢占，完成/失败释放使用 token guard。
- 2026-07-07 已在 `houduan` 落地 BE-12 缺陷记录外部 issue 链接：`BugRecord` 新增 `external_issue_provider`、`external_issue_id` 和 `external_issue_url`，管理端创建/更新会修剪字段，列表关键字搜索覆盖 issue 元数据，`admin.bug.*` 审计快照记录链接变化；正式双向同步仍待后续。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计日志报表摘要：`GET /api/admin/audit-logs/report` 与 `/report.csv` 复用审计筛选，按 action/resource_type/actor_role/event_result/failure_reason 聚合，记录 `admin.audit.report` 摘要，不导出原始条目或快照明细。
- 2026-07-07 已在 `houduan` 落地 BE-12 审计日志 CSV 导出：`GET /api/admin/audit-logs/export.csv` 复用审计筛选、排序、`limit/truncated` 和 `include_snapshot` 边界，返回下载响应与导出元数据头，默认剥离快照并对表格公式前缀做基础中和；成功导出继续写入 `admin.audit.export` 摘要。
- 2026-07-07 已在 `houduan` 落地 BE-03/BE-05 管理员密码重置：管理员可重置用户密码，重置会撤销目标用户未撤销会话、清理登录失败桶，并写入不含密码明文或 hash 的 `admin.user.password_reset` 审计。
- 2026-07-07 已在 `houduan` 落地 BE-03 last_seen 刷新节流：默认 300 秒内同一 IP 哈希不重复写库，窗口过期或 IP 哈希变化时刷新，可通过 `ASTRA_SESSION_LAST_SEEN_UPDATE_SECONDS=0` 关闭节流。
- 2026-07-07 已在 `houduan` 落地 BE-03 会话设备标识与 last_seen：`AuthSession` 新增设备摘要、登录 user-agent、最后活跃时间和最后活跃 IP 哈希；登录写入设备元数据，认证依赖开始追踪 last_seen，活动会话列表返回设备摘要与 `last_seen_at`。
- 2026-07-06 已在 `houduan` 落地 BE-03 活动会话列表与单会话撤销：当前用户可列出自己的活动会话、撤销指定活动会话，撤销当前会话会清理 cookie，撤销行为写入 `auth.session.revoke` 审计。
- 2026-07-06 已在 `houduan` 落地 BE-03/BE-05 禁用用户会话撤销：管理员将用户状态改为 `disabled` 时撤销未撤销会话，旧 token 返回 `401`，并在 `admin.user.update` 审计快照写入 `revoked_sessions`。
- 2026-07-06 已在 `houduan` 落地 BE-12 审计日志导出留痕：成功调用 `/api/admin/audit-logs/export` 后写入 `admin.audit.export`，只记录筛选条件和导出摘要，不记录导出结果明细。
- 2026-07-06 已在 `houduan` 落地 BE-12 审计日志 JSON 导出：`GET /api/admin/audit-logs/export` 复用列表筛选、排序与管理员权限，默认剥离 `snapshot_json`，通过 `include_snapshot=true` 显式包含快照，并用 `limit/truncated` 标记导出截断。
- 2026-07-06 已在 `houduan` 落地 R-21 用户名数据库级规范化约束：`users.normalized_username` 与 `login_attempts.normalized_username` 由 Alembic `20260706_0022` 回填并建立唯一约束，注册/admin bootstrap 并发唯一冲突返回 `409`，迁移测试覆盖历史重复用户阻断与重复登录失败桶清理。
- 2026-07-06 已在 `houduan` 落地 REV-04 第七批后端修复：正式内容初始化迁移测试显式覆盖中文目录和中文 SQLite 文件名，内容发布测试覆盖中文 slug 经百分号编码后的公开读取、后台搜索与版本过滤；REV-04 后端候选修复已转入生产 MySQL/部署联调风险跟进。
- 2026-07-06 已在 `houduan` 落地 REV-04 第六批后端修复：学生课程、单元、作业、学习事件、提交、复盘、个人进度、个人知识统计与个人快照按 published 课程、published 单元和 active 作业收口，周期任务只为学生生成可见课程 user snapshot，教师/班级聚合保持管理口径。
- 2026-07-06 已在 `houduan` 落地 REV-04 第五批后端修复：内容发布/回滚阶段的版本唯一冲突和同一草稿重复发布版本冲突统一返回 `409`，并新增 `source_draft_id` 数据库唯一约束。
- 2026-07-06 已在 `houduan` 落地 REV-04 第四批后端修复：注册与 admin bootstrap 统一将用户名修剪并小写落库，登录和重复校验按大小写不敏感匹配，登录失败锁定共用规范化用户名桶。
- 2026-07-06 已在 `houduan` 落地 REV-04 第三批后端修复：注册/admin bootstrap/admin user、学校/班级、课程/单元/作业和 admin bug 的必填文本在修剪后为空时统一返回 `422`。
- 2026-07-06 已在 `houduan` 落地 REV-04 第二批后端修复：`/api/admin/content/pages` 改为数据库侧状态过滤、关键字搜索、计数和分页，并转义 `%/_` 查询通配符。
- 2026-07-06 已在 `houduan` 落地 REV-04 首批后端修复：作业提交唯一性从 `assignment_id + student_id` 收窄为 `assignment_id + student_id + class_id`，同一作业挂到多个班级时学生可按班级分别提交。
- 2026-07-06 已在 `houduan` 明确班级加入双路径口径：`/join` 保留为 legacy/direct join 兼容入口，`/join-requests` 承担教师/admin 审批流。
- 2026-07-06 已在 `houduan` 落地 closed/archived 作业学生侧只读复盘入口：学生可继续查看题目、本人提交、成绩和反馈，但不可再次提交；教师/admin 提交列表与批改视角保持不变。
- 2026-07-06 已在 `houduan` 落地 active 草稿数据库级抗并发：新增 `active_key` 与唯一约束，同作者同目标页只能有一个 active 草稿，撤回/发布后可重新创建。
- 2026-07-06 已读取 `review` 分支代码审查报告并回流规划：本次只同步文档和后续任务，不合并 review 分支代码；后续开发继续在 `houduan` 上推进。
- 已保存 review 前基线快照：`houduan@c9a2b41` 工作区干净，可作为团队整体代码 review 的冻结点；统一任务执行代码已在 V6.6.55 收束，剩余大块集中在真实 MySQL/部署与多进程留证、脚本真实外网观察、审计外部锚定、外部 issue 同步、性能、安全和 RC 总验收。
- 正式内容初始化新增 `scripts.init_content_pages`，迁移和部署预检通过后可显式创建/修复内置内容页版本，并要求管理员归因与脚本引用确认；当前回归已覆盖中文数据库路径和中文 URL slug。
- 内容草稿已支持管理员发布到公开 `content_pages`、写入不可变 `content_page_versions`、按历史版本追加式回滚，并保留审计与 schema hash。
- 内容版本生命周期已补齐 `content_pages.current_version_id`、草稿 `base_version_id/base_schema_hash` 和版本 `previous_version_id`，发布/回滚不再只依赖时间顺序推断当前态。
- 管理端内容版本 diff 在保留兼容 `changes` 列表的同时新增 `semantic` 摘要，覆盖 metadata、courseUnit、sections 和 sources 的增删改移。
- 内容脚本能力已新增静态策略分析、`scriptSandbox` 契约、外部脚本资产 allowlist/SRI 静态门禁和审核/发布阶段后端下载校验；公开 render 会剥离原始脚本引用、integrity/crossorigin 元数据并返回不可执行 manifest，脚本历史版本 rollback 需走新草稿重审。
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
