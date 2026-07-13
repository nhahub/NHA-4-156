import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Starfield from "./components/Starfield";
import FloatingWords from "./components/FloatingWords";
import Navbar from "./components/Navbar";
import SearchBar from "./components/SearchBar";
import ModeToggle from "./components/ModeToggle";
import { useAuth } from "./lib/auth";
import { startIngestion, getRepoStatus, assistRepo, stopIngestion, ApiAuthError } from "./lib/api";

const TAGLINES = {
  illustrate: "Give me a repo URL and I'll map its architecture into a living constellation.",
  assistant: "Recruit an AI crewmate who already knows every corner of your codebase.",
};

export default function App() {
  const { user } = useAuth();
  const [mode, setMode] = useState("illustrate");
  const [loading, setLoading] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [info, setInfo] = useState(null);
  const navigate = useNavigate();

  // Track the in-flight ingestion so the Stop button and poller can reach them.
  const repoIdRef = useRef(null);
  const intervalRef = useRef(null);
  const cancellingRef = useRef(false);

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const handleSubmit = async (value) => {
    setLoading(true);
    setStopping(false);
    setError(null);
    setResult(null);
    setInfo(null);
    cancellingRef.current = false;
    try {
      if (mode === "illustrate") {
        const { repo_id } = await startIngestion(value);
        repoIdRef.current = repo_id;

        intervalRef.current = setInterval(async () => {
          try {
            const { status } = await getRepoStatus(repo_id);
            if (status === "ready") {
              stopPolling();
              setLoading(false);
              setStopping(false);
              navigate(`/repo/${repo_id}/illustration`);
            } else if (status === "cancelling") {
              // stop was requested, cleanup is in progress on the backend
              setStopping(true);
            } else if (status.startsWith("error")) {
              stopPolling();
              setLoading(false);
              setStopping(false);
              setError(status);
            }
            // otherwise still processing, keep polling
          } catch (err) {
            stopPolling();
            setLoading(false);
            setStopping(false);
            if (cancellingRef.current) {
              // Backend deletes the repo record once cancellation cleanup
              // finishes, so a 404 here means the stop succeeded.
              setError(null);
              setInfo("Ingestion stopped. The cloned repo and any partial data were cleaned up.");
            } else {
              setError(err instanceof Error ? err.message : "Status check failed.");
            }
          }
        }, 2000);
      } else {
        const res = await assistRepo(value);
        setResult(res.answer ?? JSON.stringify(res, null, 2));
        setLoading(false);
      }
    } catch (err) {
      if (err instanceof ApiAuthError) {
        // 401 = private repo, not logged in (or token expired). 403 = no access.
        setError(err.message);
        if (err.status === 401 && !user) {
          setInfo("Hint: this looks like a private repo. Sign in with GitHub to ingest it.");
        }
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
      setLoading(false);
      setStopping(false);
    }
  };

  const handleStop = async () => {
    const repoId = repoIdRef.current;
    if (!repoId) return;
    cancellingRef.current = true;
    setStopping(true);
    try {
      await stopIngestion(repoId);
      // Keep polling (it's still running) so we pick up "cancelling" ->
      // the eventual 404 that confirms cleanup finished.
    } catch (err) {
      cancellingRef.current = false;
      setStopping(false);
      setError(err instanceof Error ? err.message : "Failed to stop ingestion.");
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center px-4 py-24">
      <Starfield />
      <FloatingWords />
      <Navbar communityUrl="https://code-book-e6e0cdeke2cfgkgz.polandcentral-01.azurewebsites.net/HTML/HomePage.html" />

      <motion.div
        initial={{ opacity: 0, y: 28, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-2xl flex flex-col items-center gap-9 text-center"
      >
        <div className="space-y-4">
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.9 }}
            className="font-display font-semibold text-4xl md:text-6xl tracking-tight
                       bg-gradient-to-r from-[#eef1ff] via-[#4fd8ff] to-[#a78bfa]
                       bg-clip-text text-transparent"
          >
            Astrolabe
          </motion.h1>
          <p
            className="font-body text-muted text-sm md:text-base max-w-md mx-auto"
            style={{ textShadow: "0 2px 12px rgba(5, 8, 20, 0.85)" }}
          >
            {TAGLINES[mode]}
          </p>
        </div>

        <ModeToggle mode={mode} onChange={setMode} />
        <SearchBar
          mode={mode}
          onSubmit={handleSubmit}
          onStop={handleStop}
          loading={loading}
          stopping={stopping}
        />

        {error && (
          <p className="font-mono text-sm text-red-400 max-w-xl">{error}</p>
        )}
        {info && (
          <p className="font-mono text-xs text-cyan/80 max-w-xl">{info}</p>
        )}
        {result && (
          <pre className="font-mono text-xs text-left text-star/80 bg-deep/70 border border-nebula rounded-xl p-4 max-w-xl max-h-64 overflow-auto whitespace-pre-wrap">
            {result}
          </pre>
        )}
      </motion.div>
    </div>
  );
}
