# 星序 Astra · 多学科可视化学习平台

星序 Astra 是一个面向学习者与教师的多星系可视化学习平台。当前包含：

- **工科试验室**：数学、物理、化学、算法、生物五大学科，共 88 个交互实验。
- **代码空间**：独立子站 [`/codevis/`](codevis/README.md)，支持 JavaScript、Python、C、C++ 执行追踪。
- **未来星系**：地球与宇宙、工程、数据科学、信息技术、材料与人文等跨学科探索入口。

主站采用 Vanilla JavaScript 单页应用；Python/FastAPI 提供认证、课程、作业、内容、学习分析与治理 API；C++/Node 静态服务只公开经过审核的浏览器资源。

## 当前状态

- 前端主线已进入 V7.2 集成阶段，多星系导航、88 个实验、三端工作台与后端 schema 试点均已接入。
- 后端 V6.6.37–V6.6.63 阶段已完成，真实 MySQL、反向代理/四服务、Release 构建、回滚与 15/15 stage gate 已留证。
- 2026-07-11 全局 review 已修复首页 OffscreenCanvas 重入、协议页 404、全局控件重复初始化和 SQLite 时间适配告警，并补齐持续集成质量门禁。
- Webhook、GitHub issue sync、audit anchor 等外部通道未进入首个 RC，继续默认关闭；启用前必须单独审批并完成真实 staging 验证。

下一阶段只保留尚未完成的发布与产品化工作，见 [`doc/02-更新规划.md`](doc/02-更新规划.md)。已完成版本和验证证据统一记录在 [`doc/03-发布历史.md`](doc/03-发布历史.md)。

## 快速开始

### 1. 启动静态主站

需要 Node.js 22 或兼容版本：

```bash
node server/dev-static-server.mjs --port 8766
```

访问 `http://127.0.0.1:8766/`。该开发服务器使用显式公开白名单，不会暴露 `backend/`、`doc/`、`.git/` 或仓库根目录中的其他文件。

### 2. 启动 Python 业务后端

需要 Python 3.12+：

```bash
cd backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认数据库是本地 SQLite。生产或发布证据环境必须显式配置 MySQL、关闭自动建表，并按 [`doc/04-部署指南.md`](doc/04-部署指南.md) 执行预检、迁移、烟测和回滚检查。

联调入口：

```text
http://127.0.0.1:8766/?backendSchema=1&apiBase=http%3A%2F%2F127.0.0.1%3A8000#home
```

### 3. 可选 C++ 静态服务

需要 CMake 与完整支持 C++17 filesystem 的编译器（GCC 9.1+、现代 Clang 或 MSVC）：

```bash
cmake -S server -B server/build -DCMAKE_BUILD_TYPE=Release
cmake --build server/build --config Release
```

C++ 进程只承担静态资源和内部存活探针，业务 `/api/*` 必须由反向代理转发到 FastAPI。

## 质量门禁

```bash
# 后端全量回归；真实 MySQL 专项在未提供隔离数据库时会显式跳过
python -m pytest backend

# JavaScript 语法与前端契约
node tools/tests/run-contracts.cjs

# 工作区差异检查
git diff --check
```

GitHub Actions 还会执行独立 MySQL 8.4 发布证据和 C++ Release 构建。发布前需同时满足自动化、浏览器桌面/390×844 验收和部署清单。

## 项目结构

```text
.
├── index.html                 # 主站 SPA 外壳
├── pages/                     # 首页、星系、学科、实验与三端页面
├── shared/                    # 主站路由、组件、API client 与设计系统
├── codevis/                   # 代码空间独立子站
├── backend/                   # FastAPI、SQLAlchemy、Alembic、脚本与 pytest
├── server/                    # Node 开发静态服务与 C++ Release 静态服务
├── tools/tests/               # 前端/静态公开面契约
├── doc/                       # 开发、规划、历史、部署、UI、审查与索引文档
└── .github/workflows/         # 持续集成质量门禁
```

## 文档入口

| 文档 | 职责 |
| --- | --- |
| [`doc/01-开发者手册.md`](doc/01-开发者手册.md) | 长期架构、模块边界、开发约定与扩展方式 |
| [`doc/02-更新规划.md`](doc/02-更新规划.md) | 下一阶段目标、优先级、验收标准和不做事项 |
| [`doc/03-发布历史.md`](doc/03-发布历史.md) | 已完成版本、review 结论、验证证据与历史风险 |
| [`doc/04-部署指南.md`](doc/04-部署指南.md) | 环境、迁移、反向代理、服务、回滚与运维 |
| [`doc/05-UI规范模板.md`](doc/05-UI规范模板.md) | UI、Canvas、响应式与可访问性规范 |
| [`doc/06-实验体验与信度审查报告-20260606.md`](doc/06-实验体验与信度审查报告-20260606.md) | 实验体验与教学事实口径审查 |
| [`doc/07-后端优化与设计.md`](doc/07-后端优化与设计.md) | 后端与三端平台的长期设计决策 |
| [`doc/08-前端页面实现索引.md`](doc/08-前端页面实现索引.md) | 页面、路由、模块与实现文件定位 |
| [`doc/99-历史审视报告归档.md`](doc/99-历史审视报告归档.md) | 旧版一次性审视报告归档 |

## 核心边界

- 认证会话使用 HttpOnly cookie；前端不持久化 Bearer token 或学生敏感学习数据。
- `/api` 全状态 `no-store`，Service Worker 不缓存业务 API。
- 教师自定义脚本必须经过 allowlist、审核、SRI/hash、opaque iframe 与 CSP 边界，不能直接执行任意脚本。
- C++/Node 静态服务只公开 `index.html`、`sw.js`、`LICENSE.md`、`pages/`、`shared/`、`UI/`、`codevis/`。
- 外部投递、问题同步和审计锚定默认关闭，不能用本地 dry-run 冒充真实外部证据。

## 许可证

使用条件与第三方资源说明见 [`LICENSE.md`](LICENSE.md)。
