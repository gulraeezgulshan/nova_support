import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/about",
  "/about-supportnova",
  "/blog(.*)",
  "/team",
  "/how-it-works",
  "/shop(.*)",
  "/cart",
  "/contact",
  "/help",
  "/shipping",
  "/returns",
  "/warranty",
  "/privacy",
  "/terms",
  "/sign-in(.*)",
  "/sign-up(.*)",
]);

// Optimistic check only: signed-out visitors are sent to sign-in.
// Real authorisation (roles) is enforced by the FastAPI backend on every request.
export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
  if (!request.cookies.get("currency")) {
    // Vercel adds the visitor's country; the API never sees it, so the default is set here.
    const country = request.headers.get("x-vercel-ip-country");
    const response = NextResponse.next();
    response.cookies.set("currency", country === "PK" ? "PKR" : "USD", {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
    return response;
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
