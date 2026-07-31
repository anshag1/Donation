"use client";

import { useEffect, useState, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Pagination } from "@/components/admin/Pagination";
import { RequireRole } from "@/components/admin/AdminGuard";
import { adminApiClient } from "@/lib/auth";
import { ApiError } from "@/lib/api-client";
import type { AuditLogEntry, Paginated } from "@/types/api";

function AuditLogsPageInner() {
  const [data, setData] = useState<Paginated<AuditLogEntry> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback((p: number) => {
    adminApiClient
      .get<Paginated<AuditLogEntry>>(`/api/v1/admin/audit-logs?page=${p}&page_size=25`)
      .then(setData)
      .catch((error) => {
        toast.error("Could not load audit logs", {
          description: error instanceof ApiError ? error.message : "Please try again.",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(page), [load, page]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Audit logs</h1>
      <p className="text-sm text-muted-foreground">
        A record of every donation confirmation, receipt action, and admin change — insert-only, never edited.
      </p>

      {loading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No activity recorded yet.
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(log.created_at).toLocaleString("en-IN")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{log.action}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {log.entity_type}
                    {log.entity_id && <span className="ml-1 font-mono text-xs">{log.entity_id.slice(0, 8)}</span>}
                  </TableCell>
                  <TableCell className="text-sm">{log.actor_email ?? "System"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{log.ip_address ?? "—"}</TableCell>
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

export default function AuditLogsPage() {
  return (
    <RequireRole roles={["super_admin", "treasurer"]}>
      <AuditLogsPageInner />
    </RequireRole>
  );
}
