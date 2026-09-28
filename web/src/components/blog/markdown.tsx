import Link from "next/link";
import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { slugify } from "@/lib/blog";

type HastNode = { type: string; tagName?: string; value?: string; children?: HastNode[] };

/** A paragraph holding only an image: rendered as a bare <figure>, since <p> cannot contain one. */
function isImageOnly(node: HastNode | undefined): boolean {
  const kids = (node?.children ?? []).filter((c) => !(c.type === "text" && !c.value?.trim()));
  return kids.length === 1 && kids[0].type === "element" && kids[0].tagName === "img";
}

function textOf(node: HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(textOf).join("");
}

function heading(level: 2 | 3) {
  const Tag = level === 2 ? "h2" : "h3";
  function Heading({ node, children }: { node?: HastNode; children?: ReactNode }) {
    const id = slugify(textOf(node));
    return (
      <Tag id={id} className="group scroll-mt-24">
        {children}
        <a
          href={`#${id}`}
          aria-label="Link to this section"
          className="ml-2 font-normal text-brand no-underline opacity-0 transition-opacity group-hover:opacity-100"
        >
          #
        </a>
      </Tag>
    );
  }
  return Heading;
}

const components: Components = {
  h2: heading(2),
  h3: heading(3),
  p({ node, children }) {
    return isImageOnly(node as HastNode) ? <>{children}</> : <p>{children}</p>;
  },
  a({ href = "", children }) {
    if (href.startsWith("/") || href.startsWith("#")) return <Link href={href}>{children}</Link>;
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
  img({ src, alt }) {
    if (typeof src !== "string") return null;
    return (
      <figure>
        <a href={src} target="_blank" rel="noreferrer" title="Open full size">
          {/* eslint-disable-next-line @next/next/no-img-element -- large static diagrams, opened full size on click */}
          <img src={src} alt={alt ?? ""} loading="lazy" className="rounded-xl border bg-white" />
        </a>
        {alt ? <figcaption>{alt}</figcaption> : null}
      </figure>
    );
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    );
  },
};

/** Renders a Markdown article with the site's typography (tables, code, figures, anchors). */
export function Markdown({ source }: { source: string }) {
  return (
    <div className="prose prose-zinc max-w-none dark:prose-invert prose-headings:tracking-tight prose-a:text-brand prose-code:before:content-none prose-code:after:content-none prose-pre:bg-zinc-950 prose-img:my-0 prose-figcaption:text-center">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
