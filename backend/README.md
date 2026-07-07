# 星序 Astra · Python 后端

本文档记录 v6.5 后端化第一阶段的本地开发入口。当前 Python 后端与既有 `server/` C++ 静态服务并存，先承担业务 API、内容协议、内容 seed 初始化与读取无副作用边界、正式内容初始化入口、ContentDraft 草稿、脚本审核、脚本静态分析风险等级、脚本 sandbox 契约、脚本资产 allowlist/SRI 静态门禁、脚本资产下载校验证据、公开 render 脚本 manifest 脱敏与沙箱执行契约头、稳定 `sectionId/sourceId` 内容身份、草稿编辑、提交/退回/撤回工作流、active 草稿数据库唯一约束、内容发布/版本记录/回滚、发布/回滚冲突 409、脚本历史版本 rollback 重审门禁、内容页 current 指针、草稿 base version/hash、版本 previous 链、发布元数据回填、管理端版本 JSON path diff 敏感预览脱敏与带显式稳定 ID 字段的 semantic 富语义摘要、登录、密码策略、登录失败锁定、活动会话列表与单会话撤销、会话设备标识与 last_seen 追踪/节流、管理员密码重置、用户自助密码重置令牌、密码重置 token 留存清理脚本、禁用用户会话撤销、用户名大小写规范化与数据库级 normalized key 唯一约束、必填文本修剪后校验、学校、班级、班级加入申请审批、学校/班级/课程访问控制服务层、课程、作业、提交批改、跨班级提交唯一性、学生资源状态可见性、学生侧作业历史/复盘只读入口、积分流水、知识状态/班级规则统计、个人/班级知识快照、周期重算运行记录、进程内调度器、数据库租约防重入与自动心跳、管理端知识快照运行列表/健康摘要、协作式取消、手动 requeue 与调度积压摘要、管理端基础 API、学校/班级深度统计、管理端加入申请队列、管理端列表分页搜索、管理端内容页数据库侧分页、中文路径/中文 slug 回归、待批改队列、缺陷记录外部 issue 链接、审计元数据、认证事件审计、审计日志链式哈希、审计链完整性校验、审计日志 JSON/CSV 明细导出、报表摘要导出、审计高频候选摘要、审计留存预检、本地审计归档包导出/Manifest 校验和导出/摘要行为审计留痕等能力。

## 本地启动

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

首个内容协议样例会在 `ASTRA_AUTO_CREATE_TABLES=true` 的开发/测试初始化阶段写入 `content_pages`，并经过 Pydantic schema 校验后返回。内置 seed 已升级到 `2026.07-v6.5-schema.2`，所有 section/source 都带稳定 `sectionId/sourceId`：

```bash
curl http://127.0.0.1:8000/api/render/page/physics/energy-conservation
```

正式环境不会依赖启动时自动 seed。完成迁移、部署预检和首个 admin 初始化后，用显式脚本初始化内置内容页：

```bash
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts
```

脚本默认先运行部署预检，再创建或修复 `content_pages` 与 `content_page_versions`。若已有同 slug 当前版本与内置 schema 不同，默认报告冲突；确认要追加新版本时再使用 `--upgrade-existing`。存在活跃草稿时升级会被阻断，只有明确接受草稿过期风险时才使用 `--allow-stale-drafts`。`--skip-preflight` 仅用于受控测试或恢复场景。

当前回归已覆盖中文目录和中文 SQLite 文件名下的 Alembic 迁移、正式初始化 CLI、JSON 报告和内容页 current version 写入；内容发布链路也覆盖中文 slug 经百分号编码后的公开读取、后台搜索与版本过滤。

