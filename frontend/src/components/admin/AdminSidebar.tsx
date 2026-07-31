"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  HeartHandshake,
  CalendarDays,
  Users,
  UserCog,
  ScrollText,
  Settings,
  FileDown,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/admin/AuthProvider";
import { Button } from "@/components/ui/button";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/donations", label: "Donations", icon: HeartHandshake },
  { href: "/admin/events", label: "Events", icon: CalendarDays },
  { href: "/admin/donors", label: "Donors", icon: Users },
  { href: "/admin/reports", label: "Reports", icon: FileDown },
  { href: "/admin/audit-logs", label: "Audit Logs", icon: ScrollText, roles: ["super_admin", "treasurer"] },
  { href: "/admin/users", label: "Users", icon: UserCog, roles: ["super_admin"] },
  { href: "/admin/settings", label: "Settings", icon: Settings, roles: ["super_admin"] },
  { href: "/admin/account", label: "My Account", icon: ShieldCheck },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const { admin, hasRole, logout } = useAuth();

  const visibleItems = NAV_ITEMS.filter((item) => !item.roles || hasRole(...item.roles));

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-background">
      <div className="flex items-center gap-2 border-b px-4 py-4">
        <HeartHandshake className="size-5 text-primary" />
        <span className="font-semibold tracking-tight">Donation Admin</span>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {visibleItems.map((item) => {
          const isActive = item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-3">
        <div className="mb-2 px-1">
          <p className="truncate text-sm font-medium">{admin?.full_name}</p>
          <p className="truncate text-xs text-muted-foreground">{admin?.email}</p>
        </div>
        <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={() => logout()}>
          <LogOut className="size-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
