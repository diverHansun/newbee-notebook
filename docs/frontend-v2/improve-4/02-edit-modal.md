# 编辑 Modal 设计规范

## 功能定位

编辑 Modal 负责收集用户对 Notebook 名称和描述的修改，并调用已有的后端 PATCH 接口完成更新。它在用户从右键菜单点击"编辑信息"后打开。

## 表单字段

| 字段 | 类型 | 必填 | 最大长度 | 初始值 |
|------|------|------|---------|--------|
| 名称（title） | 单行文本输入 | 是 | 100 字符 | 当前 notebook.title |
| 描述（description） | 多行文本输入 | 否 | 300 字符 | 当前 notebook.description |

初始值从触发右键菜单时的 notebook 数据中预填充，用户打开 Modal 后可直接看到当前内容并修改。

## 状态管理

在 `page.tsx` 中新增状态：

```typescript
type EditNotebookState = {
  notebookId: string;
  title: string;
  description: string;
};

const [editingNotebook, setEditingNotebook] = useState<EditNotebookState | null>(null);
```

`editingNotebook` 为 `null` 时 Modal 不渲染。

## 交互流程

```
右键菜单点击"编辑信息"
    |
    v
setEditingNotebook({ notebookId, title, description })
    |
    v
Modal 打开，预填当前值
    |
    v
用户修改 title / description
    |
    v
点击"保存"
    |
    +--> 校验 title 不为空
    |       |-- 为空：输入框显示错误提示，不提交
    |       |-- 非空：继续
    |
    v
调用 updateMutation.mutate({ notebookId, title, description })
    |
    v
成功 --> 关闭 Modal，invalidateQueries(["notebooks"])
失败 --> Modal 保持开启，显示错误提示
```

## API 集成

复用已有的前端 API 函数：

```typescript
// frontend/src/lib/api/notebooks.ts（已存在，无需修改）
updateNotebook(notebookId: string, input: { title?: string; description?: string })
```

在 `page.tsx` 中新增 mutation：

```typescript
const updateMutation = useMutation({
  mutationFn: ({ notebookId, title, description }: EditNotebookState) =>
    updateNotebook(notebookId, { title, description: description || null }),
  onSuccess: () => {
    setEditingNotebook(null);
    queryClient.invalidateQueries({ queryKey: ["notebooks"] });
  },
});
```

description 字段：若用户将其清空，传 `null` 而非空字符串，与后端类型定义一致（`description: string | null`）。

## Modal 样式与结构

沿用项目中现有的创建 Notebook Modal 的实现模式（`page.tsx` 第 236-297 行），结构如下：

- 弹窗标题：修改 Notebook 信息
- 输入项：名称（`<input>`）+ 描述（`<textarea>`）
- 底部按钮：取消 / 保存
- 保存按钮在 `updateMutation.isPending` 期间显示加载状态并禁用

## 校验规则

- title 为空时，输入框下方显示提示文字"名称不能为空"，提交按钮不可用
- title 超过 100 字符时，显示提示"名称最多 100 个字符"
- description 超过 300 字符时，显示提示"描述最多 300 个字符"
- 所有校验均为前端即时校验，无需依赖后端返回错误

## i18n 字符串

需在 `uiStrings.notebooksPage` 下新增以下条目：

```typescript
editNotebook: { zh: "修改 Notebook 信息", en: "Edit Notebook" },
editSave: { zh: "保存", en: "Save" },
titleRequired: { zh: "名称不能为空", en: "Name is required" },
titleTooLong: { zh: "名称最多 100 个字符", en: "Name must be 100 characters or fewer" },
descTooLong: { zh: "描述最多 300 个字符", en: "Description must be 300 characters or fewer" },
```
