# Improve-6 文档存储与清理机制

本文档描述文档文件的存储策略(继续使用 bind mount)、精确清理工具(make clean-doc 按 document_id 删除)、以及启动时孤儿检测机制。

---

## 1. 存储策略决策

### 1.1 方案对比

| 维度 | Named Volume | Bind Mount + 清理工具 |
|------|-------------|---------------------|
| `docker compose down -v` 一致性 | 自动一致(卷随 `-v` 删除) | 需要手动执行清理命令 |
| 开发调试便利性 | 需 `docker exec` 或 `docker cp` 查看文件 | 直接在宿主机目录查看 |
| MinerU 转换结果检查 | 不便(进容器或拷贝出来) | 直接打开 `data/documents/{id}/markdown/` |
| CI/CD 适配 | 更标准 | 需要额外清理步骤 |
| 存储占用可见性 | 隐藏在 Docker 存储后端 | `du -sh data/documents/` 直接可见 |

### 1.2 决策

**选择 Bind Mount + 清理工具**，理由:

1. 项目处于 backend-v1 开发期，需要频繁检查 MinerU 转换结果(Markdown 质量、图片提取)
2. PDF 文档体积大(16MB~22MB)，bind mount 可以直接在文件管理器中浏览
3. 孤儿文件问题可以通过精确清理工具解决，不需要改变存储架构
4. Named Volume 的便利性在生产环境更有价值，可在后续部署阶段再迁移

### 1.3 docker-compose.yml 不变

当前配置保持不变:

```yaml
services:
  celery-worker:
    volumes:
      - ./:/app    # 整个项目目录挂载
```

`DOCUMENTS_DIR` 继续使用 `data/documents`(相对于 `/app`)。

---

## 2. make clean-doc: 按 document_id 精确删除

### 2.1 设计原则

1. **精确匹配**: 必须指定 document_id，不支持批量全删
2. **安全确认**: 删除前显示目录大小和内容概要，要求确认
3. **路径校验**: 防止路径遍历攻击(document_id 必须是 UUID 格式)
4. **幂等性**: 目录不存在时不报错，输出提示信息

### 2.2 Makefile 定义

```makefile
# Makefile

DOCUMENTS_DIR := data/documents

.PHONY: clean-doc clean-orphans help-clean

clean-doc:  ## 按 document_id 删除文档文件 (用法: make clean-doc ID=<document_id>)
ifndef ID
	@echo "错误: 必须指定 document_id"
	@echo "用法: make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108"
	@exit 1
endif
	@if echo "$(ID)" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$$'; then \
		if [ -d "$(DOCUMENTS_DIR)/$(ID)" ]; then \
			echo "即将删除: $(DOCUMENTS_DIR)/$(ID)"; \
			echo "目录内容:"; \
			ls -la "$(DOCUMENTS_DIR)/$(ID)/"; \
			echo "---"; \
			du -sh "$(DOCUMENTS_DIR)/$(ID)"; \
			echo "---"; \
			read -p "确认删除? [y/N] " confirm; \
			if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
				rm -rf "$(DOCUMENTS_DIR)/$(ID)"; \
				echo "已删除: $(DOCUMENTS_DIR)/$(ID)"; \
			else \
				echo "取消删除"; \
			fi; \
		else \
			echo "目录不存在: $(DOCUMENTS_DIR)/$(ID)"; \
		fi; \
	else \
		echo "错误: ID 格式无效，必须是 UUID 格式"; \
		echo "示例: make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108"; \
		exit 1; \
	fi

clean-orphans: ## 扫描并删除所有孤儿文档目录 (需要数据库运行)
	@echo "扫描孤儿文档目录..."
	@python -m newbee_notebook.scripts.clean_orphan_documents --documents-dir $(DOCUMENTS_DIR)

help-clean: ## 显示清理相关命令帮助
	@echo "文档清理命令:"
	@echo "  make clean-doc ID=<uuid>    按 document_id 精确删除单个文档目录"
	@echo "  make clean-orphans          扫描并删除所有无 DB 记录的孤儿文档目录"
	@echo ""
	@echo "说明:"
	@echo "  - clean-doc 在删除前会显示目录大小并要求确认"
	@echo "  - clean-orphans 需要数据库运行中，会对比 DB 记录和文件系统"
	@echo "  - docker compose down -v 后建议执行 make clean-orphans"
```

