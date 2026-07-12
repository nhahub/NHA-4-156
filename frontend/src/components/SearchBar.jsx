import { useState } from "react";

function Spinner({ className }) {
  return (
    <svg viewBox="0 0 24 24" className={`animate-spin ${className}`} fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function SearchBar({ mode, onSubmit, onStop, loading = false, stopping = false }) {
    const [value, setValue] = useState("");
    const placeholder = mode === "illustrate"
        ? "Share your repo URL"
        : "Ready to team up?"; 

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!value.trim() || loading)
            return;
        onSubmit(value.trim());
    };

    const handleButtonClick = (e) => {
        if (loading) {
            e.preventDefault();
            if (!stopping) onStop?.();
        }
    };

    const statusText = stopping
        ? "Stopping — cleaning up the cloned repo and partial data..."
        : loading
            ? mode === "illustrate"
                ? "Cloning the repo & building embeddings — this can take a minute..."
                : "Thinking..."
            : null;

    return (
      <div className="w-full max-w-2xl flex flex-col items-center gap-2">
        <form onSubmit={handleSubmit} className="w-full flex items-center gap-2 rounded-2xl
                     border border-nebula bg-deep/70 backdrop-blur-sm
                     px-5 py-4 focus-within:border-cyan/70
                     focus-within:shadow-[0_0_30px_rgba(79,216,255,0.15)]
                     transition-all duration-300">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            disabled={loading}
            className="flex-1 bg-transparent outline-none font-mono text-sm
                       text-star placeholder:text-muted disabled:opacity-60"
          />
          <button
            type={loading ? "button" : "submit"}
            onClick={handleButtonClick}
            onMouseDown={(e) => e.preventDefault()}
            disabled={stopping}
            className="shrink-0 flex items-center gap-1.5 rounded-xl bg-cyan text-void font-body font-medium
                       text-sm px-4 py-2 transition-all duration-200
                       hover:brightness-110 hover:scale-[1.03] active:scale-[0.98]
                       disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100
                       cursor-pointer disabled:cursor-not-allowed"
          >
            {/* Removed the button spinner from here to keep it clean */}
            {stopping ? "Stopping..." : loading ? "Stop" : mode === "illustrate" ? "Illustrate" : "Assist"}
          </button>
        </form>

        {statusText && (
          <p
            aria-live="polite"
            className="font-mono text-xs text-cyan/80 flex items-center gap-1.5"
          >
            <Spinner className="w-3 h-3" />
            {statusText}
          </p>
        )}
      </div>
    );
}