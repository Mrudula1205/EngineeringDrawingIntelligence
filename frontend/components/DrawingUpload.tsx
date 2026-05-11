"use client";

import { useState } from "react";

type DrawingUploadProps = {
  onUploaded: (jobId: string) => void;
};

const MAX_MB = 25;

export default function DrawingUpload({ onUploaded }: DrawingUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) {
      setError("Select a PDF first.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are allowed.");
      return;
    }

    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_MB}MB.`);
      return;
    }

    setError(null);
    setStatus("Uploading...");

    const form = new FormData();
    form.append("file", file);

    const response = await fetch("/api/proxy/upload", {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      setError(payload?.error?.message || "Upload failed.");
      setStatus(null);
      return;
    }

    const data = await response.json();
    setStatus("Uploaded. Job queued.");
    onUploaded(data.job_id);
  };

  return (
    <div className="field">
      <div className="inline-row">
        <input
          className="input"
          type="file"
          accept="application/pdf"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
        <button className="button" onClick={handleUpload}>
          Upload
        </button>
      </div>
      {status && <span className="badge pending">{status}</span>}
      {error && <span className="badge failed">{error}</span>}
    </div>
  );
}
