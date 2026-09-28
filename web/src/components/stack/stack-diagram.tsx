import { ArrowDown, User, UserCog } from "lucide-react";
import type { ReactNode } from "react";

import { BrandLogo } from "@/components/stack/brand-logo";
import type { IconKey } from "@/lib/stack-icons";

// The deployed architecture with real logos. Wide screens get a drawn diagram (fixed
// 1280×760 canvas that scales down); phones get the same story as a vertical flow.

type Box = { x: number; y: number; w: number; h: number };

function Group({
  box,
  label,
  icon,
  tone,
}: {
  box: Box;
  label: string;
  icon?: IconKey;
  tone: string;
}) {
  return (
    <g>
      <rect
        {...{ x: box.x, y: box.y, width: box.w, height: box.h }}
        rx={22}
        className={tone}
        strokeDasharray="6 6"
        strokeWidth={1.5}
      />
      {icon && <BrandLogo icon={icon} x={box.x + 18} y={box.y - 11} width={22} height={22} />}
      <text
        x={box.x + (icon ? 46 : 18)}
        y={box.y + 5}
        className="fill-foreground text-[15px] font-semibold"
        paintOrder="stroke"
        stroke="var(--background)"
        strokeWidth={8}
      >
        {label}
      </text>
    </g>
  );
}

function Card({
  box,
  icons = [],
  glyph,
  title,
  lines = [],
}: {
  box: Box;
  icons?: IconKey[];
  glyph?: ReactNode;
  title: string;
  lines?: string[];
}) {
  const { x, y, w, h } = box;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={14}
        className="fill-card stroke-border"
        strokeWidth={1.5}
      />
      {glyph}
      {icons.map((icon, i) => (
        <BrandLogo key={icon} icon={icon} x={x + 16 + i * 32} y={y + 16} width={24} height={24} />
      ))}
      <text x={x + 16} y={y + 62} className="fill-foreground text-[15px] font-semibold">
        {title}
      </text>
      {lines.map((line, i) => (
        <text key={line} x={x + 16} y={y + 82 + i * 17} className="fill-muted-foreground text-xs">
          {line}
        </text>
      ))}
    </g>
  );
}

function Arrow({
  points,
  label,
  at,
  anchor = "middle",
}: {
  points: [number, number][];
  label?: string;
  at?: [number, number];
  anchor?: "start" | "middle";
}) {
  return (
    <g>
      <polyline
        points={points.map((p) => p.join(",")).join(" ")}
        fill="none"
        className="stroke-brand"
        strokeWidth={2}
        strokeLinejoin="round"
        markerEnd="url(#stack-arrow)"
      />
      {label && at && (
        <text
          x={at[0]}
          y={at[1]}
          textAnchor={anchor}
          className="fill-brand text-xs font-medium"
          paintOrder="stroke"
          stroke="var(--background)"
          strokeWidth={6}
        >
          {label}
        </text>
      )}
    </g>
  );
}

function Chip({ x, icon, text }: { x: number; icon: IconKey; text: string }) {
  return (
    <g>
      <BrandLogo icon={icon} x={x} y={694} width={20} height={20} />
      <text x={x + 28} y={709} className="fill-muted-foreground text-[13px]">
        {text}
      </text>
    </g>
  );
}

const WEB_STACK: [IconKey, string][] = [
  ["react", "React 19"],
  ["typescript", "TypeScript"],
  ["tailwindcss", "Tailwind CSS"],
  ["shadcnui", "shadcn/ui"],
];

