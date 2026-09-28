import { useState } from "react";
import { updateProject } from "../../../services/api.js";

export default function OverviewTab({ project, documents, onNavigate, onProjectChanged }) {
  const [editingTopic, setEditingTopic] = useState(false);
  const [desc, setDesc] = useState(project?.description || "");
  const [saving, setSaving] = useState(false);

  if (!project) return null;

  const indexedCount = documents.filter((d) => d.status === "indexed").length;
  const processingCount = documents.filter(
    (d) => !["indexed", "failed"].includes(d.status)
  ).length;
  const failedCount = documents.filter((d) => d.status === "failed").length;

  async function handleSaveTopic(e) {
    e?.preventDefault();
    setSaving(true);
    try {
      await updateProject(project.id, { name: project.name, description: desc });
      setEditingTopic(false);
      onProjectChanged?.();
    } catch (err) {
      alert(`Failed to save topic: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8 space-y-8">
      {/* Workspace Topic & Header */}
      <div className="rounded-xl border border-line bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-pine-700 bg-pine-50 px-2 py-0.5 rounded">
              Active Research Workspace
            </span>
            <h1 className="font-display text-2xl font-bold text-ink mt-1.5">{project.name}</h1>
            
            {!editingTopic ? (
              <div className="mt-2 text-sm text-stone-600 flex items-start gap-2">
                <p className="flex-1 italic">{project.description || "No research question/description added yet. Click edit to set your research context."}</p>
                <button
                  onClick={() => {
                    setDesc(project.description || "");
                    setEditingTopic(true);
                  }}
                  className="font-mono text-[11px] uppercase tracking-wider text-pine-700 hover:underline shrink-0"
                >
                  ✎ Edit Topic
                </button>
              </div>
            ) : (
              <form onSubmit={handleSaveTopic} className="mt-3 space-y-2">
                <textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="Enter your central research question or topic (e.g. 'How do Vision Transformers compare against CNNs for medical image classification?')"
                  className="w-full rounded-md border border-line p-2.5 text-sm text-ink focus:border-pine-600 focus:outline-none"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded bg-pine-600 px-3 py-1.5 font-mono text-xs text-white uppercase hover:bg-pine-700"
                  >
                    {saving ? "Saving…" : "Save Topic"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingTopic(false)}
                    className="rounded border border-line px-3 py-1.5 font-mono text-xs text-muted uppercase hover:bg-stone-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Quick Metrics */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-line/60 pt-5">
          <div className="rounded-lg bg-stone-50 p-3.5 border border-stone-200/60">
            <p className="font-mono text-[10px] uppercase tracking-wide text-muted">Total Papers</p>
            <p className="font-display text-2xl font-bold text-ink mt-0.5">{documents.length}</p>
          </div>
          <div className="rounded-lg bg-emerald-50 p-3.5 border border-emerald-200/60">
            <p className="font-mono text-[10px] uppercase tracking-wide text-emerald-800">Indexed & Searchable</p>
            <p className="font-display text-2xl font-bold text-emerald-900 mt-0.5">{indexedCount}</p>
          </div>
          <div className="rounded-lg bg-amber-50 p-3.5 border border-amber-200/60">
            <p className="font-mono text-[10px] uppercase tracking-wide text-amber-800">In Pipeline</p>
            <p className="font-display text-2xl font-bold text-amber-900 mt-0.5">{processingCount}</p>
          </div>
          <div className="rounded-lg bg-stone-50 p-3.5 border border-stone-200/60">
            <p className="font-mono text-[10px] uppercase tracking-wide text-muted">Failed</p>
            <p className="font-display text-2xl font-bold text-stone-700 mt-0.5">{failedCount}</p>
          </div>
        </div>
      </div>

      {/* Prominent Quick Actions */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-wider text-muted mb-3">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <button
            onClick={() => onNavigate?.("discovery")}
            className="flex flex-col items-start p-4 rounded-lg border border-line bg-white hover:border-pine-400 hover:shadow-sm transition-all text-left group"
          >
            <span className="text-xl mb-1 group-hover:scale-110 transition-transform">🔍</span>
            <span className="font-semibold text-sm text-ink">Discover Literature</span>
            <span className="text-xs text-muted mt-0.5">Search arXiv & Semantic Scholar</span>
          </button>

          <button
            onClick={() => onNavigate?.("papers")}
            className="flex flex-col items-start p-4 rounded-lg border border-line bg-white hover:border-pine-400 hover:shadow-sm transition-all text-left group"
          >
            <span className="text-xl mb-1 group-hover:scale-110 transition-transform">📄</span>
            <span className="font-semibold text-sm text-ink">Upload Papers</span>
            <span className="text-xs text-muted mt-0.5">Ingest & vector-index local PDFs</span>
          </button>

          <button
            onClick={() => onNavigate?.("assistant")}
            className="flex flex-col items-start p-4 rounded-lg border border-line bg-white hover:border-pine-400 hover:shadow-sm transition-all text-left group"
          >
            <span className="text-xl mb-1 group-hover:scale-110 transition-transform">💬</span>
            <span className="font-semibold text-sm text-ink">Research Assistant</span>
            <span className="text-xs text-muted mt-0.5">Ask grounded questions with citations</span>
          </button>

          <button
            onClick={() => onNavigate?.("matrix")}
            className="flex flex-col items-start p-4 rounded-lg border border-line bg-white hover:border-pine-400 hover:shadow-sm transition-all text-left group"
          >
            <span className="text-xl mb-1 group-hover:scale-110 transition-transform">📊</span>
            <span className="font-semibold text-sm text-ink">Literature Matrix</span>
            <span className="text-xs text-muted mt-0.5">Compare methodologies & results</span>
          </button>
        </div>
      </div>

      {/* Recent Papers in this Workspace */}
      <div className="rounded-xl border border-line bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-base font-semibold text-ink">Papers in Collection ({documents.length})</h2>
          <button
            onClick={() => onNavigate?.("papers")}
            className="font-mono text-xs uppercase tracking-wider text-pine-700 hover:underline"
          >
            Manage Library →
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="text-center py-8 bg-stone-50 rounded-lg border border-dashed border-stone-200">
            <p className="text-sm text-muted">No papers added to this workspace yet.</p>
            <div className="mt-3 flex justify-center gap-2">
              <button
                onClick={() => onNavigate?.("discovery")}
                className="rounded bg-pine-600 px-3.5 py-1.5 font-mono text-xs text-white uppercase hover:bg-pine-700"
              >
                Search arXiv / S2
              </button>
              <button
                onClick={() => onNavigate?.("papers")}
                className="rounded border border-line px-3.5 py-1.5 font-mono text-xs text-ink uppercase hover:bg-white"
              >
                Upload PDF
              </button>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-line/60">
            {documents.slice(0, 5).map((doc) => (
              <div key={doc.id} className="py-3 flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="font-body text-sm font-medium text-ink truncate">
                    {doc.metadata?.title || doc.title || doc.filename}
                  </p>
                  <p className="text-xs text-stone-500 font-mono mt-0.5">
                    {doc.status.toUpperCase()} {doc.page_count ? `· ${doc.page_count} pages` : ""} {doc.chunk_count ? `· ${doc.chunk_count} chunks` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => onNavigate?.("intelligence")}
                    className="rounded bg-stone-100 hover:bg-stone-200 px-2.5 py-1 font-mono text-[10px] uppercase text-stone-700"
                  >
                    Analyze
                  </button>
                  <button
                    onClick={() => onNavigate?.("assistant")}
                    className="rounded bg-pine-50 hover:bg-pine-100 px-2.5 py-1 font-mono text-[10px] uppercase text-pine-800"
                  >
                    Query
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Suggested 5-Step Research Workflow */}
      <div className="rounded-xl border border-line bg-pine-50/50 p-6">
        <h3 className="font-mono text-xs uppercase tracking-wider text-pine-900 font-semibold mb-3">
          Recommended Research Workflow
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs text-stone-700">
          <div className="bg-white p-3 rounded-lg border border-pine-200/60">
            <span className="font-bold text-pine-700 block mb-1">1. Discover</span>
            Search real papers via arXiv or Semantic Scholar and import them.
          </div>
          <div className="bg-white p-3 rounded-lg border border-pine-200/60">
            <span className="font-bold text-pine-700 block mb-1">2. Ingest</span>
            Upload PDFs to automatically extract sections and vector embeddings.
          </div>
          <div className="bg-white p-3 rounded-lg border border-pine-200/60">
            <span className="font-bold text-pine-700 block mb-1">3. Understand</span>
            Explore structured objectives, methods, datasets, and models.
          </div>
          <div className="bg-white p-3 rounded-lg border border-pine-200/60">
            <span className="font-bold text-pine-700 block mb-1">4. Matrix</span>
            Review the side-by-side literature matrix and compare findings.
          </div>
          <div className="bg-white p-3 rounded-lg border border-pine-200/60">
            <span className="font-bold text-pine-700 block mb-1">5. Synthesize</span>
            Surface evidence-backed research gaps and investigate with Assistant.
          </div>
        </div>
      </div>
    </div>
  );
}
