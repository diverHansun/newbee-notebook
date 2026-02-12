# 错误处理设计

## 1. 概述

本文档定义 MediMind Agent 的异常层次结构和错误处理规范，确保 API 返回一致的错误响应格式。

## 2. 设计原则

- **一致性**：所有错误遵循统一的响应格式
- **可追踪**：每个错误有唯一的错误码
- **可理解**：错误消息对用户友好
- **可调试**：提供足够的上下文信息

## 3. 错误响应格式

### 3.1 标准错误响应

```json
{
    "error_code": "E3001",
    "message": "该 Notebook 已达到 Session 上限（20 个）",
    "details": {
        "current_count": 20,
        "max_count": 20,
        "suggestions": [
            "删除不需要的 Session",
            "创建新的 Notebook"
        ]
    }
}
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| error_code | string | 是 | 唯一错误码，格式 Exxxx |
| message | string | 是 | 用户友好的错误描述 |
| details | object | 否 | 额外的上下文信息 |

## 4. 错误码规范

### 4.1 错误码分类

| 范围 | 分类 | 说明 |
|------|------|------|
| E1xxx | 通用错误 | 系统级别错误 |
| E2xxx | 认证权限 | 预留多用户支持 |
| E3xxx | Notebook 相关 | Notebook 和 Session 错误 |
| E4xxx | 文档相关 | 文档处理错误 |
| E5xxx | 对话相关 | 对话和消息错误 |
| E6xxx | 外部服务 | LLM、向量存储等错误 |

### 4.2 完整错误码列表

#### 通用错误 (E1xxx)

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E1000 | INTERNAL_ERROR | 500 | 内部服务器错误 |
| E1001 | VALIDATION_ERROR | 400 | 请求参数验证失败 |
| E1002 | NOT_FOUND | 404 | 资源不存在 |
| E1003 | METHOD_NOT_ALLOWED | 405 | HTTP 方法不支持 |
| E1004 | RATE_LIMITED | 429 | 请求频率超限 |

#### 认证权限 (E2xxx) - 预留

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E2000 | UNAUTHORIZED | 401 | 未认证 |
| E2001 | FORBIDDEN | 403 | 无权限 |

#### Notebook 相关 (E3xxx)

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E3000 | NOTEBOOK_NOT_FOUND | 404 | Notebook 不存在 |
| E3001 | SESSION_LIMIT_EXCEEDED | 400 | Session 数量达到上限 |
| E3002 | SESSION_NOT_FOUND | 404 | Session 不存在 |
| E3003 | REFERENCE_NOT_FOUND | 404 | 引用关系不存在 |
| E3004 | DUPLICATE_REFERENCE | 400 | 重复引用同一文档 |

#### 文档相关 (E4xxx)

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E4000 | DOCUMENT_NOT_FOUND | 404 | 文档不存在 |
| E4001 | DOCUMENT_PROCESSING | 409 | 文档正在处理中 |
| E4002 | DOCUMENT_REFERENCED | 409 | 文档被 Notebook 引用 |
| E4003 | UNSUPPORTED_FORMAT | 400 | 不支持的文件格式 |
| E4004 | FILE_TOO_LARGE | 413 | 文件大小超限 |
| E4005 | DOCUMENT_FAILED | 500 | 文档处理失败 |
| E4006 | INVALID_URL | 400 | 无效的 URL |

#### 对话相关 (E5xxx)

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E5000 | SESSION_REQUIRED | 400 | 需要指定 Session |
| E5001 | MODE_NOT_AVAILABLE | 400 | 对话模式不可用 |
| E5002 | EMPTY_MESSAGE | 400 | 消息内容为空 |
| E5003 | CONTEXT_TOO_LONG | 400 | 上下文超过限制 |

#### 外部服务 (E6xxx)

| 错误码 | 名称 | HTTP 状态码 | 说明 |
|--------|------|-------------|------|
| E6000 | LLM_ERROR | 502 | LLM 服务错误 |
| E6001 | LLM_TIMEOUT | 504 | LLM 请求超时 |
| E6002 | VECTOR_STORE_ERROR | 502 | 向量存储错误 |
| E6003 | SEARCH_ERROR | 502 | 搜索服务错误 |
| E6004 | CELERY_ERROR | 502 | 任务队列错误 |

## 5. 异常类层次结构

### 5.1 基础异常类

```python
# src/common/exceptions.py

from typing import Optional, Dict, Any


