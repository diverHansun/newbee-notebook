# 迁移指南

## 1. 迁移概述

### 1.1 兼容性

本次改进**向后兼容**，现有本地部署可以无缝切换：

| 项目 | 兼容性 | 说明 |
|------|--------|------|
| API 端点 | 完全兼容 | 无任何变更 |
| 数据模型 | 完全兼容 | 无数据库变更 |
| 存储结构 | 完全兼容 | 文件路径不变 |
| 本地部署 | 完全兼容 | 可继续使用本地模式 |
| 配置文件 | 新增字段 | 旧配置仍有效 |

### 1.2 迁移策略

```
推荐迁移路径：
本地部署 -> 云服务（优先） -> 必要时回退本地

不推荐：
直接移除本地部署能力（保留作为备份）
```

## 2. 迁移前准备

### 2.1 环境要求

**软件版本**：

| 软件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10 | 3.11 |
| Docker | 20.10 | 24.0+ |
| Docker Compose | 2.0 | 2.20+ |

**云服务要求**（可选）：

- MinerU 账号（访问 mineru.net 注册）
- 已创建并部署的 Pipeline
- Pipeline ID（UUID 格式）

### 2.2 数据备份

```bash
# 备份数据卷
docker-compose down
docker run --rm -v medimind_postgres_data:/data \
  -v $(pwd)/backups:/backup ubuntu \
  tar czf /backup/postgres_$(date +%Y%m%d).tar.gz /data

# 备份 .env 文件
cp .env .env.backup

# 备份文档目录
tar czf backups/documents_$(date +%Y%m%d).tar.gz data/documents
```

### 2.3 版本标记

```bash
# 记录当前版本
git log -1 --oneline > backups/version.txt
docker-compose version >> backups/version.txt
```

## 3. 迁移步骤

### 3.1 步骤 1：更新代码

```bash
# 1. 拉取最新代码
git fetch origin
git checkout feature/mineru-cloud-service

# 2. 验证代码
git log --oneline -5
git diff main..feature/mineru-cloud-service

# 3. 合并到当前分支（可选）
git merge feature/mineru-cloud-service
```

### 3.2 步骤 2：安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装新依赖
pip install -r requirements.txt

# 验证 SDK 安装
python -c "from mineru_kie_sdk import MineruKIEClient; print('OK')"
```

### 3.3 步骤 3：配置云服务

**方案 A：直接切换到云服务**

```bash
# 1. 在 mineru.net 创建 Pipeline
#    - 登录 mineru.net
#    - 创建 Pipeline
#    - 部署 Pipeline
#    - 复制 Pipeline ID

# 2. 更新 .env 文件
cat >> .env <<EOF

# MinerU 云服务配置
MINERU_MODE=cloud
MINERU_PIPELINE_ID=your-pipeline-id-here
EOF

# 3. 验证配置
grep MINERU .env
```

**方案 B：保持本地模式（观望）**

```bash
# 添加配置但继续使用本地模式
cat >> .env <<EOF

# MinerU 配置（当前保持本地模式）
MINERU_MODE=local
MINERU_PIPELINE_ID=  # 后续切换时填写
EOF
```

### 3.4 步骤 4：更新 Docker 配置

```bash
# 无需手动修改，配置已在代码中更新
# 验证配置文件
diff -u docker-compose.yml.backup docker-compose.yml
```

### 3.5 步骤 5：重启服务

**云服务模式**：

```bash
# 1. 停止旧服务
docker-compose down

# 2. 启动新服务（不包含 mineru-api）
docker-compose up -d

# 3. 验证
docker-compose ps
# 应该看到:
#   medimind-postgres: Up
#   medimind-redis: Up
#   medimind-elasticsearch: Up
#   medimind-celery-worker: Up
# 不应该看到:
#   medimind-mineru-api
```

**本地模式**：

```bash
# 1. 停止旧服务
docker-compose down

