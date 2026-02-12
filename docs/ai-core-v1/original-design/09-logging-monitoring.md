# 日志与监控设计

## 1. 概述

本文档定义 MediMind Agent 的日志策略和监控方案，确保系统可观测性和问题排查能力。

## 2. 日志策略

### 2.1 日志格式

采用 **结构化日志**（JSON 格式），便于日志聚合和分析。

**日志字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | string | ISO 8601 格式时间戳 |
| level | string | 日志级别 |
| logger | string | 记录器名称 |
| message | string | 日志消息 |
| request_id | string | 请求追踪 ID（可选）|
| extra | object | 额外上下文信息 |

**示例**

```json
{
    "timestamp": "2026-01-19T12:00:00.123Z",
    "level": "INFO",
    "logger": "application.services.document_service",
    "message": "Document processed successfully",
    "request_id": "req-abc123",
    "extra": {
        "document_id": "doc-xyz789",
        "duration_ms": 1234,
        "chunk_count": 42
    }
}
```

### 2.2 日志级别规范

| 级别 | 用途 | 示例 |
|------|------|------|
| **ERROR** | 系统错误，需要告警，可能影响服务 | 数据库连接失败、LLM 服务不可用 |
| **WARNING** | 可恢复的问题，潜在风险 | 任务重试、缓存未命中、响应超时 |
| **INFO** | 关键业务操作，正常运行记录 | 创建 Notebook、上传文档、Session 创建 |
| **DEBUG** | 详细调试信息，开发时使用 | 检索结果详情、SQL 查询、请求参数 |

### 2.3 日志记录器实现

```python
# src/common/logging.py

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
import threading

# 线程本地存储，用于存储 request_id
_local = threading.local()


def set_request_id(request_id: str) -> None:
    """Set request ID for current thread."""
    _local.request_id = request_id


def get_request_id() -> Optional[str]:
    """Get request ID for current thread."""
    return getattr(_local, "request_id", None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields
        if hasattr(record, "extra") and record.extra:
            log_data["extra"] = record.extra
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging(
    level: str = "INFO",
    json_format: bool = True
) -> None:
    """Configure application logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler()
    
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
```

### 2.4 日志使用示例

```python
# 在服务中使用
from src.common.logging import get_logger

logger = get_logger(__name__)


class DocumentService:
    async def process_document(self, document_id: str) -> Document:
        start_time = time.time()
        
        logger.info(
            f"Processing document: {document_id}",
            extra={"document_id": document_id}
        )
        
        try:
            # 处理逻辑
            result = await self._do_process(document_id)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Document processed successfully",
                extra={
                    "document_id": document_id,
                    "duration_ms": round(duration_ms, 2),
                    "chunk_count": result.chunk_count
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Document processing failed: {e}",
                extra={"document_id": document_id},
                exc_info=True
            )
            raise
```

### 2.5 请求追踪中间件

```python
# api/middleware/logging.py

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.common.logging import set_request_id, get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and tracing."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params)
            }
        )
        
        # Process request
        import time
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {response.status_code}",
            extra={
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
```

## 3. 业务日志规范

### 3.1 Notebook 操作

```python
# 创建 Notebook
logger.info("Notebook created", extra={
    "notebook_id": notebook.id,
    "title": notebook.title
})

# 删除 Notebook
logger.info("Notebook deleted", extra={
    "notebook_id": notebook_id,
    "cascade_deleted": {
        "sessions": session_count,
        "documents": document_count
    }
})
```

### 3.2 Session 操作

```python
# 创建 Session
logger.info("Session created", extra={
    "session_id": session.id,
    "notebook_id": notebook_id,
    "current_count": count
})

# Session 上限达到
logger.warning("Session limit reached", extra={
    "notebook_id": notebook_id,
    "current_count": 20,
    "max_count": 20
})
```

### 3.3 文档操作

```python
# 文档上传
logger.info("Document upload started", extra={
    "document_id": document.id,
    "filename": filename,
    "content_type": content_type,
    "file_size": file_size
})

# 文档处理完成
logger.info("Document processing completed", extra={
    "document_id": document.id,
    "duration_ms": duration_ms,
    "page_count": page_count,
    "chunk_count": chunk_count
})

# 文档处理失败
logger.error("Document processing failed", extra={
    "document_id": document.id,
    "error": str(error)
}, exc_info=True)
```

### 3.4 对话操作

```python
# 对话请求
logger.info("Chat request received", extra={
    "session_id": session_id,
    "mode": mode,
    "message_length": len(message)
})

# 检索完成
logger.debug("Retrieval completed", extra={
    "session_id": session_id,
    "query": query[:100],  # 截断
    "result_count": len(results),
    "top_score": results[0].score if results else None
})

# 对话完成
logger.info("Chat completed", extra={
    "session_id": session_id,
    "mode": mode,
    "duration_ms": duration_ms,
    "input_tokens": input_tokens,
    "output_tokens": output_tokens
})
```

