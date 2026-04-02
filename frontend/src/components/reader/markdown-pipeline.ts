import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkCjkFriendly from "remark-cjk-friendly";
import remarkRehype from "remark-rehype";
import rehypeSlug from "rehype-slug";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeStringify from "rehype-stringify";
import type { Root, Element } from "hast";
import { visit } from "unist-util-visit";

type RenderMarkdownOptions = {
  documentId?: string;
};

type RehypeImgEnhanceOptions = {
  documentId?: string;
};

const CIRCLED_DIGITS = ["⓪", "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"];

function _toCircledText(value: string): string {
  const normalized = value.trim();
  if (!normalized) return value;

  if (/^(?:[0-9]|1[0-9]|20)$/.test(normalized)) {
    return CIRCLED_DIGITS[Number(normalized)] ?? normalized;
  }

  if (/^[A-Z]$/.test(normalized)) {
    return String.fromCodePoint(0x24b6 + normalized.charCodeAt(0) - 65);
  }

  if (/^[a-z]$/.test(normalized)) {
    return String.fromCodePoint(0x24d0 + normalized.charCodeAt(0) - 97);
  }

  if ([...normalized].length === 1) {
    return `${normalized}\u20DD`;
  }

  return `(${normalized})`;
}

function _normalizeTextCircled(content: string): string {
  return content
    .replace(/\$\s*\\textcircled\{([^{}]+)\}\s*\$/g, (_match, value: string) => _toCircledText(value))
    .replace(/\\textcircled\{([^{}]+)\}/g, (_match, value: string) => _toCircledText(value));
}

function _normalizeImageSrc(src: unknown, documentId?: string): string {
  const value = String(src || "").trim();
  if (!value) return value;
  if (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("data:") ||
    value.startsWith("blob:")
  ) {
    return value;
  }
  if (value.startsWith("/api/v1/")) {
    return value;
  }
  if (documentId) {
    if (value.startsWith("/assets/images/")) {
      return `/api/v1/documents/${documentId}${value}`;
    }
    if (value.startsWith("assets/images/")) {
      return `/api/v1/documents/${documentId}/${value}`;
    }
    if (value.startsWith("images/")) {
      return `/api/v1/documents/${documentId}/assets/${value}`;
    }
  }
  return value;
}

/**
 * Enhance <img> nodes:
 * - normalize relative image paths to document asset API
 * - lazy load + async decode
 * - mark loaded/failed state so CSS can avoid expensive perpetual animations
 */
function rehypeImgEnhance(options: RehypeImgEnhanceOptions = {}) {
  const documentId = options.documentId;
  return (tree: Root) => {
    visit(tree, "element", (node: Element) => {
      if (node.tagName !== "img") return;
      const props = node.properties ?? {};
      props.src = _normalizeImageSrc(props.src, documentId);
      props.loading = "lazy";
      props.decoding = "async";
      props.fetchpriority = "low";
      props["data-loaded"] = "0";
      props.onload = "this.dataset.loaded='1';";
      const alt = String(props.alt || "图片");
      // Do not keep animation on failed images, and show a lightweight fallback text block.
      props.onerror = `this.onerror=null;this.style.display='none';` +
        `this.dataset.loaded='error';` +
        `var p=document.createElement('div');p.className='img-fallback';` +
        `p.textContent='图片加载失败: ${alt.replace(/'/g, "\\'")}';` +
        `this.parentNode.insertBefore(p,this);`;
      node.properties = props;
    });
  };
}

function _shouldEnableMath(content: string): boolean {
  if (content.includes("$$")) return true;
  return /(^|[^\\])\$[^$\n]+?\$/.test(content);
}

function _shouldEnableCodeHighlight(content: string): boolean {
  return /```[\s\S]*?```/.test(content);
}

export function renderMarkdownToHtml(content: string, options: RenderMarkdownOptions = {}): string {
  const normalizedContent = _normalizeTextCircled(content || "");
  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkCjkFriendly);

  const enableMath = _shouldEnableMath(normalizedContent);
  if (enableMath) {
    processor.use(remarkMath);
  }

  processor
    .use(remarkRehype)
    .use(rehypeSlug);

  if (_shouldEnableCodeHighlight(content)) {
    processor.use(rehypeHighlight);
  }
  if (enableMath) {
    processor.use(rehypeKatex);
  }

  processor
    .use(rehypeImgEnhance, options)
    .use(rehypeStringify);

  return String(processor.processSync(normalizedContent));
}
