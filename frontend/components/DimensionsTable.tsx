"use client";

type DimensionValue = {
  value?: number | null;
  unit?: string | null;
  confidence?: number | null;
};

type ViewDimensions = Record<string, DimensionValue | null>;

type DimensionsTableProps = {
  views: Record<string, ViewDimensions>;
};

function formatDimension(value?: DimensionValue | null) {
  if (!value || value.value === null || value.value === undefined) {
    return "--";
  }

  const unit = value.unit ? ` ${value.unit}` : "";
  return `${value.value}${unit}`;
}

function isAngleDimension(key: string, value?: DimensionValue | null) {
  const normalizedKey = key.toLowerCase();
  const unit = (value?.unit || "").toLowerCase();
  return normalizedKey.includes("angle") || unit === "deg" || unit === "degree" || unit === "degrees" || unit.includes("°");
}

export default function DimensionsTable({ views }: DimensionsTableProps) {
  const entries = Object.entries(views);
  if (entries.length === 0) {
    return <span className="badge">No dimensions extracted.</span>;
  }

  return (
    <div className="card-grid">
      {entries.map(([viewName, values]) => {
        const viewObj = values || {};

        // Order: list all found dimension keys alphabetically
        const keys = Object.keys(viewObj)
          .filter((key) => !isAngleDimension(key, viewObj[key] as DimensionValue | null))
          .sort();

        return (
          <div className="card" key={viewName}>
            <h4>{viewName}</h4>
            {keys.length === 0 && <p>No labeled dimensions found.</p>}
            {keys.map((key) => (
              <p key={key}>
                {key.replace(/_/g, " ")}: {formatDimension(viewObj[key] as DimensionValue | null)}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}
