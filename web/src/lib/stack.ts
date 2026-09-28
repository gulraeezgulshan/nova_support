import type { IconKey } from "@/lib/stack-icons";

// What each technology does in SupportNova, for /how-it-works and the blog.

export type Tech = { icon: IconKey; name: string; role: string };
export type TechGroup = { title: string; items: Tech[] };

export const STACK: TechGroup[] = [
  {
    title: "Web app (Vercel)",
    items: [
      {
        icon: "nextdotjs",
        name: "Next.js 16",
        role: "The VoltHaven shop and the staff console, server-rendered with the App Router.",
      },
      { icon: "react", name: "React 19", role: "Every screen and component." },
      {
        icon: "typescript",
        name: "TypeScript",
        role: "A typed API client generated from the backend's OpenAPI schema.",
      },
      {
        icon: "tailwindcss",
        name: "Tailwind CSS",
        role: "Styling, light and dark themes, the blog's typography.",
      },
      {
        icon: "shadcnui",
        name: "shadcn/ui",
        role: "Accessible buttons, forms, dialogs and tables.",
      },
      { icon: "vercel", name: "Vercel", role: "Hosts the web app and rebuilds it on every push." },
    ],
  },
  {
    title: "Backend (Railway)",
    items: [
      {
        icon: "fastapi",
        name: "FastAPI",
        role: "The REST API: role checks on every endpoint, OpenAPI documentation.",
      },
      {
        icon: "python",
        name: "Python",
        role: "The rule matrix, the 18 validation checks, reports and the evaluation.",
      },
      {
        icon: "pydantic",
        name: "Pydantic",
        role: "The strict JSON schema the model must answer in, and every API request.",
      },
      {
        icon: "sqlalchemy",
        name: "SQLAlchemy",
        role: "Database access, with Alembic migrations run before each release.",
      },
      {
        icon: "postgresql",
        name: "PostgreSQL + pgvector",
        role: "Complaints, audit trail and policy passages with embeddings for hybrid search.",
      },
      {
        icon: "redis",
        name: "Redis",
        role: "The queue between the API and the background worker.",
      },
      {
        icon: "celery",
        name: "Celery",
        role: "Worker: analysis, document ingestion, e-mail. Beat: SLA scan and mailbox checks.",
      },
      { icon: "railway", name: "Railway", role: "Runs the API, worker, beat, database and Redis." },
    ],
  },
  {
    title: "Services",
    items: [
      {
        icon: "openai",
        name: "OpenAI",
        role: "gpt-5-mini reads each complaint and returns a structured analysis.",
      },
      {
        icon: "anthropic",
        name: "Anthropic",
        role: "Claude, the alternative model provider: one setting switches.",
      },
      {
        icon: "clerk",
        name: "Clerk",
        role: "Sign-in and session tokens; the API verifies each token and applies its own roles.",
      },
      {
        icon: "cloudflare",
        name: "Cloudflare R2",
        role: "Policy documents and complaint attachments (S3-compatible storage).",
      },
      {
        icon: "gmail",
        name: "Gmail",
        role: "The support mailbox, read over IMAP: e-mails become complaints or thread replies.",
      },
      {
        icon: "brevo",
        name: "Brevo",
        role: "Sends acknowledgements and approved replies over HTTPS (Railway blocks SMTP).",
      },
    ],
  },
  {
    title: "Build and delivery",
    items: [
      {
        icon: "githubactions",
        name: "GitHub Actions",
        role: "CI on every push: lint, types, 444 tests, web build, secret scan.",
      },
      { icon: "docker", name: "Docker", role: "One image for the API, worker and beat." },
      { icon: "uv", name: "uv", role: "Python dependencies, locked." },
      { icon: "pnpm", name: "pnpm", role: "Web dependencies, locked." },
    ],
  },
];
