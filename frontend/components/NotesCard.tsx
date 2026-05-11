"use client";

type NotesCardProps = {
  notes: Record<string, unknown> | null;
};

export default function NotesCard({ notes }: NotesCardProps) {
  if (!notes) {
    return <span className="badge">No notes.</span>;
  }

  return (
    <div className="card">
      <h4>Notes</h4>
      <p>Material: {String(notes.material || "--")}</p>
      <p>Standard: {String(notes.material_standard || "--")}</p>
    </div>
  );
}
