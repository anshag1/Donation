"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminRole, AdminUserListItem } from "@/types/api";

const ALL_ROLES: AdminRole[] = ["super_admin", "admin", "treasurer", "coordinator", "viewer"];

interface UserFormDialogProps {
  user?: AdminUserListItem;
  trigger: React.ReactNode;
  onSaved: () => void;
}

export function UserFormDialog({ user, trigger, onSaved }: UserFormDialogProps) {
  const isEditing = !!user;
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState(user?.email ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [password, setPassword] = useState("");
  const [roles, setRoles] = useState<AdminRole[]>(user?.roles ?? ["viewer"]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleRole(role: AdminRole) {
    setRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (isEditing) {
        await adminApiClient.patch(`/api/v1/admin/users/${user.id}`, { full_name: fullName, roles });
        toast.success("User updated");
      } else {
        await adminApiClient.post("/api/v1/admin/users", { email, full_name: fullName, password, roles });
        toast.success("User invited");
      }
      setOpen(false);
      onSaved();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setError(message);
      toast.error("Could not save user", { description: message });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit user" : "New admin user"}</DialogTitle>
          <DialogDescription>
            {isEditing ? "Update this admin's name and roles." : "They'll sign in with the email and password you set here."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          {!isEditing && (
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          {!isEditing && (
            <div className="space-y-1.5">
              <Label htmlFor="password">Temporary password</Label>
              <Input
                id="password"
                type="password"
                required
                minLength={10}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">At least 10 characters. Share this with them securely.</p>
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Roles</Label>
            <div className="grid grid-cols-2 gap-2">
              {ALL_ROLES.map((role) => (
                <label key={role} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={roles.includes(role)}
                    onChange={() => toggleRole(role)}
                    className="size-4 rounded border-input"
                  />
                  {role.replace("_", " ")}
                </label>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting || roles.length === 0}>
              {isSubmitting && <Loader2 className="animate-spin" />}
              {isEditing ? "Save changes" : "Create user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