本地账号与学校班级 API：

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/auth/register` | 本地账号注册；用户名会修剪并小写落库，重复校验大小写不敏感；拒绝短密码、纯数字/纯字母、常见弱口令和包含用户名的密码 |
| POST | `/api/auth/login` | 登录并返回 Bearer token，同时写入 HttpOnly cookie；用户名按规范化值大小写不敏感匹配，连续失败达到阈值返回 `429` 与 `Retry-After`；成功登录会记录 best-effort 设备标识、登录 user-agent、`last_seen_at` 和 IP 哈希；成功、失败和锁定事件写入审计 |
| POST | `/api/auth/logout` | 注销当前用户所有活动会话，并写入审计 |
| POST | `/api/auth/password-reset/request` | 用户自助密码重置请求；响应始终泛化为 `ok`，active 用户会生成哈希存储的一次性 token，并按账号哈希/IP 哈希冷却；生产环境不返回 token，本地调试也必须显式开启 `ASTRA_PASSWORD_RESET_RETURN_TOKEN_FOR_DEV=true` |
| POST | `/api/auth/password-reset/confirm` | 使用一次性 token 重置密码；行锁消费 token，复用密码强度策略，成功后撤销用户未撤销会话、清理登录失败桶，并写入不含明文密码或 token 的 `auth.password_reset.*` 审计 |
| GET | `/api/auth/sessions` | 当前用户活动会话列表；只返回未撤销、未过期会话，并标记 `is_current`；返回 `device_label`、登录时 `user_agent`、`last_seen_at` 等会话摘要，不返回 token 或 IP 明文 |
| DELETE | `/api/auth/sessions/{id}` | 撤销当前用户自己的单个活动会话；撤销当前会话会清理 cookie，并写入 `auth.session.revoke` 审计 |
| GET | `/api/users/me` | 当前用户；已撤销、过期或非 active 用户会话返回 `401` |
| POST | `/api/admin/bootstrap` | 首个管理员受控初始化；用户名会修剪并小写落库，复用密码策略，公开注册仍拒绝 admin |
| GET/PATCH | `/api/admin/users` / `/api/admin/users/{id}` | 管理端用户列表与角色/状态维护；列表返回 `items/total/limit/offset/next_offset`；把用户置为 `disabled` 时撤销未撤销会话，并在 `admin.user.update` 快照记录 `revoked_sessions` |
| POST | `/api/admin/users/{id}/password-reset` | 管理员重置用户密码；复用密码强度策略，成功后撤销目标用户未撤销会话、清理登录失败桶，并写入不含密码明文或 hash 的 `admin.user.password_reset` 审计 |
| GET | `/api/admin/schools` | 管理端学校基础查看；支持分页与关键字搜索 |
| GET | `/api/admin/schools/{id}/stats` | 学校深度统计；全局管理员或该校 active teacher/admin 读取，聚合班级、成员、课程、作业、提交、事件和积分 |
| GET | `/api/admin/classes` | 管理端班级基础查看，可按学校过滤，支持分页与关键字搜索 |
| GET | `/api/admin/classes/{id}/stats` | 班级深度统计；全局管理员或该班 active teacher 读取，含预期提交、待批改比例、积分和平均得分 |
| GET/PATCH | `/api/admin/class-join-requests` / `/api/admin/class-join-requests/{id}` | 管理端班级加入申请队列与审批；队列支持 school/class/user/role/status/q/时间窗过滤 |
| GET | `/api/admin/content/pages` | 管理端内容页状态查看；数据库侧支持 status 过滤、limit/offset 分页与 slug/title/galaxy/subject/layout 搜索，返回 `schema_hash/current_version_id/published_*` |
| GET | `/api/admin/content/drafts` | 管理端内容草稿队列；支持 status/script_review_status/script_risk_level/author/q 分页过滤，返回 `schema_hash/base_version_id/base_schema_hash/script_risk_level/script_analysis` |
| GET | `/api/admin/content/page-versions` | 管理端内容版本历史；支持 slug/source_draft/restored_from/q 分页过滤，返回 `previous_version_id` |
| GET | `/api/admin/content/page-versions/{id}/diff` | 管理端内容版本 schema diff；默认沿显式 `previous_version_id` 链对比，`base_version_id` 可指定基线，跨 slug 返回 `422`；响应保留兼容 `changes` 并新增 `semantic` 摘要，section/source 变更项显式返回 `section_id_before/after` 与 `source_id_before/after`；raw changes 与 semantic field/prop changes 会对 token/key/secret/script/sandbox/integrity/crossorigin 等敏感字段返回结构化 redaction preview |
| GET | `/api/admin/stats` | 管理端全站统计摘要；仅全局管理员读取 |
| GET | `/api/admin/knowledge-snapshot-runs` | 管理端知识快照运行记录；支持 status/granularity/trigger_source/时间窗分页过滤，不返回 `scheduler_lease_token` |
| GET | `/api/admin/knowledge-snapshot-runs/health` | 管理端知识快照运行健康摘要；汇总 stale running、lease expiring、claimable、retryable/exhausted failed、problem runs，不返回 lease token 或 metadata |
| GET | `/api/admin/knowledge-snapshot-runs/queue` | 管理端知识快照调度积压摘要；区分 dispatchable now、claimable by lease rule、manual requeue 和 blocked runs，不返回 lease token 或 metadata |
| POST | `/api/admin/knowledge-snapshot-runs/{id}/cancel` | 管理端协作式取消 pending 或带 scheduler lease 的 running 知识快照 run；标记 `cancelled`、清空租约并写入 `admin.knowledge_snapshot_run.cancel` 审计 |
| POST | `/api/admin/knowledge-snapshot-runs/{id}/requeue` | 管理端手动重排 failed、cancelled 或过期带租约 running 知识快照 run；重置为 pending 并清空错误与租约，pending 幂等，active/legacy running 与 success 返回 `409` |
| GET | `/api/admin/audit-logs` | 管理端审计日志查询，分页返回，可按 actor/action/resource/request_id/event_result/failure_reason/时间窗过滤；响应包含 `prev_hash/current_hash` 应用层链式哈希 |
| GET | `/api/admin/audit-logs/export` | 管理端审计日志 JSON 导出；复用审计筛选与倒序排序，不使用 offset，默认 `limit=1000`、最大 `5000`，默认不返回 `snapshot_json`，但保留 `prev_hash/current_hash`；成功导出后写入 `admin.audit.export`，只记录筛选条件和导出摘要 |
| GET | `/api/admin/audit-logs/export.csv` | 管理端审计日志 CSV 导出；复用 JSON 导出的筛选、排序、`limit/truncated` 和 `include_snapshot` 边界，响应为下载附件并返回 `X-Audit-Export-*` 元数据头；默认快照列为空，显式包含快照时写入紧凑 JSON 字符串，CSV 表头包含 `prev_hash/current_hash`，文本单元格会中和表格公式前缀；成功导出后同样写入 `admin.audit.export` 摘要 |
| GET | `/api/admin/audit-logs/report` | 管理端审计日志 JSON 报表摘要；复用审计筛选，按 action/resource_type/actor_role/event_result/failure_reason 聚合，`bucket_limit` 默认 20、最大 100；成功生成后写入 `admin.audit.report` 摘要 |
| GET | `/api/admin/audit-logs/report.csv` | 管理端审计日志 CSV 报表摘要；与 JSON 报表同源，响应为下载附件并返回 `X-Audit-Report-*` 元数据头，只导出聚合行，不导出原始审计条目 |
| GET | `/api/admin/audit-logs/retention-plan` | 管理端审计留存预检；复用审计筛选，按 `ASTRA_AUDIT_LOG_RETENTION_DAYS`、`retention_days` 或 `before` 计算归档候选、临期数量、聚合桶和哈希链边界；成功生成后写入 `admin.audit.retention_plan` 摘要，响应显式标记不导出归档、不删除、不提供 WORM 或外部锚定 |
| GET | `/api/admin/audit-logs/chain-integrity` | 管理端审计链完整性校验；按 `from/to`、`limit` 和 `issue_limit` 顺序扫描审计日志，重算 `current_hash`、检查相邻 `prev_hash`、把历史空 hash 标记为 partial，并返回 `valid/partial/invalid`、计数和受限 issue 样本；成功生成后写入 `admin.audit.chain_integrity` 摘要，不修复、不删除、不提供 WORM 或外部锚定 |
| GET | `/api/admin/audit-logs/high-frequency` | 管理端审计高频候选摘要；复用审计筛选，默认查看最近 24 小时，按 action、actor/action、ip/action、resource/action 和 failure_reason 聚合候选；成功生成后写入 `admin.audit.high_frequency` 摘要，不记录候选明细 |
| GET | `/api/admin/submissions/pending` | 待批改队列；全局管理员可跨范围过滤，教师仅可读取本人任教班级内 `submitted/returned` 提交，`status=graded` 仍为管理员治理视图 |
| GET/POST/PATCH | `/api/admin/bugs` | 缺陷/风险清单基础维护；可记录外部 issue provider/id/url，列表支持分页、状态过滤和关键字搜索 |
| GET/POST | `/api/schools` | 当前用户可见学校 / 创建学校 |
| GET | `/api/schools/{id}/classes` | 学校内班级 |
| GET/POST | `/api/classes` | 当前用户可见班级 / 创建班级 |
| POST | `/api/classes/{id}/join` | legacy/direct join 兼容入口：学生可直接生成学校/班级成员关系；teacher 角色 direct join 仅保留给全局 admin 或受控导入/邀请码路径，非 admin 教师必须走 join request 审批；若同角色已有 pending 申请，会同步转为 approved |
| GET | `/api/classes/{id}/members` | 班级教师或管理员查看成员列表；默认 `status=active`，可按 `role=student/teacher` 和 `status=active/inactive` 过滤 |
| PATCH | `/api/classes/{id}/members/{membership_id}` | 维护成员状态；班级教师仅可维护 student membership，管理员可维护 student/teacher membership，均只支持 `active/inactive` 并写入审计 |
| PATCH | `/api/classes/{id}/members/batch-status` | 批量维护成员状态；班级教师仅可批量维护 student membership，全局 admin 可批量维护 student/teacher membership；整批 all-or-nothing，最终不能让 active teacher 归零 |
| POST | `/api/classes/{id}/teachers/transfer` | 班级 teacher membership 转让；仅全局 admin 可把源 active teacher 转给同校 active teacher/admin，目标 membership 不存在则创建、inactive 则恢复，可选择停用源 teacher |
| POST | `/api/classes/{id}/join-requests` | 审批流入口：创建班级加入申请；不立即生成成员关系 |
| GET | `/api/classes/{id}/join-requests` | 班级教师或管理员查看加入申请，可按 `status` 过滤 |
| PATCH | `/api/classes/{id}/join-requests/{request_id}` | 班级教师或管理员审批加入申请，支持 `approved` / `rejected` |
| GET/POST | `/api/courses` | 当前用户可见课程 / 教师创建课程；学生仅返回本人 active 班级内 published 课程 |
| POST | `/api/courses/{id}/classes` | 将课程挂接到班级 |
| PATCH | `/api/courses/{id}/owner` | 课程 owner 转让；课程创建者或全局 admin 可转给同校 active teacher/admin，目标原 active collaborator 会置为 inactive |
| GET/POST | `/api/courses/{id}/collaborators` | 课程协作者列表与创建；课程创建者或全局 admin 可创建 active editor，active editor 可读取列表但不能管理协作者 |
| PATCH | `/api/courses/{id}/collaborators/{collaborator_id}` | 课程协作者状态维护；课程创建者或全局 admin 可将 editor 在 `active/inactive` 间切换 |
| GET/POST | `/api/courses/{id}/units` | 课程单元列表 / 课程创建者、active editor 或全局 admin 创建单元；学生仅可读取 published 课程下的 published 单元 |
| GET | `/api/courses/{id}/assignments` | 课程作业列表；学生仅可读取 published 单元下的 active 作业 |
| POST | `/api/courses/{id}/units/{unit_id}/assignments` | 课程创建者、active editor 或全局 admin 创建作业 |
| GET/POST | `/api/learning-events` | 学习事件查询 / 记录访问、提交、完成等事件；学生读写仅计入 published 课程、published 单元和 active 作业；教师查询按本班 teacher scope 收束 |
| POST | `/api/assignments/{id}/submissions` | 学生按 `class_id` 提交作业；同一 `assignment/student/class` 只能提交一次，同一作业挂到多个班级时可分别提交；提交目标必须位于 published 课程和 published 单元下且作业 active |
| GET | `/api/assignments/{id}/review` | 学生侧作业复盘入口；可用 `class_id` 定位班级提交，published 课程/单元内 active 未提交返回可提交，已提交、closed 或 archived 返回只读和 `submit_block_reason` |
| GET | `/api/assignments/{id}/submissions` | 学生查看本人提交 / 教师查看作业提交 |
| PATCH | `/api/submissions/{id}/grade` | 教师批改作业，并按作业积分规则目标值与当前 submission 已入账 `assignment_grade` 积分差额生成流水 |
| GET | `/api/points/ledger` | 查询个人或班级范围积分流水；教师查询按本班 teacher scope 收束 |
| GET/PATCH | `/api/points/assignments/{id}/rule` | 读取/维护 assignment 级积分规则；学校 teacher/admin 可读，课程创建者、active editor 或全局 admin 可写，默认规则不额外落库 |
| GET | `/api/progress/me` | 当前用户个人进度摘要；学生个人口径仅计入当前可见资源 |
| GET | `/api/progress/users/{id}` | 教师查看班级内学生进度摘要；要求本班 teacher scope |
| GET | `/api/knowledge/me` | 当前用户知识状态规则统计，可按班级/课程/时间窗过滤；学生个人口径仅计入 published 课程、published 单元和 active 作业 |
| POST | `/api/knowledge/me/snapshots` | 当前用户按时间窗重算并写入个人知识快照，重复窗口幂等更新；学生快照使用同一可见性口径 |
| GET | `/api/knowledge/me/snapshots` | 当前用户分页查看自己的知识快照，可按班级、课程、粒度和时间窗过滤；学生列表不暴露 hidden course 旧快照 |
| GET | `/api/classes/{id}/knowledge` | 教师查看班级知识状态与作业/正确率聚合 |
| POST | `/api/classes/{id}/knowledge/snapshots` | 教师或管理员按时间窗重算并写入班级知识快照，重复窗口幂等更新 |
| GET | `/api/classes/{id}/knowledge/snapshots` | 教师或管理员分页查看班级知识快照，可按课程、粒度和时间窗过滤 |
| GET | `/api/content/pages` | 当前已发布内容页摘要 |
| GET | `/api/content/pages/{slug}` | 已发布内容协议详情；公开响应会移除原始脚本引用，仅保留不可执行 `scriptManifest`，manifest 内含沙箱 enforcement/capabilities |
| POST | `/api/content/drafts` | 教师或管理员创建内容草稿；不会写入公开 `content_pages`，会记录草稿 schema hash、当前 published base 版本和脚本静态分析结果；新写入 schema 必须为每个 section/source 提供稳定 `sectionId/sourceId`；同一作者同一目标页只允许一个 active 草稿，数据库唯一约束并发兜底 |
| GET | `/api/content/drafts/{id}` | 草稿作者或管理员读取单条草稿 |
| PATCH | `/api/content/drafts/{id}` | 草稿作者或管理员编辑 `draft` / `changes_requested` 草稿；`schema.slug` 必须保持目标 slug，更新会复核稳定 `sectionId/sourceId`，重算 schema hash、脚本分析与脚本审核状态，且不会自动 rebase |
| POST | `/api/content/drafts/{id}/submit` | 草稿作者或管理员提交审核；允许 `draft` / `changes_requested` 进入 `submitted` |
| POST | `/api/content/drafts/{id}/withdraw` | 草稿作者或管理员撤回活跃草稿；撤回会清空 active key，之后可重新创建同目标草稿 |
| POST | `/api/content/drafts/{id}/request-changes` | 管理员退回已提交草稿，记录退回人、时间和必填备注 |
| POST | `/api/content/drafts/{id}/publish` | 管理员发布已提交草稿到公开内容页，发布前会以 `409` 复核稳定 `sectionId/sourceId` 契约，并写入不可变版本记录、current 指针和 previous 链；版本唯一冲突或同一草稿重复产出版本会返回 `409` |
| PATCH | `/api/content/drafts/{id}/script-review` | 管理员审核允许脚本的草稿；作者不能自审，阻断级脚本策略结果不可审核通过 |
| POST | `/api/content/page-versions/{id}/rollback` | 管理员按历史版本追加式回滚，生成新的当前版本；版本唯一冲突会返回 `409` |
| GET | `/api/render/page/{slug}` | 前端可渲染页面结构；公开响应会移除原始脚本引用，仅保留不可执行 `scriptManifest`，并返回 `X-Astra-Content-Script-*` 沙箱契约头 |

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
| `ASTRA_SESSION_LAST_SEEN_UPDATE_SECONDS` | `300` | 当前会话 last_seen 刷新节流窗口；同一 IP 哈希在窗口内不重复写库，设为 `0` 可关闭节流 |
| `ASTRA_PASSWORD_RESET_TOKEN_TTL_SECONDS` | `1800` | 用户自助密码重置 token 有效期，最低 60 秒 |
| `ASTRA_PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS` | `300` | 密码重置请求冷却窗口；按账号哈希和客户端 IP 哈希检查最近请求，设为 `0` 可关闭冷却 |
| `ASTRA_PASSWORD_RESET_TOKEN_RETENTION_DAYS` | `30` | 过期或已用密码重置 token 默认留存天数；清理脚本未传 `--before` 或 `--retention-days` 时据此计算 cutoff |
| `ASTRA_PASSWORD_RESET_RETURN_TOKEN_FOR_DEV` | `false` | 仅用于本地/测试调试的 token 回传开关；生产环境即便误设为 `true` 也不会回传 token |
| `ASTRA_LOGIN_MAX_ATTEMPTS` | `5` | 登录失败锁定阈值 |
| `ASTRA_LOGIN_LOCKOUT_SECONDS` | `900` | 达到失败阈值后的锁定秒数 |
| `ASTRA_LOGIN_ATTEMPT_WINDOW_SECONDS` | `900` | 统计连续失败的时间窗口 |
| `ASTRA_AUDIT_LOG_RETENTION_DAYS` | `365` | 审计留存预检与 `scripts.archive_audit_logs` 默认保留天数；未传 `retention_days`、`--retention-days` 或 `before/--before` 时据此计算候选 cutoff |
| `ASTRA_AUDIT_IP_HASH_SALT` | `astra-dev-audit-salt` | 审计中客户端 IP 哈希盐；生产环境应替换 |
| `ASTRA_CONTENT_SCRIPT_ALLOWED_HOSTS` | 空 | 外部内容脚本 host allowlist，逗号分隔；默认阻断 `scriptUrl/scriptSrc` 外链，配置后仍要求显式 `https://`、无 query/fragment、合法 SRI、`crossorigin=anonymous` 和管理员脚本审核 |
| `ASTRA_ADMIN_BOOTSTRAP_TOKEN` | 空 | 首个管理员初始化令牌；生产环境必须配置 |
| `ASTRA_CORS_ORIGINS` | `http://127.0.0.1:8766,http://localhost:8766` | 允许访问 API 的前端来源白名单 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED` | `false` | 是否随 FastAPI lifespan 启动知识快照进程内调度器 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START` | `false` | 调度器启动后是否立即检查一次到期窗口 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_INTERVAL_SECONDS` | `300` | 调度器轮询间隔，最低 30 秒 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_LEASE_SECONDS` | `3600` | 知识快照调度数据库租约有效期，过期 running 窗口可被其他 worker 接管，最低 60 秒 |
| `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_HEARTBEAT_SECONDS` | `120` | 知识快照重算长循环中的自动租约心跳间隔；调度器与 CLI 会按该间隔用 owner/token guard 续租，最低 30 秒 |
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

