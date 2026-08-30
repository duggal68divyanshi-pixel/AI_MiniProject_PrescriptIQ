import StatusTrack from "./StatusTrack.jsx";
import UploadArea from "./UploadArea.jsx";

export default function Sidebar({
  documents,
  selectedId,
  onSelect,
  onUploaded,
  loading,
}) {
  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-r border-line bg-paper">
      <div className="border-b border-line px-5 py-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-pine-600">
          Research Nexus
        </p>
        <h1 className="font-display text-lg font-semibold leading-tight text-ink">
          Intelligence Core
        </h1>
      </div>

      <div className="border-b border-line px-5 py-4">
        <UploadArea onUploaded={onUploaded} />
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
        <p className="px-2 pb-2 font-mono text-[11px] uppercase tracking-wide text-muted">
          Documents {documents.length > 0 && `(${documents.length})`}
        </p>

        {loading && (
          <p className="px-2 py-4 text-sm text-muted">Loading documents…</p>
        )}

        {!loading && documents.length === 0 && (
          <p className="px-2 py-4 text-sm text-muted">
            No papers yet. Upload a PDF to begin.
          </p>
        )}

        <ul className="flex flex-col gap-1">
          {documents.map((doc) => {
            const active = doc.id === selectedId;
            return (
              <li key={doc.id}>
                <button
                  onClick={() => onSelect(doc.id)}
                  className={`w-full rounded-md px-3 py-2.5 text-left transition-colors ${
                    active
                      ? "bg-pine-100 ring-1 ring-pine-400"
                      : "hover:bg-pine-50"
                  }`}
                >
                  <p className="truncate font-body text-sm font-medium text-ink">
                    {doc.title || doc.filename}
                  </p>
                  <p className="mt-0.5 truncate font-mono text-[11px] text-muted">
                    {doc.filename}
                  </p>
                  <div className="mt-2">
                    <StatusTrack status={doc.status} />
                  </div>
                  {doc.status === "indexed" && (
                    <p className="mt-1 font-mono text-[11px] text-muted">
                      {doc.page_count ?? "?"} pages · {doc.chunk_count ?? "?"} chunks
                    </p>
                  )}
                  {doc.status === "failed" && doc.error_message && (
                    <p className="mt-1 text-[11px] text-red-700 line-clamp-2">
                      {doc.error_message}
                    </p>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
