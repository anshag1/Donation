"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Mail, Copy, Download } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { RequireRole } from "@/components/admin/AdminGuard";
import { adminApiClient, triggerBlobDownload } from "@/lib/auth";
import { ApiError, API_BASE_URL } from "@/lib/api-client";
import { formatInrFromPaise } from "@/lib/format";
import type { AdminDonationDetail } from "@/types/api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  pending: "secondary",
  failed: "destructive",
  refunded: "outline",
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between border-b py-2 text-sm last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

export default function DonationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [donation, setDonation] = useState<AdminDonationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState(false);

  function load() {
    adminApiClient
      .get<AdminDonationDetail>(`/api/v1/admin/donations/${id}`)
      .then(setDonation)
      .catch((error) => {
        toast.error("Could not load donation", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  async function handleResendEmail() {
    setActionPending(true);
    try {
      await adminApiClient.post(`/api/v1/admin/donations/${id}/receipt/resend-email`);
      toast.success("Receipt emailed to donor");
      load();
    } catch (error) {
      toast.error("Could not resend receipt", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setActionPending(false);
    }
  }

  async function handleDuplicate() {
    setActionPending(true);
    try {
      const blob = await adminApiClient.download(`/api/v1/admin/donations/${id}/receipt/duplicate`, {
        method: "POST",
      });
      triggerBlobDownload(blob, `${donation?.receipt?.receipt_number.replace(/\//g, "_")}_DUPLICATE.pdf`);
      toast.success("Duplicate receipt downloaded");
      load();
    } catch (error) {
      toast.error("Could not generate duplicate", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setActionPending(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!donation) return <p className="text-muted-foreground">Donation not found.</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <Link href="/admin/donations" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to donations
      </Link>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{formatInrFromPaise(donation.amount_in_paise)}</h1>
        <Badge variant={STATUS_VARIANT[donation.status] ?? "outline"}>{donation.status}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Donor</CardTitle>
        </CardHeader>
        <CardContent>
          <Field label="Name" value={donation.donor_snapshot.full_name} />
          <Field label="Mobile" value={donation.donor_snapshot.mobile_number} />
          <Field label="Email" value={donation.donor_snapshot.email ?? "—"} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Donation</CardTitle>
        </CardHeader>
        <CardContent>
          <Field label="Event / Purpose" value={donation.event_title ?? donation.purpose ?? "General donation"} />
          <Field label="Date" value={new Date(donation.created_at).toLocaleString("en-IN")} />
          <Field label="Currency" value={donation.currency} />
        </CardContent>
      </Card>

      {donation.payment && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Payment</CardTitle>
          </CardHeader>
          <CardContent>
            <Field label="Order ID" value={<span className="font-mono text-xs">{donation.payment.razorpay_order_id}</span>} />
            <Field
              label="Payment ID"
              value={<span className="font-mono text-xs">{donation.payment.razorpay_payment_id ?? "—"}</span>}
            />
            <Field label="Method" value={donation.payment.method ?? "—"} />
            {donation.payment.failure_reason && (
              <Field label="Failure reason" value={donation.payment.failure_reason} />
            )}
          </CardContent>
        </Card>
      )}

      {donation.receipt && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Receipt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Receipt number" value={donation.receipt.receipt_number} />
            <Field label="Emailed" value={donation.receipt.emailed_at ? new Date(donation.receipt.emailed_at).toLocaleString("en-IN") : "Not sent"} />
            {donation.receipt.duplicate_count > 0 && (
              <Field label="Duplicates generated" value={donation.receipt.duplicate_count} />
            )}
            <Separator />
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <a href={`${API_BASE_URL}${donation.receipt.download_url}`} target="_blank" rel="noopener noreferrer">
                  <Download /> Download
                </a>
              </Button>
              <RequireRole roles={["super_admin", "admin", "treasurer"]}>
                <Button variant="outline" size="sm" disabled={actionPending} onClick={handleResendEmail}>
                  <Mail /> Resend email
                </Button>
                <Button variant="outline" size="sm" disabled={actionPending} onClick={handleDuplicate}>
                  <Copy /> Generate duplicate
                </Button>
              </RequireRole>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
