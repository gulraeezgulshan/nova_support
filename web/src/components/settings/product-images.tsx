"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ImagePlus, Star, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ProductImage } from "@/components/shop/product-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  deleteProductImageMutation,
  reorderProductImagesMutation,
  uploadProductImageMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ProductOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

const MAX_IMAGES = 5;
const ACCEPT = "image/jpeg,image/png,image/webp";

/** Upload, order (first = main image) and remove a product's images. */
export function ProductImages({
  product,
  onChanged,
}: {
  product: ProductOut;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const refresh = () => {
    queryClient.invalidateQueries();
    onChanged();
  };
  const onError = (err: unknown) => toast.error(apiErrorMessage(err, "Image update failed."));

  const upload = useMutation({ ...uploadProductImageMutation(), onError });
  const reorder = useMutation({ ...reorderProductImagesMutation(), onSuccess: refresh, onError });
  const remove = useMutation({ ...deleteProductImageMutation(), onSuccess: refresh, onError });
  const busy = upload.isPending || reorder.isPending || remove.isPending;
  const images = product.images;

  async function add(files: FileList | File[]) {
    const room = MAX_IMAGES - images.length;
    const chosen = Array.from(files).slice(0, Math.max(room, 0));
    if (!chosen.length) {
      toast.error(`A product can have at most ${MAX_IMAGES} images.`);
      return;
    }
    for (const file of chosen) {
      try {
        await upload.mutateAsync({ path: { sku: product.sku }, body: { file } });
      } catch {
        break; // onError already showed why
      }
    }
    refresh();
  }

  function move(from: number, to: number) {
    const ids = images.map((i) => i.id);
    const [id] = ids.splice(from, 1);
    ids.splice(to, 0, id);
    reorder.mutate({ path: { sku: product.sku }, body: { image_ids: ids } });
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
        {images.map((image, index) => (
          <div key={image.id} className="group relative">
            <ProductImage
              url={image.url}
              line={product.product_line}
              alt={`${product.name} image ${index + 1}`}
              className="w-full border"
            />
            {index === 0 ? <Badge className="absolute top-1 left-1 text-[10px]">Main</Badge> : null}
            <div className="mt-1 flex justify-center gap-0.5">
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label="Move left"
                disabled={busy || index === 0}
                onClick={() => move(index, index - 1)}
              >
                <ArrowLeft />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label="Make main image"
                disabled={busy || index === 0}
                onClick={() => move(index, 0)}
              >
                <Star />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label="Move right"
                disabled={busy || index === images.length - 1}
                onClick={() => move(index, index + 1)}
              >
                <ArrowRight />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-7 text-destructive"
                aria-label="Delete image"
                disabled={busy}
                onClick={() => remove.mutate({ path: { sku: product.sku, image_id: image.id } })}
              >
                <Trash2 />
              </Button>
            </div>
          </div>
        ))}
      </div>
      {images.length < MAX_IMAGES ? (
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void add(e.dataTransfer.files);
          }}
          disabled={busy}
          className={cn(
            "flex w-full flex-col items-center gap-1 rounded-xl border border-dashed p-6 text-sm text-muted-foreground transition-colors",
            dragging ? "border-primary bg-muted" : "hover:bg-muted/50",
          )}
        >
          <ImagePlus className="size-6" />
          {upload.isPending ? "Uploading…" : "Drop images here or click to choose"}
          <span className="text-xs">
            JPG, PNG or WebP, up to 5 MB each · {images.length}/{MAX_IMAGES} used · the first image
            is the main one
          </span>
        </button>
      ) : null}
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) void add(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
