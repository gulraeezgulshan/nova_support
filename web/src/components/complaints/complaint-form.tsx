"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  createComplaintMutation,
  myOrdersOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { formatDate } from "@/lib/format";

const NO_ORDER = "__none__";
const CHANNELS = ["web_form", "email", "live_chat", "whatsapp", "phone_callback"] as const;

const schema = z.object({
  title: z.string().trim().min(5, "Please give a short title (at least 5 characters)."),
  description: z
    .string()
    .trim()
    .min(20, "Please describe what happened, when, and what you would like us to do.")
    .max(5000),
  order_ref: z.string().optional(),
  product_service: z.string().max(200).optional(),
  requested_resolution: z.string().max(1000).optional(),
  previous_complaint_ref: z
    .string()
    .trim()
    .regex(/^(CMP-\d{6})?$/i, "Use the format CMP-000123.")
    .optional(),
  preferred_contact_channel: z.enum(CHANNELS).optional(),
  customer_ref: z.string().trim().optional(),
  channel: z.enum(CHANNELS),
});
type FormValues = z.infer<typeof schema>;

type ApiError = { detail?: string; issues?: string[]; existing_ref?: string };

export function ComplaintForm({ staff }: { staff: boolean }) {
  const router = useRouter();
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const orders = useQuery({ ...myOrdersOptions(), enabled: !staff });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", description: "", channel: staff ? "phone_callback" : "web_form" },
  });
  const create = useMutation({
    ...createComplaintMutation(),
    onSuccess: (complaint) => router.push(`/complaints/${complaint.complaint_ref}`),
    onError: (error) => setApiError(error as ApiError),
  });

  const submit = form.handleSubmit((values) => {
    setApiError(null);
    const body = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== undefined && v !== "" && v !== NO_ORDER),
    ) as FormValues;
    if (staff && !body.customer_ref) {
      form.setError("customer_ref", { message: "Enter the customer reference (CUST-...)." });
      return;
    }
    create.mutate({ body });
  });

  const errors = form.formState.errors;
  return (
    <form onSubmit={submit} className="max-w-2xl space-y-5">
      {apiError ? (
        <Alert variant="destructive">
          <AlertTitle>{apiError.detail ?? "The complaint could not be submitted."}</AlertTitle>
          {apiError.issues?.length ? (
            <AlertDescription>
              <ul className="list-disc pl-4">
                {apiError.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </AlertDescription>
          ) : null}
          {apiError.existing_ref ? (
            <AlertDescription>
              <Link className="underline" href={`/complaints/${apiError.existing_ref}`}>
                Open {apiError.existing_ref}
              </Link>
            </AlertDescription>
          ) : null}
        </Alert>
      ) : null}

      {staff ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Customer reference" error={errors.customer_ref?.message}>
            <Input placeholder="CUST-500001" {...form.register("customer_ref")} />
          </Field>
          <Field label="Received via">
            <Controller
              control={form.control}
              name="channel"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNELS.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
        </div>
      ) : null}

      <Field label="Title" error={errors.title?.message}>
        <Input placeholder="e.g. Laptop arrived damaged" {...form.register("title")} />
      </Field>

      <Field
        label="What happened?"
        error={errors.description?.message}
        hint="Include dates, order numbers and what you have already tried."
      >
        <Textarea rows={7} {...form.register("description")} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        {staff ? (
          <Field label="Order reference (optional)">
            <Input placeholder="ORD-240001" {...form.register("order_ref")} />
          </Field>
        ) : (
          <Field label="Related order (optional)">
            <Controller
              control={form.control}
              name="order_ref"
              render={({ field }) => (
                <Select value={field.value ?? NO_ORDER} onValueChange={field.onChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_ORDER}>No specific order</SelectItem>
                    {orders.data?.map((o) => (
                      <SelectItem key={o.order_ref} value={o.order_ref}>
                        {o.order_ref} · {o.product_name} · {formatDate(o.order_date)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
        )}
        <Field label="Product or service (optional)">
          <Input {...form.register("product_service")} />
        </Field>
      </div>

      <Field label="What would you like us to do? (optional)">
        <Input {...form.register("requested_resolution")} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Earlier complaint about this (optional)"
          error={errors.previous_complaint_ref?.message}
        >
          <Input placeholder="CMP-000123" {...form.register("previous_complaint_ref")} />
        </Field>
        <Field label="Preferred contact (optional)">
          <Controller
            control={form.control}
            name="preferred_contact_channel"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  {CHANNELS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c.replaceAll("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>

      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? "Submitting…" : "Submit complaint"}
      </Button>
    </form>
  );
}

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