class MediMindException(Exception):
    """Base exception for all MediMind errors."""
    
    error_code: str = "E1000"
    message: str = "Internal error"
    http_status: int = 500
    
    def __init__(
        self, 
        message: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response format."""
        result = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result
```

### 5.2 通用异常

```python
class ValidationError(MediMindException):
    """Request validation failed."""
    error_code = "E1001"
    message = "Validation error"
    http_status = 400


class NotFoundError(MediMindException):
    """Resource not found."""
    error_code = "E1002"
    message = "Resource not found"
    http_status = 404
```

### 5.3 Notebook 相关异常

```python
class NotebookNotFoundError(NotFoundError):
    """Notebook not found."""
    error_code = "E3000"
    message = "Notebook not found"


class SessionLimitExceededError(MediMindException):
    """Session limit exceeded."""
    error_code = "E3001"
    message = "Session limit exceeded"
    http_status = 400
    
    def __init__(self, current_count: int, max_count: int = 20):
        super().__init__(
            message=f"该 Notebook 已达到 Session 上限（{max_count} 个）",
            details={
                "current_count": current_count,
                "max_count": max_count,
                "suggestions": [
                    "删除不需要的 Session",
                    "创建新的 Notebook"
                ]
            }
        )


class SessionNotFoundError(NotFoundError):
    """Session not found."""
    error_code = "E3002"
    message = "Session not found"


class ReferenceNotFoundError(NotFoundError):
    """Reference not found."""
    error_code = "E3003"
    message = "Reference not found"


class DuplicateReferenceError(MediMindException):
    """Document already referenced."""
    error_code = "E3004"
    message = "Document already referenced in this notebook"
    http_status = 400
```

### 5.4 文档相关异常

```python
class DocumentNotFoundError(NotFoundError):
    """Document not found."""
    error_code = "E4000"
    message = "Document not found"


class DocumentProcessingError(MediMindException):
    """Document is still processing."""
    error_code = "E4001"
    message = "Document is still processing"
    http_status = 409


class DocumentReferencedError(MediMindException):
    """Document is referenced by notebooks."""
    error_code = "E4002"
    message = "Document is referenced by notebooks"
    http_status = 409
    
    def __init__(self, reference_count: int, notebook_names: list):
        super().__init__(
            message=f"该文档被 {reference_count} 个 Notebook 引用",
            details={
                "reference_count": reference_count,
                "notebooks": notebook_names,
                "confirm_required": True
            }
        )


class UnsupportedFormatError(MediMindException):
    """Unsupported file format."""
    error_code = "E4003"
    message = "Unsupported file format"
    http_status = 400


class FileTooLargeError(MediMindException):
    """File size exceeds limit."""
    error_code = "E4004"
    message = "File size exceeds limit"
    http_status = 413


class DocumentFailedError(MediMindException):
    """Document processing failed."""
    error_code = "E4005"
    message = "Document processing failed"
    http_status = 500
```

### 5.5 对话相关异常

```python
class SessionRequiredError(MediMindException):
    """Session ID is required."""
    error_code = "E5000"
    message = "Session ID is required"
    http_status = 400


class ModeNotAvailableError(MediMindException):
    """Chat mode not available."""
    error_code = "E5001"
    message = "Chat mode not available"
    http_status = 400


class EmptyMessageError(MediMindException):
    """Message content is empty."""
    error_code = "E5002"
    message = "Message content cannot be empty"
    http_status = 400
```

### 5.6 外部服务异常

```python
class LLMError(MediMindException):
    """LLM service error."""
    error_code = "E6000"
    message = "LLM service error"
    http_status = 502


class LLMTimeoutError(MediMindException):
    """LLM request timeout."""
    error_code = "E6001"
    message = "LLM request timeout"
    http_status = 504


class VectorStoreError(MediMindException):
    """Vector store error."""
    error_code = "E6002"
    message = "Vector store error"
    http_status = 502


class SearchError(MediMindException):
    """Search service error."""
    error_code = "E6003"
    message = "Search service error"
    http_status = 502


class CeleryError(MediMindException):
    """Celery task error."""
    error_code = "E6004"
    message = "Task queue error"
    http_status = 502
```

## 6. FastAPI 异常处理器

### 6.1 全局异常处理

```python
# api/middleware/error_handler.py

from fastapi import Request
from fastapi.responses import JSONResponse
from src.common.exceptions import MediMindException


async def medimind_exception_handler(
    request: Request, 
    exc: MediMindException
) -> JSONResponse:
    """Handle MediMind custom exceptions."""
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict()
    )


async def generic_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    logger.error(f"Unexpected error: {exc}\n{traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "E1000",
            "message": "An unexpected error occurred"
        }
    )
```

### 6.2 注册异常处理器

```python
# api/main.py

from fastapi import FastAPI
from src.common.exceptions import MediMindException
from api.middleware.error_handler import (
    medimind_exception_handler,
    generic_exception_handler
)

app = FastAPI()

# Register exception handlers
app.add_exception_handler(MediMindException, medimind_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

## 7. 使用示例

### 7.1 在服务层抛出异常

```python
# application/services/session_service.py

from src.common.exceptions import (
    SessionLimitExceededError,
    NotebookNotFoundError
)


class SessionService:
    async def create_session(
        self, 
        notebook_id: str, 
        title: str
    ) -> Session:
        # 检查 Notebook 是否存在
        notebook = await self.notebook_repo.get(notebook_id)
        if not notebook:
            raise NotebookNotFoundError()
        
        # 检查 Session 上限
        count = await self.session_repo.count_by_notebook(notebook_id)
        if count >= 20:
            raise SessionLimitExceededError(current_count=count)
        
        # 创建 Session
        return await self.session_repo.create(...)
```

### 7.2 在 API 层使用

```python
# api/routers/sessions.py

from fastapi import APIRouter
from application.services.session_service import SessionService

router = APIRouter()


@router.post("/notebooks/{notebook_id}/sessions")
async def create_session(
    notebook_id: str,
    request: CreateSessionRequest,
    service: SessionService = Depends()
):
    # 如果抛出异常，会被全局处理器捕获
    session = await service.create_session(
        notebook_id=notebook_id,
        title=request.title
    )
    return session
```

## 8. 最佳实践

### 8.1 异常使用原则

1. **使用具体异常**：优先使用具体的异常类，而非基类
2. **提供上下文**：在 details 中提供有助于解决问题的信息
3. **用户友好**：message 应该对最终用户友好
4. **不暴露敏感信息**：生产环境不返回堆栈跟踪

### 8.2 异常处理层次

```
API Layer        → 捕获所有异常，统一格式返回
    ↓
Application Layer → 处理业务逻辑异常
    ↓
Core Layer       → 抛出领域相关异常
    ↓
Infrastructure   → 抛出技术相关异常
```

### 8.3 日志记录

```python
# 在异常处理器中记录日志
logger.error(
    "Request failed",
    extra={
        "error_code": exc.error_code,
        "path": request.url.path,
        "method": request.method,
        "details": exc.details
    }
)
```

---

最后更新：2026-01-19
版本：v1.0.0
