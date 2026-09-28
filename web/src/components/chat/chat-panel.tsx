"use client";

import { Show, SignInButton } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { NovaAvatar } from "@/components/chat/nova-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { chooseChatOrder, confirmChat, sendChatMessage, startChat } from "@/lib/api/generated";
import { getChatOptions, getChatQueryKey } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ChatConversationOut, ChatMessageOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type OrderOption = { order_ref: string; product_name: string; order_date: string; status: string };

function awaitingReply(conversation?: ChatConversationOut): boolean {
  if (!conversation || conversation.state !== "submitted") return false;
  return !conversation.messages.some((m) => m.kind === "reply");
}

/** A specialist is reviewing: the reply may take hours, so no typing dots and slow polling. */
function underReview(conversation?: ChatConversationOut): boolean {
  return Boolean(conversation?.messages.some((m) => m.kind === "holding"));
}

export function ChatPanel({ orderRef }: { orderRef?: string }) {
  return (
    <>
      <Show when="signed-in">
        <Conversation orderRef={orderRef} />
      </Show>
      <Show when="signed-out">
        <div className="space-y-3 p-6 text-center text-sm">
          <p>Please sign in so we can look at your orders.</p>
          <SignInButton>
            <Button>Sign in</Button>
          </SignInButton>
        </div>
      </Show>
    </>
  );
}

