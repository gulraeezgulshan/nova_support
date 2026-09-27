"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PRODUCT_LINES } from "@/components/shop/lines";
import { ProductImage } from "@/components/shop/product-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  adminListProductsOptions,
  createProductMutation,
  updateProductMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ProductOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatMoney } from "@/lib/format";

import { ProductImages } from "./product-images";

const LINE_LABELS = Object.fromEntries(PRODUCT_LINES.map((l) => [l.code, l.label]));

export function ProductsManager() {
  const products = useQuery(adminListProductsOptions());
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<string | null>(null); // SKU, or "new"
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (products.data ?? []).filter(
      (p) => !needle || `${p.sku} ${p.name}`.toLowerCase().includes(needle),
    );
  }, [products.data, search]);
  const current = products.data?.find((p) => p.sku === editing);

  if (products.isPending) return <Skeleton className="h-96 w-full" />;
  if (products.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(products.error)}</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Input
          className="w-72"
          placeholder="Search SKU or name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button onClick={() => setEditing("new")}>
          <Plus /> New product
        </Button>
        <span className="self-center text-sm text-muted-foreground">
          {visible.length} of {products.data.length} products
        </span>
      </div>
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16" />
              <TableHead>Product</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Price</TableHead>
              <TableHead>Images</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((p) => (
              <TableRow key={p.sku} className={p.is_active ? "" : "opacity-60"}>
                <TableCell>
                  <ProductImage
                    url={p.images[0]?.url}
                    line={p.product_line}
                    alt={p.name}
                    className="size-12 rounded-lg"
                  />
                </TableCell>
                <TableCell>
                  <p className="font-medium">{p.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">{p.sku}</p>
                </TableCell>
                <TableCell>{LINE_LABELS[p.product_line] ?? p.product_line}</TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(p.price)}</TableCell>
                <TableCell>{p.images.length}/5</TableCell>
                <TableCell>
                  <Badge variant={p.is_active ? "secondary" : "outline"}>
                    {p.is_active ? "In shop" : "Hidden"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit ${p.name}`}
                    onClick={() => setEditing(p.sku)}
                  >
                    <Pencil />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{current ? `Edit ${current.name}` : "New product"}</DialogTitle>
            <DialogDescription>
              {current
                ? "Changes appear in the shop straight away. Every change is audited."
                : "Save the product first, then add its images."}
            </DialogDescription>
          </DialogHeader>
          {editing !== null ? (
            <ProductForm
              key={editing}
              product={current}
              onSaved={(sku) => setEditing(sku)}
              onCancel={() => setEditing(null)}
            />
          ) : null}
          {current ? (
            <div className="space-y-2 border-t pt-4">
              <Label>Images</Label>
              <ProductImages product={current} onChanged={() => products.refetch()} />
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProductForm({
  product,
  onSaved,
  onCancel,
}: {
  product?: ProductOut;
  onSaved: (sku: string) => void;
  onCancel: () => void;
}) {
  const queryClient = useQueryClient();
  const [sku, setSku] = useState(product?.sku ?? "");
  const [name, setName] = useState(product?.name ?? "");
  const [line, setLine] = useState(product?.product_line ?? "ACCESSORY");
  const [price, setPrice] = useState(product ? String(product.price) : "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [specs, setSpecs] = useState((product?.specs ?? []).join("\n"));
  const [active, setActive] = useState(product?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);

  const done = (saved: ProductOut) => {
    queryClient.invalidateQueries();
    toast.success(product ? "Product saved" : "Product created — now add its images");
    setError(null);
    onSaved(saved.sku);
  };
  const create = useMutation({
    ...createProductMutation(),
    onSuccess: done,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const update = useMutation({
    ...updateProductMutation(),
    onSuccess: done,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const pending = create.isPending || update.isPending;

  function save() {
    const fields = {
      name,
      product_line: line,
      price: Number(price),
      description,
      specs: specs
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (product)
      update.mutate({ path: { sku: product.sku }, body: { ...fields, is_active: active } });
    else create.mutate({ body: { sku: sku.trim().toUpperCase(), ...fields } });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="p-sku">SKU</Label>
          <Input
            id="p-sku"
            value={sku}
            disabled={Boolean(product)}
            placeholder="VH-PHN-NX6"
            onChange={(e) => setSku(e.target.value)}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="p-name">Name</Label>
          <Input id="p-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Category</Label>
          <Select value={line} onValueChange={setLine}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRODUCT_LINES.map((l) => (
                <SelectItem key={l.code} value={l.code}>
                  {l.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-price">Price (USD)</Label>
          <Input
            id="p-price"
            type="number"
            min="0.01"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        {product ? (
          <div className="flex items-end gap-2 pb-2">
            <Switch id="p-active" checked={active} onCheckedChange={setActive} />
            <Label htmlFor="p-active">Show in shop</Label>
          </div>
        ) : null}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="p-desc">Description</Label>
        <Textarea
          id="p-desc"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="p-specs">Key specs (one per line)</Label>
        <Textarea id="p-specs" rows={4} value={specs} onChange={(e) => setSpecs(e.target.value)} />
      </div>
      {error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive"
        >
          {error}
        </p>
      ) : null}
      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={pending}>
          Close
        </Button>
        <Button onClick={save} disabled={pending || !name.trim() || !price}>
          {pending ? "Saving…" : product ? "Save changes" : "Create product"}
        </Button>
      </DialogFooter>
    </div>
  );
}
