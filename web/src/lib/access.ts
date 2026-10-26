// Page access: what the signed-in user may open or change (set on the Page access screen).
// The API enforces the same matrix; this only decides what to show.

export type Level = "none" | "view" | "edit";
export type AccessKey =
  | "dashboard"
  | "complaints"
  | "review"
  | "enquiries"
  | "mailbox"
  | "orders"
  | "imports"
  | "analytics"
  | "reports"
  | "knowledge_base"
  | "taxonomy"
  | "rules"
  | "products"
  | "users"
  | "settings"
  | "access";

const RANK: Record<Level, number> = { none: 0, view: 1, edit: 2 };

export function can(
  user: { permissions: Record<string, Level> },
  key: AccessKey,
  level: "view" | "edit" = "view",
): boolean {
  return RANK[user.permissions[key] ?? "none"] >= RANK[level];
}
