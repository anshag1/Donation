import type { Metadata } from "next";
import { PaymentStatusPoller } from "@/components/donation/PaymentStatusPoller";

export const metadata: Metadata = {
  title: "Confirming your donation",
};

interface ConfirmationPageProps {
  params: Promise<{ donationId: string }>;
}

export default async function DonationConfirmationPage({ params }: ConfirmationPageProps) {
  const { donationId } = await params;
  return <PaymentStatusPoller donationId={donationId} />;
}
