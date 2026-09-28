import { useState } from "react";
import { searchLiterature, importDiscoveredPaper } from "../../../services/api.js";

export default function DiscoveryTab({ projectId, onPaperImported }) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState(null);
  const [importingIds, setImportingIds] = useState(new Set());
  const [importedIds, setImportedIds] = useState(new Set());
  const [expandedIds, setExpandedIds] = useState(new Set());

  async function handleSearch(e) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await searchLiterature(query.trim(), source, 15);
      setResults(data.papers || []);
      setHasSearched(true);
    } catch (err) {
      setError(err.message || "Failed to fetch scholarly literature");
    } finally {
      setLoading(false);
    }
  }

  async function handleImport(paper) {
    const id = paper.paper_id;
    setImportingIds((prev) => new Set(prev).add(id));
    try {
      await importDiscoveredPaper(projectId, {
        title: paper.title,
        pdf_url: paper.pdf_url,
        paper_url: paper.paper_url,
        authors: paper.authors,
        abstract: paper.abstract,
        publication_year: paper.publication_year,
        venue: paper.venue,
        doi: paper.doi,
        source: paper.source,
      });
      setImportedIds((prev) => new Set(prev).add(id));
      onPaperImported?.();
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    } finally {
      setImportingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  function toggleExpand(id) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      {/* Header & Search Form */}
      <div className="mb-6">
        <h2 className="font-display text-lg text-ink font-semibold">Literature Discovery</h2>
        <p className="text-xs text-muted mt-0.5">
          Search real scholarly preprints and papers across arXiv & Semantic Scholar, then 1-click import them into your research workspace.
        </p>

        <form onSubmit={handleSearch} className="mt-4 flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by topic, research question, title, or author (e.g. 'Transformer attention mechanisms for medical imaging')..."
              className="flex-1 rounded-md border border-line bg-white px-3.5 py-2 text-sm text-ink placeholder:text-muted focus:border-pine-600 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="rounded-md bg-pine-600 px-5 py-2 font-mono text-xs uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-wide text-muted">Source:</span>
            {[
              { id: "all", label: "All Sources" },
              { id: "arxiv", label: "arXiv" },
              { id: "semantic_scholar", label: "Semantic Scholar" },
              { id: "openalex", label: "OpenAlex" },
              { id: "crossref", label: "Crossref" },
            ].map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSource(s.id)}
                className={`rounded px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors ${
                  source === s.id
                    ? "bg-pine-100 text-pine-800 font-medium"
                    : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
          {error}
        </div>
      )}

      {/* Results Section */}
      {loading && (
        <div className="py-12 text-center">
          <p className="font-mono text-xs uppercase tracking-wide text-muted animate-pulse">
            Querying scholarly repositories…
          </p>
        </div>
      )}

      {!loading && hasSearched && results.length === 0 && (
        <div className="rounded-md border border-line bg-white p-8 text-center">
          <p className="text-sm text-muted">No scholarly papers found matching your query.</p>
          <p className="text-xs text-stone-400 mt-1">Try broader research keywords or alternative terms.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
              Found {results.length} relevant publications
            </p>
          </div>

          {results.map((paper) => {
            const isImporting = importingIds.has(paper.paper_id);
            const isImported = importedIds.has(paper.paper_id);
            const isExpanded = expandedIds.has(paper.paper_id);

            return (
              <div
                key={paper.paper_id}
                className="rounded-lg border border-line bg-white p-5 transition-shadow hover:shadow-sm"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-body text-base font-semibold text-ink leading-snug">
                      {paper.title}
                    </h3>
                    
                    {paper.authors && paper.authors.length > 0 && (
                      <p className="mt-1 text-xs text-stone-600">
                        {paper.authors.join(", ")}
                      </p>
                    )}

                    <div className="mt-2.5 flex flex-wrap items-center gap-2">
                      <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-[10px] uppercase text-stone-700">
                        {paper.source}
                      </span>
                      {paper.publication_year && (
                        <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-[10px] text-stone-700">
                          {paper.publication_year}
                        </span>
                      )}
                      {paper.venue && (
                        <span className="truncate max-w-[220px] rounded bg-stone-100 px-2 py-0.5 text-[10px] text-stone-700">
                          {paper.venue}
                        </span>
                      )}
                      {paper.citation_count != null && (
                        <span className="rounded bg-amber-50 border border-amber-200 px-2 py-0.5 font-mono text-[10px] text-amber-800">
                          {paper.citation_count} citations
                        </span>
                      )}
                      {paper.doi && (
                        <span className="font-mono text-[10px] text-stone-500">
                          DOI: {paper.doi}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <button
                      onClick={() => handleImport(paper)}
                      disabled={isImporting || isImported}
                      className={`rounded px-3 py-1.5 font-mono text-xs font-medium uppercase tracking-wider transition-colors ${
                        isImported
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-pine-600 text-white hover:bg-pine-700 disabled:opacity-50"
                      }`}
                    >
                      {isImported ? "✓ In Project" : isImporting ? "Importing…" : "+ Add to Project"}
                    </button>
                    {paper.paper_url && (
                      <a
                        href={paper.paper_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-mono text-[11px] text-pine-700 hover:underline"
                      >
                        View Source ↗
                      </a>
                    )}
                  </div>
                </div>

                {paper.abstract && (
                  <div className="mt-3.5 border-t border-line/60 pt-3">
                    <p className={`text-xs text-stone-600 leading-relaxed ${isExpanded ? "" : "line-clamp-2"}`}>
                      {paper.abstract}
                    </p>
                    {paper.abstract.length > 180 && (
                      <button
                        onClick={() => toggleExpand(paper.paper_id)}
                        className="mt-1 font-mono text-[10px] uppercase tracking-wide text-pine-700 hover:underline"
                      >
                        {isExpanded ? "Show Less ↑" : "Show Full Abstract ↓"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
