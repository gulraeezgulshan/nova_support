import { readFile } from "node:fs/promises";
import path from "node:path";

/** Blog posts. The Markdown lives in web/content/blog and is built into static pages. */
export type PostMeta = {
  slug: string;
  file: string;
  summary: string;
  date: string; // ISO date
  author: string;
  tags: string[];
};

export const POSTS: PostMeta[] = [
  {
    slug: "letting-the-model-talk",
    file: "letting-the-model-talk.md",
    summary:
      "How SupportNova classifies, routes and answers customer complaints with generative AI — " +
      "and why an independent Python rule engine, not the model, makes every decision.",
    date: "2026-09-28",
    author: "Team SupportNova · TechWiz 7.0",
    tags: ["Generative AI", "RAG", "Python", "Validation"],
  },
];

export type Heading = { id: string; text: string; level: 2 | 3 };
export type Post = PostMeta & { title: string; body: string; headings: Heading[]; minutes: number };

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[`*_]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function findPost(slug: string): PostMeta | undefined {
  return POSTS.find((p) => p.slug === slug);
}

export async function loadPost(meta: PostMeta): Promise<Post> {
  const raw = await readFile(path.join(process.cwd(), "content", "blog", meta.file), "utf8");
  const [first, ...rest] = raw.split("\n");
  const title = first.replace(/^#\s+/, "").trim();
  const body = rest.join("\n").trim();
  const headings: Heading[] = [];
  let inCode = false;
  for (const line of body.split("\n")) {
    if (line.startsWith("```")) inCode = !inCode;
    const match = !inCode && /^(##|###)\s+(.+)$/.exec(line);
    if (match) {
      const text = match[2].trim();
      headings.push({ id: slugify(text), text, level: match[1] === "##" ? 2 : 3 });
    }
  }
  const words = body.split(/\s+/).filter(Boolean).length;
  return { ...meta, title, body, headings, minutes: Math.max(1, Math.round(words / 220)) };
}

export function formatPostDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "long" }).format(new Date(iso));
}
