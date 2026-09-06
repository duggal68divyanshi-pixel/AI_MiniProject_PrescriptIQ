import { useCallback, useEffect, useRef, useState } from "react";
import { getProject, listProjectDocuments, deleteProject, updateProject } from "../../services/api.js";
import PapersTab from "./tabs/PapersTab.jsx";
import DiscoveryTab from "./tabs/DiscoveryTab.jsx";
import AssistantTab from "./tabs/AssistantTab.jsx";
import MatrixTab from "./tabs/MatrixTab.jsx";
import CompareTab from "./tabs/CompareTab.jsx";
import GapsTab from "./tabs/GapsTab.jsx";
import InsightsTab from "./tabs/InsightsTab.jsx";
import OverviewTab from "./tabs/OverviewTab.jsx";
import IntelligenceTab from "./tabs/IntelligenceTab.jsx";
import KnowledgeTab from "./tabs/KnowledgeTab.jsx";
import AuthoringTab from "./tabs/AuthoringTab.jsx";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "discovery", label: "Literature Discovery" },
  { id: "papers", label: "Papers" },
  { id: "assistant", label: "Research Assistant" },
  { id: "intelligence", label: "Paper Intelligence" },
  { id: "knowledge", label: "Knowledge Explorer" },
  { id: "matrix", label: "Literature Matrix" },
  { id: "compare", label: "Compare Papers" },
  { id: "gaps", label: "Research Gaps" },
  { id: "insights", label: "Insights" },
  { id: "authoring", label: "AI Paper Authoring" },
];


const ACTIVE_STATUSES = new Set(["uploaded", "extracting", "chunking", "embedding"]);

export default function ProjectWorkspace({ projectId, onProjectChanged, onProjectDeleted }) {
  const [project, setProject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [tab, setTab] = useState("overview");
  const [renaming, setRenaming] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const pollRef = useRef(null);

  const refreshProject = useCallback(async () => {
    try {
      const p = await getProject(projectId);
      setProject(p);
      return p;
    } catch {
      return null;
    }
  }, [projectId]);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await listProjectDocuments(projectId);
      setDocuments(docs);
      return docs;
    } catch {
      return [];
    }
  }, [projectId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshProject(), refreshDocuments()]);
    onProjectChanged?.();
  }, [refreshProject, refreshDocuments, onProjectChanged]);

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    const hasActive = documents.some((d) => ACTIVE_STATUSES.has(d.status));
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(refreshAll, 1800);
    }
    if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documents, refreshAll]);

  async function handleRename(e) {
    e.preventDefault();
    const name = nameInput.trim();
    if (!name) return;
    await updateProject(projectId, { name });
    setRenaming(false);
    refreshAll();
  }

  async function handleDelete() {
    if (!window.confirm(`Delete project "${project?.name}"? Papers stay indexed but leave this project.`)) {
      return;
    }
    await deleteProject(projectId);
    onProjectDeleted?.();
  }

  const indexedDocuments = documents.filter((d) => d.status === "indexed");

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-line px-8 py-4">
        <div className="flex items-center justify-between gap-4">
          {renaming ? (
            <form onSubmit={handleRename} className="flex flex-1 items-center gap-2">
              <input
                autoFocus
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                className="flex-1 rounded-md border border-line bg-white px-2 py-1 font-display text-lg text-ink outline-none focus:border-pine-400"
              />
              <button type="submit" className="font-mono text-xs uppercase text-pine-700">
                Save
              </button>
              <button
                type="button"
                onClick={() => setRenaming(false)}
                className="font-mono text-xs uppercase text-muted"
              >
                Cancel
              </button>
            </form>
          ) : (
            <div className="min-w-0">
              <p className="font-display truncate text-lg text-ink">{project?.name}</p>
              <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
                {documents.length} paper{documents.length === 1 ? "" : "s"} ·{" "}
                {indexedDocuments.length} indexed
              </p>
            </div>
          )}
          {!renaming && (
            <div className="flex shrink-0 items-center gap-3">
              <button
                onClick={() => {
                  setNameInput(project?.name ?? "");
                  setRenaming(true);
                }}
                className="font-mono text-xs uppercase text-muted hover:text-ink"
              >
                Rename
              </button>
              <button
                onClick={handleDelete}
                className="font-mono text-xs uppercase text-red-700 hover:text-red-900"
              >
                Delete
              </button>
            </div>
          )}
        </div>

        <nav className="mt-4 flex flex-wrap gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1.5 font-mono text-xs uppercase tracking-wide transition-colors ${
                tab === t.id
                  ? "bg-pine-600 text-paper"
                  : "text-muted hover:bg-pine-50 hover:text-pine-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {tab === "overview" && (
          <OverviewTab
            project={project}
            documents={documents}
            onNavigate={(t) => setTab(t)}
            onProjectChanged={refreshAll}
          />
        )}
        {tab === "discovery" && (
          <DiscoveryTab projectId={projectId} onPaperImported={refreshAll} />
        )}
        {tab === "papers" && (
          <PapersTab projectId={projectId} documents={documents} onChanged={refreshAll} />
        )}

        {tab === "assistant" && (
          <AssistantTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "intelligence" && (
          <IntelligenceTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "knowledge" && (
          <KnowledgeTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "matrix" && (
          <MatrixTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "compare" && (
          <CompareTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "gaps" && (
          <GapsTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "insights" && (
          <InsightsTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
        {tab === "authoring" && (
          <AuthoringTab projectId={projectId} indexedDocuments={indexedDocuments} />
        )}
      </div>
    </div>
  );
}
