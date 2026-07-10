import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChatMessage, getChatHistory, deleteChatSession } from "../lib/api";
import { getSessionId, setSessionId, clearSessionId } from "../lib/session";

function RocketIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}

function ChevronIcon({ className, open }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${className} transition-transform duration-150 ${open ? "rotate-90" : ""}`}
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}

function typeOutText(fullText, onUpdate, onComplete) {
  const words = fullText.split(" ");
  let i = 0;
  const interval = setInterval(() => {
    i++;
    onUpdate(words.slice(0, i).join(" "));
    if (i >= words.length) {
      clearInterval(interval);
      onComplete?.();
    }
  }, 35);
  return () => clearInterval(interval);
}

function ThinkingToggle({ thinking, expanded, onToggle, live }) {
  if (!thinking) return null;
  return (
    <div className="max-w-[85%]">
      <button
        onClick={onToggle}
        className="flex items-center gap-1 font-mono text-[11px] text-muted hover:text-cyan transition-colors px-1 py-0.5"
      >
        <ChevronIcon className="w-3 h-3" open={expanded} />
        <span className={live ? "animate-pulse" : ""}>
          {live ? "Thinking..." : "Thinking"}
        </span>
      </button>
      {expanded && (
        <div className="font-mono text-xs text-muted/70 whitespace-pre-wrap px-3 py-2 mb-1 rounded-lg bg-white/5 border border-white/10">
          {thinking}
        </div>
      )}
    </div>
  );
}

export default function ChatWindow({ repoId }) {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionIdState] = useState(() => getSessionId(repoId));
  const [messages, setMessages] = useState([]); // { role, content, thinking? }
  const [input, setInput] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [expandedThinking, setExpandedThinking] = useState(() => new Set());

  const scrollRef = useRef(null);
  const finalAnswerRef = useRef("");
  const stopTypingRef = useRef(null);

  useEffect(() => {
    if (!repoId) return;
    let cancelled = false;

    async function loadHistory() {
      setLoadingHistory(true);
      try {
        const data = await getChatHistory(sessionId);
        if (!cancelled) setMessages(data.history || []);
      } catch (e) {
        if (!cancelled) {
          console.error("Failed to load chat history:", e);
          setError(e.message);
        }
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    }
    loadHistory();
    return () => { cancelled = true; };
  }, [repoId, sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    return () => stopTypingRef.current?.();
  }, []);

  function toggleThinking(idx) {
    setExpandedThinking(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setError(null);
    setInput("");
    finalAnswerRef.current = "";
    setMessages(prev => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", thinking: "" },
    ]);
    setSending(true);

    const assistantIdx = messages.length + 1;

    function appendThinking(chunk) {
      setMessages(prev => {
        const next = [...prev];
        const cur = next[assistantIdx];
        if (!cur) return prev;
        next[assistantIdx] = { ...cur, thinking: (cur.thinking || "") + chunk };
        return next;
      });
    }

    try {
      await streamChatMessage(repoId, text, sessionId, "openrouter", (type, data) => {
        switch (type) {
          case "thinking_delta":
            appendThinking(data.text);
            break;
          case "tool_call":
            appendThinking(`\n[using ${data.tool}...]\n`);
            break;
          case "tool_result":
            break;
          case "token":
            finalAnswerRef.current = data.text;
            break;
          case "done":
            stopTypingRef.current = typeOutText(
              finalAnswerRef.current,
              (partial) => {
                setMessages(prev => {
                  const next = [...prev];
                  const cur = next[assistantIdx];
                  next[assistantIdx] = { ...cur, role: "assistant", content: partial };
                  return next;
                });
              },
              () => setSending(false)
            );
            break;
          case "error":
            setError(data.text);
            setSending(false);
            break;
          default:
            break;
        }
      });
    } catch (e) {
      setError(e.message);
      setMessages(prev => prev.slice(0, -2));
      setInput(text);
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleClear() {
    stopTypingRef.current?.();
    try {
      await deleteChatSession(sessionId);
    } catch {
    }
    clearSessionId(repoId);
    const fresh = getSessionId(repoId);
    setSessionIdState(fresh);
    setMessages([]);
    setExpandedThinking(new Set());
    setError(null);
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {open && (
        <div className="mb-3 w-[22rem] h-[28rem] rounded-2xl border border-white/10 bg-[#0b0e1a]/95 backdrop-blur-md shadow-2xl flex flex-col overflow-hidden">

          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <span className="font-display text-sm font-semibold text-star/90">Repo Assistant</span>
            <div className="flex items-center gap-3">
              <button
                onClick={handleClear}
                className="font-mono text-xs text-muted hover:text-cyan transition-colors"
                title="Clear chat"
              >
                clear
              </button>
              <button
                onClick={() => setOpen(false)}
                className="font-mono text-xs text-muted hover:text-star transition-colors"
              >
                ✕
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
            {loadingHistory ? (
              <p className="font-mono text-xs text-muted">loading history...</p>
            ) : messages.length === 0 ? (
              <p className="font-mono text-xs text-muted">Ask anything about this repo.</p>
            ) : (
              messages.map((m, i) => {
                const isLast = i === messages.length - 1;
                const stillThinking = sending && isLast && m.role === "assistant" && !m.content;
                return (
                  <div key={i} className={m.role === "user" ? "flex flex-col items-end" : "flex flex-col items-start"}>
                    {m.role === "assistant" && (
                      <ThinkingToggle
                        thinking={m.thinking}
                        expanded={expandedThinking.has(i)}
                        onToggle={() => toggleThinking(i)}
                        live={stillThinking}
                      />
                    )}
                    {m.content && (
                      <div
                        className={`px-3 py-2 rounded-xl max-w-[85%] ${
                          m.role === "user"
                            ? "bg-cyan/20 text-star border border-cyan/30 font-mono text-sm"
                            : "bg-white/5 text-star/90 border border-white/10 text-sm leading-relaxed"
                        }`}
                      >
                        {m.role === "user" ? (
                          m.content
                        ) : (
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code({ node, inline, className, children, ...props }) {
                                if (inline) {
                                  return <code className="bg-white/10 rounded px-1 py-0.5 text-xs" {...props}>{children}</code>;
                                }
                                return (
                                  <pre className="bg-black/40 rounded-lg p-3 my-2 overflow-x-auto text-xs">
                                    <code {...props}>{children}</code>
                                  </pre>
                                );
                              },
                              h1: ({ children }) => <h1 className="text-base font-bold text-star mb-2 mt-3 first:mt-0">{children}</h1>,
                              h2: ({ children }) => <h2 className="text-sm font-bold text-star mb-1.5 mt-2.5 first:mt-0">{children}</h2>,
                              h3: ({ children }) => <h3 className="text-sm font-semibold text-star mb-1 mt-2 first:mt-0">{children}</h3>,
                              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                              ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 mb-2 last:mb-0">{children}</ul>,
                              ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 mb-2 last:mb-0">{children}</ol>,
                              li: ({ children }) => <li>{children}</li>,
                              strong: ({ children }) => <strong className="font-bold text-star">{children}</strong>,
                              a: ({ href, children }) => <a href={href} className="text-cyan underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                              hr: () => <hr className="border-white/10 my-3" />,
                              blockquote: ({ children }) => <blockquote className="border-l-2 border-cyan/40 pl-3 italic text-muted my-2">{children}</blockquote>,
                            }}
                          >
                            {m.content}
                          </ReactMarkdown>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {error && (
              <p className="font-mono text-xs text-red-400">{error}</p>
            )}
          </div>

          <div className="p-3 border-t border-white/10 flex gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about this repo..."
              rows={1}
              className="flex-1 resize-none font-mono text-sm bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-star placeholder:text-muted focus:outline-none focus:border-cyan/50"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="font-mono text-xs px-3 rounded-lg bg-cyan/20 border border-cyan/30 text-cyan hover:bg-cyan/30 transition-colors disabled:opacity-40"
            >
              send
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen(o => !o)}
        className="w-12 h-12 rounded-full bg-cyan/20 border border-cyan/40 text-cyan flex items-center justify-center shadow-lg hover:bg-cyan/30 transition-colors"
        title="Chat with this repo"
      >
        <RocketIcon className="w-5 h-5" />
      </button>
    </div>
  );
}
