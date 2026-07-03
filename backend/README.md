# 星序 Astra · Python 后端

本文档记录 v6.5 后端化第一阶段的本地开发入口。当前 Python 后端与既有 `server/` C++ 静态服务并存，先承担业务 API、内容协议与后续登录/学校/班级等能力。

## 本地启动

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

首个内容协议样例：

```bash
curl http://127.0.0.1:8000/api/render/page/physics/energy-conservation
```

## 配置

配置使用 `ASTRA_` 前缀环境变量：

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `ASTRA_ENVIRONMENT` | `development` | 运行环境 |
| `ASTRA_API_PREFIX` | `/api` | API 前缀 |
| `ASTRA_DATABASE_URL` | `mysql+pymysql://astra:astra@127.0.0.1:3306/astra?charset=utf8mb4` | MySQL 连接字符串 |

可从 `.env.example` 复制本地配置；真实密码不要提交到仓库。

测试会覆盖为 SQLite 内存数据库，避免依赖本机 MySQL 实例。

## 验证

```bash
python -m pytest backend
```
