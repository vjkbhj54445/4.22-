# seedance-gateway

一个基于 **FastAPI** 的 PPIO Seedance 视频生成 API 网关。提供：

- 🎬 OpenAI 兼容的视频生成接口（`/v1/video/generations`、`/v1/chat/completions`）
- 🔀 多 Provider（多上游密钥/Base URL）管理
- 📬 Redis 任务队列 + 独立 worker 异步处理
- 🖥️ 管理后台（HTML 模板）
- 🔐 基于 `GATEWAY_ACCESS_TOKEN` 的 Bearer 鉴权（使用 `hmac.compare_digest` 防时序攻击）
- ♻️ 任务状态 URL 签名 + 过期控制
- 🩺 `healthz` / `readyz` 健康检查，Docker healthcheck
- 🧪 完整 pytest 测试套件与 HTML 覆盖率报告

---

## 📁 目录结构

```
.
├── README.md                     # 本文件
├── pyproject.toml                # mypy 配置
├── .github/workflows/ci.yml      # GitHub Actions（pytest + docker + mypy）
└── seedance-gateway/
    ├── main.py                   # FastAPI 应用入口（路由、鉴权、lifespan）
    ├── worker.py                 # 异步任务 worker（从 Redis 拉队列）
    ├── seedance_client.py        # PPIO Seedance 上游 HTTP 客户端（httpx）
    ├── task_manager.py           # Redis 任务状态/队列管理
    ├── provider_store.py         # 多 Provider CRUD（Redis 存储）
    ├── models.py                 # Pydantic v2 模型
    ├── templates/admin.html      # 管理后台页面
    ├── tests/                    # pytest 测试
    ├── Dockerfile                # python:3.13-slim，非 root 用户
    ├── docker-compose.yml        # redis + gateway-api + gateway-worker
    ├── requirements.txt          # 运行/测试依赖
    ├── requirements.lock         # pip-compile 生成的锁定版本
    ├── pytest.ini                # pytest + asyncio + coverage 配置
    └── .env.example              # 环境变量模板
```

---

## 🚀 快速开始

### 方式 A：Docker Compose（推荐，一键启动全套服务）

```bash
git clone https://github.com/vjkbhj54445/4.22-.git
cd 4.22-/seedance-gateway
cp .env.example .env
# 用编辑器填写 SEEDANCE_API_KEYS / GATEWAY_ACCESS_TOKEN 等
docker compose up --build -d
```

启动后：

- API 网关：http://localhost:8001
- 健康检查：`curl http://localhost:8001/healthz`
- 管理后台：http://localhost:8001/admin （需要 `ADMIN_ACCESS_TOKEN` 或 `GATEWAY_ACCESS_TOKEN`）

```bash
docker compose logs -f gateway-api       # 查看 API 日志
docker compose logs -f gateway-worker    # 查看 worker 日志
docker compose down                      # 停止（保留数据）
docker compose down -v                   # 停止并删除 redis 数据卷
```

### 方式 B：本地开发（uvicorn + 本地 Redis）

```bash
cd seedance-gateway

# 1) 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 安装依赖（优先使用锁定版本）
pip install -r requirements.lock
# 或：pip install -r requirements.txt

# 3) 启动本地 Redis
docker run -d --name seedance-redis -p 6379:6379 redis:7-alpine

# 4) 加载环境变量
cp .env.example .env
export $(grep -v '^#' .env | xargs)

# 5) 启动 API（开发模式，热重载）
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 6) 另开一个终端启动 worker
python worker.py
```

---

## 🔧 环境变量

| 变量名 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `SEEDANCE_API_KEYS` | ✅ | — | PPIO API Key，多个用逗号分隔（会轮询） |
| `SEEDANCE_BASE_URL` | ✅ | — | 上游 Base URL，如 `https://api.ppio.com` |
| `REDIS_URL` | ✅ | — | Redis 连接串，如 `redis://localhost:6379/0` |
| `GATEWAY_ACCESS_TOKEN` | ✅ | — | 客户端访问网关的 Bearer Token |
| `ADMIN_ACCESS_TOKEN` | — | 同 `GATEWAY_ACCESS_TOKEN` | 管理后台专用 Token |
| `GATEWAY_PUBLIC_URL` | — | `http://localhost:8001` | 任务状态签名 URL 使用 |
| `TASK_STATUS_URL_TTL` | — | `360` | 任务状态 URL 有效期（秒） |
| `TASK_POLL_INTERVAL` | — | `5` | 查询上游任务间隔（秒） |
| `TASK_TIMEOUT` | — | `300` | 任务超时（秒） |
| `TASK_QUEUE_POP_TIMEOUT` | — | `5` | Worker 从 Redis 拉队列阻塞超时（秒） |
| `TASK_EXECUTION_MODE` | — | `queue` | `queue` 或 `inline` |
| `MAX_CONCURRENT_TASKS` | — | `20` | Worker 最大并发任务数 |
| `WORKER_RESTART_DELAY` | — | `3` | Worker 异常后重启延迟（秒） |

