export default function ModeToggle({ mode, onChange }) {
  const options = [
    {
      key: "illustrate",
      label: "Illustrate repo",
      icon: (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2" />
          <path d="M15.5 8.5l-2 5-5 2 2-5z" />
        </svg>
      ),
    },
    {
      key: "assistant",
      label: "Assistant",
      icon: (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6">
          <rect x="7" y="9" width="10" height="7" rx="2" />
          <path d="M12 9V6M9 6h6" />
          <circle cx="9.5" cy="12.5" r="0.8" fill="currentColor" stroke="none" />
          <circle cx="14.5" cy="12.5" r="0.8" fill="currentColor" stroke="none" />
          <path d="M4 12h3M17 12h3" />
        </svg>
      ),
    },
  ];

  return (
    <div className="inline-flex items-center rounded-full border border-nebula bg-deep/60 p-1">
      {options.map((opt) => {
        const active = mode === opt.key;
        return (
          <button
            key={opt.key}
            onClick={() => onChange(opt.key)}
            style={{ WebkitTapHighlightColor: "transparent" }}
            className={`flex items-center gap-2 px-9 py-2 rounded-full text-sm font-body cursor-pointer
              outline-none border-none ring-0 focus:ring-0 focus:outline-none focus-visible:outline-none focus-visible:ring-0
              transition-all duration-200 active:scale-[0.96]
              ${active
                ? "bg-cyan text-void font-medium shadow-[0_0_18px_rgba(79,216,255,0.4)]"
                : "text-muted hover:text-star hover:bg-white/5 hover:scale-[1.04]"}`}
          >
            {opt.icon}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
