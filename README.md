# 古韵传习堂 · Poetry Spring

古诗文学习平台，包含 Java/Spring 业务后端、Spring Cloud Gateway 网关、Python AI 伴学 Agent 与 Vue 3 前端。

## 项目结构

- `potry-service`：业务接口、论坛、学习计划与诗词管理。
- `poetry-common`：公共返回类型及工具。
- `poetry-pojo`：实体、DTO 与 VO。
- `poetry-gateway`：统一路由与入口鉴权。
- `potry-ai-agent`：FastAPI 服务、AI 对话与工作流。
- `frontend`：Vue 3 / TypeScript / Vite 前端。
- `dev-notes`、`docs`：学习笔记、架构说明与验证脚本。

## 本地配置

真实密钥、密码、本地工具、依赖目录和运行产物不随源码上传。克隆后需自行配置环境。

Java 服务与网关读取环境变量，或分别在资源目录创建被 Git 忽略的 `application-secret.yml`。主要配置键为 `JWT_USER_SECRET`、`JWT_ADMIN_SECRET`、`MYSQL_PASSWORD`、`MAIL_PASSWORD`、`SPRING_AI_API_KEY`，以及项目配置使用的 RabbitMQ 和阿里云 OSS 配置键。

Python Agent 的配置项以 `potry-ai-agent/config.py` 为准，在本地 `.env` 中配置；JWT 密钥应与 Java 服务及网关一致。

笔记及部分本地验证脚本中的历史凭据已替换成占位值。SQL 保留表结构及诗词参考数据，账号、评论、反馈等本地使用记录已移除；管理员与测试账号需自行初始化。

## 构建与测试

Java：

```sh
mvn -pl potry-service -am package -DskipTests
mvn -pl poetry-gateway -am package -DskipTests
```

前端：

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm build
```

Agent：

```sh
cd potry-ai-agent
python -m venv .venv
# 激活虚拟环境后执行
pip install -r requirements.txt
python -m pytest -q
```

详细启动条件与服务依赖见 `CLAUDE.md`。`start-all.bat` / `stop-all.bat` 包含本机路径，换机后需调整。

## 本次上传

这是 2026-11-18 当前工作区的源码快照，包含此前尚未提交的开发内容。旧本地 Git 历史未打包到此快照。上传验证包括文件清单、凭据脱敏及源码格式检查；完整构建和服务联调需在具备依赖及配置的环境执行。
