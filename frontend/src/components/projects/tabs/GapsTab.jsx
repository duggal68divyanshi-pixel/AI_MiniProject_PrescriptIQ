import { useState, useMemo } from "react";
import { runGapAnalysis, generateResearchQuestions } from "../../../services/api.js";

const CATEGORY_LABELS = {
  repeated_limitation: "Repeated Limitation",
  underexplored_area: "Underexplored Area",
  methodological: "Methodological Gap",
  dataset: "Dataset Gap",
  evaluation: "Evaluation Gap",
  contradiction: "Contradiction",
};

const STRENGTH_STYLES = {
  High: "bg-pine-100 text-pine-800",
  Medium: "bg-amber-100 text-amber-800",
  Low: "bg-line text-muted",
};

const STRENGTH_ORDER = { High: 3, Medium: 2, Low: 1 };

export default function GapsTab({ projectId, indexedDocuments }) {
  const [gaps, setGaps] = useState(null);
  const [questionSets, setQuestionSets] = useState(null);
  const [loadingGaps, setLoadingGaps] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [error, setError] = useState(null);

  // New feature states
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [sortBy, setSortBy] = useState("strength"); // 'strength' | 'category'
  const [dismissedGapIds, setDismissedGapIds] = useState([]);
  const [showDismissed, setShowDismissed] = useState(false);
  const [expandedQuestions, setExpandedQuestions] = useState({}); // gapId -> boolean

  async function handleAnalyze(forceRefresh = false) {
    setLoadingGaps(true);
    setError(null);
    setQuestionSets(null);
    setDismissedGapIds([]);
    try {
      const result = await runGapAnalysis(projectId, forceRefresh);
      setGaps(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingGaps(false);
    }
  }

  async function handleGenerateQuestions() {
    setLoadingQuestions(true);
    setError(null);
    try {
      const result = await generateResearchQuestions(projectId);
      setQuestionSets(result.question_sets);
      // Auto-expand all matching questions
      const exp = {};
      result.question_sets?.forEach((qs) => {
        if (qs.gap_id) exp[qs.gap_id] = true;
      });
      setExpandedQuestions(exp);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingQuestions(false);
    }
  }

  function handleDismiss(gapId) {
    setDismissedGapIds((prev) => (prev.includes(gapId) ? prev : [...prev, gapId]));
  }

  function handleRestore(gapId) {
    setDismissedGapIds((prev) => prev.filter((id) => id !== gapId));
  }

  function handleRestoreAll() {
    setDismissedGapIds([]);
  }

  function toggleQuestions(gapId) {
    setExpandedQuestions((prev) => ({ ...prev, [gapId]: !prev[gapId] }));
  }

  // Categories present in the dataset with counts
  const categoryCounts = useMemo(() => {
    if (!gaps?.gaps) return {};
    const counts = { all: gaps.gaps.length };
    gaps.gaps.forEach((g) => {
      counts[g.category] = (counts[g.category] || 0) + 1;
    });
    return counts;
  }, [gaps]);

  // Filtered & sorted gaps
  const processedGaps = useMemo(() => {
    if (!gaps?.gaps) return [];
    let list = [...gaps.gaps];

    // Filter category
    if (selectedCategory !== "all") {
      list = list.filter((g) => g.category === selectedCategory);
    }

    // Sort
    if (sortBy === "strength") {
      list.sort((a, b) => (STRENGTH_ORDER[b.evidence_strength] || 0) - (STRENGTH_ORDER[a.evidence_strength] || 0));
    } else if (sortBy === "category") {
      list.sort((a, b) => (a.category || "").localeCompare(b.category || ""));
    }

    return list;
  }, [gaps, selectedCategory, sortBy]);

  const activeGaps = useMemo(() => {
    return processedGaps.filter((g) => !dismissedGapIds.includes(g.id));
  }, [processedGaps, dismissedGapIds]);

  const dismissedGapsList = useMemo(() => {
    return processedGaps.filter((g) => dismissedGapIds.includes(g.id));
  }, [processedGaps, dismissedGapIds]);

  function exportMarkdownReport() {
    if (!gaps || !gaps.gaps.length) return;
    let md = "# Research Gap Analysis Report\n\n";
    md += `*Analyzed ${gaps.papers_analyzed} paper(s)*\n\n`;
    activeGaps.forEach((g, i) => {
      md += `## Gap ${i + 1}: ${g.gap}\n\n`;
      md += `- **Category**: ${CATEGORY_LABELS[g.category] || g.category}\n`;
      md += `- **Evidence Strength**: ${g.evidence_strength}\n`;
      md += `- **Affected Papers**: ${g.affected_papers.join(", ")}\n`;
      if (g.why_it_matters) md += `- **Why It Matters**: ${g.why_it_matters}\n`;
      if (g.potential_direction) md += `- **Potential Research Direction**: ${g.potential_direction}\n`;
      if (g.evidence?.length) {
        md += `- **Supporting Evidence Passages**:\n`;
        g.evidence.forEach((e) => {
          md += `  - ${e.document}${e.page != null ? ` (Page ${e.page})` : ""}\n`;
          if (e.excerpt) md += `    > "${e.excerpt}"\n`;
        });
      }

      const matchingQs = questionSets?.find(
        (qs) => qs.gap_id === g.id || qs.gap?.toLowerCase().trim() === g.gap?.toLowerCase().trim()
      );
      if (matchingQs?.questions?.length) {
        md += `- **Candidate Research Questions**:\n`;
        matchingQs.questions.forEach((q, idx) => {
          md += `  - RQ${idx + 1}: ${q}\n`;
        });
      }
      md += "\n";
    });
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "research_gap_analysis.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  const canAnalyze = indexedDocuments.length >= 2;

  return (
    <div className="px-8 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-xl text-ink">Research Gap Analysis</p>
          <p className="mt-1 text-sm text-muted">
            Every gap below is tied to specific papers already indexed in this project — nothing here is invented.
          </p>
        </div>
        {gaps && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleGenerateQuestions}
              disabled={loadingQuestions || gaps.gaps.length === 0}
              className="rounded-md border border-pine-500 bg-white px-3 py-1.5 text-xs font-medium text-pine-700 hover:bg-pine-50 disabled:opacity-50 font-mono uppercase"
            >
              {loadingQuestions ? "Generating RQs…" : "Generate Research Questions"}
            </button>
            <button
              onClick={exportMarkdownReport}
              className="rounded-md border border-line bg-white px-3 py-1.5 text-xs text-pine-700 hover:border-pine-400 font-mono uppercase"
            >
              Export Report (.md)
            </button>
            <button
              onClick={() => handleAnalyze(true)}
              disabled={loadingGaps}
              className="rounded-md border border-line px-3 py-1.5 text-xs text-ink hover:border-pine-400 font-mono uppercase"
            >
              Re-run fresh
            </button>
          </div>
        )}
      </div>

      {!canAnalyze && (
        <p className="mt-4 text-sm text-muted">
          Needs at least 2 indexed papers ({indexedDocuments.length} currently indexed).
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          onClick={() => handleAnalyze(false)}
          disabled={!canAnalyze || loadingGaps}
          className="rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loadingGaps ? "Analyzing…" : gaps ? "Refresh Gaps" : "Analyze Research Gaps"}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loadingGaps && (
        <p className="mt-4 text-sm text-muted animate-pulse">
          Collecting structured findings, limitations, methods and datasets across papers, then
          synthesizing evidence-backed gaps…
        </p>
      )}

      {gaps && (
        <>
          {/* Controls Bar: Category Pills & Sorting */}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
            {/* Category Filter Pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted mr-1">Category:</span>
              <button
                onClick={() => setSelectedCategory("all")}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  selectedCategory === "all"
                    ? "bg-pine-600 text-white"
                    : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                }`}
              >
                All ({categoryCounts.all || 0})
              </button>
              {Object.entries(CATEGORY_LABELS).map(([catKey, catLabel]) => {
                const count = categoryCounts[catKey];
                if (!count) return null;
                return (
                  <button
                    key={catKey}
                    onClick={() => setSelectedCategory(catKey)}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                      selectedCategory === catKey
                        ? "bg-pine-600 text-white"
                        : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                    }`}
                  >
                    {catLabel} ({count})
                  </button>
                );
              })}
            </div>

            {/* Sort Toggle */}
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="rounded border border-line bg-white px-2.5 py-1 text-xs text-ink outline-none focus:border-pine-400"
              >
                <option value="strength">Evidence Strength (High → Low)</option>
                <option value="category">Category</option>
              </select>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between">
            <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
              Showing {activeGaps.length} of {gaps.gaps.length} gap(s) across {gaps.papers_analyzed} papers {gaps.cached && "(cached)"}
            </p>
            {dismissedGapIds.length > 0 && (
              <button
                onClick={() => setShowDismissed((v) => !v)}
                className="font-mono text-xs text-stone-500 hover:text-pine-700 underline"
              >
                {showDismissed ? "Hide dismissed" : `Show dismissed (${dismissedGapIds.length})`}
              </button>
            )}
          </div>

          <div className="mt-4 flex flex-col gap-3">
            {activeGaps.map((gap, i) => {
              const matchingQs = questionSets?.find(
                (qs) => qs.gap_id === gap.id || qs.gap?.toLowerCase().trim() === gap.gap?.toLowerCase().trim()
              );
              const isQuestionsOpen = Boolean(expandedQuestions[gap.id]);

              return (
                <div key={gap.id} className="rounded-md border border-line bg-white px-5 py-4 shadow-sm hover:border-pine-200 transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700 font-semibold">
                      Research Gap #{i + 1} — {CATEGORY_LABELS[gap.category] || gap.category}
                    </p>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wide font-medium ${
                          STRENGTH_STYLES[gap.evidence_strength] || STRENGTH_STYLES.Low
                        }`}
                      >
                        Evidence: {gap.evidence_strength}
                      </span>
                      <button
                        onClick={() => handleDismiss(gap.id)}
                        className="font-mono text-[11px] text-stone-400 hover:text-red-700 px-1 py-0.5 rounded"
                        title="Dismiss this gap card"
                      >
                        ✕ Dismiss
                      </button>
                    </div>
                  </div>

                  <p className="mt-2 text-sm font-semibold text-ink leading-relaxed">{gap.gap}</p>

                  <p className="mt-2 text-xs text-muted">
                    <span className="font-mono uppercase tracking-wide">Affected papers:</span>{" "}
                    {gap.affected_papers.join(", ")}
                  </p>

                  {gap.why_it_matters && (
                    <p className="mt-2 text-sm text-ink">
                      <span className="font-mono text-[11px] uppercase tracking-wide text-muted">
                        Why it matters —{" "}
                      </span>
                      {gap.why_it_matters}
                    </p>
                  )}

                  {gap.potential_direction && (
                    <p className="mt-1 text-sm text-ink">
                      <span className="font-mono text-[11px] uppercase tracking-wide text-muted">
                        Potential direction —{" "}
                      </span>
                      {gap.potential_direction}
                    </p>
                  )}

                  {/* Supporting Evidence with Full Excerpts */}
                  {gap.evidence.length > 0 && (
                    <div className="mt-3 border-t border-line/80 pt-2.5">
                      <p className="font-mono text-[11px] uppercase tracking-wide text-muted mb-1">
                        Supporting Evidence ({gap.evidence.length})
                      </p>
                      <ul className="flex flex-col gap-2">
                        {gap.evidence.map((e) => (
                          <li key={e.chunk_id || e.document} className="text-xs text-stone-700">
                            <span className="font-medium text-pine-800">
                              {e.document}
                              {e.page != null && ` — Page ${e.page}`}
                            </span>
                            {e.excerpt && (
                              <p className="mt-0.5 border-l-2 border-pine-200 pl-2 text-xs italic text-stone-600 bg-stone-50/60 py-1 rounded-r">
                                "{e.excerpt}"
                              </p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Inline Research Questions */}
                  {matchingQs && matchingQs.questions?.length > 0 && (
                    <div className="mt-3 border-t border-pine-100 bg-pine-50/40 -mx-5 -mb-4 p-4 rounded-b-md">
                      <button
                        onClick={() => toggleQuestions(gap.id)}
                        className="flex items-center justify-between w-full text-left"
                      >
                        <span className="font-mono text-xs uppercase tracking-wider text-pine-800 font-semibold flex items-center gap-1.5">
                          <span>🎯 Candidate Research Questions ({matchingQs.questions.length})</span>
                          <span>{isQuestionsOpen ? "▴" : "▾"}</span>
                        </span>
                      </button>
                      {isQuestionsOpen && (
                        <ol className="mt-2.5 flex flex-col gap-1.5 pl-4 list-decimal text-xs text-ink">
                          {matchingQs.questions.map((q, idx) => (
                            <li key={idx} className="leading-relaxed">
                              {q}
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Dismissed Gaps Section */}
          {showDismissed && dismissedGapsList.length > 0 && (
            <div className="mt-8 rounded-md border border-dashed border-line p-4 bg-stone-50/50">
              <div className="flex items-center justify-between mb-3">
                <p className="font-mono text-xs uppercase tracking-wider text-muted">
                  Dismissed Gaps ({dismissedGapsList.length})
                </p>
                <button
                  onClick={handleRestoreAll}
                  className="font-mono text-xs text-pine-700 hover:underline uppercase"
                >
                  Restore All
                </button>
              </div>
              <div className="flex flex-col gap-2">
                {dismissedGapsList.map((g) => (
                  <div key={g.id} className="flex items-center justify-between rounded bg-white p-2.5 border border-line text-xs">
                    <span className="truncate max-w-lg text-stone-500 line-through">{g.gap}</span>
                    <button
                      onClick={() => handleRestore(g.id)}
                      className="font-mono text-[11px] text-pine-700 hover:underline uppercase shrink-0"
                    >
                      Restore
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

