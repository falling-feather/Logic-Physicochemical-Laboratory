# 星序 Astra — AI 协作指南

## 项目定位

星序 Astra 是多星系可视化学习平台，不再是纯前端项目：

- 工科试验室：数学、物理、化学、算法、生物，共 88 个交互实验。
- 代码空间：`codevis/` 独立子站，提供 JavaScript、Python、C、C++ 执行追踪。
- 未来星系：宇宙、工程、数据科学、信息技术、材料与人文探索。
- 业务后端：`backend/` 中的 FastAPI + SQLAlchemy + Alembic，生产数据库目标为 MySQL。
- 静态服务：`server/` 中的 Node 开发服务和 C++ Release 服务，只公开审核后的浏览器资源。

当前基线为 V7.4.11 登录/角色外壳、后端分域及 Python/Node/C++ 依赖与产物追踪，V6.6.63 后端阶段完成。外部 Webhook、GitHub issue sync、audit anchor 默认关闭。

## 必读入口

| 文件 | 用途 |
| --- | --- |
| `README.md` | 项目概览、启动方式、质量门禁与文档索引 |
| `doc/01-开发者手册.md` | 长期架构、生命周期、编码和扩展规则 |
| `doc/02-更新规划.md` | 仅包含未来任务、优先级与验收标准 |
| `doc/03-发布历史.md` | 已完成版本、review 结论与验证证据 |
| `doc/04-部署指南.md` | MySQL、代理、服务、回滚与运维 |
| `doc/07-后端优化与设计.md` | 后端、数据、权限和三端平台设计 |
| `doc/08-前端页面实现索引.md` | 页面、路由、模块到实现文件的定位 |

## 关键实现

```text
index.html                         主站 SPA 外壳
shared/js/router.js                hash 路由、懒加载和页面生命周期
shared/js/module-selector.js       学科画廊与实验切换
shared/js/api-client.js            cookie-only API client
shared/js/backend-content.js       后端 schema 与 sandbox iframe adapter
pages/{subject}/                   学科与实验实现
pages/admin|teacher|student/       三端工作台
backend/app/main.py                FastAPI 入口
backend/app/api/endpoints/         业务路由
backend/app/services/              权限、内容、任务、审计等服务层
backend/alembic/                   连续数据库迁移
tools/tests/                       前端与静态公开面契约
tools/quality/                     Git 跟踪 JavaScript 跨平台语法门禁
```

## 开发约定

1. 页面/实验必须遵守 `init`/`destroy` 生命周期；全局初始化必须幂等，不能重复创建 DOM ID 或绑定全局监听器。
2. Canvas 必须处理 DPR、零尺寸、ResizeObserver 和离页清理；OffscreenCanvas 一旦 transfer 后不可复用原节点。
3. API 权限判断优先复用服务层，不在路由中复制学校/班级/课程范围逻辑。
4. 认证会话使用 HttpOnly cookie；禁止把 token、提交、成绩、反馈、知识状态写入 localStorage/sessionStorage。
5. `/api` 保持 `no-store`，Service Worker 不得缓存业务 API。
6. 教师脚本必须经过 allowlist、审核、SRI/hash、sandbox/CSP 与发布版本绑定；禁止放宽为任意脚本执行。
7. 静态服务只公开 `index.html`、`sw.js`、`LICENSE.md`、`pages/`、`shared/`、`UI/`、`codevis/`。
8. 数据库结构改动必须包含 Alembic 迁移、升级/降级考虑和 SQLite/MySQL 回归。
9. 完成事实进入 `03-发布历史.md`；未来任务进入 `02-更新规划.md`；不要在 README 或开发手册堆叠版本流水账。

## 最低验证

```bash
python -m pytest backend
npm ci --ignore-scripts
npm test
git diff --check
```

Node 工具链固定为 `.node-version` 中的 Node 22.20.0 和 npm 10.9.3，Playwright 必须来自 `package-lock.json`；修改 C++/CMake 时执行 Release `verify_build_manifest`，并验证 FetchContent commit 与显式离线缓存边界；修改用户可见页面时做桌面和 390×844 浏览器验收，并检查 console、重复 ID、遮罩和横向溢出。

## Git 规则

- 主线版本提交使用 `Vx.y.z 中文说明`。
- 专项 review 分支按审查批次使用 `reN：中文说明`。
- 不提交 WIP、临时数据库、截图、构建目录、测试缓存或本机 Codex/Sites 工作区。
- 不使用破坏性 reset 覆盖其他人的工作区改动。
