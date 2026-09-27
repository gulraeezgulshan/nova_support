"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MailPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  listInboundEmailsQueryKey,
  listOutboundEmailsQueryKey,
  processManualEmailMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";

import { OUTCOME_LABELS } from "./labels";

/** Run an e-mail through exactly the same processing as one received in the mailbox. */
export function ProcessEmailDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"paste" | "eml">("paste");
  const [eml, setEml] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const process = useMutation({
    ...processManualEmailMutation(),
    onSuccess: (record) => {
      queryClient.invalidateQueries({ queryKey: listInboundEmailsQueryKey() });
      queryClient.invalidateQueries({ queryKey: listOutboundEmailsQueryKey() });
      toast.success(`E-mail processed: ${OUTCOME_LABELS[record.outcome] ?? record.outcome}`, {
        description: record.complaint_ref ? (
          <Link href={`/complaints/${record.complaint_ref}`} className="underline">
            Open {record.complaint_ref}
          </Link>
        ) : (
          record.reason
        ),
      });
      setOpen(false);
      setEml(null);
      setFiles([]);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "The e-mail could not be processed.")),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <MailPlus /> Process an e-mail
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Process an e-mail</DialogTitle>
          <DialogDescription>
            Handled exactly like an e-mail received in the mailbox: it may open a complaint, be
            added to one, or get an automatic answer.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const text = (name: string) => String(data.get(name) ?? "").trim();
            process.mutate({
              body:
                mode === "eml"
                  ? { eml }
                  : {
                      from_address: text("from_address"),
                      from_name: text("from_name") || null,
                      subject: text("subject"),
                      body: text("body"),
                      files,
                    },
            });
          }}
        >
          <Tabs value={mode} onValueChange={(v) => setMode(v as "paste" | "eml")}>
            <TabsList>
              <TabsTrigger value="paste">Paste</TabsTrigger>
              <TabsTrigger value="eml">Upload .eml</TabsTrigger>
            </TabsList>
            <TabsContent value="paste" className="space-y-3 pt-2">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="mail-from">From (e-mail)</Label>
                  <Input
                    id="mail-from"
                    name="from_address"
                    type="email"
                    required={mode === "paste"}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="mail-name">Name</Label>
                  <Input id="mail-name" name="from_name" />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mail-subject">Subject</Label>
                <Input id="mail-subject" name="subject" maxLength={500} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mail-body">Message</Label>
                <Textarea id="mail-body" name="body" rows={7} required={mode === "paste"} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mail-files">Attachments (optional)</Label>
                <Input
                  id="mail-files"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
              </div>
            </TabsContent>
            <TabsContent value="eml" className="space-y-1.5 pt-2">
              <Label htmlFor="mail-eml">Saved e-mail (.eml)</Label>
              <Input
                id="mail-eml"
                type="file"
                accept=".eml,message/rfc822"
                required={mode === "eml"}
                onChange={(event) => setEml(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-muted-foreground">
                In most mail apps: open the message → Download / Save as → .eml.
              </p>
            </TabsContent>
          </Tabs>
          <DialogFooter>
            <Button type="submit" disabled={process.isPending || (mode === "eml" && !eml)}>
              {process.isPending ? "Processing…" : "Process"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