### 2.3 使用示例

**精确删除单个文档**:

```bash
$ make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108
即将删除: data/documents/393f579b-2318-42eb-8a0a-9b5232900108
目录内容:
drwxr-xr-x  original/
drwxr-xr-x  markdown/
drwxr-xr-x  assets/
---
17M     data/documents/393f579b-2318-42eb-8a0a-9b5232900108
---
确认删除? [y/N] y
已删除: data/documents/393f579b-2318-42eb-8a0a-9b5232900108
```

**格式错误时的提示**:

```bash
$ make clean-doc ID=invalid-id
错误: ID 格式无效，必须是 UUID 格式
示例: make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108
```

**未指定 ID 时的提示**:

```bash
$ make clean-doc
错误: 必须指定 document_id
用法: make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108
```

---

## 3. Windows 兼容方案 (PowerShell 脚本)

由于项目主要在 Windows 环境开发，同时提供 PowerShell 版本:

### 3.1 scripts/clean-doc.ps1

```powershell
<#
.SYNOPSIS
    按 document_id 精确删除文档目录
.PARAMETER Id
    文档的 UUID 格式 document_id
.EXAMPLE
    .\scripts\clean-doc.ps1 -Id 393f579b-2318-42eb-8a0a-9b5232900108
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Id
)

$DocumentsDir = "data\documents"

# UUID 格式校验
if ($Id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
    Write-Error "ID 格式无效，必须是 UUID 格式"
    Write-Host "示例: .\scripts\clean-doc.ps1 -Id 393f579b-2318-42eb-8a0a-9b5232900108"
    exit 1
}

$TargetPath = Join-Path $DocumentsDir $Id

if (-not (Test-Path $TargetPath)) {
    Write-Host "目录不存在: $TargetPath"
    exit 0
}

# 显示目录信息
Write-Host "即将删除: $TargetPath"
Write-Host "目录内容:"
Get-ChildItem $TargetPath | Format-Table Name, Length, LastWriteTime
$size = (Get-ChildItem $TargetPath -Recurse | Measure-Object -Property Length -Sum).Sum
Write-Host "总大小: $([math]::Round($size / 1MB, 2)) MB"
Write-Host "---"

$confirm = Read-Host "确认删除? [y/N]"
if ($confirm -eq 'y' -or $confirm -eq 'Y') {
    Remove-Item -Recurse -Force $TargetPath
    Write-Host "已删除: $TargetPath"
} else {
    Write-Host "取消删除"
}
```

### 3.2 VS Code Task 配置

在 `.vscode/tasks.json` 中添加任务，支持从 VS Code 直接运行:

```json
{
    "label": "Clean Document by ID",
    "type": "shell",
    "command": "powershell",
    "args": ["-File", "scripts/clean-doc.ps1", "-Id", "${input:documentId}"],
    "problemMatcher": []
}
```

---

## 4. 孤儿文档检测

### 4.1 启动时自动检测

在应用启动时(或 health check 中)扫描文件系统和数据库，检测孤儿文档并输出 warning 日志:

```python
# newbee_notebook/scripts/detect_orphans.py

import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)


async def detect_orphan_documents(
    documents_dir: str,
    document_repo,
) -> list[str]:
    """扫描文件系统中的文档目录，对比数据库记录，返回孤儿 document_id 列表。

    孤儿文档: 文件系统中存在目录但数据库中无对应记录的文档。

    Args:
        documents_dir: 文档存储根目录 (如 "data/documents")
        document_repo: DocumentRepository 实例

    Returns:
        孤儿 document_id 列表
    """
    doc_path = Path(documents_dir)
    if not doc_path.exists():
        return []

    # 收集文件系统中的 UUID 目录名
    fs_ids = set()
    for item in doc_path.iterdir():
        if item.is_dir() and UUID_PATTERN.match(item.name):
            fs_ids.add(item.name)

    if not fs_ids:
        return []

    # 批量查询数据库中存在的 document_id
    db_docs = await document_repo.get_batch(list(fs_ids))
    db_ids = {doc.document_id for doc in db_docs}

    # 差集即为孤儿
    orphan_ids = list(fs_ids - db_ids)

    if orphan_ids:
        total_size = 0
        for oid in orphan_ids:
            orphan_path = doc_path / oid
            for f in orphan_path.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size

        size_mb = total_size / (1024 * 1024)
        logger.warning(
            "发现 %d 个孤儿文档目录 (共 %.1f MB)。"
            "这些目录在文件系统中存在但数据库中无记录。"
            "建议执行 'make clean-orphans' 清理。"
            "孤儿 ID: %s",
            len(orphan_ids), size_mb,
            ", ".join(orphan_ids[:5]) + ("..." if len(orphan_ids) > 5 else ""),
        )

    return orphan_ids
```

