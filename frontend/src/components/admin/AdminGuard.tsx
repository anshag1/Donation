"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/components/admin/AuthProvider";

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { admin, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !admin) {
      router.replace("/admin/login");
    }
  }, [loading, admin, router]);

  if (loading || !admin) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return <>{children}</>;
}

/** Wraps a page body that requires specific roles beyond "just logged in" —
 * e.g. the Users/Settings pages. Renders nothing but a message if the
 * logged-in admin lacks the role; the backend enforces this regardless,
 * this is purely to avoid showing a confusing empty/erroring page. */
export function RequireRole({
  roles,
  children,
}: {
  roles: string[];
  children: React.ReactNode;
}) {
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        You don&apos;t have permission to view this page.
      </div>
    );
  }
  return <>{children}</>;
}
