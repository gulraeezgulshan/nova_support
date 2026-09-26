import { auth } from "@clerk/nextjs/server";
import { cache } from "react";

import { readMe } from "./generated";
import type { UserOut } from "./generated/types.gen";

const SERVER_API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type CurrentUserResult =
  | { status: "ok"; user: UserOut }
  | { status: "signed-out" }
  | { status: "unavailable"; message: string };

/**
 * The signed-in user as known by the SupportNova API (including their role).
 * Cached per request, so layouts and pages can both call it for free.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUserResult> => {
  const { getToken, userId } = await auth();
  if (!userId) return { status: "signed-out" };
  const token = await getToken();
  try {
    const { data, error, response } = await readMe({
      baseUrl: SERVER_API_URL,
      auth: token ?? undefined,
      cache: "no-store",
    });
    if (data) return { status: "ok", user: data };
    return {
      status: "unavailable",
      message: `API responded ${response?.status ?? "?"}: ${JSON.stringify(error)}`,
    };
  } catch {
    return { status: "unavailable", message: `Cannot reach the API at ${SERVER_API_URL}.` };
  }
});
