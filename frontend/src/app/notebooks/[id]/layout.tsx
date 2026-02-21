import { ReactNode } from "react";

type NotebookLayoutProps = {
  children: ReactNode;
};

export default function NotebookLayout({ children }: NotebookLayoutProps) {
  return children;
}
