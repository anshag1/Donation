import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { EventBanner } from "@/components/donation/EventBanner";
import { DonationForm } from "@/components/donation/DonationForm";
import { apiClient, ApiError } from "@/lib/api-client";
import type { PublicEvent } from "@/types/api";

interface EventDonatePageProps {
  params: Promise<{ eventSlug: string }>;
}

async function getEvent(slug: string): Promise<PublicEvent | null> {
  try {
    return await apiClient.get<PublicEvent>(`/api/v1/events/public/${slug}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function generateMetadata({ params }: EventDonatePageProps): Promise<Metadata> {
  const { eventSlug } = await params;
  const event = await getEvent(eventSlug);
  return { title: event ? `Donate to ${event.title}` : "Event not found" };
}

export default async function EventDonatePage({ params }: EventDonatePageProps) {
  const { eventSlug } = await params;
  const event = await getEvent(eventSlug);

  if (!event) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <EventBanner event={event} />
      <Card>
        <CardContent className="pt-6">
          <DonationForm event={event} />
        </CardContent>
      </Card>
    </div>
  );
}
