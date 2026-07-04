# 星序 Astra · Python 后端

本文档记录 v6.5 后端化第一阶段的本地开发入口。当前 Python 后端与既有 `server/` C++ 静态服务并存，先承担业务 API、内容协议、内容 seed 初始化与读取无副作用边界、正式内容初始化入口、ContentDraft 草稿、脚本审核、脚本静态分析风险等级、草稿编辑、提交/退回/撤回工作流、内容发布/版本记录/回滚、内容页 current 指针、草稿 base version/hash、版本 previous 链、发布元数据回填、管理端版本 diff、登录、密码策略、登录失败锁定、学校、班级、班级加入申请审批、学校/班级/课程访问控制服务层、课程、作业、提交批改、积分流水、知识状态/班级规则统计、个人/班级知识快照、周期重算运行记录与进程内调度器、管理端基础 API、学校/班级深度统计、管理端加入申请队列、管理端列表分页搜索、待批改队列、审计元数据和认证事件审计等能力。

## 本地启动

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

首个内容协议样例会在 `ASTRA_AUTO_CREATE_TABLES=true` 的开发/测试初始化阶段写入 `content_pages`，并经过 Pydantic schema 校验后返回：

```bash
curl http://127.0.0.1:8000/api/render/page/physics/energy-conservation
```

正式环境不会依赖启动时自动 seed。完成迁移、部署预检和首个 admin 初始化后，用显式脚本初始化内置内容页：

```bash
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts
```

脚本默认先运行部署预检，再创建或修复 `content_pages` 与 `content_page_versions`。若已有同 slug 当前版本与内置 schema 不同，默认报告冲突；确认要追加新版本时再使用 `--upgrade-existing`。存在活跃草稿时升级会被阻断，只有明确接受草稿过期风险时才使用 `--allow-stale-drafts`。`--skip-preflight` 仅用于受控测试或恢复场景。

