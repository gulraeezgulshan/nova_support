"use client";

import { useMutation } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { newsletterMutation } from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

/** Demo newsletter sign-up: the address is stored once and nothing is ever sent. */
export function NewsletterForm({ source, className }: { source: string; className?: string }) {
  const [email, setEmail] = useState("");
  const subscribe = useMutation({
    ...newsletterMutation(),
    onError: (error) => toast.error(apiErrorMessage(error, "Please enter a valid e-mail.")),
  });

  return (
    <div className={cn("relative", className)}>
      <AnimatePresence mode="wait" initial={false}>
        {subscribe.isSuccess ? (
          <motion.p
            key="done"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 text-sm"
          >
            <Check className="size-4 text-brand" />
            You&apos;re on the list. (Demo shop: we never actually send e-mails.)
          </motion.p>
        ) : (
          <motion.form
            key="form"
            exit={{ opacity: 0, y: -8 }}
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              subscribe.mutate({ body: { email: email.trim(), source } });
            }}
          >
            <Input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              aria-label="E-mail address"
              className="h-10 rounded-full bg-background"
            />
            <Button
              type="submit"
              className="h-10 rounded-full bg-brand px-5 text-brand-foreground hover:bg-brand/90"
              disabled={subscribe.isPending}
            >
              Subscribe
            </Button>
          </motion.form>
        )}
      </AnimatePresence>
    </div>
  );
}
