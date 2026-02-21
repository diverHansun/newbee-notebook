import { use } from "react";

import { NotebookWorkspace } from "@/components/notebooks/notebook-workspace";

type NotebookPageProps = {
  params: Promise<{ id: string }>;
};

export default function NotebookPage({ params }: NotebookPageProps) {
  const { id } = use(params);
  return <NotebookWorkspace notebookId={id} />;
}
