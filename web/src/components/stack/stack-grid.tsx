import { BrandLogo } from "@/components/stack/brand-logo";
import { STACK } from "@/lib/stack";

export function StackGrid() {
  return (
    <div className="space-y-10">
      {STACK.map((group) => (
        <section key={group.title} className="space-y-4">
          <h3 className="text-lg font-semibold tracking-tight">{group.title}</h3>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.items.map((tech) => (
              <li key={tech.name} className="flex gap-4 rounded-2xl border bg-card p-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-muted">
                  <BrandLogo icon={tech.icon} className="size-6" />
                </span>
                <span className="min-w-0">
                  <span className="block font-medium">{tech.name}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">{tech.role}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
