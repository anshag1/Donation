"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { type CurrentAdmin, fetchCurrentAdmin, login as loginRequest, logout as logoutRequest } from "@/lib/auth";

interface AuthContextValue {
  admin: CurrentAdmin | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<CurrentAdmin | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    fetchCurrentAdmin()
      .then(setAdmin)
      .finally(() => setLoading(false));
  }, []);

  const value: AuthContextValue = {
    admin,
    loading,
    login: async (email, password) => {
      await loginRequest(email, password);
      const current = await fetchCurrentAdmin();
      setAdmin(current);
    },
    logout: async () => {
      await logoutRequest();
      setAdmin(null);
      router.push("/admin/login");
    },
    hasRole: (...roles: string[]) => !!admin && roles.some((r) => admin.roles.includes(r)),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
