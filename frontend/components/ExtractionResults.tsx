"use client";

import React, { useState } from "react";

import BOMTable from "./BOMTable";
import DimensionsTable from "./DimensionsTable";
import NotesCard from "./NotesCard";
import TitleBlockCard from "./TitleBlockCard";

type ExtractionResultsProps = {
  data: Record<string, unknown> | null;
};

export default function ExtractionResults({ data }: ExtractionResultsProps) {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!data) {
    return <p className="badge">No results yet.</p>;
  }

  const titleBlock = (data.title_block as Record<string, unknown>) || {};
  const notes = (data.notes as Record<string, unknown>) || {};
  const dimensions = (data.dimensions as Record<string, unknown>) || {};
  const views = (dimensions.views as Record<string, unknown>) || {};
  const bom = (data.bom as Record<string, unknown>) || {};
  const bomRows = (bom.rows as Array<Record<string, string | null>>) || [];
  const hasBomRows = bomRows.some((row) =>
    Object.values(row).some((value) => String(value || "").trim().length > 0)
  );

  return (
    <div className="card-grid">
      <TitleBlockCard titleBlock={titleBlock} />
      <NotesCard notes={notes} />
      <div className="card">
        <h4>Dimensions Overview</h4>
        <p>Views: {Object.keys(views).length}</p>
        <p>Unit: {String((data.unit_original as string) || "mm")}</p>
      </div>
      <div className="card">
        <h4>Status</h4>
        <p>Job: {String(data.job_status || "--")}</p>
        <p>Processed: {String(data.processed_at || "--")}</p>
      </div>
      {hasBomRows ? (
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <h4>BOM</h4>
          <BOMTable rows={bomRows} />
        </div>
      ) : null}
      <div className="card" style={{ gridColumn: "1 / -1" }}>
        <h4>Dimensions</h4>
        <DimensionsTable views={views as Record<string, Record<string, { value?: number | null; unit?: string | null; confidence?: number | null } | null>>} />
      </div>
      <div className="card" style={{ gridColumn: "1 / -1" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h4>Raw JSON</h4>
          <button
            className="button secondary"
            onClick={() => setShowRawJson(!showRawJson)}
            style={{ padding: "6px 12px", fontSize: "12px" }}
          >
            {showRawJson ? "Hide" : "Show"}
          </button>
        </div>
        {showRawJson && (
          <pre className="raw-json">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
