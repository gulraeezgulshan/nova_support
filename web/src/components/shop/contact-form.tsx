"use client";

import { SignInButton, useAuth } from "@clerk/nextjs";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  contactMutation,
  myShopOrdersOptions,
  readMeOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { uploadComplaintAttachment } from "@/lib/api/generated/sdk.gen";
import type { ContactOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { openChat } from "@/lib/storefront";
import {
  ACCEPTED_TYPES,
  MAX_ATTACHMENT_BYTES,
  MAX_ATTACHMENTS,
} from "@/components/complaints/supporting-documents";

type Topic = "order_problem" | "product_question" | "business" | "feedback" | "other";

const TOPICS: { value: Topic; label: string }[] = [
  { value: "order_problem", label: "A problem with an order" },
  { value: "product_question", label: "A question about a product" },
  { value: "business", label: "Business or bulk enquiry" },
  { value: "feedback", label: "Feedback" },
  { value: "other", label: "Something else" },
];
const NO_ORDER = "none";

/** Contact us: order problems become complaints (sign-in needed); the rest become enquiries. */
export function ContactForm() {
  const { isSignedIn } = useAuth();
  const me = useQuery({ ...readMeOptions(), enabled: Boolean(isSignedIn) });
  const orders = useQuery({ ...myShopOrdersOptions(), enabled: Boolean(isSignedIn) });
  const [topic, setTopic] = useState<Topic>("product_question");
  const [orderRef, setOrderRef] = useState(NO_ORDER);
  const [result, setResult] = useState<ContactOut | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<{ ok: number; failed: string[] }>({ ok: 0, failed: [] });
  const send = useMutation({
    ...contactMutation(),
    onSuccess: async (out) => {
      // The complaint exists now; attach the files to it (a failed upload never undoes it).
      const outcome = { ok: 0, failed: [] as string[] };
      if (out.kind === "complaint" && out.reference) {
        for (const file of files) {
          try {
            await uploadComplaintAttachment({
              path: { ref: out.reference },
              body: { file },
              throwOnError: true,
            });
            outcome.ok += 1;
          } catch {
            outcome.failed.push(file.name);
          }
        }
      }
      setUploaded(outcome);
      setFiles([]);
      setResult(out);
    },
  });
  const blocked = topic === "order_problem" && !isSignedIn;

  if (result) return <Sent result={result} uploaded={uploaded} onAgain={() => setResult(null)} />;

  const pickFiles = (list: FileList | null) => {
    const chosen = Array.from(list ?? []);
    const bad = chosen.find(
      (f) => !ACCEPTED_TYPES.split(",").includes(f.type) || f.size > MAX_ATTACHMENT_BYTES,
    );
    if (chosen.length > MAX_ATTACHMENTS) setFileError(`Choose at most ${MAX_ATTACHMENTS} files.`);
    else if (bad) setFileError(`${bad.name}: only photos or PDFs up to 5 MB.`);
    else setFileError(null);
    setFiles(chosen.length <= MAX_ATTACHMENTS && !bad ? chosen : []);
  };

  return (
    <form
      // Remount when the account loads so name and e-mail prefill.
      key={me.data?.id ?? "anonymous"}
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const text = (name: string) => String(data.get(name) ?? "").trim();
        send.mutate({
          body: {
            name: text("name"),
            email: text("email"),
            topic,
            message: text("message"),
            order_ref: topic === "order_problem" && orderRef !== NO_ORDER ? orderRef : null,
            website: text("website") || null,
          },
        });
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="contact-name">Name</Label>
          <Input
            id="contact-name"
            name="name"
            required
            maxLength={200}
            autoComplete="name"
            defaultValue={me.data?.full_name ?? ""}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="contact-email">E-mail</Label>
          <Input
            id="contact-email"
            name="email"
            type="email"
            required
            autoComplete="email"
            defaultValue={me.data?.email ?? ""}
          />
        </div>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="contact-topic">What is it about?</Label>
          <Select value={topic} onValueChange={(value) => setTopic(value as Topic)}>
            <SelectTrigger id="contact-topic" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TOPICS.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {topic === "order_problem" && isSignedIn ? (
          <div className="space-y-2">
            <Label htmlFor="contact-order">Which order?</Label>
            <Select value={orderRef} onValueChange={setOrderRef}>
              <SelectTrigger id="contact-order" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_ORDER}>Not about a specific order</SelectItem>
                {(orders.data ?? []).map((o) => (
                  <SelectItem key={o.order_ref} value={o.order_ref}>
                    {o.order_ref} · {o.product_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </div>
      <AnimatePresence initial={false}>
        {blocked ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-brand/30 bg-brand-soft p-4 text-sm">
              <Info className="size-4 shrink-0 text-brand" />
              <p className="flex-1">
                Please sign in to report a problem with an order, so we can look at your orders.
              </p>
              <SignInButton>
                <Button type="button" size="sm" className="rounded-full">
                  Sign in
                </Button>
              </SignInButton>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full bg-background"
                onClick={() => openChat()}
              >
                Or chat with us
              </Button>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <div className="space-y-2">
        <Label htmlFor="contact-message">Message</Label>
        <Textarea
          id="contact-message"
          name="message"
          required
          minLength={10}
          maxLength={5000}
          rows={6}
          placeholder={
            topic === "order_problem"
              ? "What happened? Include what you expected and what you'd like us to do."
              : "How can we help?"
          }
        />
      </div>
      {topic === "order_problem" && isSignedIn ? (
        <div className="space-y-2">
          <Label htmlFor="contact-files">Photos or documents (optional, up to 5)</Label>
          <Input
            id="contact-files"
            type="file"
            multiple
            accept={ACCEPTED_TYPES}
            onChange={(event) => pickFiles(event.target.files)}
          />
          {fileError ? (
            <p className="text-sm text-destructive">{fileError}</p>
          ) : files.length ? (
            <p className="text-xs text-muted-foreground">
              {files.length} file{files.length === 1 ? "" : "s"} will be attached.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              JPG, PNG, WebP or PDF, 5 MB each. Photos of damage help us act faster.
            </p>
          )}
        </div>
      ) : null}
      {/* Honeypot: hidden from people, bots fill it in and are ignored. */}
      <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="contact-website">Website</label>
        <input id="contact-website" name="website" tabIndex={-1} autoComplete="off" />
      </div>
      {send.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {apiErrorMessage(send.error)}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-4">
        <Button
          type="submit"
          size="lg"
          disabled={send.isPending || blocked}
          className="h-12 rounded-full bg-brand px-8 text-brand-foreground hover:bg-brand/90"
        >
          {send.isPending ? "Sending…" : "Send message"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Card numbers or passwords typed here are hidden automatically. See our{" "}
          <Link href="/privacy" className="underline">
            privacy policy
          </Link>
          .
        </p>
      </div>
    </form>
  );
}

function Sent({
  result,
  uploaded,
  onAgain,
}: {
  result: ContactOut;
  uploaded: { ok: number; failed: string[] };
  onAgain: () => void;
}) {
  const complaint = result.kind === "complaint";
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center gap-4 py-10 text-center"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 16, delay: 0.1 }}
      >
        <CheckCircle2 className="size-14 text-brand" />
      </motion.div>
      <h2 className="text-2xl font-semibold tracking-tight">
        {complaint ? "Complaint received" : "Thanks, message received"}
      </h2>
      <p className="max-w-md text-muted-foreground">
        {complaint ? (
          <>
            We&apos;ve filed it as{" "}
            <span className="font-mono font-medium text-foreground">{result.reference}</span>. Our
            team is on it, and you can follow its progress in your account.
          </>
        ) : result.reference ? (
          <>
            Your reference is{" "}
            <span className="font-mono font-medium text-foreground">{result.reference}</span>.
            We&apos;ll reply by e-mail, usually within one business day.
          </>
        ) : (
          "We'll be in touch."
        )}
      </p>
      {uploaded.ok ? (
        <p className="text-sm text-muted-foreground">
          {uploaded.ok} document{uploaded.ok === 1 ? "" : "s"} attached.
        </p>
      ) : null}
      {uploaded.failed.length ? (
        <p className="text-sm text-destructive">
          Not attached: {uploaded.failed.join(", ")}. You can add them from My complaints.
        </p>
      ) : null}
      <div className="flex flex-wrap justify-center gap-3">
        {complaint ? (
          <Button asChild className="rounded-full bg-brand text-brand-foreground">
            <Link href="/complaints">Track my complaint</Link>
          </Button>
        ) : null}
        <Button variant="outline" className="rounded-full" onClick={onAgain}>
          Send another message
        </Button>
      </div>
    </motion.div>
  );
}
