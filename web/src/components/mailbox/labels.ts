/** How each received e-mail was handled, in words for staff. */
export const OUTCOME_LABELS: Record<string, string> = {
  filed: "New complaint",
  appended: "Added to complaint",
  ignored: "Ignored (automatic)",
  rejected: "Asked for more detail",
  duplicate: "Duplicate",
  failed: "Failed",
};
