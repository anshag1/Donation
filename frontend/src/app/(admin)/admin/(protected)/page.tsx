"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/admin/KpiCard";
import { adminApiClient } from "@/lib/auth";
import { formatInrFromPaise } from "@/lib/format";
import type { DashboardSummary } from "@/types/api";
import { ApiError } from "@/lib/api-client";
import { toast } from "sonner";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  pending: "secondary",
  failed: "destructive",
  refunded: "outline",
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApiClient
      .get<DashboardSummary>("/api/v1/admin/dashboard/summary")
      .then(setSummary)
      .catch((error) => {
        toast.error("Could not load dashboard", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard label="Today" value={formatInrFromPaise(summary.today_total_in_paise)} />
        <KpiCard label="This week" value={formatInrFromPaise(summary.week_total_in_paise)} />
        <KpiCard label="This month" value={formatInrFromPaise(summary.month_total_in_paise)} />
        <KpiCard label="This year" value={formatInrFromPaise(summary.year_total_in_paise)} />
        <KpiCard
          label="All time"
          value={formatInrFromPaise(summary.all_time_total_in_paise)}
          hint={`${summary.total_donation_count} donations`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent donations</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {summary.recent_donations.length === 0 ? (
            <p className="px-6 pb-6 text-sm text-muted-foreground">No donations yet.</p>
          ) : (
            <div className="divide-y">
              {summary.recent_donations.map((donation) => (
                <Link
                  key={donation.id}
                  href={`/admin/donations/${donation.id}`}
                  className="flex items-center justify-between gap-4 px-6 py-3 text-sm hover:bg-accent"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{donation.donor_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {donation.event_title ?? donation.purpose ?? "General donation"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="font-medium">{formatInrFromPaise(donation.amount_in_paise)}</span>
                    <Badge variant={STATUS_VARIANT[donation.status] ?? "outline"}>{donation.status}</Badge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
