import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DonationForm } from "@/components/donation/DonationForm";
import { apiClient } from "@/lib/api-client";
import type { PublicEvent } from "@/types/api";

export const metadata: Metadata = {
  title: "Make a donation",
};

async function getActiveEvents(): Promise<PublicEvent[]> {
  try {
    return await apiClient.get<PublicEvent[]>("/api/v1/events/public");
  } catch {
    // The donation form still works with no event picker if this fails —
    // donors can just support the general fund.
    return [];
  }
}

export default async function GeneralDonatePage() {
  const events = await getActiveEvents();

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
        <DonationForm events={events} />
      </CardContent>
    </Card>
  );
}
