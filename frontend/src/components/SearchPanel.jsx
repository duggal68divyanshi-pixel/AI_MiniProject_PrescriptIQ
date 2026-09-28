import { useState } from "react";
import { semanticSearch } from "../services/api.js";

export default function SearchPanel({ selectedDocument, documents = [], onClose }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [searchTimeMs, setSearchTimeMs] = useState(null);
  const [topK, setTopK] = useState(5);
  const [selectedDocId, setSelectedDocId] = useState(selectedDocument?.id ?? "all");

  // Deduplicate documents list if needed
  const docList = documents.length > 0 ? documents : (selectedDocument ? [selectedDocument] : []);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim() || searching) return;
    setSearching(true);
    setError(null);
    const startTime = performance.now();
    try {
      const docId = selectedDocId === "all" ? null : selectedDocId;
      const response = await semanticSearch(query.trim(), docId, topK);
      const elapsed = Math.round(performance.now() - startTime);
      setSearchTimeMs(elapsed);
      setResults(response.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="fixed inset-0 z-20 flex items-start justify-center bg-ink/40 px-4 pt-20">
      <div className="w-full max-w-2xl rounded-lg border border-line bg-paper shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <p className="font-display text-base text-ink">Semantic search</p>
          <button
            onClick={onClose}
            className="font-mono text-xs uppercase text-muted hover:text-ink"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex flex-col gap-3 px-5 py-4">
          <div className="flex gap-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. methods for improving model performance"
              className="flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm outline-none focus:border-pine-400"
            />
            <button
              type="submit"
              disabled={searching}
              className="rounded-md bg-pine-600 px-4 py-2 text-sm text-paper hover:bg-pine-700 disabled:opacity-50"
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <label htmlFor="search-doc-scope" className="font-mono text-muted">
                Scope:
              </label>
              <select
                id="search-doc-scope"
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="rounded border border-line bg-white px-2 py-1 text-xs text-ink outline-none focus:border-pine-400"
              >
                <option value="all">All Documents</option>
                {docList.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="font-mono text-muted">Top results:</span>
              {[5, 10, 20].map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setTopK(k)}
                  className={`rounded px-2 py-0.5 font-mono text-xs transition-colors ${
                    topK === k
                      ? "bg-pine-600 text-paper"
                      : "border border-line bg-white text-muted hover:border-pine-400 hover:text-ink"
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
          </div>
        </form>

        {error && <p className="px-5 pb-3 text-sm text-red-700">{error}</p>}

        {results !== null && (
          <div className="flex items-center justify-between border-b border-line/60 px-5 pb-2 font-mono text-xs text-muted">
            <span>
              {results.length} result{results.length === 1 ? "" : "s"} found
            </span>
            {searchTimeMs !== null && <span>in {searchTimeMs}ms</span>}
          </div>
        )}

        <div className="max-h-96 overflow-y-auto scrollbar-thin px-5 py-3">
          {results?.length === 0 && (
            <p className="py-4 text-center text-sm text-muted">No matching passages found.</p>
          )}
          <ul className="flex flex-col gap-2">
            {results?.map((r) => (
              <li key={r.chunk_id} className="rounded-md border border-line bg-white px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-[11px] font-medium text-pine-700">
                    {r.document_filename}
                    {r.page_number != null && ` — Page ${r.page_number}`}
                  </p>
                  <span className="rounded bg-pine-50 px-1.5 py-0.5 font-mono text-[11px] font-medium text-pine-800">
                    {(r.similarity * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{r.content}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
