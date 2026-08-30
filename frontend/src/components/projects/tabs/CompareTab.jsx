import { useState } from "react";
import { compareProjectPapers } from "../../../services/api.js";

export default function CompareTab({ projectId, indexedDocuments }) {
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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

  return (
    <div className="px-8 py-8">
      <p className="font-display text-xl text-ink">Compare Papers</p>
      <p className="mt-1 text-sm text-muted">Select 2–6 indexed papers to compare side by side.</p>

      <div className="mt-5 flex flex-wrap gap-2">
        {indexedDocuments.length === 0 && (
          <p className="text-sm text-muted">No indexed papers in this project yet.</p>
        )}
        {indexedDocuments.map((doc) => {
          const active = selected.includes(doc.id);
          return (
            <button
              key={doc.id}
              onClick={() => toggle(doc.id)}
              className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                active
                  ? "border-pine-500 bg-pine-50 text-pine-800"
                  : "border-line bg-white text-ink hover:border-pine-300"
              }`}
            >
              {doc.metadata?.title || doc.title || doc.filename}
            </button>
          );
        })}
      </div>

      <button
        onClick={handleCompare}
        disabled={selected.length < 2 || loading}
        className="mt-5 rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Comparing…" : `Compare (${selected.length} selected)`}
      </button>
      {selected.length === 1 && (
        <p className="mt-2 text-xs text-muted">Select at least one more paper to compare.</p>
      )}

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 overflow-x-auto rounded-md border border-line">
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
                <tr key={dim.dimension} className="border-b border-line align-top">
                  <td className="px-4 py-3 font-medium text-ink">{dim.dimension}</td>
                  {result.documents.map((doc) => (
                    <td key={doc.id} className="px-4 py-3 text-ink">
                      {dim.values[doc.id]}
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
      )}
    </div>
  );
}
