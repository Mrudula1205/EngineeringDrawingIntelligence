"use client";

type BOMTableProps = {
  rows: Array<Record<string, string | null>>;
  headers?: string[];
};

const HEADER_MAP: Record<string, string> = {
  item: "ITEM",
  part_number: "PART NO",
  sap_no: "SAP NO",
  code: "CODE",
  code2: "CODE2",
  description: "DESCRIPTION",
  description2: "DESCRIPTION 2",
  quantity: "QTY",
  rev: "REV",
  vendor: "VENDOR",
  vendor2: "VENDOR PART",
  weight: "WEIGHT",
};

const FIELD_ORDER = [
  "item",
  "part_number",
  "sap_no",
  "code",
  "code2",
  "description",
  "description2",
  "quantity",
  "rev",
  "vendor",
  "vendor2",
  "weight",
];

export default function BOMTable({ rows, headers }: BOMTableProps) {
  if (rows.length === 0) {
    return <span className="badge">No BOM rows.</span>;
  }

  const visibleColumns = FIELD_ORDER.filter((field) => {
    return rows.some((row) => row[field] != null);
  });

  return (
    <table className="table">
      <thead>
        <tr>
          {visibleColumns.map((field) => (
            <th key={field}>{HEADER_MAP[field] || field.toUpperCase()}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index}>
            {visibleColumns.map((field) => (
              <td key={field}>{row[field] || "--"}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