## 4. 监控指标

### 4.1 系统指标

| 指标 | 类型 | 说明 |
|------|------|------|
| api_request_total | Counter | API 请求总数 |
| api_request_duration_seconds | Histogram | API 请求延迟 |
| api_error_total | Counter | API 错误总数 |
| celery_task_total | Counter | Celery 任务总数 |
| celery_task_duration_seconds | Histogram | 任务执行时间 |

### 4.2 业务指标

| 指标 | 类型 | 说明 |
|------|------|------|
| notebook_count | Gauge | Notebook 总数 |
| session_count | Gauge | Session 总数 |
| document_count | Gauge | 文档总数 |
| document_processing_total | Counter | 文档处理数量 |
| chat_request_total | Counter | 对话请求数量 |
| retrieval_latency_seconds | Histogram | 检索延迟 |
| llm_latency_seconds | Histogram | LLM 响应延迟 |

### 4.3 资源指标

| 指标 | 类型 | 说明 |
|------|------|------|
| db_connection_pool_size | Gauge | 数据库连接池大小 |
| redis_connection_count | Gauge | Redis 连接数 |
| celery_queue_length | Gauge | Celery 队列长度 |

## 5. Celery 任务监控

### 5.1 Flower 配置

Flower 提供 Celery 任务的 Web 监控界面。

**启动命令**

```bash
celery -A src.infrastructure.tasks.celery_app flower --port=5555
```

**Docker Compose 配置**

```yaml
flower:
  build: .
  container_name: medimind-flower
  command: celery -A src.infrastructure.tasks.celery_app flower --port=5555
  ports:
    - "5555:5555"
  depends_on:
    - redis
  networks:
    - medimind_network
  profiles:
    - debug
```

### 5.2 任务日志

```python
# src/infrastructure/tasks/document_tasks.py

from celery import shared_task
from src.common.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id: str):
    """Process a document asynchronously."""
    logger.info(
        f"Task started: process_document",
        extra={
            "task_id": self.request.id,
            "document_id": document_id,
            "retry": self.request.retries
        }
    )
    
    try:
        result = do_process(document_id)
        
        logger.info(
            "Task completed: process_document",
            extra={
                "task_id": self.request.id,
                "document_id": document_id
            }
        )
        return result
        
    except Exception as e:
        logger.warning(
            f"Task failed, will retry: {e}",
            extra={
                "task_id": self.request.id,
                "document_id": document_id,
                "retry": self.request.retries
            }
        )
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
```

## 6. 健康检查

### 6.1 健康检查接口

```python
# api/routers/health.py

from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(
    db = Depends(get_db),
    redis = Depends(get_redis),
    es = Depends(get_elasticsearch)
) -> Dict[str, Any]:
    """Check if all dependencies are ready."""
    checks = {}
    all_ready = True
    
    # Check PostgreSQL
    try:
        await db.execute("SELECT 1")
        checks["postgresql"] = "ok"
    except Exception as e:
        checks["postgresql"] = f"error: {e}"
        all_ready = False
    
    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        all_ready = False
    
    # Check Elasticsearch
    try:
        await es.info()
        checks["elasticsearch"] = "ok"
    except Exception as e:
        checks["elasticsearch"] = f"error: {e}"
        all_ready = False
    
    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks
    }


@router.get("/health/live")
async def liveness_check() -> Dict[str, str]:
    """Check if service is alive."""
    return {"status": "alive"}
```

## 7. 配置

### 7.1 日志配置

```yaml
# configs/logging.yaml

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  format: json  # json or text
  
  # 按模块设置级别
  loggers:
    src.rag: DEBUG
    src.infrastructure.tasks: INFO
    uvicorn.access: WARNING
```

### 7.2 环境变量

```bash
# .env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## 8. 最佳实践

### 8.1 日志记录原则

1. **适度记录**：记录足够的信息用于排查，但不要记录过多噪音
2. **敏感信息**：不记录密码、API Key、用户隐私数据
3. **结构化**：使用 extra 字段传递结构化数据，便于查询
4. **上下文**：包含足够的上下文（如 document_id, session_id）
5. **一致性**：使用统一的字段命名（如 `duration_ms` 而不是 `time`）

### 8.2 日志级别选择

```python
# ERROR - 必须修复的问题
logger.error("Database connection failed", exc_info=True)

# WARNING - 需要关注但可恢复
logger.warning("Rate limit approaching", extra={"remaining": 10})

# INFO - 业务事件
logger.info("Document uploaded", extra={"document_id": doc_id})

# DEBUG - 调试信息（生产环境通常关闭）
logger.debug("Query result", extra={"results": results})
```

---

最后更新：2026-01-19
版本：v1.0.0
