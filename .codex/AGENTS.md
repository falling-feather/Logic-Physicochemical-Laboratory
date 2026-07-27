# 星序 Astra 项目指引

## 当前基线

星序 Astra 是多星系全栈学习平台：

- 工科试验室：五大学科、88 个可视化实验。
- 代码空间：`codevis/` 独立子站与多语言运行时。
- 未来星系：六个跨学科探索方向。
- Python/FastAPI 业务后端：认证、学校/班级/课程、作业、内容、学习分析、任务与审计。
- Node/C++ 静态服务：只承担审核后的浏览器资源托管。

V6.6.63 后端阶段已经完成；V7.4.12—V7.4.30 完成项目对接、前端注册/生命周期、认证与角色资源、组织治理及目标发布仓库门禁；V7.4.31—V7.4.36 完成统一三星系总览、单一全局治理、角色落点、9001 一键入口和独立集中验收，R5c 已关闭；V7.4.37 又把三角色页面统一纠正为星序 `astra` 工作区并完成教师四分区重构。V7.5.x 已完成代码空间、未来星系、课程编排、教师学习进度闭环和全仓 review；V7.5.13 在 `houduan` 建立 V8 终局规划，V7.6 起由 `主开发` 作为活动集成分支，前后端写入组使用隔离 worktree，`main` 保持稳定发布。公网 R6 继续暂缓，当前任务与恢复条件只认 `doc/02-项目规划.md`。

## 文档职责

- `README.md`：项目入口、启动、质量门禁和文档导航。
- `doc/00-项目总纲.md`：项目定位、宏观系统边界、文档控制面和协作入口。
- `doc/01-开发者文档.md`：当前实现的规范入口；`doc/01-开发者手册.md` 保留为详细实现卷。
- `doc/02-项目规划.md`：任务原件、责任组、依赖、版本、项目对接、风险和当前状态的唯一权威来源；`doc/02-更新规划.md` 只作兼容入口。
- `doc/03-开发历史.md`：V7.4.12 起的新提交和阶段结果；`doc/03-发布历史.md` 保留 V7.4.11 及以前的历史档案。
- `doc/04-部署指南.md`：环境、迁移、代理、服务、回滚和运维。
- `doc/05-UI规范模板.md`：UI、Canvas、响应式和可访问性。
- `doc/07-后端优化与设计.md`：后端/数据/权限/三端长期设计。
- `doc/08-前端页面实现索引.md`：前端页面、路由和文件定位。

完成项不得长期留在规划文档；临时过程记录不得进入 README 或开发者手册。

## 项目对接与写入

1. 当前任务是“星序 Astra｜主开发｜总控”，主开发集中分配后续小版本并独占 `主开发` 根工作区写入；`main` 只接收已收束的稳定版本，`houduan` 保留 V7.5.13 起点。
2. V7.6 只启用前端、后端两个写入组和一个只读 QA 组。任何小组没有在 `doc/02-项目规划.md` 登记正式任务、独立 worktree、允许路径和版本令牌时不得修改仓库；同一任务只设一个主责组。
3. QA 必须独立验收主开发或专业组交付；主开发自测不能替代 QA 回执。
4. `qianduan` worktree 已与 V7.5.11 基线对齐并保持干净；同步前的 V7.2 未提交实验完整保存在本地标签 `archive/qianduan-wip-before-main-sync-20260727`，该标签只用于恢复和审计，不是开发入口。
5. `主开发` 及其任务分支使用 `Vx.y.z GROUP type(scope): 中文说明（TASK-ID）`，责任组、任务编号与标题必须一致；`review` 当前冻结，只有用户重新启动 review 周期后才恢复 `reN：中文说明`。

## 工程边界

1. 业务 API 只进入 `backend/`，不要在 C++ 静态服务中恢复业务占位接口。
2. 全局前端组件初始化必须幂等；页面和实验必须有匹配的 init/destroy 清理。
3. 认证使用 HttpOnly cookie-only；敏感学习状态不得进入普通浏览器存储或 Service Worker 缓存。
4. 学校、班级、课程、协作者和作业策略是不同授权轴，优先复用 `app.services.access_control` 与现有策略服务。
5. 教师自定义脚本必须经过审核、allowlist、SRI/hash、sandbox/CSP 和版本绑定。
6. 外部投递/问题同步/审计锚定默认关闭，启用需要独立审批和真实 staging 证据。
7. 数据库结构变化必须带 Alembic、回滚考虑、SQLite 回归和真实 MySQL 门禁。

## 验证要求

- 后端：`python -m pytest backend`。
- Python 依赖：新环境/CI 使用 `backend/requirements.lock` 和 `--require-hashes`；直接约束变化后以固定 uv 版本重生成，并执行 `python backend/scripts/compile_requirements_lock.py --check`。
- Node 工具链：使用 `.node-version` 的 Node 22.20.0、npm 10.9.3 和 `npm ci --ignore-scripts`；Playwright 只从 `package-lock.json` 安装，不在安装阶段下载浏览器。
- 前端契约与 JavaScript 语法：`npm test`，必须覆盖全部 Git 跟踪的 JS/CJS/MJS。
- 用户界面：桌面与 390×844 浏览器验收，检查页面身份、交互、console、重复 ID、遮罩和溢出。
- C++/CMake：合格 C++17 工具链构建 `verify_build_manifest`；FetchContent 必须复核完整 commit，离线模式必须显式提供已验证 source，公开面 smoke 保持 `/api/info`、`/api/eval` 和私有路径 404。
- 提交前：`git diff --check`，并确认无临时数据库、构建目录、截图或本机工作区。

## Git 提交

- `主开发` 及其任务分支使用 `Vx.y.z GROUP type(scope): 中文说明（TASK-ID）`；V7.6 通过独立验收后再按计划同步到 `houduan` 与 `main`。
- `review` 分支当前只保留 V7.5.11 冻结基线；新 review 周期经用户明确启动后使用 `reN：中文说明`。
- 不提交 `WIP`、`temp`、`checkpoint` 或无实际内容的提交。
