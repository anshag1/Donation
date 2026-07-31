"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Loader2, Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Pagination } from "@/components/admin/Pagination";
import { RequireRole } from "@/components/admin/AdminGuard";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AdminEvent, Paginated } from "@/types/api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  active: "default",
  draft: "secondary",
  closed: "outline",
};

export default function EventsListPage() {
  const [data, setData] = useState<Paginated<AdminEvent> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback((p: number) => {
    adminApiClient
      .get<Paginated<AdminEvent>>(`/api/v1/admin/events?page=${p}&page_size=20`)
      .then(setData)
      .catch((error) => {
        toast.error("Could not load events", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(page), [load, page]);

  async function handleDelete(id: string) {
    try {
      await adminApiClient.delete(`/api/v1/admin/events/${id}`);
      toast.success("Event deleted");
      load(page);
    } catch (error) {
      toast.error("Could not delete event", {
        description: error instanceof ApiError ? error.message : "Please try again.",
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Events</h1>
        <RequireRole roles={["super_admin", "admin", "coordinator"]}>
          <Button asChild>
            <Link href="/admin/events/new">
              <Plus /> New event
            </Link>
          </Button>
        </RequireRole>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No events yet.
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((event) => (
                <TableRow key={event.id}>
                  <TableCell className="font-medium">{event.title}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">/donate/{event.slug}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[event.status] ?? "outline"}>{event.status}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {event.start_date ?? "—"} {event.end_date ? `– ${event.end_date}` : ""}
                  </TableCell>
                  <TableCell className="text-right">
                    <RequireRole roles={["super_admin", "admin", "coordinator"]}>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" asChild>
                          <Link href={`/admin/events/${event.id}/edit`}>
                            <Pencil className="size-4" />
                          </Link>
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <Trash2 className="size-4 text-destructive" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete &ldquo;{event.title}&rdquo;?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This can&apos;t be undone. Events with donations recorded against them can&apos;t be
                                deleted — close them instead.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(event.id)}>Delete</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </RequireRole>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}
