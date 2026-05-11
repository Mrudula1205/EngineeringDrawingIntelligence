"use client";

type ExcelDownloadButtonProps = {
  disabled?: boolean;
};

export default function ExcelDownloadButton({ disabled }: ExcelDownloadButtonProps) {
  const handleDownload = () => {
    window.open("/api/proxy/excel/download", "_blank", "noopener,noreferrer");
  };

  return (
    <button className="button secondary" onClick={handleDownload} disabled={disabled}>
      Download Excel
    </button>
  );
}
