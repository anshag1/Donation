"use client";

import Link from "next/link";
import { CheckCircle2, Loader2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useDonationStatusPoll } from "@/hooks/use-donation-status-poll";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function PaymentStatusPoller({ donationId }: { donationId: string }) {
  const { status, outcome } = useDonationStatusPoll(donationId);

  if (outcome === "polling") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
          <Loader2 className="size-10 animate-spin text-primary" />
          <div>
            <p className="font-medium">Verifying your payment…</p>
            <p className="text-sm text-muted-foreground">
              This usually takes just a few seconds. Please don&apos;t close this page.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (outcome === "success" && status) {
    const downloadUrl = status.receipt_download_url
      ? `${API_BASE_URL}${status.receipt_download_url}`
      : undefined;

    return (
      <Card>
        <CardHeader className="items-center text-center">
          <CheckCircle2 className="size-12 text-emerald-600" />
          <CardTitle className="text-2xl">Thank you for your donation!</CardTitle>
          <CardDescription>
            Your payment was successful and your donation has been recorded.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          {status.receipt_number && (
            <p className="text-sm text-muted-foreground">
              Receipt number: <span className="font-mono font-medium text-foreground">{status.receipt_number}</span>
            </p>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            {downloadUrl && (
              <Button asChild>
                <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
                  Download receipt
                </a>
              </Button>
            )}
            <Button variant="outline" asChild>
              <Link href="/donate">Make another donation</Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            A copy of your receipt has also been emailed to you, if you provided an email address.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (outcome === "failed") {
    return (
      <Card>
        <CardHeader className="items-center text-center">
          <XCircle className="size-12 text-destructive" />
          <CardTitle className="text-2xl">Payment unsuccessful</CardTitle>
          <CardDescription>
            Your payment could not be completed, and no amount has been deducted for this attempt.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center">
          <Button asChild>
            <Link href="/donate">Try again</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  // timed_out — payment may have gone through but confirmation is delayed
  return (
    <Card>
      <CardHeader className="items-center text-center">
        <Clock className="size-12 text-amber-600" />
        <CardTitle className="text-2xl">Still confirming your payment</CardTitle>
        <CardDescription>
          This is taking longer than usual. If your payment succeeded, you&apos;ll receive your
          receipt by email shortly — no action is needed on your part.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex justify-center">
        <Button variant="outline" onClick={() => window.location.reload()}>
          Check again
        </Button>
      </CardContent>
    </Card>
  );
}
