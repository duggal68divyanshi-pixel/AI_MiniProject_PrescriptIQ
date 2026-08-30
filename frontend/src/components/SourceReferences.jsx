export default function SourceReferences({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className="mb-2 font-mono text-[11px] uppercase tracking-wide text-muted">
        Sources
      </p>
      <ul className="flex flex-col gap-2">
        {sources.map((s, i) => (
          <li
            key={s.chunk_id}
            className="rounded-md border border-line bg-paper px-3 py-2"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="font-mono text-[11px] text-pine-700">
                [{i + 1}] {s.document}
                {s.page != null && ` — Page ${s.page}`}
              </p>
              <span className="shrink-0 font-mono text-[11px] text-muted">
                {(s.similarity * 100).toFixed(0)}% match
              </span>
            </div>
            <p className="mt-1 text-sm text-muted">{s.excerpt}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
