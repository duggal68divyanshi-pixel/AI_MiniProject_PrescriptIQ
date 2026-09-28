import { useState, useEffect } from "react";
import { generateAuthoringSection, getAuthoringSection } from "../../../services/api.js";

const SECTION_OPTIONS = [
  { id: "abstract", label: "Abstract", desc: "Structured 250-word paper summary" },
  { id: "introduction", label: "Introduction", desc: "Problem domain, significance, and contribution overview" },
  { id: "related_work", label: "Related Work / Literature Review", desc: "Theme-grouped literature review with citations" },
  { id: "methodology_comparison", label: "Methodology Comparison", desc: "Technical trade-offs and paradigm comparison" },
  { id: "research_gaps", label: "Research Gaps & Motivation", desc: "Literature limitations & research question formulation" },
  { id: "conclusion", label: "Conclusion & Future Work", desc: "Synthesis of research outcomes and next steps" },
];

export default function AuthoringTab({ projectId, indexedDocuments }) {
  const [sectionType, setSectionType] = useState("related_work");
  const [customInstructions, setCustomInstructions] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadSavedDraft() {
      if (!projectId) return;
      try {
        const saved = await getAuthoringSection(projectId, sectionType);
        if (active && saved && saved.content) {
          setResult(saved);
        }
      } catch {
        // No saved draft yet for this section
      }
    }
    loadSavedDraft();
    return () => { active = false; };
  }, [projectId, sectionType]);

  async function handleGenerate(e, forceRefresh = false) {
    e?.preventDefault();
    if (indexedDocuments.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await generateAuthoringSection(projectId, sectionType, customInstructions, forceRefresh);
      setResult(data);
    } catch (err) {
      setError(err.message || "Failed to generate manuscript section.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!result?.content) return;
    navigator.clipboard.writeText(result.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleExportMd() {
    if (!result?.content) return;
    const blob = new Blob([result.content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `manuscript_${sectionType}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold text-ink">AI Paper Authoring Assistant</h2>
        <p className="mt-1 text-xs text-muted">
          Generate publication-ready manuscript sections grounded in your project's indexed literature, extracted entities, and research gaps (Module 8).
        </p>
      </div>

      <form onSubmit={handleGenerate} className="rounded-lg border border-line bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block font-mono text-[11px] uppercase tracking-wide text-muted mb-1.5">
              Manuscript Section:
            </label>
            <select
              value={sectionType}
              onChange={(e) => setSectionType(e.target.value)}
              className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-pine-600"
            >
              {SECTION_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-stone-500">
              {SECTION_OPTIONS.find((s) => s.id === sectionType)?.desc}
            </p>
          </div>

          <div>
            <label className="block font-mono text-[11px] uppercase tracking-wide text-muted mb-1.5">
              Custom Focus / Instructions (Optional):
            </label>
            <input
              type="text"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. Focus on deep learning architectures vs classical SVMs..."
              className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-stone-400 outline-none focus:border-pine-600"
            />
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-line/60 pt-4">
          <p className="font-mono text-[11px] text-muted">
            Analyzing {indexedDocuments.length} indexed paper(s) in project context
          </p>
          <div className="flex gap-2">
            {result && !loading && (
              <button
                type="button"
                onClick={(e) => handleGenerate(e, true)}
                disabled={loading || indexedDocuments.length === 0}
                className="rounded-md border border-line px-4 py-2 font-mono text-xs uppercase tracking-wider text-ink hover:border-pine-400 disabled:opacity-50"
              >
                Regenerate Fresh
              </button>
            )}
            <button
              type="button"
              onClick={(e) => handleGenerate(e, false)}
              disabled={loading || indexedDocuments.length === 0}
              className="rounded-md bg-pine-600 px-6 py-2 font-mono text-xs uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Drafting Section…" : result ? "Load Draft" : "Generate Section Draft"}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-xs text-red-800">
          {error}
        </div>
      )}

      {loading && (
        <div className="py-12 text-center">
          <p className="font-mono text-xs uppercase tracking-wider text-pine-700 animate-pulse">
            Synthesizing literature context & drafting manuscript section…
          </p>
        </div>
      )}

      {result && !loading && (
        <div className="mt-6 rounded-lg border border-line bg-white p-6 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
            <div>
              <span className="rounded bg-pine-100 px-2.5 py-0.5 font-mono text-[11px] uppercase text-pine-800 font-medium">
                {SECTION_OPTIONS.find((s) => s.id === result.section_type)?.label || result.section_type}
              </span>
              <span className="ml-2 font-mono text-[11px] text-muted">
                Synthesized from {result.papers_analyzed} papers
              </span>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleCopy}
                className="rounded border border-line px-3 py-1.5 font-mono text-xs uppercase text-pine-700 hover:border-pine-400"
              >
                {copied ? "✓ Copied!" : "Copy Text"}
              </button>
              <button
                onClick={handleExportMd}
                className="rounded bg-pine-600 px-3 py-1.5 font-mono text-xs uppercase text-white hover:bg-pine-700"
              >
                Export .md Draft
              </button>
            </div>
          </div>

          <div className="prose prose-stone max-w-none text-sm leading-relaxed text-stone-800">
            <pre className="whitespace-pre-wrap font-sans text-sm text-stone-800 leading-relaxed">
              {result.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