- `app.services.access_control` 负责学校、班级和课程范围判断，普通业务端点不再各自复制 `_require_*` helper；学生课程访问会额外要求课程 `published`，单元读取/事件/提交/复盘会继续要求单元 `published`，事件与提交写入要求作业 `active`；教师端涉及班级挂课、班级成员列表、学生成员状态维护、学习事件查询、积分流水、学生进度、查看提交、批改和待批改队列时必须具备对应班级的 active teacher membership；同校非本班教师不能通过 legacy direct join 自助成为班级 teacher，必须提交 join request 并由本班 active teacher 或 admin 审批；学校/班级深度统计分别要求对应 school teacher scope / class teacher scope，且非授权用户不通过统计端点暴露对象存在性；课程结构写入（单元/作业创建）和 assignment 级积分规则维护要求课程创建者、active editor 协作者或全局 admin，协作者管理和课程 owner 转让仅限课程创建者或全局 admin；全局 admin 保留跨范围治理能力，可维护、批量维护或转让 teacher membership，但不能禁用班级最后一个 active teacher；后续权限矩阵扩展应优先在这里收口。
- `app.services.points` 负责 assignment 级积分规则规范化与批改积分计算；默认规则为 `enabled=true`、`points_per_score=1`、`max_points=null`，批改时写入“规则目标积分 - 当前 submission 已入账 assignment_grade 积分”的差额流水，避免重复批改累计膨胀，并支持封顶或禁用规则后的反向校正。
- `app.services.class_join_requests` 负责加入申请审批状态流转和成员关系补齐。
- `POST /api/classes/{id}/join` 与 `POST /api/classes/{id}/join-requests` 长期并存：前者是保留给学生自助加入、admin 治理、受控导入/邀请码或旧 UI 的 direct join；teacher 角色的普通教师加入必须走后者，由教师/admin 审批后生成 teacher membership；前端不得把审批流表现为唯一加入路径，也不得让普通教师绕过审批自助成为班级 teacher。
- `app.services.audit` 负责写入审计日志及 request_id、IP 哈希、user-agent 等请求元数据；新审计记录会以 `prev_hash/current_hash` 保存应用层 SHA-256 链式哈希，用于追踪篡改迹象，但不能替代备份、binlog、外部归档、WORM 或第三方时间戳；管理端 JSON/CSV 明细导出接口默认剥离 `snapshot_json`，需要审查内容快照时必须显式传入 `include_snapshot=true`，且导出完成后会以 `admin.audit.export` 记录筛选条件、导出格式、导出数量和截断状态，不记录导出条目明细；审计报表摘要以 `admin.audit.report` 留痕，只记录格式、筛选和 bucket 数量；审计留存预检以 `admin.audit.retention_plan` 留痕，只记录策略、候选数量、临期数量、bucket 数量和链边界，不记录候选明细或原始快照；`scripts.archive_audit_logs` 是离线只读归档包导出工具，会生成 JSONL/CSV 数据文件与 Manifest，并支持 SHA-256 和记录数复验，默认不删除源数据、不写新的审计日志、不提供 WORM 或外部锚定；高频候选摘要以 `admin.audit.high_frequency` 留痕，只记录筛选、时间窗、阈值、总量和维度命中数，不记录候选明细、原始日志 id 或完整 IP 哈希清单。
- `app.services.audit_chain` 负责复用型审计链校验：按传入顺序重算 `current_hash`、检查相邻记录 `prev_hash` 是否衔接上一条 `current_hash`，并把历史空 hash 作为 partial 状态暴露给 API 与归档 Manifest；它只报告 `current_hash_mismatch`、`prev_hash_mismatch` 和 `null_current_hash`，不执行修复、删除、回填或外部锚定。
- `/api/admin/bugs` 负责缺陷与风险清单的最小维护；`external_issue_provider/external_issue_id/external_issue_url` 只是外部 issue 链接元数据，不代表已经实现外部平台自动创建或双向状态同步。
- `app.services.request_metadata` 统一解析请求元数据；审计与会话治理共享 request_id、user-agent 和 IP 哈希口径。`AuthSession.device_label` 优先来自 `X-Device-Label` / `X-Device-Name`，缺省回退到登录 user-agent，因此只是 best-effort 设备摘要，不等同强设备绑定。
- `app.api.deps.auth.get_current_auth_context()` 会在有效鉴权后按 `ASTRA_SESSION_LAST_SEEN_UPDATE_SECONDS` 刷新当前 `AuthSession.last_seen_at` 和 `last_seen_ip_hash`；默认 300 秒内同一 IP 哈希不重复写库，窗口过期、IP 哈希变化或配置为 `0` 时刷新。该机制只降低 last_seen 写放大，不等同强设备绑定或长期会话风控。
- `/api/auth/password-reset/request` 与 `/api/auth/password-reset/confirm` 只提供本地账号自助重置 token 能力；邮件/短信/MFA 投递暂列 `P4 / 最低优先级 / 暂缓`。请求审计使用账号哈希作为 `resource_id`，不记录明文用户名或 token；确认阶段会对 token 行加锁并一次性消费。`app.services.password_reset_tokens` 与 `scripts.cleanup_password_reset_tokens` 提供过期/已用 token 的离线清理入口，默认 dry-run，显式 `--apply` 才删除，摘要不返回用户名、IP 哈希、user-agent 或 token hash。
- `app.services.content_catalog` 负责内容页 seed、正式内容初始化、已发布 schema 读取和内容页摘要；`/api/content/pages*` 与 `/api/render/*` 查询只读 published 当前记录，不在 GET 路径隐式写库，公开响应会剥离原始脚本引用、SRI/crossorigin 元数据和 sandbox 原始字段，只保留不可执行 `scriptManifest`；manifest 会返回沙箱 enforcement/capabilities，`/api/render/page/{slug}` 会额外返回 `X-Astra-Content-Script-Sandbox`、`X-Astra-Content-Script-Manifest-Count`、`X-Astra-Content-Script-Iframe-Sandbox` 和 `X-Astra-Content-Script-CSP` 契约头；正式初始化会显式创建/修复内置内容页版本，默认不覆盖已有差异版本。
- `app.services.content_identity` 负责内容协议稳定身份契约：历史 schema 读取仍允许缺失 `sectionId/sourceId`，但新建/编辑/发布草稿和内置内容初始化要求每个 section/source 带稳定 ID，并拒绝重复 ID 或与 `props.sectionId/props.id` 冲突的章节身份。
- `app.services.content_script_policy` 负责内容草稿脚本静态分析、脚本资产 allowlist/SRI 静态门禁、后端下载校验与 sandbox 契约；当前识别脚本引用、外链脚本、事件处理器、阻断协议、路径穿越、内联 `<script>` 和不安全 sandbox 能力。外部 `scriptUrl/scriptSrc` 默认阻断，只有 host 出现在 `ASTRA_CONTENT_SCRIPT_ALLOWED_HOSTS` 且 URL 为显式 `https://`、无 query/fragment、声明合法 SRI 与 `crossorigin=anonymous` 时才可进入 high-risk 管理员审核；管理员批准外部脚本和发布已审核草稿时会下载资产并按声明 SRI 比对字节，下载失败、SRI mismatch 或发布前 CDN 字节漂移会阻断流程，默认下载器不跟随重定向。下载校验 finding 会通过 metadata 保留资产 SHA-256、字节大小、SRI token 数量和匹配算法；公开 `scriptManifest.sandbox` 会按 `network=none/same-origin` 派生 CSP、显式返回 enforcement/capabilities，并对 unsafe sandbox 防御性降级为 blocked；分析结果带 `policy_context_hash`，allowlist 配置变化会触发发布/审核前重分析。当前不承担浏览器 iframe/worker 运行时容器本身。
- `/api/admin/content/page-versions/{id}/diff` 负责版本对比：旧 `changes` 继续返回 JSON path 级差异，新 `semantic` 汇总 metadata、courseUnit、sections 与 sources 的增删改移；sections/sources 优先按 `sectionId/sourceId` 识别，保留旧标题、label、url 和 index fallback，并在每条 section/source 变更中显式返回 before/after 稳定 ID，便于后续管理端 UI 展示。diff 响应会对路径或字段名命中 token/key/secret/script/sandbox/integrity/crossorigin 等敏感语义的值返回 `{redacted, reason, value_type, length}` 预览对象；非敏感字段保持原值，避免破坏既有标题、summary、source URL 和普通 props 展示。
- `PATCH /api/content/drafts/{id}` 负责草稿编辑闭环：仅允许作者或管理员编辑 `draft` / `changes_requested` 草稿，禁止 retarget 到其他 slug，保存时重算 `schema_hash/script_analysis/script_risk_level`，并清空旧脚本审核元数据；`base_version_id/base_schema_hash` 保持创建时基线，发布前仍由 stale guard 拦截过期草稿。
- `/api/content/drafts/{id}/submit`、`/request-changes`、`/withdraw` 与 `/publish` 负责草稿状态流转；创建草稿时绑定当前 published base 版本和 hash，写入 `active_key='active'`，并由 `(author_user_id, target_slug, active_key)` 唯一约束防止同一作者同一目标页并发创建多个 active 草稿；撤回或发布会清空 active key。发布前校验 base 未过期并复核当前配置下的脚本 policy，脚本引用必须带 `scriptSandbox.mode=isolated-iframe` 且不能声明危险能力；外部脚本还必须满足 allowlist/SRI/crossorigin 契约、完成管理员审核，并在审核批准和发布时通过后端下载/SRI 字节校验。发布阶段由 `(slug, version)` 和 `source_draft_id` 唯一约束兜底，冲突统一返回 `409`，发布后回填 page/version/publisher 元数据，审计只记录状态和版本元数据，不记录完整 schema。
- `/api/content/page-versions/{id}/rollback` 负责内容版本追加式回滚：更新 `content_pages.current_version_id/schema_hash/published_*` 当前态、追加带 `previous_version_id` 的 `content_page_versions`，并在审计中只记录版本元数据与 schema hash，不记录完整 schema。
- `app.services.knowledge_snapshot_runs` 与 `app.services.knowledge_snapshot_scheduler` 负责知识快照窗口重算、运行记录、进程内调度、数据库租约防重入、长重算自动心跳、健康摘要、调度积压摘要、协作式取消和手动 requeue；同一 `run_key` 通过 scheduler lease owner/token/expires/heartbeat 元数据抢占，调度器与 CLI 会把 token-guard heartbeat callback 注入重算循环，完成或失败释放使用 token guard，失去租约或被 admin 取消的旧 worker 会中止而不覆盖新状态；requeue 会把 failed、cancelled 或过期带租约 running run 重置为 pending，调度器会扫描 pending run 并重新抢占执行；积压摘要会显式区分 scheduler 实际会处理的 dispatchable now 和仅符合租约抢占规则的 claimable by lease rule，管理端响应不返回 `scheduler_lease_token` 或 `metadata_json`。
- `POST /api/assignments/{id}/submissions` 的提交唯一性按 `assignment_id + student_id + class_id` 收口；同一课程作业挂到多个班级时，学生可在不同班级各提交一次，同班级重复提交仍返回 `409`；学生提交只允许 published 课程、published 单元下的 active 作业。`GET /api/classes/{id}/members` 只允许全局 admin 或该班 active teacher membership 读取，默认仅返回 active 成员，响应包含成员关系状态和用户状态但不暴露密码、会话或联系方式；`PATCH /api/classes/{id}/members/{membership_id}` 支持 student membership 的 `active/inactive`，teacher membership 仅限全局 admin 维护；`PATCH /api/classes/{id}/members/batch-status` 支持 all-or-nothing 批量维护，普通班级教师只能批量维护 student membership，全局 admin 可批量维护 teacher membership；`POST /api/classes/{id}/teachers/transfer` 支持 admin 将源 active teacher 转给同校 active teacher/admin，目标 class membership 不存在则创建、inactive 则恢复；单条、批量和转让路径都不能让 active teacher 归零。`GET /api/assignments/{id}/submissions` 对教师默认只返回其任教班级内的提交，指定 `class_id` 时要求本班 teacher scope；`PATCH /api/submissions/{id}/grade` 同样要求本班 teacher scope，并按 assignment 级积分规则写入差额流水。`PATCH /api/courses/{id}/owner` 提供课程 owner 转让首轮，课程创建者或全局 admin 可转给同校 active teacher/admin membership 用户，目标若原本是 active editor 会被置为 `inactive` 以避免 owner/协作者身份重叠。`GET/POST /api/courses/{id}/collaborators` 与 `PATCH /api/courses/{id}/collaborators/{collaborator_id}` 提供课程协作者最小闭环，课程创建者或全局 admin 可把同校 active teacher/admin membership 用户设为 `editor` 或置为 `inactive`，active editor 可创建单元/作业和维护作业积分规则，但不能管理协作者。`GET /api/points/assignments/{id}/rule` 允许学校 teacher/admin 读取，`PATCH /api/points/assignments/{id}/rule` 只允许课程创建者、active editor 或全局 admin 维护；同校非作者/非协作者教师可批改自己班级提交，但不能改写共享作业规则。`GET /api/learning-events`、`GET /api/points/ledger` 和 `GET /api/progress/users/{id}` 对教师也使用同一班级 teacher scope；不传 `class_id` 的事件/积分查询只返回教师任教班级内的数据。
- `GET /api/assignments/{id}/review` 是学生侧只读复盘入口：只允许 student 访问自己的提交历史，可用 `class_id` 定位班级提交；published 课程/单元内 closed / archived 作业不允许再次提交但仍返回题目、成绩和反馈；教师和管理员继续使用 submissions 列表与批改接口。

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

