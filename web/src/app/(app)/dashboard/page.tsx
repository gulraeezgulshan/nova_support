import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff, ROLE_LABELS } from "@/lib/roles";

export const metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") return null; // handled by the layout
  const { user } = result;
  const firstName = user.full_name?.split(" ")[0];

  return (
    <>
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : "Welcome"}
        description={`You are signed in as ${ROLE_LABELS[user.role]}.`}
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {isStaff(user.role) ? (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Complaint queue</CardTitle>
                <CardDescription>
                  Every complaint with its AI analysis, risk signals and review flags.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild>
                  <Link href="/complaints">Open queue</Link>
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Knowledge base</CardTitle>
                <CardDescription>
                  Versioned policies, SOPs and FAQs that ground every AI recommendation.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild variant="outline">
                  <Link href="/knowledge-base">Open knowledge base</Link>
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Taxonomy & SLAs</CardTitle>
                <CardDescription>
                  Complaint categories, departments and response targets, configurable at runtime.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild variant="outline">
                  <Link href="/settings/taxonomy">View configuration</Link>
                </Button>
              </CardContent>
            </Card>
          </>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Have a problem with an order?</CardTitle>
              <CardDescription>
                Tell us what happened and track progress here. We acknowledge every complaint
                immediately.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex gap-2">
              <Button asChild>
                <Link href="/complaints/new">Submit a complaint</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/complaints">My complaints</Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
