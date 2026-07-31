"use client";

import { useEffect, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { adminApiClient, triggerBlobDownload } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminEvent, Paginated } from "@/types/api";

function ExportCard() {
  const [status, setStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [downloading, setDownloading] = useState<"csv" | "xlsx" | null>(null);

  function buildParams() {
    const params = new URLSearchParams();
    if (status !== "all") params.set("status", status);
    if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
    if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
    return params;
  }

  async function handleDownload(format: "csv" | "xlsx") {
    setDownloading(format);
    try {
      const params = buildParams();
      const blob = await adminApiClient.download(`/api/v1/admin/reports/export.${format}?${params}`);
      triggerBlobDownload(blob, `donations-export-${new Date().toISOString().slice(0, 10)}.${format}`);
      toast.success("Export downloaded");
    } catch (error) {
      toast.error("Could not generate export", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setDownloading(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Export donations</CardTitle>
        <CardDescription>Download donations matching the filters below as CSV or Excel.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="refunded">Refunded</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date_from">From</Label>
            <Input id="date_from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date_to">To</Label>
            <Input id="date_to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => handleDownload("csv")} disabled={downloading !== null}>
            {downloading === "csv" ? <Loader2 className="animate-spin" /> : <Download />}
            Download CSV
          </Button>
          <Button variant="outline" onClick={() => handleDownload("xlsx")} disabled={downloading !== null}>
            {downloading === "xlsx" ? <Loader2 className="animate-spin" /> : <Download />}
            Download Excel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryReportCard() {
  const [period, setPeriod] = useState<"event" | "month" | "year">("year");
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [eventId, setEventId] = useState<string>("");
  const now = new Date();
  const [year, setYear] = useState(String(now.getFullYear()));
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (period !== "event") return;
    adminApiClient
      .get<Paginated<AdminEvent>>("/api/v1/admin/events?page=1&page_size=100")
      .then((res) => setEvents(res.items))
      .catch(() => setEvents([]));
  }, [period]);

  async function handleDownload() {
    setDownloading(true);
    try {
      const params = new URLSearchParams({ period });
      if (period === "event") {
        if (!eventId) {
          toast.error("Choose an event first");
          setDownloading(false);
          return;
        }
        params.set("event_id", eventId);
      } else if (period === "month") {
        params.set("year", year);
        params.set("month", month);
      } else {
        params.set("year", year);
      }
      const blob = await adminApiClient.download(`/api/v1/admin/reports/summary.pdf?${params}`);
      triggerBlobDownload(blob, `summary-${period}-${new Date().toISOString().slice(0, 10)}.pdf`);
      toast.success("Summary report downloaded");
    } catch (error) {
      toast.error("Could not generate report", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Summary report (PDF)</CardTitle>
        <CardDescription>A board-ready totals summary — event-wise, monthly, or yearly.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label>Report type</Label>
          <Select value={period} onValueChange={(v) => setPeriod(v as typeof period)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="year">Yearly</SelectItem>
              <SelectItem value="month">Monthly</SelectItem>
              <SelectItem value="event">Event-wise</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {period === "event" && (
          <div className="space-y-1.5">
            <Label>Event</Label>
            <Select value={eventId} onValueChange={setEventId}>
              <SelectTrigger>
                <SelectValue placeholder="Choose an event" />
              </SelectTrigger>
              <SelectContent>
                {events.map((event) => (
                  <SelectItem key={event.id} value={event.id}>
                    {event.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {(period === "month" || period === "year") && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="report_year">Year</Label>
              <Input id="report_year" type="number" value={year} onChange={(e) => setYear(e.target.value)} />
            </div>
            {period === "month" && (
              <div className="space-y-1.5">
                <Label htmlFor="report_month">Month</Label>
                <Select value={month} onValueChange={setMonth}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <SelectItem key={m} value={String(m)}>
                        {new Date(2000, m - 1, 1).toLocaleString("default", { month: "long" })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        )}

        <Button onClick={handleDownload} disabled={downloading}>
          {downloading ? <Loader2 className="animate-spin" /> : <Download />}
          Download summary PDF
        </Button>
      </CardContent>
    </Card>
  );
}

export default function ReportsPage() {
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
      <ExportCard />
      <SummaryReportCard />
    </div>
  );
}
