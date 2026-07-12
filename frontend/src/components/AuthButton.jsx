import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../lib/auth";

/**
 * Minimal, self-contained auth button for the Navbar.
 *
 * - Logged out: shows "Sign in with GitHub" (clicking -> /auth/login redirect)
 * - Logged in: shows avatar + dropdown (name, @login, Sign out)
 *
 * Styling intentionally matches the existing Navbar pill style
 * (border-nebula / bg-deep / text-star / text-cyan) so it drops in cleanly.
 * The frontend teammate can move this component anywhere in the layout.
 */
export default function AuthButton() {
  const { user, loading, login, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (loading) {
    return (
      <div className="font-body text-sm px-4 py-2 rounded-full border border-nebula bg-deep/80 text-muted opacity-60">
        …
      </div>
    );
  }

  if (!user) {
    return (
      <button
        onClick={login}
        className="relative z-10 font-body text-sm px-4 py-2 rounded-full border border-nebula bg-deep/80 backdrop-blur-md text-star/80 hover:text-star hover:border-cyan/60 hover:shadow-[0_0_16px_rgba(79,216,255,0.25)] transition-all duration-300"
      >
        Sign in with GitHub
      </button>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-full border border-nebula bg-deep/80 backdrop-blur-md hover:border-cyan/60 transition-all duration-300"
      >
        <img
          src={user.avatar_url}
          alt={user.login}
          className="w-7 h-7 rounded-full border border-white/10"
        />
        <span className="font-body text-sm text-star/80 pr-2 hidden sm:inline">
          {user.name || user.login}
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 mt-2 w-56 rounded-xl border border-white/10 bg-deep/95 backdrop-blur-md shadow-xl py-2 z-50"
          >
            <div className="px-4 py-2 border-b border-white/5">
              <p className="font-display text-sm text-star truncate">{user.name || user.login}</p>
              <p className="font-mono text-xs text-muted truncate">@{user.login}</p>
              {user.email && (
                <p className="font-mono text-[11px] text-muted/70 truncate mt-0.5">{user.email}</p>
              )}
            </div>
            {user.html_url && (
              <a
                href={user.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-2 font-body text-sm text-star/70 hover:text-cyan hover:bg-white/5 transition-colors"
              >
                GitHub profile
              </a>
            )}
            <button
              onClick={() => { setOpen(false); logout(); }}
              className="w-full text-left px-4 py-2 font-body text-sm text-star/70 hover:text-red-400 hover:bg-white/5 transition-colors"
            >
              Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
