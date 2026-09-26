"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createCategoryMutation,
  createDepartmentMutation,
  createSubcategoryMutation,
  listCategoriesOptions,
  listCategoriesQueryKey,
  listDepartmentsOptions,
  listDepartmentsQueryKey,
  listSlaPoliciesOptions,
  listSlaPoliciesQueryKey,
  updateSlaPolicyMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { SlaPolicyOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

import { AddItemForm } from "./add-item-form";

const hours = (minutes: number) => (minutes % 60 === 0 ? `${minutes / 60} h` : `${minutes} min`);

export function TaxonomyManager({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const categories = useQuery(listCategoriesOptions());
  const departments = useQuery(listDepartmentsOptions());
  const slas = useQuery(listSlaPoliciesOptions());

  const handlers = (queryKey: readonly unknown[], message: string) => ({
    onSuccess: () => {
      toast.success(message);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (err: unknown) => toast.error(apiErrorMessage(err)),
  });
  const addCategory = useMutation({
    ...createCategoryMutation(),
    ...handlers(listCategoriesQueryKey(), "Category added"),
  });
  const addSubcategory = useMutation({
    ...createSubcategoryMutation(),
    ...handlers(listCategoriesQueryKey(), "Subcategory added"),
  });
  const addDepartment = useMutation({
    ...createDepartmentMutation(),
    ...handlers(listDepartmentsQueryKey(), "Department added"),
  });
  const updateSla = useMutation({
    ...updateSlaPolicyMutation(),
    ...handlers(listSlaPoliciesQueryKey(), "SLA updated"),
  });

  const saveSla = (
    sla: SlaPolicyOut,
    field: "first_response_minutes" | "resolution_minutes",
    value: string,
  ) => {
    const minutes = Number(value);
    if (!Number.isInteger(minutes) || minutes <= 0 || minutes === sla[field]) return;
    updateSla.mutate({ path: { sla_id: sla.id }, body: { [field]: minutes } });
  };

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <Card className="xl:col-span-2">
        <CardHeader>
          <CardTitle>Complaint categories</CardTitle>
          <CardDescription>
            {categories.data
              ? `${categories.data.length} categories · ${categories.data.reduce((n, c) => n + c.subcategories.length, 0)} subcategories`
              : "Loading…"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canManage ? (
            <AddItemForm
              codePlaceholder="NEW_CATEGORY"
              namePlaceholder="Category name"
              pending={addCategory.isPending}
              onSubmit={(body, reset) => addCategory.mutate({ body }, { onSuccess: reset })}
            />
          ) : null}
          {categories.isPending ? <Skeleton className="h-64" /> : null}
          <ul className="divide-y rounded-lg border">
            {categories.data?.map((category) => (
              <li key={category.id} className="space-y-2 p-3">
                <div className="flex items-baseline gap-2">
                  <span className="font-medium">{category.name}</span>
                  <code className="text-xs text-muted-foreground">{category.code}</code>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {category.subcategories.map((sub) => (
                    <Badge key={sub.id} variant="secondary" title={sub.code}>
                      {sub.name}
                    </Badge>
                  ))}
                </div>
                {canManage ? (
                  <AddItemForm
                    codePlaceholder="SUBCATEGORY"
                    namePlaceholder={`New ${category.name.toLowerCase()} subcategory`}
                    pending={addSubcategory.isPending}
                    onSubmit={(body, reset) =>
                      addSubcategory.mutate(
                        { path: { category_id: category.id }, body },
                        { onSuccess: reset },
                      )
                    }
                  />
                ) : null}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Departments</CardTitle>
            <CardDescription>Teams complaints can be routed to.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {canManage ? (
              <AddItemForm
                codePlaceholder="DEPT_CODE"
                namePlaceholder="Department name"
                pending={addDepartment.isPending}
                onSubmit={(body, reset) => addDepartment.mutate({ body }, { onSuccess: reset })}
              />
            ) : null}
            <ul className="space-y-2">
              {departments.data?.map((d) => (
                <li key={d.id} className="text-sm">
                  <span className="font-medium">{d.name}</span>{" "}
                  <code className="text-xs text-muted-foreground">{d.code}</code>
                  {d.description ? (
                    <p className="text-xs text-muted-foreground">{d.description}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>SLA targets</CardTitle>
            <CardDescription>
              Minutes per priority.{canManage ? " Edit a value and leave the field to save." : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Priority</TableHead>
                  <TableHead>First response</TableHead>
                  <TableHead>Resolution</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {slas.data?.map((sla) => (
                  <TableRow key={sla.id}>
                    <TableCell className="font-medium">
                      {sla.priority} <span className="text-muted-foreground">{sla.name}</span>
                    </TableCell>
                    {(["first_response_minutes", "resolution_minutes"] as const).map((field) => (
                      <TableCell key={field}>
                        {canManage ? (
                          <Input
                            key={sla[field]}
                            type="number"
                            min={1}
                            className="h-8 w-24"
                            defaultValue={sla[field]}
                            aria-label={`${sla.priority} ${field.replaceAll("_", " ")}`}
                            onBlur={(e) => saveSla(sla, field, e.target.value)}
                          />
                        ) : (
                          hours(sla[field])
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
