"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { searchKnowledgeBaseOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";

/** Try the retrieval the GenAI pipeline will use: only ACTIVE policy versions are searched. */
export function SearchPanel() {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const results = useQuery({
    ...searchKnowledgeBaseOptions({ query: { q: query, limit: 5 } }),
    enabled: query.length >= 2,
  });

  return (
    <div className="space-y-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(draft.trim());
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="e.g. customer wants compensation for a parcel that arrived a week late"
          aria-label="Search active policies"
        />
        <Button type="submit" variant="secondary" disabled={draft.trim().length < 2}>
          <Search /> Search
        </Button>
      </form>
      {results.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(results.error)}</p>
      ) : null}
      {results.data?.length === 0 ? (
        <p className="text-sm text-muted-foreground">No matching active policy sections.</p>
      ) : null}
      <ol className="space-y-3">
        {results.data?.map((r) => (
          <li key={r.chunk_code} className="rounded-lg border p-3">
            <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{r.doc_title}</span>
              <code>
                {r.doc_code} v{r.version}
                {r.section ? ` §${r.section}` : ""}
              </code>
              {r.page_start ? <span>p. {r.page_start}</span> : null}
              <span className="ml-auto tabular-nums">score {r.score.toFixed(4)}</span>
            </div>
            {r.heading ? <p className="text-sm font-medium">{r.heading}</p> : null}
            <p className="line-clamp-4 text-sm text-muted-foreground">{r.content}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
