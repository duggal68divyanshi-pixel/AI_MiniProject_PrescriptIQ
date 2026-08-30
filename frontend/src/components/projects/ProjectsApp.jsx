import { useCallback, useEffect, useState } from "react";
import { listProjects, createProject } from "../../services/api.js";
import ProjectWorkspace from "./ProjectWorkspace.jsx";

export default function ProjectsApp() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await listProjects();
      setProjects(rows);
      return rows;
    } catch {
      return [];
    }
  }, []);

  useEffect(() => {
    (async () => {
      const rows = await refresh();
      setLoading(false);
      if (rows.length > 0 && !selectedId) setSelectedId(rows[0].id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  async function handleCreate(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name || creating) return;
    setCreating(true);
    setError(null);
    try {
      const project = await createProject(name);
      setNewName("");
      await refresh();
      setSelectedId(project.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex h-full w-full">
      <aside className="flex h-full w-72 shrink-0 flex-col border-r border-line bg-paper">
        <div className="border-b border-line px-5 py-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-pine-600">
            Research Nexus
          </p>
          <h1 className="font-display text-lg font-semibold leading-tight text-ink">
            Research Projects
          </h1>
        </div>

        <form onSubmit={handleCreate} className="border-b border-line px-5 py-4">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New project name…"
            className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm outline-none focus:border-pine-400"
          />
          <button
            type="submit"
            disabled={creating || !newName.trim()}
            className="mt-2 w-full rounded-md bg-pine-600 px-3 py-2 text-sm font-medium text-paper hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create project"}
          </button>
          {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
        </form>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
          {loading && <p className="px-2 py-4 text-sm text-muted">Loading projects…</p>}
          {!loading && projects.length === 0 && (
            <p className="px-2 py-4 text-sm text-muted">
              No research projects yet. Create one to group papers around a topic.
            </p>
          )}
          <ul className="flex flex-col gap-1">
            {projects.map((p) => {
              const active = p.id === selectedId;
              return (
                <li key={p.id}>
                  <button
                    onClick={() => setSelectedId(p.id)}
                    className={`w-full rounded-md px-3 py-2.5 text-left transition-colors ${
                      active ? "bg-pine-100 ring-1 ring-pine-400" : "hover:bg-pine-50"
                    }`}
                  >
                    <p className="truncate font-body text-sm font-medium text-ink">{p.name}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-muted">
                      {p.document_count} paper{p.document_count === 1 ? "" : "s"} ·{" "}
                      {p.indexed_count} indexed
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {selectedId ? (
          <ProjectWorkspace
            key={selectedId}
            projectId={selectedId}
            onProjectChanged={refresh}
            onProjectDeleted={() => {
              setSelectedId(null);
              refresh();
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center px-8 text-center">
            <div>
              <p className="font-display text-xl text-ink">No project selected</p>
              <p className="mt-2 max-w-sm text-sm text-muted">
                Create a research project on the left, then upload a collection of papers to
                query, compare, and analyze them together.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