当前 Alembic head：`20260707_0029`（课程协作者表）。

知识快照周期重算：

```bash
cd backend
python -m scripts.rebuild_knowledge_snapshots --granularity day
python -m scripts.rebuild_knowledge_snapshots --granularity week --date 2026-07-03
```

脚本按日或自然周对齐窗口，先抢占 `knowledge_snapshot_runs` 数据库租约，再重算活跃班级已挂接课程的个人/班级快照；学生 user snapshot 跳过 unpublished 课程并按学生可见性过滤单元/作业，class snapshot 保持教师/管理聚合口径；重算长循环会按 `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_HEARTBEAT_SECONDS` 自动续租，租约不可用时输出 `status=skipped`，失去租约或失败时输出 JSON 并返回非零退出码。

知识快照进程内调度器默认关闭。生产启用时应先完成 Alembic 迁移和部署预检，再设置 `ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED=true`；调度器与周期重算 CLI 已通过数据库租约和自动心跳降低多 worker/多副本重复执行风险，过期 running 窗口可被抢占，成功/失败释放使用 token guard，心跳失败会让旧 worker 中止。管理员可通过 `/api/admin/knowledge-snapshot-runs` 查看 run，通过 `/health` 汇总 stale running、即将过期 lease、claimable 和失败重试状态，通过 `/queue` 区分 dispatchable now、manual requeue 和 blocked backlog，通过 `/cancel` 对 `pending` 或带 scheduler lease 的 `running` run 做协作式取消，并通过 `/requeue` 将 failed、cancelled 或过期带租约 running run 重置为 pending；取消不是强杀线程，而是清空租约并让旧 worker 在下一次 heartbeat/finish guard 处停止写回。当前仍不是完整任务队列，外部告警、外部队列和真实 MySQL 并发取消/重排演练仍是后续部署增强项。

