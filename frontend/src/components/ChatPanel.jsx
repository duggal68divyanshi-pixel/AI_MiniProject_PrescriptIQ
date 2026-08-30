import { useState } from "react";
import { askQuestion } from "../services/api.js";
import SourceReferences from "./SourceReferences.jsx";

export default function ChatPanel({ selectedDocument }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);

  const indexed = selectedDocument?.status === "indexed";

  async function handleAsk(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || asking) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setAsking(true);

    try {
      const response = await askQuestion(
        question,
        selectedDocument?.id ?? null
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer,
          sources: response.sources,
          grounded: response.grounded,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "error", text: err.message },
      ]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto scrollbar-thin px-8 py-6">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl pt-10 text-center">
            <p className="font-display text-xl text-ink">
              Ask the research assistant
            </p>
            <p className="mt-2 text-sm text-muted">
              {selectedDocument
                ? `Questions will be answered from "${
                    selectedDocument.title || selectedDocument.filename
                  }".`
                : "Select or upload a paper, then ask a question grounded in its content."}
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
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
                    {m.text}
                  </p>
                  {!m.grounded && (
                    <p className="mt-2 font-mono text-[11px] uppercase tracking-wide text-muted">
                      No grounded sources retrieved
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
              Retrieving relevant passages and generating an answer…
            </div>
          )}
        </div>
      </div>

      <form
        onSubmit={handleAsk}
        className="border-t border-line bg-paper px-8 py-4"
      >
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              indexed || !selectedDocument
                ? "Ask a question about the research…"
                : "Waiting for this paper to finish indexing…"
            }
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