本地账号与学校班级 API：

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/auth/register` | 本地账号注册；拒绝短密码、纯数字/纯字母、常见弱口令和包含用户名的密码 |
| POST | `/api/auth/login` | 登录并返回 Bearer token，同时写入 HttpOnly cookie；连续失败达到阈值返回 `429` 与 `Retry-After`；成功、失败和锁定事件写入审计 |
| POST | `/api/auth/logout` | 注销当前用户所有活动会话，并写入审计 |
| GET | `/api/users/me` | 当前用户 |
| POST | `/api/admin/bootstrap` | 首个管理员受控初始化；复用密码策略，公开注册仍拒绝 admin |
| GET/PATCH | `/api/admin/users` / `/api/admin/users/{id}` | 管理端用户列表与角色/状态维护；列表返回 `items/total/limit/offset/next_offset` |
| GET | `/api/admin/schools` | 管理端学校基础查看；支持分页与关键字搜索 |
| GET | `/api/admin/schools/{id}/stats` | 管理端学校深度统计，聚合班级、成员、课程、作业、提交、事件和积分 |
| GET | `/api/admin/classes` | 管理端班级基础查看，可按学校过滤，支持分页与关键字搜索 |
| GET | `/api/admin/classes/{id}/stats` | 管理端班级深度统计，含预期提交、待批改比例、积分和平均得分 |
| GET/PATCH | `/api/admin/class-join-requests` / `/api/admin/class-join-requests/{id}` | 管理端班级加入申请队列与审批；队列支持 school/class/user/role/status/q/时间窗过滤 |
| GET | `/api/admin/content/pages` | 管理端内容页状态查看；支持分页与 slug/title/galaxy/subject 搜索，返回 `schema_hash/current_version_id/published_*` |
| GET | `/api/admin/content/drafts` | 管理端内容草稿队列；支持 status/script_review_status/script_risk_level/author/q 分页过滤，返回 `schema_hash/base_version_id/base_schema_hash/script_risk_level/script_analysis` |
| GET | `/api/admin/content/page-versions` | 管理端内容版本历史；支持 slug/source_draft/restored_from/q 分页过滤，返回 `previous_version_id` |
| GET | `/api/admin/content/page-versions/{id}/diff` | 管理端内容版本 schema diff；默认沿显式 `previous_version_id` 链对比，`base_version_id` 可指定基线，跨 slug 返回 `422` |
| GET | `/api/admin/stats` | 管理端全站统计摘要 |
| GET | `/api/admin/audit-logs` | 管理端审计日志查询，分页返回，可按 actor/action/resource/request_id/event_result/failure_reason/时间窗过滤 |
| GET | `/api/admin/submissions/pending` | 管理端待批改队列，支持 school/class/course/assignment/student/status/时间窗过滤和 limit/offset 分页 |
| GET/POST/PATCH | `/api/admin/bugs` | 缺陷/风险清单基础维护；列表支持分页、状态过滤和关键字搜索 |
| GET/POST | `/api/schools` | 当前用户可见学校 / 创建学校 |
| GET | `/api/schools/{id}/classes` | 学校内班级 |
| GET/POST | `/api/classes` | 当前用户可见班级 / 创建班级 |
| POST | `/api/classes/{id}/join` | 以学生或教师角色加入班级 |
| POST | `/api/classes/{id}/join-requests` | 创建班级加入申请；不立即生成成员关系 |
| GET | `/api/classes/{id}/join-requests` | 班级教师或管理员查看加入申请，可按 `status` 过滤 |
| PATCH | `/api/classes/{id}/join-requests/{request_id}` | 班级教师或管理员审批加入申请，支持 `approved` / `rejected` |
| GET/POST | `/api/courses` | 当前用户可见课程 / 教师创建课程 |
| POST | `/api/courses/{id}/classes` | 将课程挂接到班级 |
| GET/POST | `/api/courses/{id}/units` | 课程单元列表 / 教师创建单元 |
| GET | `/api/courses/{id}/assignments` | 课程作业列表 |
| POST | `/api/courses/{id}/units/{unit_id}/assignments` | 教师创建作业 |
| GET/POST | `/api/learning-events` | 学习事件查询 / 记录访问、提交、完成等事件 |
| POST | `/api/assignments/{id}/submissions` | 学生提交作业 |
| GET | `/api/assignments/{id}/submissions` | 学生查看本人提交 / 教师查看作业提交 |
| PATCH | `/api/submissions/{id}/grade` | 教师批改作业并生成积分流水 |
| GET | `/api/points/ledger` | 查询个人或班级范围积分流水 |
| GET | `/api/progress/me` | 当前用户个人进度摘要 |
| GET | `/api/progress/users/{id}` | 教师查看班级内学生进度摘要 |
| GET | `/api/knowledge/me` | 当前用户知识状态规则统计，可按班级/课程/时间窗过滤 |
| POST | `/api/knowledge/me/snapshots` | 当前用户按时间窗重算并写入个人知识快照，重复窗口幂等更新 |
| GET | `/api/knowledge/me/snapshots` | 当前用户分页查看自己的知识快照，可按班级、课程、粒度和时间窗过滤 |
| GET | `/api/classes/{id}/knowledge` | 教师查看班级知识状态与作业/正确率聚合 |
| POST | `/api/classes/{id}/knowledge/snapshots` | 教师或管理员按时间窗重算并写入班级知识快照，重复窗口幂等更新 |
| GET | `/api/classes/{id}/knowledge/snapshots` | 教师或管理员分页查看班级知识快照，可按课程、粒度和时间窗过滤 |
| GET | `/api/content/pages` | 当前已发布内容页摘要 |
| GET | `/api/content/pages/{slug}` | 已发布内容协议详情 |
| POST | `/api/content/drafts` | 教师或管理员创建内容草稿；不会写入公开 `content_pages`，会记录草稿 schema hash、当前 published base 版本和脚本静态分析结果 |
| GET | `/api/content/drafts/{id}` | 草稿作者或管理员读取单条草稿 |
| PATCH | `/api/content/drafts/{id}` | 草稿作者或管理员编辑 `draft` / `changes_requested` 草稿；`schema.slug` 必须保持目标 slug，更新会重算 schema hash、脚本分析与脚本审核状态，且不会自动 rebase |
| POST | `/api/content/drafts/{id}/submit` | 草稿作者或管理员提交审核；允许 `draft` / `changes_requested` 进入 `submitted` |
| POST | `/api/content/drafts/{id}/withdraw` | 草稿作者或管理员撤回活跃草稿；撤回后不再发布，可重新创建同目标草稿 |
| POST | `/api/content/drafts/{id}/request-changes` | 管理员退回已提交草稿，记录退回人、时间和必填备注 |
| POST | `/api/content/drafts/{id}/publish` | 管理员发布已提交草稿到公开内容页，并写入不可变版本记录、current 指针和 previous 链 |
| PATCH | `/api/content/drafts/{id}/script-review` | 管理员审核允许脚本的草稿；作者不能自审，阻断级脚本策略结果不可审核通过 |
| POST | `/api/content/page-versions/{id}/rollback` | 管理员按历史版本追加式回滚，生成新的当前版本 |
| GET | `/api/render/page/{slug}` | 前端可渲染页面结构 |

## 前端 schema smoke

默认前端不会请求后端 schema。启动 API 后，再从项目根目录启动静态服务：

```bash
node server/dev-static-server.mjs --port 8766
```

访问本地试点：

```text
http://localhost:8766/?backendSchema=1&apiBase=http%3A%2F%2F127.0.0.1%3A8000#physics/energy-conservation
```

`backendSchema=1` 打开试点 adapter，`apiBase=` 指向本地 FastAPI。也可用 `CONFIG.backend.apiBaseUrl` 或 localStorage `astra-api-base` 设置 API 地址。默认静态页面保持回退，不依赖后端可用。

## 配置

配置使用 `ASTRA_` 前缀环境变量：

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `ASTRA_ENVIRONMENT` | `development` | 运行环境 |
| `ASTRA_API_PREFIX` | `/api` | API 前缀 |
| `ASTRA_API_CACHE_CONTROL` | `no-store` | API 响应默认缓存策略；业务 JSON 默认不进入浏览器或中间层缓存 |
| `ASTRA_AUTO_CREATE_TABLES` | `false` | 是否启动时自动建表，开发临时可用，正式迁移应使用 Alembic |
| `ASTRA_SESSION_COOKIE_NAME` | `astra_session` | 登录会话 cookie 名称 |
| `ASTRA_SESSION_DAYS` | `7` | 登录会话有效天数 |
| `ASTRA_LOGIN_MAX_ATTEMPTS` | `5` | 登录失败锁定阈值 |
| `ASTRA_LOGIN_LOCKOUT_SECONDS` | `900` | 达到失败阈值后的锁定秒数 |
| `ASTRA_LOGIN_ATTEMPT_WINDOW_SECONDS` | `900` | 统计连续失败的时间窗口 |
| `ASTRA_AUDIT_IP_HASH_SALT` | `astra-dev-audit-salt` | 审计中客户端 IP 哈希盐；生产环境应替换 |
| `ASTRA_ADMIN_BOOTSTRAP_TOKEN` | 空 | 首个管理员初始化令牌；生产环境必须配置 |
| `ASTRA_CORS_ORIGINS` | `http://127.0.0.1:8766,http://localhost:8766` | 允许访问 API 的前端来源白名单 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED` | `false` | 是否随 FastAPI lifespan 启动知识快照进程内调度器 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START` | `false` | 调度器启动后是否立即检查一次到期窗口 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_INTERVAL_SECONDS` | `300` | 调度器轮询间隔，最低 30 秒 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_DAILY_ENABLED` | `true` | 是否启用每日窗口调度 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_DAILY_HOUR` | `3` | 每日重算在 UTC 当日达到该小时后重算前一日窗口 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_WEEKLY_ENABLED` | `true` | 是否启用每周窗口调度 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_WEEKLY_WEEKDAY` | `0` | 每周重算星期，0 表示周一 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_WEEKLY_HOUR` | `4` | 每周重算在配置星期达到该小时后重算上一自然周 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_RETRY_ATTEMPTS` | `3` | 失败窗口在调度器中允许的最大尝试次数 |
| `ASTRA_DATABASE_URL` | `mysql+pymysql://astra:astra@127.0.0.1:3306/astra?charset=utf8mb4` | MySQL 连接字符串 |

