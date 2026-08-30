export default function OverviewTab({ project, documents }) {
  if (!project) return null;

  const byStatus = documents.reduce((acc, d) => {
    acc[d.status] = (acc[d.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-2xl px-8 py-8">
      <p className="font-display text-xl text-ink">{project.name}</p>
      {project.description && <p className="mt-2 text-sm text-muted">{project.description}</p>}

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Papers", documents.length],
          ["Indexed", byStatus.indexed ?? 0],
          ["Processing", (documents.length - (byStatus.indexed ?? 0) - (byStatus.failed ?? 0))],
          ["Failed", byStatus.failed ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-md border border-line bg-white px-4 py-3">
            <p className="font-mono text-[11px] uppercase tracking-wide text-muted">{label}</p>
            <p className="mt-1 font-display text-2xl text-ink">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8">
        <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
          Suggested workflow
        </p>
        <ol className="mt-2 flex flex-col gap-1.5 text-sm text-ink">
          <li>1. Upload papers on the <b>Papers</b> tab and wait for them to index.</li>
          <li>2. Ask cross-paper questions in the <b>Research Assistant</b>.</li>
          <li>3. Build the <b>Literature Matrix</b> to see structured findings side by side.</li>
          <li>4. Select papers in <b>Compare Papers</b> for a focused comparison.</li>
          <li>5. Run <b>Research Gaps</b> to surface evidence-backed gaps and questions.</li>
          <li>6. Check <b>Insights</b> for a project-level summary.</li>
        </ol>
      </div>
    </div>
  );
}
