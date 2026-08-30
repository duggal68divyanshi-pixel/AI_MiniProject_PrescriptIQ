import { useState } from "react";
import { semanticSearch } from "../services/api.js";

export default function SearchPanel({ selectedDocument, onClose }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim() || searching) return;
    setSearching(true);
    setError(null);
    try {
      const response = await semanticSearch(query.trim(), selectedDocument?.id ?? null);
      setResults(response.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="fixed inset-0 z-20 flex items-start justify-center bg-ink/40 px-4 pt-20">
      <div className="w-full max-w-xl rounded-lg border border-line bg-paper shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <p className="font-display text-base text-ink">Semantic search</p>
          <button
            onClick={onClose}
            className="font-mono text-xs uppercase text-muted hover:text-ink"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2 px-5 py-4">
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
            className="rounded-md bg-pine-600 px-3 py-2 text-sm text-paper hover:bg-pine-700 disabled:opacity-50"
          >
            Search
          </button>
        </form>

        {error && <p className="px-5 pb-3 text-sm text-red-700">{error}</p>}

        <div className="max-h-96 overflow-y-auto scrollbar-thin px-5 pb-5">
          {results?.length === 0 && (
            <p className="text-sm text-muted">No matching passages found.</p>
          )}
          <ul className="flex flex-col gap-2">
            {results?.map((r) => (
              <li key={r.chunk_id} className="rounded-md border border-line bg-white px-3 py-2">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-[11px] text-pine-700">
                    {r.document_filename}
                    {r.page_number != null && ` — Page ${r.page_number}`}
                  </p>
                  <span className="font-mono text-[11px] text-muted">
                    {(r.similarity * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">{r.content}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
