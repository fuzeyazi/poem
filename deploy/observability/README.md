# 可观测性栈（Prometheus + Grafana）

指标链路：`potry-service:8081` / `poetry-gateway:9080` 的 `/actuator/prometheus`
→ Prometheus 抓取（5s）→ Grafana 大盘（自动 provisioning，免手工配置）。

- Grafana：http://localhost:3001（admin / poetry），大盘"poetry-spring2 服务总览"自动加载
- Prometheus：http://localhost:9091
- 端口避开 Langfuse 容器占用的 3000/9090（台账 §5）

## 启动方式一：Docker（Docker 引擎稳定时首选）

```bash
cd deploy/observability && docker compose up -d
```

## 启动方式二：Windows 裸跑（本机 Docker 引擎不稳时的替代，已实测）

```bash
deploy\observability\start-obs.bat        # 启动
deploy\observability\start-obs.bat stop   # 停止
```

首次部署（二进制在 E:\javatexts\observability，不入仓库）：
1. Prometheus：GitHub release 下载 `prometheus-2.54.1.windows-amd64.zip` 解压，
   将本目录 `prometheus/prometheus.yml` 中 `host.docker.internal` 改为 `127.0.0.1` 后放入
2. Grafana：仅 dl.grafana.com 提供 Windows 包（国内镜像不同步），单连接限速时用
   Range 并行分段下载；解压后建 `gprovisioning/`（datasource 指向 127.0.0.1:9091，
   dashboards provider 指向本仓库目录的绝对路径）
3. 大盘面板 JSON：`grafana/dashboards/poetry-overview.json`（HTTP QPS/P95/P99、
   HikariCP、JVM 堆/GC、错误率、CPU）

## 已知坑（2026-10-25 实测沉淀）

- **Micrometer 默认不发 `http_server_requests` 直方图分桶**（只有 count/sum/max），
  Prometheus 端 `histogram_quantile` 查不到 P95/P99 —— 必须
  `management.metrics.distribution.percentiles-histogram.http.server.requests: true`
- 服务端 P99 与压测客户端 P99 口径不同：前者是 Tomcat 处理耗时，后者含并发排队与网络
  （实测：服务端 P95 3ms vs 客户端 106ms @ c=50）——定位"慢在服务还是慢在排队"的依据
- health 聚合会把 RabbitMQ/Mail 等外部依赖纳入判定，中间件缺席时整体 DOWN
  （已按需关闭 mail；rabbit 属核心依赖应保持开启）