function Drawing() {
  return (
    <svg
      viewBox="0 0 1280 760"
      role="img"
      aria-labelledby="stack-title"
      className="h-auto w-full"
      fontFamily="inherit"
    >
      <title id="stack-title">
        SupportNova architecture: Next.js on Vercel, FastAPI, Celery, PostgreSQL and Redis on
        Railway, with Clerk, OpenAI, Cloudflare R2, Gmail and Brevo.
      </title>
      <defs>
        <marker
          id="stack-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" className="fill-brand" />
        </marker>
      </defs>

      <Group box={{ x: 10, y: 100, w: 200, h: 310 }} label="Users" tone="fill-none stroke-border" />
      <Group
        box={{ x: 240, y: 100, w: 270, h: 310 }}
        label="Vercel"
        icon="vercel"
        tone="fill-muted/40 stroke-border"
      />
      <Group
        box={{ x: 560, y: 100, w: 460, h: 470 }}
        label="Railway"
        icon="railway"
        tone="fill-muted/40 stroke-border"
      />
      <Group
        box={{ x: 1050, y: 40, w: 220, h: 590 }}
        label="Services"
        tone="fill-none stroke-border"
      />

      <Card
        box={{ x: 30, y: 130, w: 160, h: 110 }}
        glyph={<User x={46} y={146} width={24} height={24} className="stroke-foreground" />}
        title="Customers"
        lines={["shop · chat", "Contact us · e-mail"]}
      />
      <Card
        box={{ x: 30, y: 280, w: 160, h: 110 }}
        glyph={<UserCog x={46} y={296} width={24} height={24} className="stroke-foreground" />}
        title="Staff"
        lines={["console · review", "reports"]}
      />

      <g>
        <rect
          x={260}
          y={130}
          width={230}
          height={260}
          rx={14}
          className="fill-card stroke-border"
          strokeWidth={1.5}
        />
        <BrandLogo icon="nextdotjs" x={276} y={146} width={28} height={28} />
        <text x={314} y={166} className="fill-foreground text-base font-semibold">
          Next.js 16
        </text>
        <text x={276} y={196} className="fill-muted-foreground text-xs">
          shop · staff console · blog
        </text>
        {WEB_STACK.map(([icon, name], i) => (
          <g key={icon}>
            <BrandLogo icon={icon} x={276} y={216 + i * 36} width={20} height={20} />
            <text x={306} y={231 + i * 36} className="fill-foreground text-sm">
              {name}
            </text>
          </g>
        ))}
      </g>

      <Card
        box={{ x: 580, y: 130, w: 170, h: 100 }}
        icons={["fastapi", "pydantic", "sqlalchemy"]}
        title="api"
        lines={["FastAPI · role checks"]}
      />
      <Card
        box={{ x: 830, y: 130, w: 170, h: 100 }}
        icons={["postgresql"]}
        title="PostgreSQL + pgvector"
        lines={["complaints · audit · policies"]}
      />
      <Card
        box={{ x: 580, y: 300, w: 170, h: 90 }}
        icons={["redis"]}
        title="Redis"
        lines={["task queue"]}
      />
      <Card
        box={{ x: 830, y: 300, w: 170, h: 90 }}
        icons={["celery", "python"]}
        title="worker"
        lines={["analysis · ingestion · e-mail"]}
      />
      <Card
        box={{ x: 580, y: 460, w: 170, h: 90 }}
        icons={["celery"]}
        title="beat"
        lines={["SLA 5 min · mailbox 1 min"]}
      />

      <Card
        box={{ x: 1070, y: 110, w: 180, h: 90 }}
        icons={["clerk"]}
        title="Clerk"
        lines={["sign-in · session tokens"]}
      />
      <Card
        box={{ x: 1070, y: 250, w: 180, h: 100 }}
        icons={["openai", "anthropic"]}
        title="OpenAI / Anthropic"
        lines={["structured analysis"]}
      />
      <Card
        box={{ x: 1070, y: 390, w: 180, h: 90 }}
        icons={["cloudflare"]}
        title="Cloudflare R2"
        lines={["documents · attachments"]}
      />
      <Card
        box={{ x: 1070, y: 520, w: 180, h: 90 }}
        icons={["gmail", "brevo"]}
        title="Gmail + Brevo"
        lines={["IMAP in · HTTPS API out"]}
      />

      <Arrow
        points={[
          [190, 185],
          [258, 185],
        ]}
      />
      <Arrow
        points={[
          [190, 335],
          [258, 335],
        ]}
      />
      <Arrow
        points={[
          [490, 180],
          [578, 180],
        ]}
        label="REST + JWT"
        at={[534, 170]}
      />
      <Arrow
        points={[
          [375, 130],
          [375, 70],
          [1160, 70],
          [1160, 108],
        ]}
        label="sign in"
        at={[770, 62]}
      />
      <Arrow
        points={[
          [750, 180],
          [828, 180],
        ]}
        label="SQL"
        at={[789, 170]}
      />
      <Arrow
        points={[
          [665, 230],
          [665, 298],
        ]}
        label="queue work"
        at={[674, 268]}
        anchor="start"
      />
      <Arrow
        points={[
          [665, 460],
          [665, 392],
        ]}
        label="schedules"
        at={[674, 430]}
        anchor="start"
      />
      <Arrow
        points={[
          [750, 345],
          [828, 345],
        ]}
        label="tasks"
        at={[789, 335]}
      />
      <Arrow
        points={[
          [915, 300],
          [915, 232],
        ]}
        label="results"
        at={[924, 270]}
        anchor="start"
      />
      <Arrow
        points={[
          [1000, 318],
          [1068, 318],
        ]}
        label="analyse"
        at={[1034, 308]}
      />
      <Arrow
        points={[
          [1000, 372],
          [1035, 372],
          [1035, 435],
          [1068, 435],
        ]}
      />
      <Arrow
        points={[
          [915, 390],
          [915, 565],
          [1068, 565],
        ]}
        label="read · send"
        at={[990, 555]}
      />

      <rect
        x={10}
        y={660}
        width={1260}
        height={90}
        rx={22}
        className="fill-none stroke-border"
        strokeDasharray="6 6"
        strokeWidth={1.5}
      />
      <text x={30} y={690} className="fill-foreground text-[15px] font-semibold">
        Build and delivery
      </text>
      <Chip
        x={30}
        icon="githubactions"
        text="GitHub Actions: lint · types · tests · build · gitleaks"
      />
      <Chip x={520} icon="docker" text="Docker: one image for api, worker, beat" />
      <Chip x={850} icon="uv" text="uv: Python packages" />
      <Chip x={1040} icon="pnpm" text="pnpm: web packages" />
    </svg>
  );
}

