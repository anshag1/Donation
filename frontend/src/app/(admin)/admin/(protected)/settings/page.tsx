"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { RequireRole } from "@/components/admin/AdminGuard";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { Organization, OrganizationUpdateInput } from "@/types/api";

function SettingsPageInner() {
  const [org, setOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    adminApiClient
      .get<Organization>("/api/v1/admin/organization")
      .then(setOrg)
      .catch((error) => {
        toast.error("Could not load organization settings", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setIsSubmitting(true);
    const body: OrganizationUpdateInput = {
      name: org.name,
      contact_email: org.contact_email ?? undefined,
      pan_number: org.pan_number ?? undefined,
      address: org.address ?? undefined,
      receipt_prefix: org.receipt_prefix,
      logo_url: org.logo_url ?? undefined,
      signature_image_url: org.signature_image_url ?? undefined,
    };
    try {
      const updated = await adminApiClient.patch<Organization>("/api/v1/admin/organization", body);
      setOrg(updated);
      toast.success("Settings saved");
    } catch (error) {
      toast.error("Could not save settings", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!org) return null;

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Organization settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
          <CardDescription>Shown on receipts and the public donation pages.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Organization name</Label>
              <Input id="name" value={org.name} onChange={(e) => setOrg({ ...org, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="receipt_prefix">Receipt prefix</Label>
              <Input
                id="receipt_prefix"
                value={org.receipt_prefix}
                onChange={(e) => setOrg({ ...org, receipt_prefix: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Receipts are numbered {org.receipt_prefix}/2026-27/000001, and so on.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="contact_email">Contact email</Label>
              <Input
                id="contact_email"
                type="email"
                value={org.contact_email ?? ""}
                onChange={(e) => setOrg({ ...org, contact_email: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pan_number">Organization PAN</Label>
              <Input
                id="pan_number"
                value={org.pan_number ?? ""}
                onChange={(e) => setOrg({ ...org, pan_number: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="address">Address</Label>
              <Input id="address" value={org.address ?? ""} onChange={(e) => setOrg({ ...org, address: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="logo_url">
                Logo URL <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="logo_url"
                value={org.logo_url ?? ""}
                onChange={(e) => setOrg({ ...org, logo_url: e.target.value })}
              />
            </div>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" />}
              Save changes
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireRole roles={["super_admin"]}>
      <SettingsPageInner />
    </RequireRole>
  );
}