审计归档候选导出：

```bash
cd backend
python -m scripts.archive_audit_logs --retention-days 365 --output-dir audit-archives
python -m scripts.archive_audit_logs --before 2026-07-01T00:00:00Z --format csv --include-snapshot --output-dir audit-archives
python -m scripts.archive_audit_logs --verify audit-archives/audit-logs-archive-<stamp>.manifest.json
```

该脚本按 `created_at <= cutoff` 选择候选，支持 `--retention-days`、`--before`、`--action`、`--resource-type`、`--resource-id`、`--school-id`、`--class-id`、`--event-result`、`--failure-reason`、`--request-id`、`--from` 和 `--to` 过滤。输出 Manifest 记录策略、筛选、导出数量、截断状态、首尾候选、链边界、hash-chain 重算状态、归档文件 SHA-256 和字节数；`--dry-run` 只打印 Manifest 预览不写文件。脚本默认只读，不删除 `audit_logs`、不写 `admin.audit.*` 事件、不提供 WORM 或外部锚定。

密码重置 token 留存清理：

```bash
cd backend
python -m scripts.cleanup_password_reset_tokens --retention-days 30
python -m scripts.cleanup_password_reset_tokens --retention-days 30 --apply
```

该脚本按 `used_at <= cutoff` 或 `used_at IS NULL AND expires_at <= cutoff` 选择已使用或已过期的终态 token。默认只做 dry-run，显式传入 `--apply` 才删除；`--retention-days` 与 `--before` 互斥，`--before` 不允许指向未来时间，`--limit` 控制单批候选数量。输出只包含数量、状态、id 范围、终态时间和候选口径，不返回用户名、IP 哈希、user-agent、token hash 或明文 token。

