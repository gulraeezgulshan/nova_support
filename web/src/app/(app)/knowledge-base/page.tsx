import { redirect } from "next/navigation";

import { DocumentsTable } from "@/components/knowledge-base/documents-table";
import { SearchPanel } from "@/components/knowledge-base/search-panel";
import { UploadDialog } from "@/components/knowledge-base/upload-dialog";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Knowledge base" };

export default async function KnowledgeBasePage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "knowledge_base")) return <NoAccess />;
  const canManage = can(result.user, "knowledge_base", "edit");

  return (
    <>
      <PageHeader
        title="Knowledge base"
        description="Approved company documents. Only the active version of each document is used to resolve complaints."
        actions={canManage ? <UploadDialog /> : undefined}
      />
      <div className="space-y-6">
        <DocumentsTable canManage={canManage} />
        <Card>
          <CardHeader>
            <CardTitle>Policy retrieval test</CardTitle>
            <CardDescription>
              Hybrid semantic + keyword search over active policy sections, the same retrieval the
              complaint pipeline uses.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SearchPanel />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
