"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminEvent, EventCreateInput, EventUpdateInput, EventStatus } from "@/types/api";

function slugify(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function EventForm({ event }: { event?: AdminEvent }) {
  const router = useRouter();
  const isEditing = !!event;

  const [title, setTitle] = useState(event?.title ?? "");
  const [slug, setSlug] = useState(event?.slug ?? "");
  const [slugTouched, setSlugTouched] = useState(isEditing);
  const [description, setDescription] = useState(event?.description ?? "");
  const [bannerUrl, setBannerUrl] = useState(event?.banner_url ?? "");
  const [status, setStatus] = useState<EventStatus>(event?.status ?? "draft");
  const [startDate, setStartDate] = useState(event?.start_date ?? "");
  const [endDate, setEndDate] = useState(event?.end_date ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (isEditing) {
        const body: EventUpdateInput = {
          title,
          description: description || null,
          banner_url: bannerUrl || null,
          status,
          start_date: startDate || null,
          end_date: endDate || null,
        };
        await adminApiClient.patch<AdminEvent>(`/api/v1/admin/events/${event.id}`, body);
        toast.success("Event updated");
      } else {
        const body: EventCreateInput = {
          title,
          slug,
          description: description || undefined,
          banner_url: bannerUrl || undefined,
          status,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        };
        await adminApiClient.post<AdminEvent>("/api/v1/admin/events", body);
        toast.success("Event created");
      }
      router.push("/admin/events");
      router.refresh();
    } catch (err) {
      setIsSubmitting(false);
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setError(message);
      toast.error("Could not save event", { description: message });
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          required
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            if (!slugTouched) setSlug(slugify(e.target.value));
          }}
        />
      </div>

      {!isEditing && (
        <div className="space-y-1.5">
          <Label htmlFor="slug">
            Slug <span className="font-normal text-muted-foreground">— used in the donation link</span>
          </Label>
          <Input
            id="slug"
            required
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value);
              setSlugTouched(true);
            }}
          />
          <p className="text-xs text-muted-foreground">/donate/{slug || "your-event-slug"}</p>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="banner_url">
          Banner image URL <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input id="banner_url" value={bannerUrl} onChange={(e) => setBannerUrl(e.target.value)} />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label>Status</Label>
          <Select value={status} onValueChange={(v) => setStatus(v as EventStatus)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="start_date">Start date</Label>
          <Input id="start_date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="end_date">End date</Label>
          <Input id="end_date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" />}
          {isEditing ? "Save changes" : "Create event"}
        </Button>
        <Button type="button" variant="outline" onClick={() => router.push("/admin/events")}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
