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

/**
 * rehype plugin: enhance <img> elements with lazy loading,
 * error-fallback data attributes, and decoding hints.
 */
function rehypeImgEnhance() {
  return (tree: Root) => {
    visit(tree, "element", (node: Element) => {
      if (node.tagName !== "img") return;
      const props = node.properties ?? {};
      // Add lazy loading and async decoding
      props.loading = "lazy";
      props.decoding = "async";
      // Add onerror fallback — show alt text placeholder on broken images
      const alt = String(props.alt || "图片");
      props.onerror = `this.onerror=null;this.style.display='none';` +
        `var p=document.createElement('div');p.className='img-fallback';` +
        `p.textContent='⚠ 图片加载失败: ${alt.replace(/'/g, "\\'")}';` +
        `this.parentNode.insertBefore(p,this);`;
      node.properties = props;
    });
  };
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(remarkCjkFriendly)
  .use(remarkRehype)
  .use(rehypeSlug)
  .use(rehypeHighlight)
  .use(rehypeKatex)
  .use(rehypeImgEnhance)
  .use(rehypeStringify);

export function renderMarkdownToHtml(content: string): string {
  return String(processor.processSync(content || ""));
}
