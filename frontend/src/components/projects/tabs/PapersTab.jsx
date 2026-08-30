import { useRef, useState } from "react";
import { uploadPaperToProject, removePaperFromProject } from "../../../services/api.js";
import StatusTrack from "../../StatusTrack.jsx";

export default function PapersTab({ projectId, documents, onChanged }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState([]);
  const [dragOver, setDragOver] = useState(false);

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (files.length === 0) return;
    setUploading(true);
    setErrors([]);
    const failures = [];
    for (const file of files) {
      try {
        // Sequential on purpose: each call kicks off a background pipeline
        // job server-side, so this just needs to register all of them —
        // parallelizing the HTTP calls wouldn't meaningfully speed up
        // extraction/embedding, which happens in the background anyway.
        await uploadPaperToProject(projectId, file);
      } catch (err) {
        failures.push(`${file.name}: ${err.message}`);
      }
    }
    setErrors(failures);
    setUploading(false);
    if (inputRef.current) inputRef.current.value = "";
    onChanged?.();
  }

  async function handleRemove(documentId) {
    await removePaperFromProject(projectId, documentId);
    onChanged?.();
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-md border border-dashed px-6 py-8 text-center transition-colors ${
          dragOver ? "border-pine-600 bg-pine-50" : "border-line hover:border-pine-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <p className="font-mono text-xs uppercase tracking-wide text-pine-700">
          {uploading ? "Uploading…" : "Drop multiple PDFs, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted">Each paper is extracted, chunked, embedded, and indexed independently.</p>
      </div>

      {errors.length > 0 && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2">
          {errors.map((e, i) => (
            <p key={i} className="text-xs text-red-800">{e}</p>
          ))}
        </div>
      )}

      <div className="mt-6 flex flex-col gap-2">
        {documents.length === 0 && (
          <p className="text-sm text-muted">No papers in this project yet.</p>
        )}
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center justify-between gap-4 rounded-md border border-line bg-white px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate font-body text-sm font-medium text-ink">
                {doc.metadata?.title || doc.title || doc.filename}
              </p>
              <p className="truncate font-mono text-[11px] text-muted">{doc.filename}</p>
              <div className="mt-1.5">
                <StatusTrack status={doc.status} />
              </div>
              {doc.status === "failed" && doc.error_message && (
                <p className="mt-1 text-[11px] text-red-700">{doc.error_message}</p>
              )}
            </div>
            <button
              onClick={() => handleRemove(doc.id)}
              className="shrink-0 font-mono text-[11px] uppercase text-muted hover:text-red-700"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
