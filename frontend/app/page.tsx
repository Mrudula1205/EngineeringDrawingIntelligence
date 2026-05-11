"use client";

import { useCallback, useState } from "react";

import ChatInterface from "../components/ChatInterface";
import DrawingUpload from "../components/DrawingUpload";
import ExcelDownloadButton from "../components/ExcelDownloadButton";
import ExtractionResults from "../components/ExtractionResults";
import JobStatusPoller from "../components/JobStatusPoller";

export default function HomePage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const handleStatus = useCallback((nextStatus: string) => {
    setStatus(nextStatus);
  }, []);

  const handleResult = useCallback((data: Record<string, unknown>) => {
    setResult(data);
  }, []);

  return (
    <div className="dashboard">
      <section className="panel">
        <div className="panel-header">
          <h1>Upload drawing</h1>
          <p>Send a CAD-exported PDF. We will extract metadata, BOM, and dimensions.</p>
        </div>
        <DrawingUpload
          onUploaded={(id) => {
            setJobId(id);
            setStatus("pending");
            setResult(null);
          }}
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Job status</h2>
          <p>We will poll until the extraction completes.</p>
        </div>
        <JobStatusPoller
          jobId={jobId}
          onStatus={handleStatus}
          onResult={handleResult}
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Extraction results</h2>
          <p>Structured output from the pipeline.</p>
        </div>
        <ExtractionResults data={result} />
      </section>

      <section className="panel panel-split">
        <div>
          <div className="panel-header">
            <h2>Chat with the drawing</h2>
            <p>Ask questions using the extracted data.</p>
          </div>
          <ChatInterface jobId={jobId} disabled={status === "failed" || !result} />
        </div>
        <div className="panel-aside">
          <div className="panel-header">
            <h3>Exports</h3>
            <p>Download Excel after extractions complete.</p>
          </div>
          <ExcelDownloadButton disabled={!result} />
        </div>
      </section>
    </div>
  );
}
