import { useCallback, useEffect, useState } from "react";
import {
  analyzeProject,
  getProjectEntityDetail,
  getProjectKnowledge,
  getProjectTopicDetail,
} from "../../../services/api.js";

const TYPE_LABELS = {
  model: "Models",
  dataset: "Datasets",
  method: "Methods",
  metric: "Metrics",
  domain: "Domains",
  task: "Tasks",
};

function EntityGroup({ title, entities, onSelect }) {
  if (!entities || entities.length === 0) return null;
  return (
    <div>
      <p className="font-mono text-[11px] uppercase tracking-wide text-muted">{title}</p>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {entities.map((e) => (
          <li key={e.entity_id || e.canonical_name}>
            <button
              onClick={() => onSelect?.(e)}
              className="rounded-full border border-line bg-white px-2.5 py-1 text-xs text-ink hover:border-pine-400 hover:text-pine-700"
            >
              {e.canonical_name}
              {e.paper_count != null && (
                <span className="ml-1 text-muted">({e.paper_count})</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function KnowledgeTab({ projectId, indexedDocuments }) {
  const [knowledge, setKnowledge] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [selectedTopic, setSelectedTopic] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getProjectKnowledge(projectId);
      setKnowledge(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      await analyzeProject(projectId, true);
      // Extraction runs in the background; give it a moment then refresh.
      // The papers list / job status is authoritative — this is just a
      // convenience re-fetch so newly-analyzed papers show up without a
      // manual reload.
      setTimeout(load, 4000);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSelectEntity(entity) {
    try {
      const detail = await getProjectEntityDetail(projectId, entity.entity_id);
      setSelectedEntity(detail);
      setSelectedTopic(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSelectTopic(topic) {
    try {
      const detail = await getProjectTopicDetail(projectId, topic.id);
      setSelectedTopic(detail);
      setSelectedEntity(null);
    } catch (err) {
      setError(err.message);
    }
  }

  const canAnalyze = indexedDocuments.length >= 1;
  const hasKnowledge =
    knowledge &&
    (knowledge.top_models.length ||
      knowledge.top_datasets.length ||
      knowledge.top_methods.length ||
      knowledge.top_metrics.length);

  return (
    <div className="px-8 py-8">
      <p className="font-display text-xl text-ink">Project Knowledge & Knowledge Explorer</p>
      <p className="mt-1 text-sm text-muted">
        Scientific structure, entities, topics, and findings extracted from every indexed paper —
        each item traces back to the paper and page it came from.
      </p>

      <div className="mt-5 flex gap-2">
        <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || analyzing}
          className="rounded-md bg-pine-600 px-4 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {analyzing ? "Starting analysis…" : "Analyze All Papers"}
        </button>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-md border border-line px-4 py-2 text-sm text-ink hover:border-pine-400"
        >
          Refresh
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">
        Runs section detection, entity/keyphrase extraction, claim &amp; limitation extraction,
        and topic discovery in the background for every indexed paper. Large projects may take a
        few minutes — refresh to see progress.
      </p>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!loading && knowledge && !hasKnowledge && (
        <p className="mt-6 text-sm text-muted">
          No scientific knowledge extracted yet. Click "Analyze All Papers" above, then refresh in
          a minute or two.
        </p>
      )}

      {hasKnowledge && (
        <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* Entities */}
          <div className="rounded-md border border-line bg-white px-5 py-4">
            <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">Entities</p>
            <div className="mt-3 flex flex-col gap-4">
              <EntityGroup title={TYPE_LABELS.model} entities={knowledge.top_models} onSelect={handleSelectEntity} />
              <EntityGroup title={TYPE_LABELS.dataset} entities={knowledge.top_datasets} onSelect={handleSelectEntity} />
              <EntityGroup title={TYPE_LABELS.method} entities={knowledge.top_methods} onSelect={handleSelectEntity} />
              <EntityGroup title={TYPE_LABELS.metric} entities={knowledge.top_metrics} onSelect={handleSelectEntity} />
              <EntityGroup title={TYPE_LABELS.domain} entities={knowledge.top_domains} onSelect={handleSelectEntity} />
              <EntityGroup title={TYPE_LABELS.task} entities={knowledge.top_tasks} onSelect={handleSelectEntity} />
            </div>
          </div>

          {/* Topics */}
          <div className="rounded-md border border-line bg-white px-5 py-4">
            <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">
              Research Topics
            </p>
            {knowledge.topics.length === 0 ? (
              <p className="mt-2 text-sm text-muted">
                Not enough distinct papers to discover topics yet (needs at least 3).
              </p>
            ) : (
              <ul className="mt-3 flex flex-col gap-2">
                {knowledge.topics.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => handleSelectTopic(t)}
                      className="w-full rounded-md border border-line px-3 py-2 text-left hover:border-pine-400"
                    >
                      <p className="text-sm font-medium text-ink">{t.label}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {t.document_count} paper{t.document_count === 1 ? "" : "s"} ·{" "}
                        {t.keywords.slice(0, 5).join(", ")}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Common limitations */}
          <div className="rounded-md border border-line bg-white px-5 py-4">
            <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">
              Common Limitations
            </p>
            {knowledge.common_limitations.length === 0 ? (
              <p className="mt-2 text-sm text-muted">None extracted yet.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1.5">
                {knowledge.common_limitations.map((l, i) => (
                  <li key={i} className="text-sm text-ink">
                    {l.limitation}
                    <span className="ml-2 text-xs text-muted">
                      ({l.paper_count} paper{l.paper_count === 1 ? "" : "s"})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Key findings */}
          <div className="rounded-md border border-line bg-white px-5 py-4">
            <p className="font-mono text-[11px] uppercase tracking-wide text-pine-700">
              Key Findings
            </p>
            {knowledge.key_findings.length === 0 ? (
              <p className="mt-2 text-sm text-muted">None extracted yet.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {knowledge.key_findings.map((f, i) => (
                  <li key={i} className="text-sm text-ink">
                    {f.claim_text}
                    <span className="ml-1.5 text-xs text-muted">— {f.filename}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Entity detail drill-down */}
      {selectedEntity && (
        <div className="mt-6 rounded-md border border-pine-300 bg-pine-50/40 px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="font-display text-base text-ink">
              {selectedEntity.entity.canonical_name}
              <span className="ml-2 font-mono text-[11px] uppercase text-muted">
                {selectedEntity.entity.entity_type}
              </span>
            </p>
            <button onClick={() => setSelectedEntity(null)} className="font-mono text-xs uppercase text-muted">
              Close
            </button>
          </div>
          <ul className="mt-3 flex flex-col gap-2">
            {selectedEntity.mentions.map((m) => (
              <li key={m.id} className="border-t border-line pt-2 text-sm text-ink">
                <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
                  {m.filename}
                  {m.page_number != null && ` — page ${m.page_number}`}
                  {m.section_label && ` — ${m.section_label}`}
                </p>
                <p className="mt-1 text-sm italic text-ink">"{m.source_excerpt}"</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Topic detail drill-down */}
      {selectedTopic && (
        <div className="mt-6 rounded-md border border-pine-300 bg-pine-50/40 px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="font-display text-base text-ink">{selectedTopic.topic.label}</p>
            <button onClick={() => setSelectedTopic(null)} className="font-mono text-xs uppercase text-muted">
              Close
            </button>
          </div>
          <p className="mt-1 text-xs text-muted">Keywords: {selectedTopic.topic.keywords.join(", ")}</p>
          <ul className="mt-3 flex flex-col gap-1.5">
            {selectedTopic.papers.map((p) => (
              <li key={p.document_id} className="text-sm text-ink">
                {p.filename}
                {p.probability != null && (
                  <span className="ml-2 text-xs text-muted">
                    ({Math.round(p.probability * 100)}% match)
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
