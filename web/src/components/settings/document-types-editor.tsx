"use client";

import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { DocumentTypeSetting } from "@/lib/api/generated/types.gen";

/**
 * Knowledge-base document types and their precedence (lower wins when sources disagree).
 * A type that documents still use cannot be removed; the server checks this too.
 */
export function DocumentTypesEditor({
  value,
  onChange,
  inUse,
}: {
  value: DocumentTypeSetting[];
  onChange: (next: DocumentTypeSetting[]) => void;
  /** Type code → document IDs that use it. */
  inUse: Record<string, string[]>;
}) {
  const update = (i: number, patch: Partial<DocumentTypeSetting>) =>
    onChange(value.map((t, j) => (j === i ? { ...t, ...patch } : t)));

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead className="w-28">Precedence</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {value.map((t, i) => {
              const docs = inUse[t.code] ?? [];
              return (
                <TableRow key={i}>
                  <TableCell>
                    <Input
                      aria-label="Type code"
                      value={t.code}
                      disabled={docs.length > 0}
                      onChange={(e) => update(i, { code: e.target.value.toLowerCase() })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      aria-label="Type name"
                      value={t.name}
                      onChange={(e) => update(i, { name: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      aria-label="Precedence"
                      type="number"
                      min={1}
                      max={9}
                      value={t.precedence}
                      onChange={(e) => update(i, { precedence: Number(e.target.value) })}
                    />
                  </TableCell>
                  <TableCell>
                    {docs.length ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span tabIndex={0}>
                            <Button variant="ghost" size="icon" disabled aria-label="In use">
                              <Trash2 />
                            </Button>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>Used by {docs.join(", ")}</TooltipContent>
                      </Tooltip>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove ${t.code}`}
                        onClick={() => onChange(value.filter((_, j) => j !== i))}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange([...value, { code: "", name: "", precedence: 5 }])}
      >
        <Plus /> Add type
      </Button>
      <p className="text-xs text-muted-foreground">
        Lower precedence wins when two documents disagree (compliance 1 … FAQ 6). Codes use
        lowercase letters, digits and underscores; a type used by documents cannot be removed.
      </p>
    </div>
  );
}
