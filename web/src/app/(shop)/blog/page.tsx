import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatPostDate, loadPost, POSTS } from "@/lib/blog";

export const metadata: Metadata = {
  title: "Blog",
  description:
    "How SupportNova handles customer complaints with generative AI and Python validation.",
};

export default async function BlogIndex() {
  const posts = await Promise.all(POSTS.map(loadPost));
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <p className="text-sm font-medium tracking-wide text-brand uppercase">Blog</p>
      <h1 className="mt-2 text-5xl font-semibold tracking-tight">Engineering notes</h1>
      <p className="mt-3 max-w-2xl text-lg text-muted-foreground">
        How the VoltHaven support system works: generative AI that reads and writes, and Python that
        decides.
      </p>
      <ul className="mt-10 space-y-6">
        {posts.map((post) => (
          <li key={post.slug}>
            <Link
              href={`/blog/${post.slug}`}
              className="group block rounded-3xl border bg-card p-6 transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-lg sm:p-8"
            >
              <p className="text-sm text-muted-foreground">
                {formatPostDate(post.date)} · {post.minutes} min read
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight group-hover:text-brand">
                {post.title}
              </h2>
              <p className="mt-3 text-muted-foreground">{post.summary}</p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {post.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
                <span className="ml-auto flex items-center gap-1 text-sm font-medium text-brand">
                  Read the article <ArrowRight className="size-4" />
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
