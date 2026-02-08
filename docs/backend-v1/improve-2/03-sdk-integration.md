# SDK 集成细节

## 1. MinerU KIE SDK 概述

### 1.1 SDK 信息

| 项目 | 信息 |
|------|------|
| 包名 | `mineru-kie-sdk` |
| 版本 | 0.1.1+ |
| Python 要求 | >= 3.10 |
| 依赖 | aiohttp, filetype, func-timeout, requests |
| 官方文档 | https://mineru.net/apiManage/kie-sdk |

### 1.2 核心功能

```
MinerU KIE SDK 提供的功能：
1. 文件上传（upload_file）
2. 结果查询（get_result）
3. 自动重试机制
4. 完整类型提示
```

### 1.3 支持的文件类型

```
- PDF (application/pdf)
- JPEG (image/jpeg)
- PNG (image/png)
- GIF (image/gif)
```

## 2. SDK 安装

### 2.1 添加到依赖

**requirements.txt**：

```txt
# MinerU Cloud Service SDK
mineru-kie-sdk>=0.1.1
```

### 2.2 验证安装

```bash
# 进入虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 验证安装
python -c "from mineru_kie_sdk import MineruKIEClient; print('SDK installed successfully')"
```

## 3. SDK API 详解

### 3.1 MineruKIEClient 类

**初始化**：

```python
from mineru_kie_sdk import MineruKIEClient

client = MineruKIEClient(
    pipeline_id="550e8400-e29b-41d4-a716-446655440000",  # 必填
    base_url="https://mineru.net/api/kie",              # 可选
    timeout=30                                           # 可选，请求超时
)
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 | 默认值 |
|------|------|------|------|--------|
| `pipeline_id` | str | 是 | Pipeline ID（UUID 格式） | - |
| `base_url` | str | 否 | API 基础 URL | https://mineru.net/api/kie |
| `timeout` | int | 否 | HTTP 请求超时（秒） | 30 |

### 3.2 upload_file 方法

**方法签名**：

```python
def upload_file(self, file_path: Union[str, Path]) -> List[int]:
    """
    上传文件到服务器

    Args:
        file_path: 文件路径

    Returns:
        List[int]: 文件 ID 列表

    Raises:
        ValueError: 文件类型不支持或文件不存在
        requests.RequestException: 上传失败
    """
```

**返回示例**：

```python
file_ids = client.upload_file("document.pdf")
# 返回: [123]
```

**错误处理**：

```python
try:
    file_ids = client.upload_file("document.pdf")
except ValueError as e:
    # 文件类型不支持或文件不存在
    print(f"文件错误: {e}")
except requests.RequestException as e:
    # 网络错误或服务端错误
    print(f"上传失败: {e}")
```

### 3.3 get_result 方法

**方法签名**：

```python
def get_result(
    self,
    file_ids: List[int] = [],
    timeout: int = 60,
    poll_interval: int = 10
) -> Dict[str, Optional[dict]]:
    """
    获取文件的解析结果（轮询直到完成或超时）

    Args:
        file_ids: 文件 ID 列表，默认使用上次上传的 ID
        timeout: 超时时间（秒），-1 表示无限等待
        poll_interval: 轮询间隔（秒）

    Returns:
        Dict[str, Optional[dict]]: 包含 parse、split、extract 的字典

    Raises:
        ValueError: 未上传文件或 file_ids 无效
        requests.RequestException: 请求失败或处理失败
        TimeoutError: 超时
    """
```

**返回示例**：

```python
results = client.get_result(timeout=60, poll_interval=5)
# 返回:
# {
#     "parse": {
#         "md_content": "# 标题\n\n正文内容...",
#         "page_count": 5,
#         ...
#     },
#     "split": {...},
#     "extract": {...}
# }
```

**状态码说明**：

| code | 含义 | SDK 行为 |
|------|------|----------|
| 0 | 处理完成 | 返回结果 |
| 1 | 处理中 | 继续轮询 |
| -1 | 处理失败 | 抛出异常 |
| -2 | 等待执行 | 继续轮询 |

## 4. MinerUCloudConverter 实现

### 4.1 类设计

```python
import asyncio
from pathlib import Path
from typing import Optional
import requests
from mineru_kie_sdk import MineruKIEClient
from pypdf import PdfReader

from .base import Converter, ConversionResult


