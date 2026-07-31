"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  type CurrentAdmin,
  type LoginResult,
  fetchCurrentAdmin,
  login as loginRequest,
  logout as logoutRequest,
  verifyLogin2fa,
} from "@/lib/auth";

interface AuthContextValue {
  admin: CurrentAdmin | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  verifyTwoFactor: (mfaToken: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
  refreshAdmin: () => Promise<void>;
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
      const result = await loginRequest(email, password);
      if (!result.mfaRequired) {
        const current = await fetchCurrentAdmin();
        setAdmin(current);
      }
      return result;
    },
    verifyTwoFactor: async (mfaToken, code) => {
      await verifyLogin2fa(mfaToken, code);
      const current = await fetchCurrentAdmin();
      setAdmin(current);
    },
    logout: async () => {
      await logoutRequest();
      setAdmin(null);
      router.push("/admin/login");
    },
    hasRole: (...roles: string[]) => !!admin && roles.some((r) => admin.roles.includes(r)),
    refreshAdmin: async () => {
      const current = await fetchCurrentAdmin();
      setAdmin(current);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
