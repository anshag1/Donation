"use client";

import { useState } from "react";
import { Loader2, ShieldCheck, ShieldOff } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuth } from "@/components/admin/AuthProvider";
import { disable2fa, enable2fa, setup2fa, type TwoFactorSetup } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";

export default function AccountPage() {
  const { admin, refreshAdmin } = useAuth();
  const [setup, setSetup] = useState<TwoFactorSetup | null>(null);
  const [code, setCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function startEnrollment() {
    setIsSubmitting(true);
    try {
      const result = await setup2fa();
      setSetup(result);
    } catch (error) {
      toast.error("Could not start two-factor setup", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function confirmEnrollment(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await enable2fa(code);
      toast.success("Two-factor authentication enabled");
      setSetup(null);
      setCode("");
      await refreshAdmin();
    } catch (error) {
      toast.error("Invalid code", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onDisable(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await disable2fa(code);
      toast.success("Two-factor authentication disabled");
      setCode("");
      await refreshAdmin();
    } catch (error) {
      toast.error("Invalid code", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!admin) return null;

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">My account</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="text-muted-foreground">Name:</span> {admin.full_name}</p>
          <p><span className="text-muted-foreground">Email:</span> {admin.email}</p>
          <p><span className="text-muted-foreground">Roles:</span> {admin.roles.join(", ")}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {admin.two_factor_enabled ? (
              <ShieldCheck className="size-4 text-emerald-600" />
            ) : (
              <ShieldOff className="size-4 text-muted-foreground" />
            )}
            Two-factor authentication
          </CardTitle>
          <CardDescription>
            {admin.two_factor_enabled
              ? "Enabled — a code from your authenticator app is required at every sign-in."
              : "Add an extra layer of security using an authenticator app (Google Authenticator, Authy, 1Password, etc.)."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {admin.two_factor_enabled ? (
            <form onSubmit={onDisable} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="disable-code">Enter a current code to disable</Label>
                <Input
                  id="disable-code"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <Button type="submit" variant="destructive" disabled={isSubmitting || code.length !== 6}>
                {isSubmitting && <Loader2 className="animate-spin" />}
                Disable two-factor authentication
              </Button>
            </form>
          ) : setup ? (
            <form onSubmit={confirmEnrollment} className="space-y-4">
              <div className="flex justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={setup.qr_code_data_uri}
                  alt="Scan this QR code with your authenticator app"
                  className="size-48 rounded-md border"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Can&apos;t scan? Enter this code manually: <span className="font-mono">{setup.secret}</span>
              </p>
              <div className="space-y-1.5">
                <Label htmlFor="enable-code">Enter the 6-digit code to confirm</Label>
                <Input
                  id="enable-code"
                  inputMode="numeric"
                  maxLength={6}
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={isSubmitting || code.length !== 6}>
                  {isSubmitting && <Loader2 className="animate-spin" />}
                  Confirm and enable
                </Button>
                <Button type="button" variant="ghost" onClick={() => setSetup(null)}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <Button onClick={startEnrollment} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" />}
              Set up two-factor authentication
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
