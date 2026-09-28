import { useRef, useState } from "react";
import {
  uploadPaperToProject,
  removePaperFromProject,
  getDocumentCitation,
  getProjectBibtexUrl,
  getProjectRisUrl,
} from "../../../services/api.js";
import StatusTrack from "../../StatusTrack.jsx";

export default function PapersTab({ projectId, documents, onChanged }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [activeCiteDoc, setActiveCiteDoc] = useState(null);
  const [citations, setCitations] = useState(null);
  const [citationFormat, setCitationFormat] = useState("apa");
  const [copied, setCopied] = useState(false);
  const [loadingCitations, setLoadingCitations] = useState(false);

  const [uploadProgress, setUploadProgress] = useState(null); // { current: number, total: number }
  const [skippedNonPdf, setSkippedNonPdf] = useState(0);

  async function handleFiles(fileList) {
    const rawFiles = Array.from(fileList || []);
    const pdfFiles = rawFiles.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const nonPdfs = rawFiles.length - pdfFiles.length;
    setSkippedNonPdf(nonPdfs);

    if (pdfFiles.length === 0) return;

    setUploading(true);
    setErrors([]);
    setUploadProgress({ current: 0, total: pdfFiles.length });

    let completed = 0;
    const failures = [];

    // Upload files concurrently using Promise.allSettled
    const uploadPromises = pdfFiles.map(async (file) => {
      try {
        await uploadPaperToProject(projectId, file);
      } catch (err) {
        failures.push(`${file.name}: ${err.message}`);
      } finally {
        completed += 1;
        setUploadProgress({ current: completed, total: pdfFiles.length });
      }
    });

    await Promise.allSettled(uploadPromises);

    setErrors(failures);
    setUploading(false);
    setUploadProgress(null);
    if (inputRef.current) inputRef.current.value = "";
    onChanged?.();
  }

  async function handleRemove(documentId, filename) {
    const displayName = filename || "this paper";
    if (!window.confirm(`Remove "${displayName}" from this project? This cannot be undone.`)) {
      return;
    }
    await removePaperFromProject(projectId, documentId);
    onChanged?.();
  }

  async function handleOpenCite(doc) {
    setActiveCiteDoc(doc);
    setLoadingCitations(true);
    setCopied(false);
    try {
      const data = await getDocumentCitation(doc.id);
      setCitations(data);
    } catch {
      setCitations(null);
    } finally {
      setLoadingCitations(false);
    }
  }

  function handleCopy() {
    if (!citations || !citations[citationFormat]) return;
    navigator.clipboard.writeText(citations[citationFormat]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const indexedCount = documents.filter((d) => d.status === "indexed").length;
  const processingCount = documents.filter((d) =>
    ["uploaded", "extracting", "chunking", "embedding"].includes(d.status)
  ).length;
  const failedCount = documents.filter((d) => d.status === "failed").length;

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      {/* Top action bar */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg text-ink font-semibold">Project Papers</h2>
        {indexedCount > 0 && (
          <div className="flex gap-2">
            <a
              href={getProjectBibtexUrl(projectId)}
              download
              className="rounded border border-line bg-white px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-pine-700 hover:border-pine-400"
            >
              Export .bib
            </a>
            <a
              href={getProjectRisUrl(projectId)}
              download
              className="rounded border border-line bg-white px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-pine-700 hover:border-pine-400"
            >
              Export .ris
            </a>
          </div>
        )}
      </div>

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
        <p className="font-mono text-xs uppercase tracking-wide text-pine-700 font-medium">
          {uploading
            ? `Uploading ${uploadProgress ? `${uploadProgress.current} of ${uploadProgress.total} papers…` : "…"}`
            : "Drop multiple PDFs, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted">
          Each paper is extracted, chunked, embedded, and indexed independently in parallel.
        </p>

        {uploading && uploadProgress && (
          <div className="mt-3 max-w-xs mx-auto">
            <div className="h-1.5 w-full bg-stone-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-pine-600 transition-all duration-300"
                style={{
                  width: `${Math.round((uploadProgress.current / uploadProgress.total) * 100)}%`,
                }}
              />
            </div>
            <p className="mt-1 text-[11px] font-mono text-muted">
              {Math.round((uploadProgress.current / uploadProgress.total) * 100)}% complete
            </p>
          </div>
        )}
      </div>

      {skippedNonPdf > 0 && (
        <div className="mt-2.5 rounded-md border border-amber-200 bg-amber-50 px-3.5 py-2 text-xs text-amber-800 flex items-center justify-between">
          <span>⚠️ {skippedNonPdf} non-PDF file(s) skipped — only PDF documents are supported.</span>
          <button
            onClick={() => setSkippedNonPdf(0)}
            className="text-amber-900 font-bold ml-2 text-xs"
            title="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {errors.length > 0 && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2">
          {errors.map((e, i) => (
            <p key={i} className="text-xs text-red-800">{e}</p>
          ))}
        </div>
      )}

      {/* Paper Count Summary Bar */}
      {documents.length > 0 && (
        <div className="mt-5 flex flex-wrap items-center gap-2 rounded-md bg-stone-50 border border-line px-4 py-2 text-xs">
          <span className="font-mono uppercase tracking-wider text-muted font-semibold">Summary:</span>
          <span className="font-medium text-pine-800 bg-pine-100/70 px-2 py-0.5 rounded-full">
            {indexedCount} Indexed
          </span>
          {processingCount > 0 && (
            <span className="font-medium text-amber-800 bg-amber-100/70 px-2 py-0.5 rounded-full animate-pulse">
              {processingCount} Processing
            </span>
          )}
          {failedCount > 0 && (
            <span className="font-medium text-red-800 bg-red-100/70 px-2 py-0.5 rounded-full">
              {failedCount} Failed
            </span>
          )}
          <span className="text-muted ml-auto font-mono text-[11px]">
            {documents.length} Total Paper{documents.length === 1 ? "" : "s"}
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2">
        {documents.length === 0 && (
          <p className="text-sm text-muted">No papers in this project yet.</p>
        )}
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center justify-between gap-4 rounded-md border border-line bg-white px-4 py-3 shadow-sm hover:border-pine-200 transition-colors"
          >
            <div className="min-w-0 flex-1">
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
            <div className="flex items-center gap-3 shrink-0">
              {doc.status === "indexed" && (
                <button
                  onClick={() => handleOpenCite(doc)}
                  className="font-mono text-[11px] uppercase text-pine-700 hover:underline"
                >
                  Cite
                </button>
              )}
              <button
                onClick={() => handleRemove(doc.id, doc.metadata?.title || doc.title || doc.filename)}
                className="font-mono text-[11px] uppercase text-muted hover:text-red-700 transition-colors"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>


      {/* Citation Modal */}
      {activeCiteDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-line bg-white p-6 shadow-lg">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-display text-base font-semibold text-ink">Citation Formats</h3>
                <p className="mt-0.5 text-xs text-muted truncate max-w-md">
                  {activeCiteDoc.metadata?.title || activeCiteDoc.title || activeCiteDoc.filename}
                </p>
              </div>
              <button
                onClick={() => setActiveCiteDoc(null)}
                className="text-muted hover:text-ink text-sm"
              >
                ✕
              </button>
            </div>

            {loadingCitations ? (
              <p className="py-8 text-center font-mono text-xs uppercase tracking-wide text-muted">
                Generating citations…
              </p>
            ) : citations ? (
              <div className="mt-4 space-y-4">
                <div className="flex flex-wrap gap-1 border-b border-line pb-2">
                  {["apa", "ieee", "mla", "chicago", "bibtex", "ris"].map((fmt) => (
                    <button
                      key={fmt}
                      onClick={() => setCitationFormat(fmt)}
                      className={`rounded px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider ${
                        citationFormat === fmt
                          ? "bg-pine-600 text-white"
                          : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                      }`}
                    >
                      {fmt}
                    </button>
                  ))}
                </div>

                <div className="rounded border border-line bg-stone-50 p-3">
                  <pre className="whitespace-pre-wrap font-mono text-xs text-stone-800 leading-relaxed">
                    {citations[citationFormat]}
                  </pre>
                </div>

                <div className="flex justify-end gap-2">
                  <button
                    onClick={handleCopy}
                    className="rounded bg-pine-600 px-4 py-1.5 font-mono text-xs uppercase text-white hover:bg-pine-700"
                  >
                    {copied ? "✓ Copied!" : "Copy Citation"}
                  </button>
                </div>
              </div>
            ) : (
              <p className="py-4 text-xs text-red-700">Failed to generate citation for this paper.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
