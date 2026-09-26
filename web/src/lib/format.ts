import type { ComplaintStatus } from "@/lib/api/generated/types.gen";

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value));
}

export const STATUS_LABELS: Record<ComplaintStatus, string> = {
  new: "Received",
  analyzed: "Under review",
  assigned: "Assigned",
  in_progress: "In progress",
  awaiting_customer: "Awaiting your reply",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Closed",
  reopened: "Reopened",
};

export const ESCALATION_LABELS = [
  "No escalation",
  "Supervisor review",
  "Department manager",
  "Specialist team",
  "Compliance review",
  "Critical management",
];

/** "PRODUCT_DEFECT" -> "Product defect" */
export function humanize(code: string | null | undefined): string {
  if (!code) return "—";
  const text = code.replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
