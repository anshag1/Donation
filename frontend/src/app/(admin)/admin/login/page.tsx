"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, HeartHandshake, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuth } from "@/components/admin/AuthProvider";
import { ApiError } from "@/lib/api-client";

export default function AdminLoginPage() {
  const { login, verifyTwoFactor } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmitPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
        setIsSubmitting(false);
      } else {
        router.push("/admin");
      }
    } catch (err) {
      setIsSubmitting(false);
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setError(message);
      toast.error("Sign in failed", { description: message });
    }
  }

  async function onSubmitCode(e: React.FormEvent) {
    e.preventDefault();
    if (!mfaToken) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await verifyTwoFactor(mfaToken, code);
      router.push("/admin");
    } catch (err) {
      setIsSubmitting(false);
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setError(message);
      toast.error("Verification failed", { description: message });
    }
  }

  if (mfaToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
        <Card className="w-full max-w-sm">
          <CardHeader className="items-center text-center">
            <ShieldCheck className="size-8 text-primary" />
            <CardTitle className="text-xl">Two-factor verification</CardTitle>
            <CardDescription>Enter the 6-digit code from your authenticator app.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmitCode} className="space-y-4" noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="code">Verification code</Label>
                <Input
                  id="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={isSubmitting || code.length !== 6}>
                {isSubmitting ? <Loader2 className="animate-spin" /> : "Verify"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setMfaToken(null);
                  setCode("");
                  setError(null);
                }}
              >
                Back to sign in
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <HeartHandshake className="size-8 text-primary" />
          <CardTitle className="text-xl">Admin sign in</CardTitle>
          <CardDescription>Manage donations, events, and receipts.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmitPassword} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <Link href="/admin/forgot-password" className="text-xs text-primary hover:underline">
                  Forgot password?
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="animate-spin" /> : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
