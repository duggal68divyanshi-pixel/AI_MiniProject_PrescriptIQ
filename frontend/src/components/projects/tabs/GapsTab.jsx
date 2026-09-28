import { useState } from "react";
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

export default function GapsTab({ projectId, indexedDocuments }) {
  const [gaps, setGaps] = useState(null);
  const [questionSets, setQuestionSets] = useState(null);
  const [loadingGaps, setLoadingGaps] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [error, setError] = useState(null);

  async function handleAnalyze(forceRefresh = false) {
    setLoadingGaps(true);
    setError(null);
    setQuestionSets(null);
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingQuestions(false);
    }
  }

  function exportMarkdownReport() {
    if (!gaps || !gaps.gaps.length) return;
    let md = "# Research Gap Analysis Report\n\n";
    md += `*Analyzed ${gaps.papers_analyzed} paper(s)*\n\n`;
    gaps.gaps.forEach((g, i) => {
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
        });
      }
      md += "\n";
    });
    if (questionSets?.length) {
      md += "## Candidate Research Questions\n\n";
      questionSets.forEach((qs) => {
        md += `### Gap: ${qs.gap}\n`;
        qs.questions.forEach((q, i) => {
          md += `${i + 1}. ${q}\n`;
        });
        md += "\n";
      });
    }
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
      <p className="font-display text-xl text-ink">Research Gap Analysis</p>
      <p className="mt-1 text-sm text-muted">
        Every gap below is tied to specific papers already indexed in this project — nothing here
        is invented.
      </p>

      {!canAnalyze && (
        <p className="mt-4 text-sm text-muted">
          Needs at least 2 indexed papers ({indexedDocuments.length} currently indexed).
        </p>
      )}

      <div className="mt-5 flex gap-2">
        <button
          onClick={() => handleAnalyze(false)}
          disabled={!canAnalyze || loadingGaps}
          className="rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loadingGaps ? "Analyzing…" : "Analyze Research Gaps"}
        </button>
        {gaps && (
          <>
            <button
              onClick={() => handleAnalyze(true)}
              disabled={loadingGaps}
              className="rounded-md border border-line px-4 py-2 text-sm text-ink hover:border-pine-400"
            >
              Re-run fresh
            </button>
            <button
              onClick={exportMarkdownReport}
              className="rounded-md border border-line bg-white px-3 py-2 text-sm text-pine-700 hover:border-pine-400 font-mono uppercase text-xs"
            >
              Export Report (.md)
            </button>
          </>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loadingGaps && (
        <p className="mt-4 text-sm text-muted">
          Collecting structured findings, limitations, methods and datasets across papers, then
          synthesizing evidence-backed gaps…
        </p>
      )}

      {gaps && (
        <>
          <p className="mt-6 font-mono text-[11px] uppercase tracking-wide text-muted">
            {gaps.gaps.length} gap{gaps.gaps.length === 1 ? "" : "s"} found across{" "}
            {gaps.papers_analyzed} papers {gaps.cached && "(cached result)"}
          </p>

          <div className="mt-3 flex flex-col gap-3">
            {gaps.gaps.map((gap, i) => (
              <div key={gap.id} className="rounded-md border border-line bg-white px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">
                    Research Gap #{i + 1} — {CATEGORY_LABELS[gap.category] || gap.category}
                  </p>
                  <span
                    className={`rounded-full px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wide ${
                      STRENGTH_STYLES[gap.evidence_strength] || STRENGTH_STYLES.Low
                    }`}
                  >
                    Evidence: {gap.evidence_strength}
                  </span>
                </div>

                <p className="mt-2 text-sm font-medium text-ink">{gap.gap}</p>

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

                {gap.evidence.length > 0 && (
                  <div className="mt-3 border-t border-line pt-2">
                    <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
                      Evidence
                    </p>
                    <ul className="mt-1 flex flex-col gap-1">
                      {gap.evidence.map((e) => (
                        <li key={e.chunk_id} className="text-xs text-muted">
                          {e.document}
                          {e.page != null && ` — Page ${e.page}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>

          <button
            onClick={handleGenerateQuestions}
            disabled={loadingQuestions || gaps.gaps.length === 0}
            className="mt-6 rounded-md border border-pine-500 px-4 py-2 text-sm font-medium text-pine-700 hover:bg-pine-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loadingQuestions ? "Generating…" : "Generate Potential Research Questions"}
          </button>

          {questionSets && (
            <div className="mt-4 flex flex-col gap-3">
              {questionSets.map((qs) => (
                <div key={qs.gap_id} className="rounded-md border border-line bg-pine-50/40 px-5 py-4">
                  <p className="text-xs text-muted">
                    <span className="font-mono uppercase tracking-wide">Detected gap —</span>{" "}
                    {qs.gap}
                  </p>
                  <ol className="mt-2 flex flex-col gap-1">
                    {qs.questions.map((q, i) => (
                      <li key={i} className="text-sm text-ink">
                        <span className="font-mono text-xs text-pine-700">RQ{i + 1}.</span> {q}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