可从 `.env.example` 复制本地配置；真实密码不要提交到仓库。

测试会覆盖为 SQLite 内存数据库，避免依赖本机 MySQL 实例。

## 服务层边界

- `app.services.access_control` 负责学校、班级和课程范围判断，普通业务端点不再各自复制 `_require_*` helper；后续权限矩阵扩展应优先在这里收口。
- `app.services.class_join_requests` 负责加入申请审批状态流转和成员关系补齐。
- `app.services.audit` 负责写入审计日志及 request_id、IP 哈希、user-agent 等请求元数据。
- `app.services.content_catalog` 负责内容页 seed、正式内容初始化、已发布 schema 读取和内容页摘要；`/api/content/pages*` 与 `/api/render/*` 查询只读 published 当前记录，不在 GET 路径隐式写库；正式初始化会显式创建/修复内置内容页版本，默认不覆盖已有差异版本。
- `app.services.content_script_policy` 负责内容草稿脚本静态分析；当前识别脚本引用、外链脚本、事件处理器、阻断协议、路径穿越和内联 `<script>`，并输出 `script_risk_level` 与 `script_analysis`。这只是静态 policy scan，不是脚本沙箱执行。
- `PATCH /api/content/drafts/{id}` 负责草稿编辑闭环：仅允许作者或管理员编辑 `draft` / `changes_requested` 草稿，禁止 retarget 到其他 slug，保存时重算 `schema_hash/script_analysis/script_risk_level`，并清空旧脚本审核元数据；`base_version_id/base_schema_hash` 保持创建时基线，发布前仍由 stale guard 拦截过期草稿。
- `/api/content/drafts/{id}/submit`、`/request-changes`、`/withdraw` 与 `/publish` 负责草稿状态流转；创建草稿时绑定当前 published base 版本和 hash，记录脚本静态分析结果，发布前校验 base 未过期并复核脚本 policy，发布后回填 page/version/publisher 元数据，审计只记录状态和版本元数据，不记录完整 schema。
- `/api/content/page-versions/{id}/rollback` 负责内容版本追加式回滚：更新 `content_pages.current_version_id/schema_hash/published_*` 当前态、追加带 `previous_version_id` 的 `content_page_versions`，并在审计中只记录版本元数据与 schema hash，不记录完整 schema。
- `app.services.knowledge_snapshot_runs` 与 `app.services.knowledge_snapshot_scheduler` 负责知识快照窗口重算、运行记录和单进程调度。

