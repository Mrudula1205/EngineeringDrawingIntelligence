"use client";

import { useEffect, useState } from "react";

type JobStatusPollerProps = {
  jobId: string | null;
  onStatus: (status: string) => void;
  onResult: (result: Record<string, unknown>) => void;
};

const POLL_INTERVAL = 3000;

export default function JobStatusPoller({ jobId, onStatus, onResult }: JobStatusPollerProps) {
  const [localStatus, setLocalStatus] = useState<string>("Idle");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setLocalStatus("Idle");
      return;
    }

    let timer: NodeJS.Timeout;

    const poll = async () => {
      const response = await fetch(`/api/proxy/job/${jobId}/status`);
      if (!response.ok) {
        setLocalStatus("Failed to load status");
        return;
      }

      const data = await response.json();
      setLocalStatus(data.status);
      setLastUpdated(new Date().toLocaleTimeString());
      onStatus(data.status);

      if (data.status === "completed" || data.status === "partial") {
        const resultRes = await fetch(`/api/proxy/job/${jobId}/result`);
        if (resultRes.ok) {
          const resultData = await resultRes.json();
          onResult(resultData.result);
        }
      }

      if (data.status === "completed" || data.status === "partial" || data.status === "failed") {
        return;
      }

      timer = setTimeout(poll, POLL_INTERVAL);
    };

    poll();

    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [jobId, onStatus, onResult]);

  const badgeClass =
    localStatus === "completed"
      ? "badge completed"
      : localStatus === "failed"
      ? "badge failed"
      : "badge pending";

  return (
    <div className="inline-row">
      <span className={badgeClass}>{localStatus}</span>
      {lastUpdated && <span className="badge">Updated {lastUpdated}</span>}
    </div>
  );
}
