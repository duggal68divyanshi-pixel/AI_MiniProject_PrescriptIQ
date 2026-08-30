import { useEffect, useState } from "react";
import { getProjectAnalytics } from "../../../services/api.js";

export default function InsightsTab({ projectId, indexedDocuments }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getProjectAnalytics(projectId);
        if (!cancelled) setAnalytics(result);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, indexedDocuments.length]);

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <p className="font-display text-xl text-ink">Research Insights</p>
      <p className="mt-1 text-sm text-muted">
        A project-level summary, computed only from data that's already been extracted.
      </p>

      {loading && <p className="mt-6 text-sm text-muted">Loading analytics…</p>}
      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {analytics && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label="Papers" value={analytics.paper_count} />
            <Stat label="Metadata extracted" value={analytics.metadata_extracted_count} />
            <Stat label="Literature matrix" value={analytics.matrix_available ? "Available" : "Not yet generated"} />
          </div>

          <Section title="Publication Years">
            {analytics.years.length === 0 ? (
              <Empty text="No publication years could be extracted yet." />
            ) : (
              <div className="flex flex-col gap-1.5">
                {analytics.years.map((y) => (
                  <div key={y.year} className="flex items-center gap-3">
                    <span className="w-12 font-mono text-xs text-muted">{y.year}</span>
                    <div className="h-2 flex-1 rounded-full bg-line">
                      <div
                        className="h-2 rounded-full bg-pine-500"
                        style={{
                          width: `${Math.min(
                            100,
                            (y.count / Math.max(...analytics.years.map((v) => v.count))) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <span className="w-6 text-right font-mono text-xs text-muted">{y.count}</span>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Most Common Methods / Models">
            {analytics.common_methods.length === 0 ? (
              <Empty text="Generate the Literature Matrix first to derive common methods." />
            ) : (
              <TagList items={analytics.common_methods} />
            )}
          </Section>

          <Section title="Common Datasets">
            {analytics.common_datasets.length === 0 ? (
              <Empty text="Generate the Literature Matrix first to derive common datasets." />
            ) : (
              <TagList items={analytics.common_datasets} />
            )}
          </Section>

          <Section title="Research Gaps">
            <p className="text-sm text-muted">
              Run <span className="font-medium text-ink">Research Gaps</span> to see repeated
              limitations, underexplored areas, and potential directions here.
            </p>
          </Section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-md border border-line bg-white px-4 py-3">
      <p className="font-mono text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 font-display text-xl text-ink">{value}</p>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mt-8">
      <p className="font-mono text-[11px] uppercase tracking-wide text-muted">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Empty({ text }) {
  return <p className="text-sm text-muted">{text}</p>;
}

function TagList({ items }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-pine-200 bg-pine-50 px-3 py-1 text-xs text-pine-800"
        >
          {item}
        </span>
      ))}
    </div>
  );
}