## 验证

```bash
python -m pytest backend
```

权限范围回归可单独运行：

```bash
python -m pytest backend/tests/test_access_control.py
```

迁移烟测：

```bash
cd backend
$env:ASTRA_DATABASE_URL='sqlite+pysqlite:///:memory:'
python -m alembic upgrade head
```

当前 Alembic head：`20260704_0018`（内容草稿脚本静态分析元数据）。

知识快照周期重算：

```bash
cd backend
python -m scripts.rebuild_knowledge_snapshots --granularity day
python -m scripts.rebuild_knowledge_snapshots --granularity week --date 2026-07-03
```

脚本按日或自然周对齐窗口，重算活跃班级已挂接课程的个人/班级快照，并写入 `knowledge_snapshot_runs` 运行记录；失败时输出 JSON 并返回非零退出码。

知识快照进程内调度器默认关闭。生产启用时应先完成 Alembic 迁移和部署预检，再设置 `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED=true`；调度器当前适合单 worker / 单副本运行，多进程锁、外部任务队列和告警仍是后续部署增强项。

部署预检：

```bash
cd backend
python -m scripts.deploy_preflight
```

预检会检查 `ASTRA_DATABASE_URL` 可连通，并确认数据库 Alembic 当前 revision 已到 head；失败时返回非零退出码和 JSON 报告。正式部署应先执行 `python -m alembic upgrade head`，再执行预检。

部署 smoke：

```bash
cd backend
python -m scripts.deploy_smoke --require-mysql
```

smoke 会复用部署预检，再检查当前模型期望表是否全部存在，并用同一配置启动 FastAPI TestClient 访问 `/api/health`。脚本运行时会临时关闭自动建表和知识快照调度器，只验证迁移后的现有状态。`--require-mysql` 用作生产门禁：如果当前连接不是 MySQL 方言会返回非零退出码；本地或 CI 需要覆盖临时库时可追加 `--database-url`。

正式内容初始化：

```bash
cd backend
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts
```

脚本输出 JSON 报告；非 dry-run 写入前必须确认内置脚本引用已审核。若不传 `--publisher-user-id`，脚本会选择第一个 active admin 作为发布归因；生产环境建议显式传入。
