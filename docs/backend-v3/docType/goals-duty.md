# goals-duty.md — 文档类型扩展模块

## Design Goals

1. 让 `.pptx` 和 `.epub` 在 `backend-v3` 中获得**正式、稳定**的上传与处理支持。
2. 优先保证新类型可以进入完整闭环：上传、转换、索引、检索、总结。
3. 保持现有 `MinerU` 兼容边界不变：
   - 本地 `MinerU` 仍只兼容 PDF
   - 云端 `MinerU` 仍按现有实现兼容 PDF / DOC / DOCX
4. 先利用现有 `MarkItDown` 能力交付稳定版本，再根据真实质量决定是否引入专用解析器。

## Phase 1 Duties

1. 在后端 `DocumentType` 枚举中注册 `PPTX` 和 `EPUB`。
2. 在上传存储层的扩展名白名单中加入 `pptx` 和 `epub`，保证文件能成功入库。
3. 在 `MarkItDownConverter._supported` 集合中补齐 `.epub`。
4. 保持 `DocumentProcessor` 当前总体路由策略不变，并通过测试明确：
   - `.pptx/.epub` 由 `MarkItDown` 接管
   - `MinerU` 对这两类格式不参与处理
5. 在前端上传入口同步支持格式说明与 `accept` 过滤。
6. 增加覆盖类型识别、上传白名单、转换路由、真实文件转换的测试。

## Phase 2 Candidate Duties

只有在阶段一验证后发现质量明显不足时，才进入阶段二，候选职责如下：

1. 新增专用 `PPTX` converter，参考 `Burner-X/js` 的按幻灯片结构提取思路。
2. 新增专用 `EPUB` converter，参考 `Burner-X/js` 的 `OPF/spine` 顺序控制思路。
3. 将专用 converter 放在 `MarkItDown` 之前，保留 fallback。

## Non-Duties

- 不扩展 MinerU 现有支持范围
- 不引入新的 OCR 服务或云解析服务
- 不修改 PDF、DOCX、CSV、XLSX 等既有格式链路
- 不在本次实现中承诺完整保留 `.pptx/.epub` 的图片、批注、复杂排版语义
- 不重做下游索引、切块、检索、总结逻辑
- 不在本次实现中重构整个 document processing 架构

## Delivery Standard

阶段一交付标准不是“结构语义完美”，而是：

1. 文件可以成功上传
2. 文件可以成功转为非空 Markdown
3. 文档可进入现有索引与检索链路
4. Studio / Notebook 侧可以正常基于该文档做总结或问答
5. 不破坏既有 PDF / DOCX / TXT / Markdown 等格式行为
