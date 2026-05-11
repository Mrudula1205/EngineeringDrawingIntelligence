"use client";

type BOMTableProps = {
  rows: Array<Record<string, string | null>>;
};

export default function BOMTable({ rows }: BOMTableProps) {
  if (rows.length === 0) {
    return <span className="badge">No BOM rows.</span>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Part</th>
          <th>Description</th>
          <th>Qty</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index}>
            <td>{row.part_number || "--"}</td>
            <td>{row.description || "--"}</td>
            <td>{row.quantity || "--"}</td>
            <td>{row.notes || "--"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