const FLOW: { title: string; icons: IconKey[]; text: string }[] = [
  {
    title: "Customers and staff",
    icons: ["nextdotjs", "vercel", "clerk"],
    text: "Use the Next.js web app on Vercel and sign in with Clerk.",
  },
  {
    title: "API on Railway",
    icons: ["fastapi", "postgresql", "redis"],
    text: "FastAPI checks the Clerk token and the role, stores complaints in PostgreSQL and queues the analysis in Redis.",
  },
  {
    title: "Worker and scheduler",
    icons: ["celery", "openai", "cloudflare", "gmail", "brevo"],
    text: "Celery analyses each complaint with OpenAI, reads documents from R2, reads the support mailbox and sends replies through Brevo; beat runs the SLA scan and mailbox checks.",
  },
];

export function StackDiagram() {
  return (
    <figure className="space-y-3">
      <div className="hidden rounded-3xl border bg-background p-4 md:block">
        <Drawing />
      </div>
      <ol className="space-y-2 md:hidden">
        {FLOW.map((step, i) => (
          <li key={step.title}>
            <div className="rounded-2xl border bg-card p-4">
              <div className="flex gap-2">
                {step.icons.map((icon) => (
                  <BrandLogo key={icon} icon={icon} className="size-6" />
                ))}
              </div>
              <p className="mt-3 font-semibold">{step.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{step.text}</p>
            </div>
            {i < FLOW.length - 1 && (
              <ArrowDown className="mx-auto my-1 size-5 text-brand" aria-hidden />
            )}
          </li>
        ))}
      </ol>
      <figcaption className="text-center text-sm text-muted-foreground">
        How a complaint travels through SupportNova, from the browser to the model and back.
      </figcaption>
    </figure>
  );
}
