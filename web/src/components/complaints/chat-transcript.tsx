"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { complaintChatOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const KIND_LABELS: Record<string, string> = {
  summary: "Summary",
  reference: "Filed",
  reply: "Reply sent",
  holding: "Holding message",
  acknowledgement: "Acknowledged",
  order_options: "Order choice",
  note: "Added later",
};

/** The support-chat conversation behind a complaint (staff view). */
export function ChatTranscript({ complaintRef }: { complaintRef: string }) {
  const chat = useQuery(complaintChatOptions({ path: { ref: complaintRef } }));
  if (!chat.data?.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Chat transcript</CardTitle>
        <CardDescription>
          The customer&apos;s conversation with the support assistant.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="space-y-2 text-sm">
          {chat.data.map((m) => (
            <li
              key={m.id}
              className={cn(
                "rounded-lg border p-2",
                m.role === "customer" ? "bg-muted/40" : "bg-background",
              )}
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  {m.role === "customer" ? "Customer" : "Assistant"}
                </span>
                {KIND_LABELS[m.kind] ? (
                  <Badge variant="outline" className="text-[10px]">
                    {KIND_LABELS[m.kind]}
                  </Badge>
                ) : null}
                <span className="ml-auto">{formatDateTime(m.created_at)}</span>
              </div>
              <p className="whitespace-pre-line">{m.content}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
