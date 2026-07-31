import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DonationForm } from "@/components/donation/DonationForm";

export const metadata: Metadata = {
  title: "Make a donation",
};

export default function GeneralDonatePage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Make a donation</CardTitle>
        <CardDescription>
          Your contribution goes directly toward our ongoing programs. You&apos;ll receive an
          official receipt by email as soon as your payment is confirmed.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <DonationForm />
      </CardContent>
    </Card>
  );
}
