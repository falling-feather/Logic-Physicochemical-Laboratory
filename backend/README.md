# 星序 Astra · Python 后端

本文档记录 v6.5 后端化第一阶段的本地开发入口。当前 Python 后端与既有 `server/` C++ 静态服务并存，先承担业务 API、内容协议、登录、密码策略、登录失败锁定、学校、班级、课程、作业、提交批改、积分流水、知识状态/班级规则统计、管理端基础 API、学校/班级深度统计、管理端列表分页搜索、待批改队列、审计元数据和认证事件审计等能力。

## 本地启动

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

首个内容协议样例会由数据库 seed 写入 `content_pages`，并经过 Pydantic schema 校验后返回：

```bash
curl http://127.0.0.1:8000/api/render/page/physics/energy-conservation
```

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
| GET | `/api/admin/content/pages` | 管理端内容页状态查看；支持分页与 slug/title/galaxy/subject 搜索 |
| GET | `/api/admin/stats` | 管理端全站统计摘要 |
| GET | `/api/admin/audit-logs` | 管理端审计日志查询，分页返回，可按 actor/action/resource/request_id/event_result/failure_reason/时间窗过滤 |
| GET | `/api/admin/submissions/pending` | 管理端待批改队列，支持 school/class/course/assignment/student/status/时间窗过滤和 limit/offset 分页 |
| GET/POST/PATCH | `/api/admin/bugs` | 缺陷/风险清单基础维护；列表支持分页、状态过滤和关键字搜索 |
| GET/POST | `/api/schools` | 当前用户可见学校 / 创建学校 |
| GET | `/api/schools/{id}/classes` | 学校内班级 |
| GET/POST | `/api/classes` | 当前用户可见班级 / 创建班级 |
| POST | `/api/classes/{id}/join` | 以学生或教师角色加入班级 |
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
| GET | `/api/classes/{id}/knowledge` | 教师查看班级知识状态与作业/正确率聚合 |
| GET | `/api/content/pages` | 当前内容页摘要 |
| GET | `/api/content/pages/{slug}` | 内容协议详情 |
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
| `ASTRA_DATABASE_URL` | `mysql+pymysql://astra:astra@127.0.0.1:3306/astra?charset=utf8mb4` | MySQL 连接字符串 |

可从 `.env.example` 复制本地配置；真实密码不要提交到仓库。

测试会覆盖为 SQLite 内存数据库，避免依赖本机 MySQL 实例。

## 验证

```bash
python -m pytest backend
```

迁移烟测：

```bash
cd backend
$env:ASTRA_DATABASE_URL='sqlite+pysqlite:///:memory:'
python -m alembic upgrade head
```

部署预检：

```bash
cd backend
python -m scripts.deploy_preflight
```

预检会检查 `ASTRA_DATABASE_URL` 可连通，并确认数据库 Alembic 当前 revision 已到 head；失败时返回非零退出码和 JSON 报告。正式部署应先执行 `python -m alembic upgrade head`，再执行预检。