### 4.2 检测触发时机

在应用启动流程中调用一次即可:

```python
# main.py 或 startup event 中
@app.on_event("startup")
async def startup_event():
    ...
    # 孤儿文档检测 (仅日志警告，不自动删除)
    from newbee_notebook.scripts.detect_orphans import detect_orphan_documents
    orphans = await detect_orphan_documents(
        documents_dir=settings.DOCUMENTS_DIR,
        document_repo=document_repo,
    )
    if orphans:
        logger.info("如需清理孤儿文档，请执行: make clean-orphans")
```

### 4.3 批量清理孤儿脚本

```python
# newbee_notebook/scripts/clean_orphan_documents.py

"""扫描并交互式清理孤儿文档目录。

用法: python -m newbee_notebook.scripts.clean_orphan_documents --documents-dir data/documents
"""

import argparse
import asyncio
import shutil
from pathlib import Path


async def main(documents_dir: str):
    # 初始化数据库连接和 repository
    ...

    orphan_ids = await detect_orphan_documents(documents_dir, document_repo)

    if not orphan_ids:
        print("未发现孤儿文档目录")
        return

    print(f"发现 {len(orphan_ids)} 个孤儿文档目录:")
    doc_path = Path(documents_dir)
    total_size = 0
    for oid in orphan_ids:
        p = doc_path / oid
        size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        total_size += size
        print(f"  {oid}  ({size / (1024*1024):.1f} MB)")

    print(f"\n总计: {total_size / (1024*1024):.1f} MB")
    confirm = input("确认删除所有孤儿目录? [y/N] ")
    if confirm.lower() != 'y':
        print("取消删除")
        return

    for oid in orphan_ids:
        p = doc_path / oid
        shutil.rmtree(p)
        print(f"  已删除: {oid}")

    print(f"清理完成，共删除 {len(orphan_ids)} 个目录")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents-dir", default="data/documents")
    args = parser.parse_args()
    asyncio.run(main(args.documents_dir))
```

---

## 5. 运维文档说明

在 README.md 或 quickstart.md 中增加以下说明:

### 5.1 环境重建流程

```
# 1. 停止并删除 Docker 卷 (数据库和索引数据将被清除)
docker compose down -v

# 2. 清理宿主机上的孤儿文档文件
# 方式 A: 批量清理 (需要数据库运行)
docker compose up -d postgres
make clean-orphans

# 方式 B: 按文档 ID 精确清理
make clean-doc ID=393f579b-2318-42eb-8a0a-9b5232900108

# 方式 C: PowerShell (Windows)
.\scripts\clean-doc.ps1 -Id 393f579b-2318-42eb-8a0a-9b5232900108

# 3. 重新启动所有服务
docker compose up -d
```

### 5.2 日常注意事项

- `docker compose down` (不带 `-v`): 安全操作，数据全部保留
- `docker compose down -v`: 危险操作，数据库和索引被删除，需要手动清理文档文件
- 应用启动时如果看到孤儿文档警告，按提示执行清理命令即可

---

## 6. 需要新增的文件

| 文件 | 用途 |
|------|------|
| `Makefile` | 新增 `clean-doc`、`clean-orphans`、`help-clean` targets |
| `scripts/clean-doc.ps1` | Windows PowerShell 版精确删除脚本 |
| `newbee_notebook/scripts/detect_orphans.py` | 孤儿文档检测模块 |
| `newbee_notebook/scripts/clean_orphan_documents.py` | 批量清理孤儿脚本 |

## 7. 需要修改的文件

| 文件 | 改动 |
|------|------|
| `main.py` (或应用启动入口) | startup event 中调用 `detect_orphan_documents()` |
| `README.md` 或 `quickstart.md` | 增加环境重建和文档清理说明 |
