import { useRef, useState } from "react";
import { uploadDocument } from "../services/api.js";

export default function UploadArea({ onUploaded }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const result = await uploadDocument(file);
      onUploaded(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-md border border-dashed px-4 py-5 text-center transition-colors ${
          dragOver ? "border-pine-600 bg-pine-50" : "border-line hover:border-pine-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">
          {uploading ? "Uploading…" : "Drop a PDF, or click to browse"}
        </p>
      </div>
      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
    </div>
  );
}
