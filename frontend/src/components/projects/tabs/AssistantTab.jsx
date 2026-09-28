import { useState, useEffect } from "react";
import { askProjectQuestion, getProjectChatHistory } from "../../../services/api.js";
import SourceReferences from "../../SourceReferences.jsx";

// Lightweight inline markdown renderer — no external dependency needed.
// Handles: **bold**, *italic*, `code`, ## headers, numbered/bullet lists, line breaks.
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements = [];
  let i = 0;

  const parseLine = (line) => {
    // Replace inline markdown: **bold**, *italic*, `code`
    const parts = [];
    const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g;
    let last = 0;
    let m;
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push(line.slice(last, m.index));
      if (m[2]) parts.push(<strong key={m.index}>{m[2]}</strong>);
      else if (m[3]) parts.push(<em key={m.index}>{m[3]}</em>);
      else if (m[4]) parts.push(<code key={m.index} className="rounded bg-stone-100 px-1 font-mono text-xs text-stone-700">{m[4]}</code>);
      last = m.index + m[0].length;
    }
    if (last < line.length) parts.push(line.slice(last));
    return parts.length > 0 ? parts : line;
  };

  while (i < lines.length) {
    const line = lines[i];
    // Heading
    if (/^#{1,3}\s/.test(line)) {
      const level = line.match(/^(#+)/)[1].length;
      const content = line.replace(/^#+\s/, "");
      const cls = level === 1 ? "mt-3 mb-1 text-sm font-bold text-ink" : level === 2 ? "mt-2 mb-0.5 text-sm font-semibold text-ink" : "mt-1.5 mb-0.5 text-xs font-semibold text-muted uppercase tracking-wide";
      elements.push(<p key={i} className={cls}>{parseLine(content)}</p>);
      i++;
      continue;
    }
    // Numbered list
    if (/^\d+\.\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(<li key={i} className="ml-4 list-decimal">{parseLine(lines[i].replace(/^\d+\.\s/, ""))}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`} className="my-1 flex flex-col gap-0.5 text-sm text-ink">{items}</ol>);
      continue;
    }
    // Bullet list
    if (/^[-*]\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        items.push(<li key={i} className="ml-4 list-disc">{parseLine(lines[i].replace(/^[-*]\s/, ""))}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`} className="my-1 flex flex-col gap-0.5 text-sm text-ink">{items}</ul>);
      continue;
    }
    // Empty line
    if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
      i++;
      continue;
    }
    // Regular paragraph
    elements.push(<p key={i} className="text-sm leading-relaxed text-ink">{parseLine(line)}</p>);
    i++;
  }
  return <div className="flex flex-col gap-0.5">{elements}</div>;
}

export default function AssistantTab({ projectId, indexedDocuments }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadHistory() {
      if (!projectId) return;
      try {
        const history = await getProjectChatHistory(projectId);
        if (active && Array.isArray(history) && history.length > 0) {
          const loaded = [];
          for (const item of history) {
            loaded.push({ role: "user", text: item.question });
            loaded.push({
              role: "assistant",
              text: item.answer,
              sources: item.sources || [],
              papersCited: [...new Set((item.sources || []).map((s) => s.document))],
              grounded: (item.sources || []).length > 0,
            });
          }
          setMessages(loaded);
        }
      } catch {
        // No history saved yet
      }
    }
    loadHistory();
    return () => { active = false; };
  }, [projectId]);

  async function handleAsk(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || asking) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setAsking(true);

    try {
      const response = await askProjectQuestion(projectId, question);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer,
          sources: response.sources,
          papersCited: response.papers_cited,
          grounded: response.grounded,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "error", text: err.message }]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 px-8 py-6">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl pt-10 text-center">
            <p className="font-display text-xl text-ink">Ask anything about the papers in this project</p>
            <p className="mt-2 text-sm text-muted">
              {indexedDocuments.length > 0
                ? `Answers are grounded across ${indexedDocuments.length} indexed paper${
                    indexedDocuments.length === 1 ? "" : "s"
                  }.`
                : "Upload and index papers first, then ask a cross-paper question here."}
            </p>
          </div>
        )}

        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "self-end" : "self-start"}>
              {m.role === "user" && (
                <div className="max-w-md rounded-lg bg-pine-600 px-4 py-2.5 text-sm text-paper">
                  {m.text}
                </div>
              )}
              {m.role === "assistant" && (
                <div className="max-w-xl rounded-lg border border-line bg-white px-4 py-3">
                  <div className="leading-relaxed">{renderMarkdown(m.text)}</div>
                  {!m.grounded && (
                    <p className="mt-2 font-mono text-[11px] uppercase tracking-wide text-muted">
                      No grounded sources retrieved
                    </p>
                  )}
                  {m.papersCited?.length > 0 && (
                    <p className="mt-2 font-mono text-[11px] uppercase tracking-wide text-pine-700">
                      Papers cited: {m.papersCited.join(", ")}
                    </p>
                  )}
                  <SourceReferences sources={m.sources} />
                </div>
              )}
              {m.role === "error" && (
                <div className="max-w-xl rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-800">
                  {m.text}
                </div>
              )}
            </div>
          ))}
          {asking && (
            <div className="self-start rounded-lg border border-line bg-white px-4 py-3 text-sm text-muted">
              Retrieving relevant passages across papers and synthesizing an answer…
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleAsk} className="border-t border-line bg-paper px-8 py-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. Which methodologies are commonly used across these papers?"
            className="flex-1 rounded-md border border-line bg-white px-3 py-2.5 text-sm text-ink outline-none placeholder:text-muted focus:border-pine-400"
          />
          <button
            type="submit"
            disabled={asking || !input.trim()}
            className="rounded-md bg-pine-600 px-4 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-pine-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}
