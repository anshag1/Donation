import { CalendarDays } from "lucide-react";
import type { PublicEvent } from "@/types/api";

function formatDateRange(start: string | null, end: string | null): string | null {
  if (!start && !end) return null;
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "long", year: "numeric" };
  const startLabel = start ? new Intl.DateTimeFormat("en-IN", opts).format(new Date(start)) : null;
  const endLabel = end ? new Intl.DateTimeFormat("en-IN", opts).format(new Date(end)) : null;
  if (startLabel && endLabel && startLabel !== endLabel) return `${startLabel} – ${endLabel}`;
  return startLabel ?? endLabel;
}

export function EventBanner({ event }: { event: PublicEvent }) {
  const dateRange = formatDateRange(event.start_date, event.end_date);

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      {event.banner_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={event.banner_url} alt="" className="h-40 w-full object-cover sm:h-52" />
      ) : (
        <div className="h-24 w-full bg-gradient-to-br from-primary to-primary/70" />
      )}
      <div className="space-y-2 p-5">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{event.title}</h1>
        {dateRange && (
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <CalendarDays className="size-4" />
            {dateRange}
          </p>
        )}
        {event.description && (
          <p className="text-sm leading-relaxed text-muted-foreground">{event.description}</p>
        )}
      </div>
    </div>
  );
}
