# 星序 Astra · 多学科可视化学习平台

星序 Astra 是一个面向学习者与教师的多星系可视化学习平台。当前包含：

- **工科试验室**：数学、物理、化学、算法、生物五大学科，共 88 个交互实验。
- **代码空间**：独立子站 [`/codevis/`](codevis/README.md)，提供 6 组课程目录、18 个“预测—运行—追踪—修正”活动以及 JavaScript、Python、C、C++ 浏览器学习运行时。
- **未来星系**：6 个跨学科课程群、18 个独立活动，以课程目录、单目标子课、Canvas 观测和按需 Three.js 互动组织地球与宇宙、工程、数据、信息、材料与人文学习。

主站采用 Vanilla JavaScript 单页应用；Python/FastAPI 提供认证、课程、作业、内容、学习分析与治理 API；C++/Node 静态服务只公开经过审核的浏览器资源。

## 当前状态

- 当前稳定实现基线为 V7.5.10。V7.5.3—V7.5.9 已交付三星系稳定课程/活动键、班级 `hidden/locked/open` 发布计划、代码空间和未来星系各 6 组/18 活动、provider-neutral 代码提交/判题契约、Cookie 会话学生上下文、星序教师课程节奏/进度/代码审阅，以及资源、性能、缓存、9001、44px 触达和键盘导航收束。QA-010 对精确提交 `9b0ea63cc7257a8eaaaca0f615de6af35248e17f` 使用真实外部 Edge 150 完成最终复验：Future 核心 hit/focus 区、教师 tablist 左右/上下/Home/End/循环行为、根宽与控制台全部通过，首轮角色权限、课程链、OJ `runner_unavailable` 诚实降级、性能、9001 和只读账本证据继续有效；最终 PASS，P0/P1/P2/P3 均为 0。当前 `review` 已从 V7.5.10 文档冻结提交 `8723dde196e70ea7ca5b1db8251dfbfa3a7736a0` 建立并进入全仓审查；旧 V6.6 `review` 引用保留为 `legacy/review-v6.6`，不改写历史。真实 MySQL、隔离 runner 与 staging 仍未补证，本机结果不得外推。唯一任务状态以 [`doc/02-项目规划.md`](doc/02-项目规划.md) 为准。
- V7.4.37 已完成星序角色层级与教师工作台纠偏：`#student/#teacher/#admin` 统一归属 `astra`，与工科试验室、代码空间、未来星系三个学习单元共同由星序统领，不再继承工科 navbar、页脚或实验课程壳；教师端改为教学总览、组织与课程、作业发布、批改与学情四分区，创建操作按需展开。外部 Edge/Chrome 已从 9001 使用仓库外本机管理员验证桌面四分区、管理员层级与精确 390×844 固定移动 dock；`npm test` 为 171/25，相关本机预览与认证后端 45 项通过。测试数据库、凭据和截图不进入仓库。
- V7.4.36 已完成 R5c 本机可用性与集中验收收尾：QA-009 对精确提交 `ef17c7bcc354b4b2a9403c357d23c4f209eb5f35` 使用全新 SQLite、独立账号和真实 Edge 150 完成 9001 单入口复验，12/12 发布语义、三角色业务/越权、Service Worker、桌面/390×844、7 张截图与同库只读总账全部通过，P0/P1/P2 为 0；两项视觉 P3 仅记录为后续可选优化。FE/UI/OPS/QA 长期组均已取消置顶并归档，当前恢复用户与主开发单一对接。首管理员未预置且运行时开关关闭时 bootstrap 为 403；经 `-BootstrapAdmin` 预置后重复请求为 409 single-use，两种状态都不会创建新管理员。
- V7.4.34 新增根目录 `astra-local.ps1`：自动建立 Python 3.12+ 隔离环境、按哈希锁安装依赖、迁移本机 SQLite，并从 `http://127.0.0.1:9001/` 同源提供主站、代码空间和 `/api`。公开面只挂载审核过的静态白名单；数据目录哈希绑定并发互斥和实例识别，same-origin-only 模式拒绝旧跨端口 API；首管理员可经交互式 stdin 引导创建，脚本不接收或保存命令行密码。该入口仅用于 development/本机验收，不替代 `deploy.ps1`、MySQL、TLS 或 R6 目标发布证据。
- V7.4.12 建立 `doc/00-项目总纲.md` 与项目对接控制面；`houduan` 继续由主开发单写。本轮 FE/UI/OPS/QA 长期只读任务已完成方案审查、概念—实装对照和独立验收，并在 V7.4.36 统一归档。
- V7.4.13 建立 19 个主站页面的只读注册表并通过 V7.4.15 独立 QA；V7.4.16 的 88 项冻结实验注册结构已通过 QA-002，V7.4.17—V7.4.18 已将 23 项升级为经离开/重入验证的 cleanup，并补齐排序与细胞结构的取消协议。QA-003 随后发现 DNA/遗传模式控件未挂载到真实 DOM，V7.4.19 已修正挂载锚点和失真的合同夹具；QA-005 已对精确提交 `572f9e314fa45f6e45b762ac0835e724b70cc9b3` 完成 DNA、光合作用与遗传的桌面/390×844 三轮独立复验并通过。V7.4.20 又恢复活动首页的固定视口裁剪，消除通用 `.page.active` 覆盖引起的 390px 根级横向溢出。
- V7.4.26 已关闭 R4b 实验模块切换生命周期：`AstraExperimentRegistry.cleanupModule(subject, id)` 只对 23 项 `verified:true` owner 执行精确 cleanup，65 项 legacy 全部保持 fail closed，0 项 missing；A→B、B→画廊、画廊→A 和整页离开由 transition generation、Zoom 前置关闭、失败中止与页面级兼容清理共同约束，迟到资源/init/焦点/相关推荐任务不能写入新模块。五大学科桌面三轮、精确 390×844、整页离开重入和独立只读复审均通过。
- V7.4.27 已关闭 R5 当前构建三角色终验：QA-007 使用全新一次性 SQLite、隔离账号和真实 Edge，证明匿名登录门禁与 Service Worker 先于首个业务写入，学生/教师/管理员只加载各自允许的 CSS/JS，角色资源与 `/api` 均不进入 CacheStorage；注册后退出并在新上下文显式登录、建课/发布、真实批量导入、入班/提交/反馈、批改、审批、用户与组织治理、审计和越权拒绝全部通过。桌面与精确 390×844、5 张截图、浏览器诊断及同库只读总账均通过，R1—R5 已形成仓库发布候选；真实 MySQL、staging 和指定目标环境发布仍只由 R6/OPS-001 关闭。
- V7.4.28 已完成 R5b 目标发布证据语义收束，并由 OPS/QA 长期组独立复审为 0 blocker：`target-release-v2` 的 51 项总闸把 target instance/origin 与 release version/revision、同包五类制品清单路径/SHA、evidence bundle 绑定，原始 evidence 数组必须精确七项、run ID 唯一，自动 raw 与目标浏览器完成时间同时受封装时刻和总闸当前时刻约束。示例域名、manifest 自选状态、匿名/自定义第八项、空壳 `ok=true`、跨环境/跨提交拼装、敏感正文和正式时间回拨均失败；目标 topology 还强制绑定可解析公网 host、外部探测引用、公网原始 API 端口不可达与四服务逐项 SCM，deploy smoke 固定 0047 组织治理列和现存 `version >= 1`，目标浏览器固定组织归档/恢复。该版本只强化仓库发布闸，未生成真实目标环境证据，R6/OPS-001 仍外部阻塞。
- V7.4.30 在 V7.4.29 的基础上补齐服务包环境参数：`deploy.ps1`/`windows_service_drill_bundle.py` 只接受 staging/production，生成的 API/worker XML、报告和 health 语义一致，默认 production 仅保持旧调用兼容；development 不得写入目标包。用户已将域名与公网发布后置，真实 MySQL、四服务、公网入口、备份恢复、监控、七证据与 51/51 保持 R6 暂缓，恢复前不宣称 staging/production 通过。
- V7.4.22 已完成认证双通道契约硬化：浏览器继续只使用 HttpOnly Cookie，非浏览器客户端保留显式 Bearer；Cookie+Bearer、重复会话 Cookie、重复 Authorization 和畸形 Authorization 全部 fail closed，不再允许凭据静默覆盖。登录响应保留的兼容 token 只供非浏览器 API 客户端使用，浏览器必须忽略且不得存储或回传。
- V7.4.23 已完成并通过 QA-008 独立验收：`#student/#teacher/#admin` 的 CSS/JS 只在 `/api/users/me` 确认权威角色后按矩阵加载；角色资源不进入 APP_SHELL、星系 HTTP fallback 或 Service Worker 共享 CacheStorage，登出、401 与跨角色切换会清理旧角色样式并整页重载。精确提交 `4ea2fe732437792a145339c8f339f7380b5e14c2` 的 163 个受跟踪 JavaScript、17/17 合同及三角色桌面/390×844、强制 Service Worker、CacheStorage 矩阵均通过；前端裁剪只减少暴露面和误执行，服务端授权仍是安全边界。
- V7.4.24 已完成 R3 管理组织受约束治理：管理员只能通过学校/班级白名单 schema、必填原因和 `expected_version` 修改元数据或执行归档/恢复；最后责任人、活动子班级、跨校注入、陈旧版本和无变化写入均被拒绝，所有成功动作审计并权威回读。Alembic 0047、活动组织写门禁、当前学情/进度归档过滤和条件式 MySQL schema 门禁已同步；真实 MySQL 仍须在指定隔离库或目标环境补证。
- V7.4.25 已关闭 R4 管理组织治理 UI：管理数据地图可按学校/班级查看 active/archived 统计并进入受限原生对话框；元数据与归档/恢复分离，双确认后只发送一次 PATCH，2xx、409 和发送后取消/超时/网络歧义均通过精确 GET 对账，权威不一致会保留写锁且禁止自动重放。教师端对归档组织关闭成员、成绩和作业策略写入，学生端明确显示 `class_archived`；路由销毁/重建竞态、焦点/Escape、44px 控件、390×844、CORS PUT 预检和统一缓存代际均已进入自动化与 Edge 隔离证明。R4b 已由 V7.4.26 关闭，QA-006 与 QA-007 均已独立通过。
- V7.4.21 已恢复现行 [`doc/09-后端阶段收束小版本开发安排.md`](doc/09-后端阶段收束小版本开发安排.md)：历史 V6.6.37—V6.6.63 结论保持只读，当前按 R1—R6 依次收束认证双通道契约、角色资源裁剪、管理组织治理、三角色终验和指定目标环境发布；任务原件和版本仍只认 `doc/02-项目规划.md`。
- 三角色工作台已接入第一方账号入口；QA-007 隔离端到端门禁现覆盖建课、入班、提交、反馈、批改、管理审批、组织治理、审计对账、越权拒绝、写入歧义、角色资源矩阵和三端 390×844。该结论只证明当前仓库候选，不替代真实 MySQL、staging 或指定目标环境 R6 发布证据。
- 后端 V6.6.37–V6.6.63 阶段已完成，真实 MySQL、反向代理/四服务、Release 构建、回滚与 15/15 stage gate 已留证；V7.4.9–V7.4.11 已完成 Python、Node 与 C++ 依赖/产物追踪门禁。
- V7.3.2 的首版目标证据闸已由 V7.4.28 `target-release-v2` 取代；没有真实域名/实例、owner、TLS、secret、备份恢复、日志监控及七份同源固定语义报告时默认延期，不能用本地基线或模板冒充正式上线。
- 2026-07-11 全局 review 已修复首页 OffscreenCanvas 重入、协议页 404、全局控件重复初始化和 SQLite 时间适配告警，并补齐持续集成质量门禁。
- Webhook、GitHub issue sync、audit anchor 等外部通道未进入首个 RC，继续默认关闭；启用前必须单独审批并完成真实 staging 验证。

