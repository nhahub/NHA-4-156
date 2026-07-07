import { useEffect, useRef, useState } from "react";
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

export default function ChatWindow({ repoId }) {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionIdState] = useState(() => getSessionId(repoId));
  const [messages, setMessages] = useState([]); 
  const [input, setInput] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [liveTrace, setLiveTrace] = useState(""); 
  const [error, setError] = useState(null);

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
  }, [messages, sending, liveTrace]);

  useEffect(() => {
    return () => stopTypingRef.current?.();
  }, []);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setError(null);
    setInput("");
    setLiveTrace("");
    finalAnswerRef.current = "";
    setMessages(prev => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setSending(true);

    try {
      await streamChatMessage(repoId, text, sessionId, "groq", (type, data) => {
        switch (type) {
          case "thinking_delta":
            setLiveTrace(prev => prev + data.text);
            break;
          case "tool_call":
            setLiveTrace(prev => prev + `\n[using ${data.tool}...]\n`);
            break;
          case "tool_result":
            break;
          case "token":
            finalAnswerRef.current = data.text;
            break;
          case "done":
            setLiveTrace("");
            stopTypingRef.current = typeOutText(
              finalAnswerRef.current,
              (partial) => {
                setMessages(prev => {
                  const next = [...prev];
                  next[next.length - 1] = { role: "assistant", content: partial };
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
    setLiveTrace("");
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

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {loadingHistory ? (
              <p className="font-mono text-xs text-muted">loading history...</p>
            ) : messages.length === 0 ? (
              <p className="font-mono text-xs text-muted">Ask anything about this repo.</p>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={`font-mono text-sm px-3 py-2 rounded-xl max-w-[85%] whitespace-pre-wrap ${
                    m.role === "user"
                      ? "ml-auto bg-cyan/20 text-star border border-cyan/30"
                      : "bg-white/5 text-star/90 border border-white/10"
                  }`}
                >
                  {m.content}
                </div>
              ))
            )}

            {sending && liveTrace && (
              <div className="font-mono text-xs text-muted/70 whitespace-pre-wrap px-3">
                {liveTrace}
              </div>
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
