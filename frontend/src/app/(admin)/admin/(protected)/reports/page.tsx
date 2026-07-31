"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { adminApiClient, triggerBlobDownload } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";

export default function ReportsPage() {
  const [status, setStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    try {
      const params = new URLSearchParams();
      if (status !== "all") params.set("status", status);
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());

      const blob = await adminApiClient.download(`/api/v1/admin/reports/export.csv?${params}`);
      triggerBlobDownload(blob, `donations-export-${new Date().toISOString().slice(0, 10)}.csv`);
      toast.success("Export downloaded");
    } catch (error) {
      toast.error("Could not generate export", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export donations</CardTitle>
          <CardDescription>Download a CSV of donations matching the filters below.</CardDescription>
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
          <Button onClick={handleDownload} disabled={downloading}>
            {downloading ? <Loader2 className="animate-spin" /> : <Download />}
            Download CSV
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
