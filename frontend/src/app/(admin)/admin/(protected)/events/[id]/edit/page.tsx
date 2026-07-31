"use client";

import { use, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EventForm } from "@/components/admin/EventForm";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminEvent } from "@/types/api";

export default function EditEventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [event, setEvent] = useState<AdminEvent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApiClient
      .get<AdminEvent>(`/api/v1/admin/events/${id}`)
      .then(setEvent)
      .catch((error) => {
        toast.error("Could not load event", {
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

  if (!event) {
    return <p className="text-muted-foreground">Event not found.</p>;
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Edit event</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Event details</CardTitle>
        </CardHeader>
        <CardContent>
          <EventForm event={event} />
        </CardContent>
      </Card>
    </div>
  );
}