下一阶段任务、认领和版本见 [`doc/02-项目规划.md`](doc/02-项目规划.md)。V7.4.12 起的新提交记录在 [`doc/03-开发历史.md`](doc/03-开发历史.md)，V7.4.11 及以前的完整证据保留在 [`doc/03-发布历史.md`](doc/03-发布历史.md)。

## 快速开始

### 推荐：9001 单入口一键启动

在 Windows PowerShell 中从仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\astra-local.ps1
```

脚本会自动创建仓库内忽略的 `.venv`、按 `backend/requirements.lock` 安装哈希锁依赖、执行 Alembic 迁移，并把前端与 API 同源启动在 `http://127.0.0.1:9001/`。数据默认保存在 `%LOCALAPPDATA%\Astra\local-preview`；再次执行会识别已经运行的星序站点，停止使用 `Ctrl+C`。

全新数据目录需要首个管理员时，使用交互式入口；密码只在隐藏输入和当前进程内短暂存在，不写入参数、脚本或仓库：

```powershell
powershell -ExecutionPolicy Bypass -File .\astra-local.ps1 -BootstrapAdmin
```

这是本机 development/验收入口，不配置域名、TLS、Windows 服务或正式 MySQL，也不能作为 staging/production 发布证据。完整边界见 [`doc/04-部署指南.md`](doc/04-部署指南.md)。

