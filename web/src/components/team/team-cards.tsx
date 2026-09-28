import Image from "next/image";

import { cn } from "@/lib/utils";
import { COMPETITION, type TeamMember } from "@/lib/team";

export function TechWizBadge({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-3xl bg-zinc-950 p-6 sm:p-8", className)}>
      <Image
        src={COMPETITION.logo}
        alt={`${COMPETITION.name}: ${COMPETITION.tagline}`}
        width={900}
        height={300}
        className="mx-auto h-auto w-full max-w-md"
        priority
      />
    </div>
  );
}

export function MemberCard({ member, large = false }: { member: TeamMember; large?: boolean }) {
  return (
    <figure className="flex flex-col items-center rounded-3xl border bg-card p-6 text-center">
      <Image
        src={member.photo}
        alt={`Photo of ${member.name}`}
        width={large ? 224 : 160}
        height={large ? 224 : 160}
        className={cn(
          "aspect-square h-auto w-full rounded-full object-cover ring-4 ring-brand/20",
          large ? "max-w-40 sm:max-w-56" : "max-w-32 sm:max-w-40",
        )}
      />
      <figcaption className="mt-5 space-y-1">
        <p className={cn("font-semibold tracking-tight", large ? "text-2xl" : "text-lg")}>
          {member.name}
        </p>
        <p className="text-sm font-medium text-brand">{member.role}</p>
        {member.studentId && (
          <p className="font-mono text-xs text-muted-foreground">{member.studentId}</p>
        )}
      </figcaption>
    </figure>
  );
}

/** A compact row of faces, used at the end of blog posts. */
export function TeamStrip({ members }: { members: TeamMember[] }) {
  return (
    <ul className="grid grid-cols-3 gap-x-4 gap-y-6 sm:grid-cols-6">
      {members.map((m) => (
        <li key={m.name} className="flex flex-col items-center text-center">
          <Image
            src={m.photo}
            alt={`Photo of ${m.name}`}
            width={96}
            height={96}
            className="size-16 rounded-full object-cover ring-2 ring-brand/20 sm:size-20"
          />
          <p className="mt-2 text-sm leading-tight font-medium">{m.name}</p>
          <p className="text-xs text-muted-foreground">{m.role}</p>
        </li>
      ))}
    </ul>
  );
}
