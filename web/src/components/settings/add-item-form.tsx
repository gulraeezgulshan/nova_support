"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** Small inline "code + name" form used for categories, subcategories and departments. */
export function AddItemForm({
  codePlaceholder,
  namePlaceholder,
  pending,
  onSubmit,
}: {
  codePlaceholder: string;
  namePlaceholder: string;
  pending: boolean;
  onSubmit: (value: { code: string; name: string }, reset: () => void) => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(
          {
            code: code
              .trim()
              .toUpperCase()
              .replaceAll(/[\s-]+/g, "_"),
            name: name.trim(),
          },
          () => {
            setCode("");
            setName("");
          },
        );
      }}
    >
      <Input
        className="w-44 font-mono uppercase"
        placeholder={codePlaceholder}
        value={code}
        onChange={(e) => setCode(e.target.value)}
        aria-label="Code"
        required
      />
      <Input
        className="min-w-48 flex-1"
        placeholder={namePlaceholder}
        value={name}
        onChange={(e) => setName(e.target.value)}
        aria-label="Name"
        required
      />
      <Button type="submit" variant="outline" disabled={pending}>
        <Plus /> Add
      </Button>
    </form>
  );
}
