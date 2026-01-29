# Celery队列配置修复

## 问题描述

文档上传后状态始终为pending，不会自动处理。

## 问题排查过程

### 1. 检查Celery Worker状态

```bash
docker logs medimind-celery-worker --tail 100
```

输出显示Worker正常启动，已注册任务，但无任何任务执行记录:

```
[tasks]
  . medimind_agent.infrastructure.tasks.document_tasks.process_document_task
  . medimind_agent.infrastructure.tasks.document_tasks.process_pending_documents_task
  . medimind_agent.infrastructure.tasks.document_tasks.delete_document_nodes_task

[queues]
  .> default          exchange=default(direct) key=default

celery@xxx ready.
```

### 2. 检查Redis队列

```bash
# 检查default队列
docker exec medimind-redis redis-cli LLEN default
# 结果: 0

# 检查documents队列
docker exec medimind-redis redis-cli LLEN documents
# 结果: 4
```

发现4个任务积压在`documents`队列。

### 3. 定位根因

| 文件 | 配置 | 问题 |
|------|------|------|
| `celery_app.py:19-21` | `task_routes = {"process_document_task": {"queue": "documents"}}` | 任务路由到documents队列 |
| `docker-compose.yml:81` | `celery worker --loglevel=info` | Worker只监听default队列 |

**结论**: 任务投递到`documents`队列，Worker监听`default`队列，队列名不匹配导致任务无法被消费。

## 解决方案

### 方案A: 修改Worker监听多队列

修改`docker-compose.yml`第81行:

```yaml
# 修改前
celery -A medimind_agent.infrastructure.tasks.celery_app worker --loglevel=info

# 修改后
celery -A medimind_agent.infrastructure.tasks.celery_app worker -Q default,documents --loglevel=info
```

### 方案B: 移除队列路由配置 (推荐)

修改`medimind_agent/infrastructure/tasks/celery_app.py`:

```python
# 删除以下配置
app.conf.task_routes = {
    "medimind_agent.infrastructure.tasks.document_tasks.process_document_task": {"queue": "documents"},
}
```

修改后所有任务使用default队列，简化配置。

**推荐方案B**，理由:
- 当前无队列优先级需求
- 减少配置复杂度
- 后续需要分队列时再添加

## 修复后验证

1. 应用修改后重启Worker:

```bash
docker-compose restart celery-worker
```

2. 清理积压的旧任务(可选):

```bash
docker exec medimind-redis redis-cli DEL documents
```

3. 重新上传文档或手动触发处理，观察Worker日志:

```bash
docker logs -f medimind-celery-worker
```

应看到任务执行日志:

```
[INFO/MainProcess] Received task: process_document_task[xxx]
[INFO/ForkPoolWorker-1] Task process_document_task[xxx] succeeded
```

4. 检查文档状态:

```bash
curl -s http://localhost:8000/api/v1/library/documents | jq '.data[].status'
# 应返回 "completed" 或 "failed"
```

## 预防措施

1. 在`/health/ready`接口中增加pending文档计数检查
2. 添加管理API手动触发处理pending文档
3. Celery配置变更时同步检查Worker启动参数