> ⚠️ **安全提示**：不要把真实的 `.env` 提交到仓库。本仓库 `.gitignore` 已忽略 `**/.env`。

---

## 📡 API 概览

所有 `/v1/*` 路由（除带签名的任务状态 GET 外）均需要在 `Authorization` 头携带：

```
Authorization: Bearer <GATEWAY_ACCESS_TOKEN>
```

### 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 存活探针（永远 200） |
| GET | `/readyz` | 就绪探针（检查 Redis 可用） |

### 视频生成（OpenAI 兼容）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/video/generations` | 提交视频生成任务 |
| POST | `/v1/chat/completions` | OpenAI chat 语义包装 |
| POST | `/v1` | 同上别名 |
| GET | `/v1/tasks/{task_id}?status_token=...&expires_at=...` | 查询任务状态（签名 URL，无需 Bearer） |

**示例：提交任务**

```bash
curl -X POST http://localhost:8001/v1/video/generations \
  -H "Authorization: Bearer $GATEWAY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance-v1",
    "prompt": "一只在雪地里奔跑的柴犬，电影级画面",
    "duration": 5,
    "resolution": "1080p"
  }'
```

响应：

```json
{
  "task_id": "...",
  "status_url": "http://localhost:8001/v1/tasks/...?status_token=...&expires_at=..."
}
```

**查询状态**（响应返回的 `status_url` 已包含签名，可直接 GET）：

```bash
curl "http://localhost:8001/v1/tasks/<task_id>?status_token=...&expires_at=..."
```

### 多 Provider（指定上游）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/providers/{slug}/video/generations` | 使用指定 Provider 提交 |
| POST | `/v1/providers/{slug}/chat/completions` | — |
| GET | `/v1/providers/{slug}/tasks/{task_id}` | 查询指定 Provider 任务 |

### 管理接口（需 `ADMIN_ACCESS_TOKEN`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin` | 管理后台 HTML |
| GET | `/admin/api/providers` | Provider 列表 |
| GET | `/admin/api/providers/{slug}` | Provider 详情 |
| POST | `/admin/api/providers` | 创建 Provider |
| PUT | `/admin/api/providers/{slug}` | 更新 Provider |
| DELETE | `/admin/api/providers/{slug}` | 删除 Provider |
| POST | `/admin/api/providers/{slug}/set-default` | 设为默认 |

---

## 🧪 测试

```bash
cd seedance-gateway
pip install -r requirements.txt
pytest
```

- 默认配置见 [seedance-gateway/pytest.ini](seedance-gateway/pytest.ini)
- 生成覆盖率 HTML 到 `seedance-gateway/htmlcov/index.html`
- 只跑某类测试：

```bash
pytest -m unit
pytest -m integration
pytest -m e2e
```

### 测试文件

- [seedance-gateway/tests/test_main.py](seedance-gateway/tests/test_main.py) — FastAPI 端点、鉴权、签名 URL
- [seedance-gateway/tests/test_seedance_client.py](seedance-gateway/tests/test_seedance_client.py) — 上游 HTTP 客户端（mock httpx）
- [seedance-gateway/tests/test_task_manager.py](seedance-gateway/tests/test_task_manager.py) — Redis 状态/队列

---

## 🔎 类型检查

```bash
pip install mypy
mypy seedance-gateway
```

配置见 [pyproject.toml](pyproject.toml)，采用 **渐进式** 策略（`strict = false`），可逐文件收紧。

---

## 📦 依赖管理

- `requirements.txt` — 人工维护的直接依赖（带版本范围）
- `requirements.lock` — `pip-compile` 生成的全量锁定（含传递依赖）

更新锁定版本：

```bash
pip install pip-tools
cd seedance-gateway
pip-compile --output-file=requirements.lock requirements.txt
```

CI 与生产部署建议使用 `requirements.lock` 保证可复现构建。

---

## 🤖 CI / CD

GitHub Actions 工作流 [.github/workflows/ci.yml](.github/workflows/ci.yml) 包含三个 Job：

1. **pytest** — Python 3.13，启动 Redis service container，运行完整测试
2. **docker build** — 使用 `buildx` 验证 Dockerfile 可构建
3. **mypy** — 类型检查（`continue-on-error: true`，渐进式）

触发条件：`push` 到 `main` 或对 `main` 的 PR。

---

## 🏗️ 架构

