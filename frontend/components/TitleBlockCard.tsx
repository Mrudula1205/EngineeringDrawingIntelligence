"use client";

type TitleBlockCardProps = {
  titleBlock: Record<string, unknown> | null;
};

export default function TitleBlockCard({ titleBlock }: TitleBlockCardProps) {
  if (!titleBlock) {
    return <span className="badge">No title block.</span>;
  }

  return (
    <div className="card">
      <h4>Title Block</h4>
      <p>Drawing: {String(titleBlock.drawing_number || "--")}</p>
      <p>Title: {String(titleBlock.title || "--")}</p>
      <p>Company: {String(titleBlock.company || "--")}</p>
      <p>Revision: {String(titleBlock.revision || "--")}</p>
    </div>
  );
}
