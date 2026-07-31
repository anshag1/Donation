"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import { formatInrFromPaise } from "@/lib/format";
import type { DonorDetail } from "@/types/api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  pending: "secondary",
  failed: "destructive",
  refunded: "outline",
};

export default function DonorDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [donor, setDonor] = useState<DonorDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApiClient
      .get<DonorDetail>(`/api/v1/admin/donors/${id}`)
      .then(setDonor)
      .catch((error) => {
        toast.error("Could not load donor", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!donor) return <p className="text-muted-foreground">Donor not found.</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <Link href="/admin/donors" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to donors
      </Link>

      <h1 className="text-2xl font-semibold tracking-tight">{donor.full_name}</h1>

      <Card>
        <CardContent className="grid gap-2 p-5 sm:grid-cols-2">
          <p className="text-sm">
            <span className="text-muted-foreground">Mobile:</span> {donor.mobile_number}
          </p>
          <p className="text-sm">
            <span className="text-muted-foreground">Email:</span> {donor.email ?? "—"}
          </p>
          <p className="text-sm">
            <span className="text-muted-foreground">PAN:</span> {donor.pan_number ?? "—"}
          </p>
          <p className="text-sm">
            <span className="text-muted-foreground">Address:</span> {donor.address ?? "—"}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Donation history</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Event / Purpose</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Receipt</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {donor.donations.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No donations yet.
                  </TableCell>
                </TableRow>
              )}
              {donor.donations.map((donation) => (
                <TableRow key={donation.id}>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(donation.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </TableCell>
                  <TableCell className="text-sm">{donation.event_title ?? donation.purpose ?? "—"}</TableCell>
                  <TableCell className="font-medium">{formatInrFromPaise(donation.amount_in_paise)}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[donation.status] ?? "outline"}>{donation.status}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {donation.receipt_number ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
