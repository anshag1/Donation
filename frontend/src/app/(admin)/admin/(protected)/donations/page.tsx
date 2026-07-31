"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Pagination } from "@/components/admin/Pagination";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import { formatInrFromPaise } from "@/lib/format";
import type { AdminDonationListItem, Paginated } from "@/types/api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  pending: "secondary",
  failed: "destructive",
  refunded: "outline",
};

export default function DonationsListPage() {
  const [data, setData] = useState<Paginated<AdminDonationListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("all");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback((p: number, statusFilter: string, search: string) => {
    const params = new URLSearchParams({ page: String(p), page_size: "20" });
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (search) params.set("q", search);

    adminApiClient
      .get<Paginated<AdminDonationListItem>>(`/api/v1/admin/donations?${params}`)
      .then(setData)
      .catch((error) => {
        toast.error("Could not load donations", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  // `q` deliberately excluded: search runs on form submit (onSearchSubmit),
  // not on every keystroke — only page/status changes should auto-refetch.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(page, status, q), [load, page, status]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    load(1, status, q);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Donations</h1>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <form onSubmit={onSearchSubmit} className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by donor name or mobile number"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </form>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="refunded">Refunded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Donor</TableHead>
                <TableHead>Event / Purpose</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No donations match these filters.
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((donation) => (
                <TableRow key={donation.id} className="cursor-pointer">
                  <TableCell>
                    <Link href={`/admin/donations/${donation.id}`} className="block hover:underline">
                      <p className="font-medium">{donation.donor_name}</p>
                      <p className="text-xs text-muted-foreground">{donation.donor_mobile}</p>
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {donation.event_title ?? donation.purpose ?? "—"}
                  </TableCell>
                  <TableCell className="font-medium">{formatInrFromPaise(donation.amount_in_paise)}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[donation.status] ?? "outline"}>{donation.status}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(donation.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}