### 手动拆分 1：启动静态主站

需要 `.node-version` 指定的 Node.js 22.20.0（配套 npm 10.9.3）。先按锁安装测试/浏览器证明工具，不执行依赖安装脚本：

```bash
npm ci --ignore-scripts
node server/dev-static-server.mjs --port 8766
```

访问 `http://127.0.0.1:8766/`。该开发服务器使用显式公开白名单，不会暴露 `backend/`、`doc/`、`.git/` 或仓库根目录中的其他文件。

### 手动拆分 2：启动 Python 业务后端

需要 Python 3.12+：

```bash
cd backend
python -m pip install --require-hashes -r requirements.lock
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认数据库是本地 SQLite。生产或发布证据环境必须显式配置 MySQL、关闭自动建表，并按 [`doc/04-部署指南.md`](doc/04-部署指南.md) 执行预检、迁移、烟测和回滚检查。

`backend/requirements.txt` 是直接依赖约束输入，不能用于发布安装。依赖升级必须在独立变更中同时更新哈希锁：先安装 `uv==0.10.6`，再从仓库根目录执行 `python backend/scripts/compile_requirements_lock.py --exclude-newer YYYY-MM-DD`；CI 会重新解析并拒绝漂移。

联调入口：

```text
http://127.0.0.1:8766/?backendSchema=1&apiBase=http%3A%2F%2F127.0.0.1%3A8000#home
```

### 手动拆分 3：可选 C++ 静态服务

需要 CMake 与完整支持 C++17 filesystem 的编译器（GCC 9.1+、现代 Clang 或 MSVC）：

```bash
cmake -S server -B server/build -DCMAKE_BUILD_TYPE=Release
cmake --build server/build --config Release --target verify_build_manifest
```

C++ 进程只承担静态资源和内部存活探针，业务 `/api/*` 必须由反向代理转发到 FastAPI。FetchContent 固定 cpp-httplib v0.18.3 的完整 commit；构建旁生成并校验包含产物 SHA-256、工具链和依赖来源的 `englab_server.build-manifest.json`，离线缓存用法见 [`server/README.md`](server/README.md)。

## 质量门禁

```powershell
# 后端全量回归；真实 MySQL 专项在未提供隔离数据库时会显式跳过
python -m pytest backend

# 精确 Node/npm + package-lock；覆盖全部跟踪脚本语法与前端契约
npm ci --ignore-scripts
npm test

# 9001 三角色业务证明：先以全新 -DataDirectory 和 -BootstrapAdmin 启动服务；
# 再只在当前证明进程临时提供同一管理员用户名/密码，--out 指向仓库外空目录。
$env:ASTRA_QA_ADMIN_USERNAME = '<刚才创建的管理员用户名>'
$secret = Read-Host '管理员密码' -AsSecureString
$secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
$proofOut = Join-Path $env:TEMP ('astra-role-proof-' + [guid]::NewGuid().ToString('N'))
try {
  $env:ASTRA_QA_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
  node tools/browser/role-workflows-proof.cjs --api http://127.0.0.1:9001 --web http://127.0.0.1:9001 --out $proofOut --confirm-isolated-environment
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
  Remove-Item Env:ASTRA_QA_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:ASTRA_QA_ADMIN_USERNAME -ErrorAction SilentlyContinue
}

# 指定 staging 使用 --confirm-target-staging；API/web 必须是同一真实 HTTPS origin，
# Git 必须干净，--out 必须显式指向仓库外不存在或为空的目录，
# bootstrap token 只通过 ASTRA_ADMIN_BOOTSTRAP_TOKEN 环境注入；成功后直接使用
# <out>/target-browser-smoke.json 进入 target-release-v2 seal，完整诊断保留在同目录。

# 工作区差异检查
git diff --check
```

GitHub Actions 还会执行独立 MySQL 8.4 发布证据和 C++ Release 构建。发布前需同时满足自动化、浏览器桌面/390×844 验收和部署清单。

## 项目结构

```text
.
├── index.html                 # 主站 SPA 外壳
├── package.json/package-lock.json # Node 质量工具入口与 integrity 锁
├── pages/                     # 首页、星系、学科、实验与三端页面
├── shared/                    # 主站路由、组件、API client 与设计系统
├── codevis/                   # 代码空间独立子站
├── backend/                   # FastAPI、SQLAlchemy、Alembic、脚本与 pytest
├── server/                    # Node 开发静态服务与 C++ Release 静态服务
├── tools/quality/             # 跨平台跟踪脚本语法门禁
├── tools/tests/               # 前端/静态公开面契约
├── doc/                       # 开发、规划、历史、部署、UI、审查与索引文档
└── .github/workflows/         # 持续集成质量门禁
```

## 文档入口

| 文档 | 职责 |
| --- | --- |
| [`doc/00-项目总纲.md`](doc/00-项目总纲.md) | 项目定位、系统边界、文档控制面和协作入口 |
| [`doc/01-开发者文档.md`](doc/01-开发者文档.md) | 当前实现规范入口；链接详细开发者手册 |
| [`doc/02-项目规划.md`](doc/02-项目规划.md) | 任务原件、认领、版本、项目对接、状态和验收标准 |
| [`doc/03-开发历史.md`](doc/03-开发历史.md) | V7.4.12 起的提交、阶段结果和验证证据 |
| [`doc/03-发布历史.md`](doc/03-发布历史.md) | V7.4.11 及以前的完整发布历史档案 |
| [`doc/04-部署指南.md`](doc/04-部署指南.md) | 环境、迁移、反向代理、服务、回滚与运维 |
| [`doc/05-UI规范模板.md`](doc/05-UI规范模板.md) | UI、Canvas、响应式与可访问性规范 |
| [`doc/06-实验体验与信度审查报告-20260606.md`](doc/06-实验体验与信度审查报告-20260606.md) | 实验体验与教学事实口径审查 |
| [`doc/07-后端优化与设计.md`](doc/07-后端优化与设计.md) | 后端与三端平台的长期设计决策 |
| [`doc/08-前端页面实现索引.md`](doc/08-前端页面实现索引.md) | 页面、路由、模块与实现文件定位 |
| [`doc/09-后端阶段收束小版本开发安排.md`](doc/09-后端阶段收束小版本开发安排.md) | 后端重构阶段顺序、退出门禁、历史锚点与目标环境证据边界 |
| [`doc/99-历史审视报告归档.md`](doc/99-历史审视报告归档.md) | 旧版一次性审视报告归档 |

## 核心边界

- 认证会话使用 HttpOnly cookie；前端不持久化 Bearer token 或学生敏感学习数据。
- `/api` 全状态 `no-store`，Service Worker 不缓存业务 API。
- 教师自定义脚本必须经过 allowlist、审核、SRI/hash、opaque iframe 与 CSP 边界，不能直接执行任意脚本。
- C++/Node 静态服务只公开 `index.html`、`sw.js`、`LICENSE.md`、`pages/`、`shared/`、`UI/`、`codevis/`。
- 外部投递、问题同步和审计锚定默认关闭，不能用本地 dry-run 冒充真实外部证据。

## 许可证

使用条件与第三方资源说明见 [`LICENSE.md`](LICENSE.md)。