class MinerUCloudConverter(Converter):
    """基于 MinerU KIE SDK 的云服务 Converter"""

    def __init__(
        self,
        pipeline_id: str,
        base_url: str = "https://mineru.net/api/kie",
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> None:
        if not pipeline_id:
            raise ValueError("pipeline_id is required for MinerU cloud service")

        self.client = MineruKIEClient(
            pipeline_id=pipeline_id,
            base_url=base_url,
            timeout=30  # HTTP 请求超时
        )
        self.processing_timeout = timeout_seconds
        self.poll_interval = poll_interval

    def can_handle(self, ext: str) -> bool:
        """支持 PDF、JPEG、PNG"""
        return ext.lower() in [".pdf", ".jpg", ".jpeg", ".png"]

    async def convert(self, file_path: str) -> ConversionResult:
        """转换文档为 Markdown"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        # 1. 检查限制
        await self._check_limits(path)

        # 2. 上传文件（同步，使用线程池）
        file_ids = await asyncio.to_thread(
            self.client.upload_file,
            path
        )

        # 3. 轮询获取结果
        results = await asyncio.to_thread(
            self.client.get_result,
            file_ids=file_ids,
            timeout=self.processing_timeout,
            poll_interval=self.poll_interval
        )

        # 4. 提取结果
        parse_result = results.get("parse") or {}
        markdown = parse_result.get("md_content", "")

        if not markdown:
            raise RuntimeError("MinerU cloud service returned empty markdown")

        page_count = parse_result.get("page_count", 0)
        if not page_count and path.suffix.lower() == ".pdf":
            page_count = await self._count_pages(path)

        return ConversionResult(
            markdown=markdown,
            page_count=page_count or 1,
            images=None  # 云服务暂不返回图片
        )

    async def _check_limits(self, path: Path) -> None:
        """检查云服务限制"""
        # 检查文件大小
        size = path.stat().st_size
        max_size = 100 * 1024 * 1024  # 100MB
        if size > max_size:
            raise ValueError(
                f"文件过大 ({size / 1024 / 1024:.1f}MB)，"
                f"云服务限制为 100MB"
            )

        # 检查 PDF 页数
        if path.suffix.lower() == ".pdf":
            page_count = await self._count_pages(path)
            if page_count > 10:
                raise ValueError(
                    f"PDF 页数过多 ({page_count} 页)，"
                    f"云服务限制为 10 页"
                )

    @staticmethod
    async def _count_pages(path: Path) -> int:
        """统计 PDF 页数"""
        def _count() -> int:
            with path.open("rb") as f:
                return len(PdfReader(f).pages)

        try:
            return await asyncio.to_thread(_count)
        except Exception:
            return 0
```

### 4.2 关键设计点

**异步适配**：

```python
# SDK 是同步的，使用 asyncio.to_thread 适配异步环境
file_ids = await asyncio.to_thread(self.client.upload_file, path)
results = await asyncio.to_thread(self.client.get_result, ...)
```

**限制检查**：

```python
# 在上传前检查，避免浪费网络流量
await self._check_limits(path)
```

**错误传播**：

```python
# SDK 抛出的异常会被上层 DocumentProcessor 捕获并降级
# ValueError -> 限制错误，记录警告，降级到 PyPDF
# requests.RequestException -> 网络错误，启用熔断，降级到 PyPDF
# TimeoutError -> 超时，记录警告，降级到 PyPDF
```

## 5. 与 DocumentProcessor 集成

### 5.1 初始化逻辑

```python
class DocumentProcessor:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or get_document_processing_config()
        dp_cfg = cfg.get("document_processing", {})

        mode = dp_cfg.get("mineru_mode", "cloud")
        converters: List[Converter] = []

        # Cloud 模式
        if mode == "cloud":
            cloud_cfg = dp_cfg.get("mineru_cloud", {})
            pipeline_id = cloud_cfg.get("pipeline_id")

            if pipeline_id:
                try:
                    converters.append(MinerUCloudConverter(
                        pipeline_id=pipeline_id,
                        base_url=cloud_cfg.get("base_url", "https://mineru.net/api/kie"),
                        timeout_seconds=cloud_cfg.get("timeout_seconds", 300),
                        poll_interval=cloud_cfg.get("poll_interval", 5),
                    ))
                except ValueError as e:
                    logger.error(f"Failed to initialize MinerU cloud converter: {e}")
            else:
                logger.warning(
                    "MINERU_MODE=cloud but no pipeline_id provided. "
                    "MinerU cloud service will be disabled."
                )

        # Local 模式
        elif mode == "local":
            local_cfg = dp_cfg.get("mineru_local", {})
            converters.append(MinerULocalConverter(
                base_url=local_cfg.get("api_url", "http://mineru-api:8000"),
                timeout_seconds=local_cfg.get("timeout_seconds", 0),
                backend=local_cfg.get("backend", "pipeline"),
                lang_list=local_cfg.get("lang_list", "ch"),
            ))

        # Fallback converters
        converters.extend([PyPdfConverter(), MarkItDownConverter()])
        self._converters = converters
```

### 5.2 错误处理

```python
async def convert(self, file_path: str) -> ConversionResult:
    """转换文档，支持 Fallback"""
    ext = Path(file_path).suffix.lower()
    converters = self._get_converters_for_ext(ext)

    if not converters:
        raise RuntimeError(f"Unsupported file type: {ext}")

    last_error: Optional[Exception] = None
    for converter in converters:
        # 熔断检查（针对云服务）
        if isinstance(converter, MinerUCloudConverter):
            if time.monotonic() < self._mineru_unavailable_until:
                logger.info("MinerU 云服务在熔断期，跳过")
                continue

        try:
            return await converter.convert(file_path)

        except Exception as e:
            converter_name = type(converter).__name__

            # 云服务特殊处理
            if isinstance(converter, MinerUCloudConverter):
                # 网络错误 -> 熔断
                if isinstance(e, (requests.RequestException, TimeoutError)):
                    self._mineru_unavailable_until = (
                        time.monotonic() + self._mineru_unavailable_cooldown
                    )
                    logger.warning(
                        f"MinerU 云服务不可达，熔断 {self._mineru_unavailable_cooldown}s"
                    )

                # 限制错误 -> 记录警告
                elif isinstance(e, ValueError):
                    logger.warning(f"MinerU 云服务限制: {e}")

            logger.info(f"{converter_name} 失败: {e}，尝试下一个 converter")
            last_error = e
            continue

    raise RuntimeError(
        f"所有 converter 都失败了，最后一个错误: {last_error}"
    )
```

## 6. SDK 限制与约束

### 6.1 云服务限制

| 限制项 | 值 | 说明 |
|--------|-----|------|
| Pipeline 文件数 | 10 | 单个 Pipeline 最多 10 个文件 |
| 单文件大小 | 100MB | 超过需使用本地模式 |
| PDF 页数 | 10 页 | 超过需使用本地模式 |
| 并发请求 | 未限制 | 由云端控制 |

### 6.2 应对策略

**文件过大**：

```python
# 自动降级到本地 converter
# 或提示用户压缩文件
```

**Pipeline 满**：

```python
# 方案 1: 定期手动清理旧文件
# 方案 2: 创建多个 Pipeline 轮换
# 方案 3: 在错误信息中提示用户
```

**网络不稳定**：

```python
# SDK 内置重试机制（3 次）
# 应用层熔断机制（5 分钟）
```

## 7. 测试与调试

### 7.1 单元测试

```python
import pytest
from unittest.mock import Mock, patch
from mineru_kie_sdk import MineruKIEClient


def test_cloud_converter_init():
    """测试初始化"""
    converter = MinerUCloudConverter(
        pipeline_id="test-id",
        timeout_seconds=60
    )
    assert converter.client.pipeline_id == "test-id"


def test_cloud_converter_check_limits():
    """测试限制检查"""
    converter = MinerUCloudConverter(pipeline_id="test-id")

    # 文件过大应抛出异常
    with pytest.raises(ValueError, match="文件过大"):
        await converter._check_limits(Path("large_file.pdf"))


@patch.object(MineruKIEClient, 'upload_file')
@patch.object(MineruKIEClient, 'get_result')
async def test_cloud_converter_convert(mock_get, mock_upload):
    """测试转换流程"""
    mock_upload.return_value = [123]
    mock_get.return_value = {
        "parse": {"md_content": "# Test", "page_count": 1}
    }

    converter = MinerUCloudConverter(pipeline_id="test-id")
    result = await converter.convert("test.pdf")

    assert result.markdown == "# Test"
    assert result.page_count == 1
```

### 7.2 手动测试

```python
# 测试脚本: scripts/test_mineru_cloud.py
import asyncio
from pathlib import Path
from medimind_agent.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter
)


async def main():
    converter = MinerUCloudConverter(
        pipeline_id="your-pipeline-id",
        timeout_seconds=120,
        poll_interval=5
    )

    test_file = Path("test_data/sample.pdf")
    print(f"测试文件: {test_file}")

    try:
        result = await converter.convert(str(test_file))
        print(f"✓ 转换成功")
        print(f"  - Markdown 长度: {len(result.markdown)}")
        print(f"  - 页数: {result.page_count}")
        print(f"  - 前 200 字符:\n{result.markdown[:200]}")
    except Exception as e:
        print(f"✗ 转换失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 7.3 调试技巧

**启用详细日志**：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**查看 HTTP 请求**：

```python
# SDK 使用 requests，可以启用 HTTP 日志
import http.client
http.client.HTTPConnection.debuglevel = 1
```

**轮询进度监控**：

```python
# 修改 SDK 源码（临时调试）
# 在 get_result 轮询循环中添加进度打印
print(f"轮询中... 状态: {code}, 消息: {msg}")
```
