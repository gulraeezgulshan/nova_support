"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { fill, TextField } from "@/components/settings/text-field";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  readTextsOptions,
  readTextsQueryKey,
  updateTextsMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type {
  ChatTexts,
  ComplaintEmailTexts,
  OrderEmailText,
  TextSettings,
} from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

const ORDER_LABELS: Record<string, string> = {
  placed: "Order placed",
  shipped: "Shipped",
  delayed: "Delayed",
  delivered: "Delivered",
  cancelled: "Cancelled",
  returned: "Return approved",
  return_refused: "Return refused",
};
const COMPLAINT_LABELS: Record<Exclude<keyof ComplaintEmailTexts, "signature">, string> = {
  acknowledgement: "Complaint received",
  holding: "Under review",
  rejected: "Could not open a complaint",
  duplicate: "Duplicate of an earlier complaint",
};
const CHAT_LABELS: Record<Exclude<keyof ChatTexts, "fallback_questions">, string> = {
  greeting: "Greeting (chat without an order)",
  ask_what_happened: "First question (chat about an order)",
  neutral_question: "Neutral follow-up question",
  summary_lead: "Before the summary",
  faq_follow_up: "After an FAQ answer",
  added_to_complaint: "Message added to a filed complaint",
  submitted: "Complaint filed",
};
const FALLBACK_LABELS = ["1 What happened", "2 When", "3 What the customer wants"];

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-lg border p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

export function TextsManager() {
  const queryClient = useQueryClient();
  const query = useQuery(readTextsOptions());
  const [edits, setEdits] = useState<TextSettings | null>(null);
  const save = useMutation({
    ...updateTextsMutation(),
    onSuccess: (data) => {
      toast.success("Texts saved. They apply within about 15 seconds.");
      queryClient.setQueryData(readTextsQueryKey(), data);
      setEdits(null);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Texts were not saved.")),
  });

  if (query.isPending) return <Skeleton className="h-96 w-full" />;
  if (query.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(query.error)}</p>;
  const data = query.data;
  const form = edits ?? data.texts;
  const dirty = edits !== null && JSON.stringify(edits) !== JSON.stringify(data.texts);
  const rule = (path: string) => data.placeholders[path] ?? { allowed: [], required: [] };
  const setOrder = (kind: string, patch: Partial<OrderEmailText>) =>
    setEdits({
      ...form,
      order_emails: { ...form.order_emails, [kind]: { ...form.order_emails[kind], ...patch } },
    });
  const setComplaint = (patch: Partial<ComplaintEmailTexts>) =>
    setEdits({ ...form, complaint_emails: { ...form.complaint_emails, ...patch } });
  const setChat = (patch: Partial<ChatTexts>) =>
    setEdits({ ...form, chat: { ...form.chat, ...patch } });
  const signatureRule = rule("complaint_emails.signature");
  const signature = fill(form.complaint_emails.signature, signatureRule.allowed, data.samples);
  const suffix = signature ? `\n\n${signature}` : "";

  const footer = (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <p className="text-xs text-muted-foreground">
        {data.updated_at
          ? `Last changed by ${data.updated_by ?? "an administrator"} on ${new Date(data.updated_at).toLocaleString()}`
          : "Using the default settings."}
      </p>
      <div className="flex gap-2">
        <Button variant="ghost" disabled={!dirty} onClick={() => setEdits(null)}>
          Discard
        </Button>
        <Button
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate({ body: { version: data.version, texts: form } })}
        >
          Save changes
        </Button>
      </div>
    </div>
  );

  return (
    <Tabs defaultValue="order" className="space-y-6">
      <TabsList className="flex-wrap group-data-horizontal/tabs:h-auto">
        <TabsTrigger value="order">Order e-mails</TabsTrigger>
        <TabsTrigger value="complaint">Complaint e-mails</TabsTrigger>
        <TabsTrigger value="chat">Chat</TabsTrigger>
      </TabsList>

      <TabsContent value="order" className="space-y-4">
        {Object.keys(ORDER_LABELS).map((kind) => {
          const text = form.order_emails[kind];
          const original = data.defaults.order_emails[kind];
          if (!text || !original) return null;
          return (
            <Card key={kind} title={ORDER_LABELS[kind]}>
              <TextField
                label="Subject"
                value={text.subject}
                defaultValue={original.subject}
                rule={rule(`order_emails.${kind}.subject`)}
                samples={data.samples}
                onChange={(subject) => setOrder(kind, { subject })}
              />
              <TextField
                label="Body"
                multiline
                value={text.body}
                defaultValue={original.body}
                rule={rule(`order_emails.${kind}.body`)}
                samples={data.samples}
                onChange={(body) => setOrder(kind, { body })}
              />
            </Card>
          );
        })}
        {footer}
      </TabsContent>

      <TabsContent value="complaint" className="space-y-4">
        {(Object.keys(COMPLAINT_LABELS) as (keyof typeof COMPLAINT_LABELS)[]).map((name) => (
          <Card key={name} title={COMPLAINT_LABELS[name]}>
            <TextField
              label="Body (the signature is added below)"
              multiline
              value={form.complaint_emails[name]}
              defaultValue={data.defaults.complaint_emails[name]}
              rule={rule(`complaint_emails.${name}`)}
              samples={data.samples}
              suffix={suffix}
              onChange={(v) => setComplaint({ [name]: v })}
            />
          </Card>
        ))}
        <Card title="Signature">
          <TextField
            label="Added to every complaint e-mail, including approved replies"
            multiline
            value={form.complaint_emails.signature}
            defaultValue={data.defaults.complaint_emails.signature}
            rule={signatureRule}
            samples={data.samples}
            onChange={(signature) => setComplaint({ signature })}
          />
        </Card>
        {footer}
      </TabsContent>

      <TabsContent value="chat" className="space-y-4">
        {(Object.keys(CHAT_LABELS) as (keyof typeof CHAT_LABELS)[]).map((name) => (
          <Card key={name} title={CHAT_LABELS[name]}>
            <TextField
              label="Message"
              value={form.chat[name]}
              defaultValue={data.defaults.chat[name]}
              rule={rule(`chat.${name}`)}
              samples={data.samples}
              onChange={(v) => setChat({ [name]: v })}
            />
          </Card>
        ))}
        <Card title="Questions without the AI (no API key)">
          {form.chat.fallback_questions.map((question, i) => (
            <TextField
              key={i}
              label={FALLBACK_LABELS[i] ?? `Question ${i + 1}`}
              value={question}
              defaultValue={data.defaults.chat.fallback_questions[i] ?? ""}
              rule={rule("chat.fallback_questions")}
              samples={data.samples}
              onChange={(v) =>
                setChat({
                  fallback_questions: form.chat.fallback_questions.map((q, j) =>
                    j === i ? v : q,
                  ) as ChatTexts["fallback_questions"],
                })
              }
            />
          ))}
        </Card>
        {footer}
      </TabsContent>
    </Tabs>
  );
}
