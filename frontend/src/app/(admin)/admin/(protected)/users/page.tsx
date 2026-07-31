"use client";

import { useEffect, useState, useCallback } from "react";
import { Loader2, Plus, Pencil } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RequireRole } from "@/components/admin/AdminGuard";
import { UserFormDialog } from "@/components/admin/UserFormDialog";
import { useAuth } from "@/components/admin/AuthProvider";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminUserListItem, Paginated } from "@/types/api";

function UsersPageInner() {
  const { admin } = useAuth();
  const [data, setData] = useState<Paginated<AdminUserListItem> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    adminApiClient
      .get<Paginated<AdminUserListItem>>("/api/v1/admin/users?page=1&page_size=100")
      .then(setData)
      .catch((error) => {
        toast.error("Could not load users", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  async function toggleActive(user: AdminUserListItem) {
    if (user.id === admin?.id) {
      toast.error("You cannot deactivate your own account");
      return;
    }
    try {
      await adminApiClient.patch(`/api/v1/admin/users/${user.id}`, { is_active: !user.is_active });
      toast.success(user.is_active ? "User deactivated" : "User activated");
      load();
    } catch (error) {
      toast.error("Could not update user", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <UserFormDialog
          onSaved={load}
          trigger={
            <Button>
              <Plus /> New user
            </Button>
          }
        />
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Active</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.full_name}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{user.email}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {user.roles.map((role) => (
                      <Badge key={role} variant="outline">
                        {role.replace("_", " ")}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <Switch
                    checked={user.is_active}
                    onCheckedChange={() => toggleActive(user)}
                    disabled={user.id === admin?.id}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <UserFormDialog
                    user={user}
                    onSaved={load}
                    trigger={
                      <Button variant="ghost" size="icon">
                        <Pencil className="size-4" />
                      </Button>
                    }
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function UsersPage() {
  return (
    <RequireRole roles={["super_admin"]}>
      <UsersPageInner />
    </RequireRole>
  );
}
