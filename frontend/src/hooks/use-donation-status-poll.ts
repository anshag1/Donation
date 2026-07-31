"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api-client";
import type { DonationStatusResponse } from "@/types/api";

const POLL_INTERVAL_MS = 2000;
const TIMEOUT_MS = 60_000;

export type PollOutcome = "polling" | "success" | "failed" | "timed_out";

export function useDonationStatusPoll(donationId: string) {
  const [status, setStatus] = useState<DonationStatusResponse | null>(null);
  const [outcome, setOutcome] = useState<PollOutcome>("polling");
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timeoutHandle: ReturnType<typeof setTimeout>;
    startedAtRef.current = Date.now();

    async function poll() {
      try {
        const result = await apiClient.get<DonationStatusResponse>(
          `/api/v1/donations/${donationId}/status`,
        );
        if (cancelled) return;

        setStatus(result);

        if (result.status === "success") {
          setOutcome("success");
          return;
        }
        if (result.status === "failed") {
          setOutcome("failed");
          return;
        }
      } catch {
        // transient network error — keep polling until the timeout below
      }

      if (Date.now() - (startedAtRef.current ?? Date.now()) > TIMEOUT_MS) {
        if (!cancelled) setOutcome("timed_out");
        return;
      }

      timeoutHandle = setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timeoutHandle);
    };
  }, [donationId]);

  return { status, outcome };
}