```
   ┌─────────────┐       ┌───────────────┐       ┌──────────────┐
   │  Client     │ POST  │ gateway-api   │ LPUSH │   Redis      │
   │ (curl/SDK)  │──────▶│ (FastAPI)     │──────▶│ queue + kv   │
   └─────────────┘       └───────┬───────┘       └──────┬───────┘
                                 │                      │ BLPOP
                                 │ GET status           ▼
                                 │              ┌───────────────┐
                                 └─────────────▶│ gateway-worker│
                                   (kv read)    │ (worker.py)   │
                                                └───────┬───────┘
                                                        │ HTTP
                                                        ▼
                                                ┌───────────────┐
                                                │ PPIO Seedance │
                                                └───────────────┘
```

- **API** 只负责鉴权、校验、入队、读取状态，不阻塞调用上游。
- **Worker** 从 Redis 拉任务，调用 [seedance-gateway/seedance_client.py](seedance-gateway/seedance_client.py) 轮询上游结果，写回 Redis。
- **Provider** 配置持久化在 Redis，管理后台可热更新。

---

## 🔒 安全

- Bearer Token 校验使用 `hmac.compare_digest`（见 [seedance-gateway/main.py](seedance-gateway/main.py) 中的 `verify_token` / `verify_admin_token` / `verify_task_status_access`）
- 任务状态 URL 使用 HMAC 签名 + 过期时间戳，防止任务 ID 枚举
- Docker 以 `uid 10001` 非 root 用户运行
- 管理后台响应默认带安全头中间件

> ⚠️ 如果早期曾将 `.env` 推送到远程，**请务必轮换 API Key 与 Token**。可选用 `git filter-repo` 从历史彻底清除敏感文件后强制推送。

---

## 🛠️ 常见问题

**Q:** 启动报 `Missing required environment variables: ...`  
**A:** 检查 `.env` 是否已加载。Docker Compose 会自动读取同目录的 `.env`；本地开发需 `export $(grep -v '^#' .env | xargs)`。

**Q:** `/readyz` 返回 503 `Redis unavailable`  
**A:** 检查 `REDIS_URL` 和 Redis 实例是否运行（`docker compose ps`）。

**Q:** 任务一直处于 `queued` 不推进  
**A:** 没启动 `worker.py`。Docker Compose 下应有 `gateway-worker` service，本地开发需手动运行 `python worker.py`。

**Q:** 401 Invalid token  
**A:** 请求头格式必须是 `Authorization: Bearer <token>`，且 token 与 `GATEWAY_ACCESS_TOKEN` 一致。

**Q:** 如何水平扩容？  
**A:** 直接扩容 `gateway-worker` 副本数（`docker compose up -d --scale gateway-worker=N`），它们共享同一 Redis 队列。`gateway-api` 是无状态的也可扩容并前置负载均衡。

---

## 📝 License

未提供 license 文件；如需开源请补充 `LICENSE`。
# seedance-gateway

FastAPI 网关，代理 PPIO Seedance 视频生成 API，提供任务队列、状态查询、多 Provider 管理和管理后台。

## 目录结构

```
.
├── seedance-gateway/      # 主应用
│   ├── main.py            # FastAPI 入口
│   ├── worker.py          # 异步任务 worker
│   ├── seedance_client.py # 上游客户端
│   ├── task_manager.py    # Redis 任务管理
│   ├── provider_store.py  # Provider 管理
│   ├── models.py          # Pydantic 模型
│   ├── templates/         # 管理后台模板
│   ├── tests/             # pytest 测试
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
└── .github/workflows/ci.yml
```

## 快速开始

### 1. 配置环境变量

```bash
cd seedance-gateway
cp .env.example .env
# 编辑 .env 填入 SEEDANCE_API_KEYS、GATEWAY_ACCESS_TOKEN 等
```

### 2. 使用 Docker Compose（推荐）

```bash
cd seedance-gateway
docker compose up --build -d
```

服务启动后：
- API: http://localhost:8001
- 健康检查: `curl http://localhost:8001/healthz`

### 3. 本地开发（uvicorn）

```bash
cd seedance-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 需要一个本地 Redis
# docker run -d -p 6379:6379 redis:7-alpine

uvicorn main:app --host 0.0.0.0 --port 8001 --reload
# 另开一个终端跑 worker
python worker.py
```

## 运行测试

```bash
cd seedance-gateway
pip install -r requirements.txt
pytest
```

覆盖率报告会输出到 `seedance-gateway/htmlcov/index.html`。

## 类型检查

```bash
pip install mypy
mypy seedance-gateway
```

## CI

推送到 `main` 或打开 PR 会触发 [.github/workflows/ci.yml](.github/workflows/ci.yml)：
- 运行 `pytest` + 覆盖率
- 构建 Docker 镜像（验证 Dockerfile 可用）
