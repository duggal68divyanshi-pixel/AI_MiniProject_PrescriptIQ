import { useState, useEffect, useMemo } from "react";
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
  const [progressStep, setProgressStep] = useState(1);
  const [savedSections, setSavedSections] = useState({}); // { [sectionId]: boolean }
  const [isEditing, setIsEditing] = useState(true);

  // Check saved drafts across all 6 sections on projectId change
  useEffect(() => {
    let active = true;
    async function checkSavedDrafts() {
      if (!projectId) return;
      const statuses = {};
      await Promise.all(
        SECTION_OPTIONS.map(async (opt) => {
          try {
            const saved = await getAuthoringSection(projectId, opt.id);
            if (saved?.content) {
              statuses[opt.id] = true;
            }
          } catch {
            // ignore
          }
        })
      );
      if (active) setSavedSections(statuses);
    }
    checkSavedDrafts();
    return () => { active = false; };
  }, [projectId]);

  // Load saved draft for currently active section
  useEffect(() => {
    let active = true;
    async function loadSavedDraft() {
      if (!projectId) return;
      try {
        const saved = await getAuthoringSection(projectId, sectionType);
        if (active && saved && saved.content) {
          setResult(saved);
        } else if (active) {
          setResult(null);
        }
      } catch {
        if (active) setResult(null);
      }
    }
    loadSavedDraft();
    return () => { active = false; };
  }, [projectId, sectionType]);

  // Progress step animation during generation
  useEffect(() => {
    if (!loading) {
      setProgressStep(1);
      return;
    }
    const t1 = setTimeout(() => setProgressStep(2), 2000);
    const t2 = setTimeout(() => setProgressStep(3), 4500);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [loading]);

  async function handleGenerate(e, forceRefresh = false) {
    e?.preventDefault();
    if (indexedDocuments.length === 0) return;
    setLoading(true);
    setError(null);
    setProgressStep(1);
    try {
      const data = await generateAuthoringSection(projectId, sectionType, customInstructions, forceRefresh);
      setResult(data);
      setSavedSections((prev) => ({ ...prev, [sectionType]: true }));
    } catch (err) {
      setError(err.message || "Failed to generate manuscript section.");
    } finally {
      setLoading(false);
    }
  }

  const wordCount = useMemo(() => {
    if (!result?.content) return 0;
    return result.content.trim().split(/\s+/).filter(Boolean).length;
  }, [result?.content]);

  function handleContentChange(newContent) {
    setResult((prev) => (prev ? { ...prev, content: newContent } : null));
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
    <div className="mx-auto max-w-5xl px-8 py-8">
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold text-ink">AI Paper Authoring Assistant</h2>
        <p className="mt-1 text-xs text-muted">
          Generate publication-ready manuscript sections grounded in your project's indexed literature, extracted entities, and research gaps (Module 8).
        </p>
      </div>

      {/* Section Navigation Tabs */}
      <div className="mb-6 flex flex-wrap gap-1.5 border-b border-line pb-3">
        {SECTION_OPTIONS.map((opt) => {
          const hasDraft = Boolean(savedSections[opt.id]);
          const isActive = sectionType === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => setSectionType(opt.id)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-pine-600 text-white shadow-sm"
                  : "bg-white border border-line text-stone-700 hover:border-pine-400 hover:text-pine-800"
              }`}
            >
              <span>{opt.label}</span>
              {hasDraft && (
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    isActive ? "bg-emerald-300" : "bg-emerald-500"
                  }`}
                  title="Saved draft available"
                />
              )}
            </button>
          );
        })}
      </div>

      <form onSubmit={handleGenerate} className="rounded-lg border border-line bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block font-mono text-[11px] uppercase tracking-wide text-muted mb-1.5">
              Current Manuscript Section:
            </label>
            <select
              value={sectionType}
              onChange={(e) => setSectionType(e.target.value)}
              className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-pine-600"
            >
              {SECTION_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label} {savedSections[opt.id] ? "(✓ draft saved)" : ""}
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
              {loading ? "Drafting Section…" : result ? "Reload Saved Draft" : "Generate Section Draft"}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-xs text-red-800">
          {error}
        </div>
      )}

      {/* Multi-step progress indicator during generation */}
      {loading && (
        <div className="mt-6 rounded-lg border border-pine-200 bg-pine-50/50 p-6">
          <p className="font-mono text-xs uppercase tracking-wider text-pine-800 font-semibold mb-3 text-center">
            Synthesizing Literature &amp; Authoring Manuscript
          </p>
          <div className="flex flex-col gap-2.5 max-w-md mx-auto">
            <div className={`flex items-center gap-2 text-xs ${progressStep >= 1 ? "text-pine-800 font-medium" : "text-muted"}`}>
              <span>{progressStep > 1 ? "✓" : "⏳"}</span>
              <span>Step 1: Ingesting literature matrix findings...</span>
            </div>
            <div className={`flex items-center gap-2 text-xs ${progressStep >= 2 ? "text-pine-800 font-medium" : "text-muted"}`}>
              <span>{progressStep > 2 ? "✓" : progressStep === 2 ? "⏳" : "○"}</span>
              <span>Step 2: Integrating detected gaps &amp; dominant methodologies...</span>
            </div>
            <div className={`flex items-center gap-2 text-xs ${progressStep >= 3 ? "text-pine-800 font-medium" : "text-muted"}`}>
              <span>{progressStep === 3 ? "⏳" : "○"}</span>
              <span>Step 3: Generating publication-quality section draft (up to 4,096 tokens)...</span>
            </div>
          </div>
        </div>
      )}

      {result && !loading && (
        <div className="mt-6 rounded-lg border border-line bg-white p-6 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="rounded bg-pine-100 px-2.5 py-0.5 font-mono text-[11px] uppercase text-pine-800 font-medium">
                {SECTION_OPTIONS.find((s) => s.id === result.section_type)?.label || result.section_type}
              </span>
              <span className="font-mono text-[11px] text-muted">
                Synthesized from {result.papers_analyzed} papers
              </span>
              <span className="rounded-full bg-stone-100 px-2.5 py-0.5 font-mono text-[11px] text-stone-700 font-medium">
                ~{wordCount} words
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsEditing((v) => !v)}
                className="rounded border border-line px-3 py-1.5 font-mono text-xs uppercase text-ink hover:border-pine-400"
              >
                {isEditing ? "Preview" : "Edit"}
              </button>
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

          {/* Editable text area or markdown preview */}
          {isEditing ? (
            <div className="relative">
              <label className="block font-mono text-[10px] uppercase text-muted mb-1">
                Editable Manuscript Draft (Directly edit below before copying/exporting):
              </label>
              <textarea
                value={result.content}
                onChange={(e) => handleContentChange(e.target.value)}
                rows={18}
                className="w-full rounded-md border border-line p-3 font-mono text-xs text-ink leading-relaxed outline-none focus:border-pine-500 bg-stone-50/50"
              />
            </div>
          ) : (
            <div className="prose prose-stone max-w-none text-sm leading-relaxed text-stone-800 bg-stone-50/40 p-4 rounded-md border border-line">
              <pre className="whitespace-pre-wrap font-sans text-sm text-stone-800 leading-relaxed">
                {result.content}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

