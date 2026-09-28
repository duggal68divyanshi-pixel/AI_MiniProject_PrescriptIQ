import { useState, useMemo } from "react";
import { compareProjectPapers } from "../../../services/api.js";

export default function CompareTab({ projectId, indexedDocuments }) {
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchPaperQuery, setSearchPaperQuery] = useState("");
  const [showSources, setShowSources] = useState(false);

  // Sort alphabetically by title/filename and apply search filter
  const sortedAndFilteredDocs = useMemo(() => {
    let list = [...indexedDocuments].sort((a, b) => {
      const nameA = a.metadata?.title || a.title || a.filename || "";
      const nameB = b.metadata?.title || b.title || b.filename || "";
      return nameA.localeCompare(nameB);
    });
    if (searchPaperQuery.trim()) {
      const q = searchPaperQuery.toLowerCase();
      list = list.filter((d) => {
        const name = (d.metadata?.title || d.title || d.filename || "").toLowerCase();
        return name.includes(q);
      });
    }
    return list;
  }, [indexedDocuments, searchPaperQuery]);

  function toggle(id) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length >= 6 ? prev : [...prev, id]
    );
  }

  async function handleCompare() {
    if (selected.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const response = await compareProjectPapers(projectId, selected);
      setResult(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function exportCSV() {
    if (!result?.dimensions?.length) return;
    const headers = [
      "Dimension",
      ...result.documents.map((d) => `"${(d.title || d.filename).replace(/"/g, '""')}"`),
    ];
    const rows = result.dimensions.map((dim) => [
      `"${dim.dimension.replace(/"/g, '""')}"`,
      ...result.documents.map(
        (d) => `"${(dim.values[String(d.id)] ?? "Not reported").replace(/"/g, '""')}"`
      ),
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "paper_comparison.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function exportMarkdownReport() {
    if (!result?.dimensions?.length) return;
    let md = "# Multi-Paper Comparison Report\n\n";
    md += `*Comparing ${result.documents.length} papers across key dimensions*\n\n`;
    md += `| Dimension | ${result.documents.map((d) => d.title || d.filename).join(" | ")} |\n`;
    md += `| ${"-".repeat(10)} | ${result.documents.map(() => "---").join(" | ")} |\n`;
    result.dimensions.forEach((dim) => {
      const vals = result.documents.map((d) =>
        (dim.values[String(d.id)] ?? "Not reported").replace(/\n/g, " ")
      );
      md += `| **${dim.dimension}** | ${vals.join(" | ")} |\n`;
    });

    if (result.sources?.length) {
      md += "\n## Grounding Evidence & Sources\n\n";
      result.sources.forEach((s) => {
        md += `- **${s.document || s.document_filename}** (Page ${s.page || s.page_number || "n/a"}): ${s.excerpt || s.content}\n`;
      });
    }

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "paper_comparison.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  function renderDimensionValue(val) {
    if (
      !val ||
      val.toLowerCase().includes("not reported in the indexed text") ||
      val.toLowerCase() === "not reported"
    ) {
      return (
        <span className="italic text-xs text-stone-400 select-none">
          Not reported in indexed text
        </span>
      );
    }
    return val;
  }

  return (
    <div className="px-8 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-xl text-ink">Compare Papers</p>
          <p className="mt-1 text-sm text-muted">
            Select 2–6 indexed papers to compare side by side across methodology, datasets, and outcomes.
          </p>
        </div>
        {result && (
          <div className="flex gap-2">
            <button
              onClick={exportCSV}
              className="rounded-md border border-line bg-white px-3 py-1.5 font-mono text-xs uppercase text-pine-700 hover:border-pine-400"
            >
              Export CSV
            </button>
            <button
              onClick={exportMarkdownReport}
              className="rounded-md border border-line bg-white px-3 py-1.5 font-mono text-xs uppercase text-pine-700 hover:border-pine-400"
            >
              Export Report (.md)
            </button>
          </div>
        )}
      </div>

      {/* Paper selection filter & status */}
      <div className="mt-5">
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <input
            type="text"
            value={searchPaperQuery}
            onChange={(e) => setSearchPaperQuery(e.target.value)}
            placeholder="Search papers to compare..."
            className="w-full max-w-xs rounded-md border border-line bg-white px-3 py-1.5 text-xs text-ink outline-none placeholder:text-muted focus:border-pine-400"
          />
          <div className="flex items-center gap-2">
            {selected.length >= 6 && (
              <span className="font-mono text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                Maximum 6 papers reached
              </span>
            )}
            <span className="font-mono text-xs text-muted">
              {selected.length}/6 selected
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-1 border border-line/60 rounded-md bg-stone-50/50">
          {indexedDocuments.length === 0 && (
            <p className="p-3 text-sm text-muted">No indexed papers in this project yet.</p>
          )}
          {sortedAndFilteredDocs.map((doc) => {
            const active = selected.includes(doc.id);
            return (
              <button
                key={doc.id}
                onClick={() => toggle(doc.id)}
                className={`rounded-md border px-3 py-1.5 text-left text-xs transition-colors ${
                  active
                    ? "border-pine-500 bg-pine-50 text-pine-800 font-medium shadow-sm"
                    : "border-line bg-white text-ink hover:border-pine-300"
                }`}
              >
                {active ? "✓ " : ""}{doc.metadata?.title || doc.title || doc.filename}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleCompare}
          disabled={selected.length < 2 || loading}
          className="rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Comparing…" : `Compare (${selected.length} selected)`}
        </button>
        {selected.length === 1 && (
          <p className="text-xs text-muted">Select at least one more paper to compare.</p>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6">
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="min-w-[900px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-line bg-pine-50">
                  <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-pine-800">
                    Dimension
                  </th>
                  {result.documents.map((doc) => (
                    <th
                      key={doc.id}
                      className="min-w-[220px] px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-pine-800"
                    >
                      {doc.title || doc.filename}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.dimensions.map((dim) => (
                  <tr key={dim.dimension} className="border-b border-line align-top hover:bg-stone-50/50">
                    <td className="px-4 py-3 font-medium text-ink bg-stone-50/30">{dim.dimension}</td>
                    {result.documents.map((doc) => (
                      <td key={doc.id} className="px-4 py-3 text-ink leading-relaxed">
                        {renderDimensionValue(dim.values[String(doc.id)])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {result.cached && (
              <p className="border-t border-line bg-paper px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-muted">
                Showing a cached comparison for this exact paper set
              </p>
            )}
          </div>

          {/* Collapsible Grounding Evidence Panel */}
          {result.sources && result.sources.length > 0 && (
            <div className="mt-4 rounded-md border border-line bg-white shadow-sm">
              <button
                onClick={() => setShowSources((v) => !v)}
                className="flex w-full items-center justify-between p-3.5 text-left font-mono text-xs uppercase tracking-wider text-pine-800 font-semibold hover:bg-stone-50"
              >
                <span>Grounding Evidence &amp; Literature Sources ({result.sources.length})</span>
                <span>{showSources ? "▴" : "▾"}</span>
              </button>
              {showSources && (
                <ul className="border-t border-line p-4 flex flex-col gap-3">
                  {result.sources.map((s, idx) => (
                    <li key={idx} className="text-xs text-stone-700">
                      <span className="font-semibold text-pine-700">
                        {s.document || s.document_filename}
                      </span>
                      {(s.page || s.page_number) != null && (
                        <span className="text-muted"> — Page {s.page || s.page_number}</span>
                      )}
                      {s.similarity != null && (
                        <span className="ml-2 font-mono text-[10px] text-muted">
                          ({(s.similarity * 100).toFixed(0)}% match)
                        </span>
                      )}
                      {(s.excerpt || s.content) && (
                        <p className="mt-1 border-l-2 border-pine-300 pl-2.5 italic text-stone-600 bg-stone-50/70 py-1.5 rounded-r">
                          "{s.excerpt || s.content}"
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