# 2. 启动新服务（包含 mineru-api）
docker-compose --profile mineru-local up -d

# 3. 验证
docker-compose ps
# 应该看到所有服务包括 mineru-api
```

### 3.6 步骤 6：功能验证

```bash
# 1. 检查服务健康
docker-compose ps

# 2. 查看日志
docker-compose logs -f celery-worker | head -50

# 3. 测试文档上传
# 通过 API 或前端上传一个测试文档

# 4. 检查处理日志
docker-compose logs celery-worker | grep -i mineru

# 云服务模式应该看到:
# "使用 MinerU 云服务"
# "上传文件到 Pipeline"

# 本地模式应该看到:
# "调用本地 MinerU API"
```

## 4. 回滚方案

### 4.1 快速回滚

如果迁移后遇到问题，可以快速回滚：

```bash
# 1. 停止服务
docker-compose down

# 2. 切换回旧代码
git checkout main  # 或之前的分支

# 3. 恢复 .env
cp .env.backup .env

# 4. 启动旧服务
docker-compose up -d

# 5. 验证
docker-compose logs -f celery-worker
```

### 4.2 数据恢复

```bash
# 如果需要恢复数据
docker-compose down -v
docker volume create medimind_postgres_data
docker run --rm -v medimind_postgres_data:/data \
  -v $(pwd)/backups:/backup ubuntu \
  tar xzf /backup/postgres_YYYYMMDD.tar.gz -C /data --strip-components=1

docker-compose up -d
```

## 5. 常见迁移场景

### 5.1 场景 1：开发环境迁移

**目标**：快速验证云服务，保留本地能力

```bash
# 1. 配置云服务但默认使用本地
export MINERU_MODE=local
export MINERU_PIPELINE_ID=your-pipeline-id

# 2. 启动本地服务
docker-compose --profile mineru-local up -d

# 3. 临时测试云服务
docker-compose down
MINERU_MODE=cloud docker-compose up -d

# 4. 测试完成后切回本地
docker-compose down
MINERU_MODE=local docker-compose --profile mineru-local up -d
```

### 5.2 场景 2：生产环境迁移

**目标**：稳妥迁移，减少中断

```bash
# 第一阶段：代码部署（保持本地模式）
# 1. 部署新代码
# 2. 配置 MINERU_MODE=local
# 3. 重启服务
# 4. 验证功能正常

# 第二阶段：切换到云服务
# 1. 获取 Pipeline ID
# 2. 配置 MINERU_PIPELINE_ID
# 3. 在低峰期执行：
docker-compose down
sed -i 's/MINERU_MODE=local/MINERU_MODE=cloud/' .env
docker-compose up -d

# 4. 监控日志
docker-compose logs -f celery-worker

# 5. 验证文档处理

# 第三阶段：优化（可选）
# 1. 停止 mineru-api 容器释放资源
# 2. 调整超时和轮询参数
```

### 5.3 场景 3：离线环境

**目标**：继续使用本地模式

```bash
# 配置保持本地模式
export MINERU_MODE=local

# 正常启动
docker-compose --profile mineru-local up -d

# 说明：
# - 云服务相关代码不会被执行
# - 所有功能与之前一致
# - 可以随时切换到云服务（联网后）
```

## 6. 验证检查清单

### 6.1 部署验证

- [ ] 代码已更新到最新版本
- [ ] requirements.txt 已安装（mineru-kie-sdk 存在）
- [ ] .env 文件已配置 MINERU_MODE
- [ ] 云服务模式已配置 MINERU_PIPELINE_ID
- [ ] Docker Compose 配置已更新

### 6.2 功能验证

- [ ] 服务启动成功（docker-compose ps 全绿）
- [ ] 日志无错误（docker-compose logs）
- [ ] 文档上传成功
- [ ] 文档处理成功（查看 Celery 日志）
- [ ] 文档可以搜索和问答

### 6.3 模式验证

**云服务模式**：

- [ ] mineru-api 容器未启动
- [ ] 日志显示 "使用 MinerU 云服务"
- [ ] 处理速度明显提升

**本地模式**：

- [ ] mineru-api 容器已启动且健康
- [ ] 日志显示 "调用本地 MinerU API"
- [ ] 处理功能正常

## 7. 故障排查

### 7.1 迁移后常见问题

**问题 1：celery-worker 报错 "No module named 'mineru_kie_sdk'"**

```
原因: requirements.txt 未安装

