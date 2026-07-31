"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Pagination } from "@/components/admin/Pagination";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import { formatInrFromPaise } from "@/lib/format";
import type { DonorListItem, Paginated } from "@/types/api";

export default function DonorsListPage() {
  const [data, setData] = useState<Paginated<DonorListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback((p: number, search: string) => {
    const params = new URLSearchParams({ page: String(p), page_size: "20" });
    if (search) params.set("q", search);

    adminApiClient
      .get<Paginated<DonorListItem>>(`/api/v1/admin/donors?${params}`)
      .then(setData)
      .catch((error) => {
        toast.error("Could not load donors", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  // `q` deliberately excluded: search runs on form submit (onSearchSubmit),
  // not on every keystroke — only page changes should auto-refetch.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(page, q), [load, page]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    load(1, q);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Donors</h1>

      <form onSubmit={onSearchSubmit} className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search by name, mobile, or email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9"
        />
      </form>

      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Donations</TableHead>
                <TableHead>Total donated</TableHead>
                <TableHead>Last donation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No donors found.
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((donor) => (
                <TableRow key={donor.id}>
                  <TableCell>
                    <Link href={`/admin/donors/${donor.id}`} className="font-medium hover:underline">
                      {donor.full_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {donor.mobile_number}
                    {donor.email && <span className="block">{donor.email}</span>}
                  </TableCell>
                  <TableCell>{donor.donation_count}</TableCell>
                  <TableCell className="font-medium">{formatInrFromPaise(donor.total_donated_in_paise)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {donor.last_donation_at
                      ? new Date(donor.last_donation_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })
                      : "—"}
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