部署预检：

```bash
cd backend
python -m scripts.deploy_preflight --require-mysql
```

预检会检查 `ASTRA_DATABASE_URL` 可连通，并确认数据库 Alembic 当前 revision 已到 head；失败时返回非零退出码和 JSON 报告。正式部署应先执行 `python -m alembic upgrade head`，再执行预检。生产环境建议追加 `--require-mysql`，此时预检会要求当前连接为 MySQL，并报告 `dialect`、`driver`、数据库/连接字符集、排序规则和 `time_zone`；若数据库或连接字符集不是 `utf8mb4`，或排序规则不是 `utf8mb4_` 前缀，会返回非零退出码。

部署 smoke：

```bash
cd backend
python -m scripts.deploy_smoke --require-mysql
```

smoke 会复用部署预检，再检查当前模型期望表是否全部存在，并用同一配置启动 FastAPI TestClient 访问 `/api/health`。脚本运行时会临时关闭自动建表和知识快照调度器，只验证迁移后的现有状态。`--require-mysql` 用作生产门禁：会把 MySQL 方言、`utf8mb4` 字符集/排序规则检查传递给预检层，并继续在 schema 层阻断非 MySQL 方言；本地或 CI 需要覆盖临时库时可追加 `--database-url` 且不传 `--require-mysql`。

正式内容初始化：

```bash
cd backend
python -m scripts.init_content_pages --dry-run --publisher-user-id <admin_id>
python -m scripts.init_content_pages --publisher-user-id <admin_id> --allow-reviewed-scripts
```

脚本输出 JSON 报告；非 dry-run 写入前必须确认内置脚本引用已审核。内置本地脚本引用不依赖外部 host allowlist；若未来引入外部内容脚本，必须先配置 `ASTRA_CONTENT_SCRIPT_ALLOWED_HOSTS` 并满足 `https`、无 query/fragment、SRI、`crossorigin=anonymous` 和管理员审核契约。若不传 `--publisher-user-id`，脚本会选择第一个 active admin 作为发布归因；生产环境建议显式传入。

相关回归入口：`python -m pytest backend/tests/test_content_initialization.py backend/tests/test_content_publication.py -q`，其中初始化用例覆盖中文数据库路径，发布用例覆盖中文 URL slug 的创建、发布、公开读取、后台查询和版本历史过滤。