解决:
docker-compose down
docker-compose up -d --build celery-worker
```

**问题 2：云服务模式报错 "pipeline_id is required"**

```
原因: .env 中未配置 MINERU_PIPELINE_ID

解决:
echo "MINERU_PIPELINE_ID=your-id" >> .env
docker-compose restart celery-worker
```

**问题 3：本地模式报错 "Connection refused to mineru-api"**

```
原因: 本地模式但未启用 profile

解决:
docker-compose down
docker-compose --profile mineru-local up -d
```

**问题 4：文档处理失败，日志显示 "MinerU 云服务在熔断期"**

```
原因: 云服务不可达，触发熔断机制

解决:
1. 检查网络连接
2. 验证 Pipeline ID 是否正确
3. 等待 5 分钟后自动恢复
4. 或临时切换到本地模式
```

### 7.2 性能问题

**问题：云服务处理速度未明显提升**

```
可能原因:
1. 网络延迟较高
2. 轮询间隔过大
3. 文件较小，网络传输成为瓶颈

优化:
1. 减少 poll_interval（如改为 3s）
2. 增加 timeout（避免频繁超时）
3. 对于小文件考虑继续使用本地模式
```

### 7.3 获取支持

```
遇到问题时：

1. 查看文档
   - README.md：快速开始
   - 01-architecture.md：架构设计
   - 02-configuration.md：配置说明

2. 检查日志
   - docker-compose logs celery-worker
   - docker-compose logs mineru-api

3. 提交 Issue
   - 提供详细的错误日志
   - 说明环境配置
   - 描述复现步骤
```

## 8. 最佳实践

### 8.1 渐进式迁移

```
推荐顺序：
1. 开发环境验证（本地模式）
2. 开发环境测试（云服务模式）
3. 预发环境部署（云服务模式）
4. 生产环境灰度（部分文档使用云服务）
5. 生产环境全量（完全使用云服务）
```

### 8.2 配置管理

```bash
# 使用不同环境的配置文件
.env.development   # 开发环境（本地模式）
.env.staging       # 预发环境（云服务模式）
.env.production    # 生产环境（云服务模式）

# 部署时复制对应配置
cp .env.production .env
```

### 8.3 监控指标

```
关键监控指标：
1. 文档处理成功率
2. 文档处理平均耗时
3. MinerU 调用失败率
4. Fallback 触发次数
5. 熔断触发次数

建议使用 Prometheus + Grafana 监控
```

## 9. 迁移时间表参考

### 9.1 小型项目（单服务器）

| 阶段 | 预计时间 | 说明 |
|------|----------|------|
| 准备阶段 | 30min | 备份、获取 Pipeline ID |
| 代码更新 | 15min | Git 拉取、依赖安装 |
| 配置更新 | 10min | 修改 .env 文件 |
| 服务重启 | 5min | docker-compose 重启 |
| 功能验证 | 30min | 测试文档处理 |
| **总计** | **90min** | 约 1.5 小时 |

### 9.2 中型项目（多服务器）

| 阶段 | 预计时间 | 说明 |
|------|----------|------|
| 准备阶段 | 1h | 备份、计划、沟通 |
| 灰度部署 | 2h | 部分服务器迁移 |
| 观察期 | 24h | 监控灰度效果 |
| 全量部署 | 1h | 所有服务器迁移 |
| **总计** | **28h** | 约 1-2 天 |
