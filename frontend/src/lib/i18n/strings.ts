export type LocalizedString = {
  zh: string;
  en: string;
};

export const uiStrings = {
  thinking: {
    default: { zh: "AI 正在思考...", en: "AI is thinking..." },
    retrieving: { zh: "正在检索知识库...", en: "Retrieving knowledge base..." },
    searching: { zh: "正在搜索相关内容...", en: "Searching relevant content..." },
    generating: { zh: "正在生成回答...", en: "Generating answer..." },
  },
  sourceSelector: {
    open: { zh: "选择检索范围", en: "Select sources" },
    done: { zh: "完成", en: "Done" },
    allDocuments: { zh: "全部文档", en: "All documents" },
    loading: { zh: "加载中...", en: "Loading..." },
    noDocuments: { zh: "暂无可用文档", en: "No available documents" },
    loadFailed: { zh: "加载文档失败", en: "Failed to load documents" },
    retry: { zh: "重试", en: "Retry" },
    firstNHint: { zh: "仅显示前", en: "Showing first" },
    noSourcesChip: { zh: "不使用文档", en: "No documents" },
    more: { zh: "更多", en: "more" },
  },
} as const satisfies Record<string, unknown>;

export function zh(text: LocalizedString): string {
  return text.zh;
}
