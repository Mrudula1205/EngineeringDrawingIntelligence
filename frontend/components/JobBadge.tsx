"use client";

type JobBadgeProps = {
  status: string;
};

export default function JobBadge({ status }: JobBadgeProps) {
  const className = status === "completed" ? "badge completed" : status === "failed" ? "badge failed" : "badge pending";
  return <span className={className}>{status}</span>;
}
