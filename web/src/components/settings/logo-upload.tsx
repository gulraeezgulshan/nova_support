"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Trash2 } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  deleteLogoMutation,
  readBrandingQueryKey,
  readSettingsQueryKey,
  uploadLogoMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { API_URL } from "@/lib/api/runtime-config";

export function LogoUpload({
  target,
  label,
  url,
}: {
  target: "shop" | "console";
  label: string;
  url: string | null | undefined;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const done = (message: string) => ({
    onSuccess: () => {
      toast.success(message);
      queryClient.invalidateQueries({ queryKey: readSettingsQueryKey() });
      queryClient.invalidateQueries({ queryKey: readBrandingQueryKey() });
    },
    onError: (err: unknown) => toast.error(apiErrorMessage(err, "Logo update failed.")),
  });
  const upload = useMutation({ ...uploadLogoMutation(), ...done("Logo updated") });
  const remove = useMutation({ ...deleteLogoMutation(), ...done("Logo removed") });

  return (
    <div className="flex items-center gap-4 rounded-xl border p-4">
      <div className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-lg border bg-muted">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element -- served by the API host
          <img
            src={`${API_URL}${url}`}
            alt={`${label} logo`}
            className="size-full object-contain"
          />
        ) : (
          <span className="text-xs text-muted-foreground">None</span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label} logo</p>
        <p className="text-xs text-muted-foreground">
          PNG, JPEG or WebP, up to 1 MB. Square works best.
        </p>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate({ path: { target }, body: { file } });
          e.target.value = "";
        }}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={upload.isPending}
        onClick={() => input.current?.click()}
      >
        <ImagePlus /> Upload
      </Button>
      {url ? (
        <Button
          variant="ghost"
          size="sm"
          disabled={remove.isPending}
          onClick={() => remove.mutate({ path: { target } })}
        >
          <Trash2 /> Remove
        </Button>
      ) : null}
    </div>
  );
}
