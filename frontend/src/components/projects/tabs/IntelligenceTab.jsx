import { useCallback, useEffect, useState } from "react";
import { analyzeDocument, getDocumentJobStatus, getPaperIntelligence } from "../../../services/api.js";

const SECTION_LABELS = {
  title: "Title",
  abstract: "Abstract",
  introduction: "Introduction",
  related_work: "Related Work",
  methodology: "Methodology",
  dataset: "Dataset",
  experiments: "Experiments",
  results: "Results",
  discussion: "Discussion",
  conclusion: "Conclusion",
  limitations: "Limitations",
  future_work: "Future Work",
  references: "References",
  other: "Other",
};

function Section({ title, children }) {
  return (
    <div className="rounded-md border border-line bg-white px-5 py-4">
      <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function IntelligenceTab({ projectId, indexedDocuments }) {
  const [selectedId, setSelectedId] = useState(indexedDocuments[0]?.id ?? null);
  const [intelligence, setIntelligence] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (documentId) => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getPaperIntelligence(documentId);
      setIntelligence(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(selectedId);
  }, [selectedId, load]);

  async function handleAnalyze() {
    if (!selectedId) return;
    setAnalyzing(true);
    setError(null);
    try {
      const { job_id } = await analyzeDocument(selectedId);
      // Lightweight poll — same pattern as document StatusTrack polling elsewhere.
      const poll = setInterval(async () => {
        try {
          const job = await getDocumentJobStatus(selectedId, job_id);
          if (job.status === "completed" || job.status === "failed") {
            clearInterval(poll);
            setAnalyzing(false);
            load(selectedId);
          }
        } catch {
          clearInterval(poll);
          setAnalyzing(false);
        }
      }, 2000);
    } catch (err) {
      setError(err.message);
      setAnalyzing(false);
    }
  }

  const groupedEntities = {};
  (intelligence?.entities ?? []).forEach((e) => {
    groupedEntities[e.entity_type] = groupedEntities[e.entity_type] || [];
    groupedEntities[e.entity_type].push(e);
  });

  return (
    <div className="px-8 py-8">
      <p className="font-display text-xl text-ink">Paper Intelligence</p>
      <p className="mt-1 text-sm text-muted">
        Structural, entity-level, and claim-level understanding of one paper — not just chat.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <select
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value)}
          className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink"
        >
          {indexedDocuments.length === 0 && <option value="">No indexed papers</option>}
          {indexedDocuments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.metadata?.title || d.title || d.filename}
            </option>
          ))}
        </select>
        <button
          onClick={handleAnalyze}
          disabled={!selectedId || analyzing}
          className="rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {analyzing ? "Analyzing…" : "Analyze This Paper"}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!loading && intelligence && !intelligence.analysis_available && (
        <p className="mt-6 text-sm text-muted">
          No scientific extraction has run for this paper yet. Click "Analyze This Paper" above.
        </p>
      )}

      {intelligence?.analysis_available && (
        <div className="mt-8 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Section title="Sections">
            <ul className="flex flex-col gap-1">
              {intelligence.sections.map((s, i) => (
                <li key={i} className="flex items-center justify-between text-sm text-ink">
                  <span>{SECTION_LABELS[s.section_label] || s.section_label}</span>
                  <span className="font-mono text-[11px] text-muted">
                    {s.page_start != null ? `p.${s.page_start}${s.page_end && s.page_end !== s.page_start ? `–${s.page_end}` : ""}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Keyphrases">
            <ul className="flex flex-wrap gap-1.5">
              {intelligence.keyphrases.map((k) => (
                <li
                  key={k.phrase}
                  className="rounded-full border border-line px-2.5 py-1 text-xs text-ink"
                  title={`relevance ${k.score}`}
                >
                  {k.phrase}
                </li>
              ))}
              {intelligence.keyphrases.length === 0 && <p className="text-sm text-muted">None extracted.</p>}
            </ul>
          </Section>

          {Object.entries(groupedEntities).map(([type, entities]) => (
            <Section key={type} title={type[0].toUpperCase() + type.slice(1) + "s"}>
              <ul className="flex flex-col gap-2">
                {entities.map((e, i) => (
                  <li key={i} className="text-sm text-ink">
                    <span className="font-medium">{e.canonical_name}</span>
                    <span className="ml-2 font-mono text-[11px] text-muted">
                      {e.section_label && SECTION_LABELS[e.section_label]}
                      {e.page_number != null && ` · p.${e.page_number}`}
                      {e.confidence != null && ` · ${Math.round(e.confidence * 100)}%`}
                      {e.extraction_method === "spacy_candidate" && " · candidate"}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          ))}

          <Section title="Claims & Findings">
            <ul className="flex flex-col gap-2">
              {intelligence.claims.map((c, i) => (
                <li key={i} className="text-sm text-ink">
                  <span className="mr-1.5 rounded-full bg-pine-100 px-2 py-0.5 font-mono text-[10px] uppercase text-pine-800">
                    {c.claim_type}
                  </span>
                  {c.claim_text}
                </li>
              ))}
              {intelligence.claims.length === 0 && <p className="text-sm text-muted">None extracted.</p>}
            </ul>
          </Section>

          <Section title="Limitations">
            <ul className="flex flex-col gap-2">
              {intelligence.limitations.map((l, i) => (
                <li key={i} className="text-sm text-ink">
                  <span className="mr-1.5 rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[10px] uppercase text-amber-800">
                    {l.category}
                  </span>
                  {l.limitation_text}
                </li>
              ))}
              {intelligence.limitations.length === 0 && <p className="text-sm text-muted">None extracted.</p>}
            </ul>
          </Section>

          <Section title="Relationships">
            <ul className="flex flex-col gap-1.5">
              {intelligence.relationships.map((r, i) => (
                <li key={i} className="text-sm text-ink">
                  <span className="font-mono text-[11px] uppercase text-pine-700">{r.predicate}</span>{" "}
                  {r.entity_name || r.claim_text || r.limitation_text || r.object_text}
                </li>
              ))}
              {intelligence.relationships.length === 0 && <p className="text-sm text-muted">None derived.</p>}
            </ul>
          </Section>

          {intelligence.topics.length > 0 && (
            <Section title="Topic Profile">
              <ul className="flex flex-col gap-1">
                {intelligence.topics.map((t, i) => (
                  <li key={i} className="text-sm text-ink">
                    {t.label}
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
