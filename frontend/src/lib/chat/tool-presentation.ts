import { uiStrings, type LocalizedString } from "@/lib/i18n/strings";

const TOOL_LABELS: Record<string, LocalizedString> = {
  bash: uiStrings.tools.shell,
  read_file: uiStrings.tools.readFile,
  grep_files: uiStrings.tools.grepFiles,
  glob_files: uiStrings.tools.globFiles,
  edit_file: uiStrings.tools.editFile,
  write_file: uiStrings.tools.writeFile,
  knowledge_base: uiStrings.tools.knowledgeBase,
  image_generate: uiStrings.tools.imageGenerate,
  tavily_search: uiStrings.tools.webSearch,
  tavily_crawl: uiStrings.tools.webCrawl,
  zhipu_web_search: uiStrings.tools.webSearch,
  zhipu_web_crawl: uiStrings.tools.webCrawl,
  time: uiStrings.tools.getTime,
  list_notes: uiStrings.tools.listNotes,
  read_note: uiStrings.tools.readNote,
  create_note: uiStrings.tools.createNote,
  update_note: uiStrings.tools.updateNote,
  delete_note: uiStrings.tools.deleteNote,
  list_marks: uiStrings.tools.listMarks,
  associate_note_document: uiStrings.tools.associateDoc,
  disassociate_note_document: uiStrings.tools.disassociateDoc,
  list_diagrams: uiStrings.tools.listDiagrams,
  read_diagram: uiStrings.tools.readDiagram,
  confirm_diagram_type: uiStrings.tools.confirmDiagramType,
  create_diagram: uiStrings.tools.createDiagram,
  update_diagram: uiStrings.tools.updateDiagram,
  delete_diagram: uiStrings.tools.deleteDiagram,
  update_diagram_positions: uiStrings.tools.updateDiagramPositions,
};

export function toolLabel(toolName: string): LocalizedString {
  return TOOL_LABELS[toolName] ?? uiStrings.tools.generic;
}

export function toolDisplayName(toolName: string): string {
  return toolName === "bash" ? "shell" : toolName;
}

export function normalizeToolDisplayText(text: string): string {
  return text.replace(/\bBash\b/g, "Shell").replace(/\bbash\b/g, "shell");
}
