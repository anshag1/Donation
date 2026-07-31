import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HeartHandshake } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EventBanner } from "@/components/donation/EventBanner";
import { apiClient, ApiError } from "@/lib/api-client";
import type { PublicEvent } from "@/types/api";

interface EventDetailsPageProps {
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

export async function generateMetadata({ params }: EventDetailsPageProps): Promise<Metadata> {
  const { eventSlug } = await params;
  const event = await getEvent(eventSlug);
  return { title: event ? event.title : "Event not found" };
}

export default async function EventDetailsPage({ params }: EventDetailsPageProps) {
  const { eventSlug } = await params;
  const event = await getEvent(eventSlug);

  if (!event) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <EventBanner event={event} />
      <Button asChild size="lg" className="w-full sm:w-auto">
        <Link href={`/donate/${event.slug}`}>
          <HeartHandshake />
          Donate to this event
        </Link>
      </Button>
    </div>
  );
}
