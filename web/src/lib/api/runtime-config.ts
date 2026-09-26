import { getToken } from "@clerk/nextjs";

import type { CreateClientConfig } from "./generated/client.gen";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Base configuration of the generated API client.
 * In the browser every request carries the current Clerk session token; server code
 * passes its own token per call (see `lib/api/server.ts`).
 */
export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: API_URL,
  auth: async () => {
    if (typeof window === "undefined") return undefined;
    return (await getToken()) ?? undefined;
  },
});
