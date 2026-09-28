import { ArrowLeft, ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Markdown } from "@/components/blog/markdown";
import { TeamStrip } from "@/components/team/team-cards";
import { Badge } from "@/components/ui/badge";
import { findPost, formatPostDate, loadPost, POSTS } from "@/lib/blog";
import { COMPETITION, TEAM } from "@/lib/team";

export const dynamicParams = false; // only the posts that exist, built at deploy time

export function generateStaticParams() {
  return POSTS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: PageProps<"/blog/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const meta = findPost(slug);
  if (!meta) return {};
  const post = await loadPost(meta);
  return {
    title: post.title,
    description: post.summary,
    openGraph: {
      type: "article",
      title: post.title,
      description: post.summary,
      publishedTime: post.date,
      images: ["/blog/diagrams/1-architecture-overview.png"],
    },
  };
}

export default async function BlogPost({ params }: PageProps<"/blog/[slug]">) {
  const { slug } = await params;
  const meta = findPost(slug);
  if (!meta) notFound();
  const post = await loadPost(meta);
  const sections = post.headings.filter((h) => h.level === 2);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <Link
        href="/blog"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> All posts
      </Link>
      <header className="mt-6 max-w-3xl space-y-4 border-b pb-8">
        <div className="flex flex-wrap gap-2">
          {post.tags.map((tag) => (
            <Badge key={tag} variant="secondary">
              {tag}
            </Badge>
          ))}
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          {post.title}
        </h1>
        <p className="text-lg text-muted-foreground">{post.summary}</p>
        <p className="text-sm text-muted-foreground">
          {post.author} · {formatPostDate(post.date)} · {post.minutes} min read
        </p>
      </header>
      <div className="mt-10 grid gap-12 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="On this page" className="hidden lg:block">
          <div className="sticky top-24 max-h-[calc(100vh-8rem)] space-y-3 overflow-y-auto">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              On this page
            </p>
            <ul className="space-y-1 border-l text-sm">
              {sections.map((h) => (
                <li key={h.id}>
                  <a
                    href={`#${h.id}`}
                    className="-ml-px block border-l-2 border-transparent py-1 pl-4 text-muted-foreground hover:border-brand hover:text-foreground"
                  >
                    {h.text}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </nav>
        <article className="max-w-3xl min-w-0">
          <Markdown source={post.body} />
          <section aria-labelledby="team" className="mt-16 rounded-3xl border bg-card p-6 sm:p-8">
            <h2 id="team" className="text-2xl font-semibold tracking-tight">
              Meet the team
            </h2>
            <p className="mt-2 text-muted-foreground">
              Built by five students and their mentor for {COMPETITION.name}.
            </p>
            <div className="mt-6">
              <TeamStrip members={TEAM} />
            </div>
            <Link
              href="/team"
              className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
            >
              Meet the team <ArrowRight className="size-4" />
            </Link>
          </section>
        </article>
      </div>
    </div>
  );
}
