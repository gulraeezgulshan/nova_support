"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  listDepartmentsOptions,
  listUsersOptions,
  listUsersQueryKey,
  updateUserMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { Role } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { ROLE_LABELS } from "@/lib/roles";

const NO_DEPARTMENT = "__none__";

export function UsersTable({
  canManage,
  currentUserId,
}: {
  canManage: boolean;
  currentUserId: string;
}) {
  const queryClient = useQueryClient();
  const users = useQuery(listUsersOptions());
  const departments = useQuery(listDepartmentsOptions());
  const update = useMutation({
    ...updateUserMutation(),
    onSuccess: () => {
      toast.success("User updated");
      queryClient.invalidateQueries({ queryKey: listUsersQueryKey() });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (users.isPending) return <Skeleton className="h-48" />;
  if (users.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(users.error)}</p>;

  return (
    <div className="rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>User</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Department</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.data.map((user) => {
            const editable = canManage && user.id !== currentUserId;
            return (
              <TableRow key={user.id}>
                <TableCell>
                  <div className="font-medium">{user.full_name ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">{user.email ?? "no e-mail"}</div>
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Select
                      value={user.role}
                      onValueChange={(role) =>
                        update.mutate({ path: { user_id: user.id }, body: { role: role as Role } })
                      }
                    >
                      <SelectTrigger className="w-44">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(ROLE_LABELS).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    ROLE_LABELS[user.role]
                  )}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Select
                      value={user.department?.id ?? NO_DEPARTMENT}
                      onValueChange={(id) =>
                        update.mutate({
                          path: { user_id: user.id },
                          body: { department_id: id === NO_DEPARTMENT ? null : id },
                        })
                      }
                    >
                      <SelectTrigger className="w-52">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NO_DEPARTMENT}>No department</SelectItem>
                        {departments.data?.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    (user.department?.name ?? "—")
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={user.is_active ? "secondary" : "destructive"}>
                    {user.is_active ? "Active" : "Deactivated"}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
