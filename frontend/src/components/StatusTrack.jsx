const STAGES = ["uploaded", "extracting", "chunking", "embedding", "indexed"];

const LABELS = {
  uploaded: "Uploaded",
  extracting: "Extracting",
  chunking: "Chunking",
  embedding: "Embedding",
  indexed: "Indexed",
  failed: "Failed",
};

export default function StatusTrack({ status }) {
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wide text-red-700">
        <span className="h-1.5 w-1.5 rounded-full bg-red-600" />
        Processing failed
      </span>
    );
  }

  const currentIndex = STAGES.indexOf(status);

  return (
    <div className="flex items-center gap-1">
      {STAGES.map((stage, i) => {
        const done = i < currentIndex || status === "indexed";
        const active = i === currentIndex && status !== "indexed";
        return (
          <div key={stage} className="flex items-center gap-1" title={LABELS[stage]}>
            <span
              className={`h-1.5 w-1.5 rounded-full transition-colors ${
                done
                  ? "bg-pine-600"
                  : active
                  ? "bg-pine-400 animate-pulse"
                  : "bg-line"
              }`}
            />
            {i < STAGES.length - 1 && (
              <span className={`h-px w-3 ${done ? "bg-pine-600" : "bg-line"}`} />
            )}
          </div>
        );
      })}
      <span className="ml-2 text-xs font-mono uppercase tracking-wide text-muted">
        {LABELS[status] ?? status}
      </span>
    </div>
  );
}
