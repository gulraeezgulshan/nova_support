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
              <CardTitle>Complaints</CardTitle>
              <CardDescription>
                Complaint submission and tracking open in the next release.
              </CardDescription>
            </CardHeader>
          </Card>
        )}
      </div>
    </>
  );
}
