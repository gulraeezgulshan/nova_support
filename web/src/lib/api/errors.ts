/** Turn an API error body into a readable message (FastAPI `detail` + our `issues`). */
export function apiErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (!error || typeof error !== "object") return fallback;
  const body = error as { detail?: unknown; issues?: unknown };
  const issues = Array.isArray(body.issues) ? body.issues.map(String) : [];
  if (typeof body.detail === "string") {
    return issues.length ? `${body.detail}: ${issues.join(" ")}` : body.detail;
  }
  if (Array.isArray(body.detail)) {
    return body.detail
      .map(
        (d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`,
      )
      .join(" ");
  }
  return fallback;
}