function Conversation({ orderRef }: { orderRef?: string }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const start = useQuery({
    queryKey: ["chat-start", orderRef ?? null],
    queryFn: async () =>
      (await startChat({ body: { order_ref: orderRef ?? null }, throwOnError: true })).data,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });
  const id = start.data?.id;
  const live = useQuery({
    ...getChatOptions({ path: { conversation_id: id ?? "" } }),
    enabled: Boolean(id),
    initialData: start.data,
    refetchInterval: (query) =>
      awaitingReply(query.state.data) ? (underReview(query.state.data) ? 15000 : 2000) : false,
  });
  const conversation = live.data ?? start.data;

  const store = (next: ChatConversationOut) =>
    queryClient.setQueryData(getChatQueryKey({ path: { conversation_id: next.id } }), next);
  const onError = (err: unknown) => toast.error(apiErrorMessage(err));

  const send = useMutation({
    mutationFn: async (message: string) =>
      (
        await sendChatMessage({
          path: { conversation_id: id ?? "" },
          body: { text: message },
          throwOnError: true,
        })
      ).data,
    onSuccess: store,
    onError,
  });
  const choose = useMutation({
    mutationFn: async (ref: string | null) =>
      (
        await chooseChatOrder({
          path: { conversation_id: id ?? "" },
          body: { order_ref: ref },
          throwOnError: true,
        })
      ).data,
    onSuccess: store,
    onError,
  });
  const confirm = useMutation({
    mutationFn: async () =>
      (await confirmChat({ path: { conversation_id: id ?? "" }, throwOnError: true })).data,
    onSuccess: store,
    onError: (err) => {
      onError(err);
      live.refetch();
    },
  });
  const restart = useMutation({
    mutationFn: async () =>
      (await startChat({ body: { order_ref: orderRef ?? null, new: true }, throwOnError: true }))
        .data,
    onSuccess: (next) => {
      queryClient.setQueryData(["chat-start", orderRef ?? null], next);
      store(next);
      setText("");
    },
    onError,
  });
  const busy = send.isPending || choose.isPending || confirm.isPending || restart.isPending;

  const messageCount = conversation?.messages.length ?? 0;
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messageCount, busy]);

  if (start.isError)
    return <p className="p-6 text-sm text-destructive">{apiErrorMessage(start.error)}</p>;
  if (!conversation) return <p className="p-6 text-sm text-muted-foreground">Connecting…</p>;

  const closed = conversation.state === "closed" || conversation.state === "submitting";
  const lastSummaryId = [...conversation.messages].reverse().find((m) => m.kind === "summary")?.id;
  const submit = () => {
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    send.mutate(message, { onError: () => setText(message) }); // give it back if sending fails
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {conversation.recent_complaint_ref ? (
          <p className="rounded-xl border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Your recent complaint{" "}
            <Link
              href={`/complaints/${conversation.recent_complaint_ref}`}
              className="font-medium text-foreground underline underline-offset-2"
            >
              {conversation.recent_complaint_ref}
            </Link>{" "}
            — view its status and our reply.
          </p>
        ) : null}
        {conversation.messages.map((m) => (
          <Message
            key={m.id}
            message={m}
            canChoose={conversation.state === "gathering" && !busy}
            canConfirm={conversation.state === "confirming" && m.id === lastSummaryId && !busy}
            onChoose={(ref) => choose.mutate(ref)}
            onConfirm={() => confirm.mutate()}
            onChange={() => inputRef.current?.focus()}
          />
        ))}
        {send.isPending && send.variables ? (
          // Show the customer's message at once; the server copy replaces it with the reply.
          <Message
            message={{
              id: -1,
              role: "customer",
              kind: "text",
              content: send.variables,
              payload: {},
              created_at: new Date().toISOString(),
            }}
            canChoose={false}
            canConfirm={false}
            onChoose={() => undefined}
            onConfirm={() => undefined}
            onChange={() => undefined}
          />
        ) : null}
        {busy || (awaitingReply(conversation) && !underReview(conversation)) ? <Typing /> : null}
        <div ref={endRef} />
      </div>
      <div className="border-t p-3">
        <div className="flex items-end gap-2">
          <Textarea
            ref={inputRef}
            rows={2}
            maxLength={2000}
            value={text}
            placeholder={
              conversation.state === "submitted"
                ? "Add something to your complaint…"
                : "Type your message…"
            }
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            aria-label="Message"
          />
          <Button
            size="icon"
            onClick={submit}
            disabled={busy || !text.trim() || closed}
            aria-label="Send"
          >
            <Send />
          </Button>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {conversation.complaint_ref ? `Complaint ${conversation.complaint_ref}` : null}
          </span>
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            disabled={busy}
            onClick={() => restart.mutate()}
          >
            {conversation.state === "submitted" ? "New question" : "Start over"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Typing() {
  return (
    <div className="flex items-end gap-2" aria-label="Nova is typing">
      <NovaAvatar className="size-7" />
      <div className="flex gap-1 rounded-2xl bg-muted px-3 py-2.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-2 animate-bounce rounded-full bg-muted-foreground/60"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function Message({
  message: m,
  canChoose,
  canConfirm,
  onChoose,
  onConfirm,
  onChange,
}: {
  message: ChatMessageOut;
  canChoose: boolean;
  canConfirm: boolean;
  onChoose: (ref: string | null) => void;
  onConfirm: () => void;
  onChange: () => void;
}) {
  const mine = m.role === "customer";
  const payload = m.payload as Record<string, unknown>;
  return (
    <div className={cn("flex items-end gap-2", mine ? "justify-end" : "justify-start")}>
      {!mine && m.kind !== "reply" ? <NovaAvatar className="mb-0.5 size-7" /> : null}
      <div
        className={cn(
          "max-w-[85%] space-y-2 rounded-2xl px-3 py-2 text-sm whitespace-pre-line",
          mine ? "bg-primary text-primary-foreground" : "bg-muted",
          m.kind === "holding" && "border border-dashed bg-transparent text-muted-foreground",
          m.kind === "reference" && "border border-emerald-600/40 bg-emerald-500/10",
        )}
      >
        {m.kind === "reply" ? (
          <Badge variant="secondary" className="text-[10px]">
            Support team
          </Badge>
        ) : null}
        <p>{m.content}</p>
        {m.kind === "order_options" ? (
          <div className="flex flex-col gap-1.5">
            {((payload.orders as OrderOption[] | undefined) ?? []).map((o) => (
              <Button
                key={o.order_ref}
                size="sm"
                variant="outline"
                className="h-auto justify-start py-1.5 text-left whitespace-normal"
                disabled={!canChoose}
                onClick={() => onChoose(o.order_ref)}
              >
                {o.product_name}
                <span className="ml-auto pl-2 text-xs text-muted-foreground">{o.order_ref}</span>
              </Button>
            ))}
            <Button size="sm" variant="ghost" disabled={!canChoose} onClick={() => onChoose(null)}>
              Something else
            </Button>
          </div>
        ) : null}
        {m.kind === "summary" ? (
          <div className="space-y-2 rounded-xl border bg-background p-3 text-foreground">
            <p className="font-medium">{String(payload.title ?? "")}</p>
            <p className="text-muted-foreground">{String(payload.description ?? "")}</p>
            {payload.order_ref ? (
              <p className="text-xs">Order {String(payload.order_ref)}</p>
            ) : null}
            {payload.requested_resolution ? (
              <p className="text-xs">You would like: {String(payload.requested_resolution)}</p>
            ) : null}
            {canConfirm ? (
              <div className="flex gap-2 pt-1">
                <Button size="sm" onClick={onConfirm}>
                  <CheckCircle2 /> Confirm
                </Button>
                <Button size="sm" variant="outline" onClick={onChange}>
                  Change something
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
