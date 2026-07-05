import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import Starfield from "./components/Starfield";
import FloatingWords from "./components/FloatingWords";
import Navbar from "./components/Navbar";
import SearchBar from "./components/SearchBar";
import ModeToggle from "./components/ModeToggle";
import { startIngestion, getRepoStatus, assistRepo } from "./lib/api";

const TAGLINES = {
  illustrate: "Give me a repo URL and I'll map its architecture into a living constellation.",
  assistant: "Recruit an AI crewmate who already knows every corner of your codebase.",
};

export default function App() {
  const [mode, setMode] = useState("illustrate");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (value) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      if (mode === "illustrate") {
        const { repo_id } = await startIngestion(value);

        const interval = setInterval(async () => {
          try {
            const { status } = await getRepoStatus(repo_id);
            if (status === "ready") {
              clearInterval(interval);
              setLoading(false);
              navigate(`/repo/${repo_id}/illustration`);
            } else if (status.startsWith("error")) {
              clearInterval(interval);
              setLoading(false);
              setError(status);
            }
            //polling l7d ma t5ls
          } catch (err) {
            clearInterval(interval);
            setLoading(false);
            setError(err instanceof Error ? err.message : "Status check failed.");
          }
        }, 2000);
      } else {
        const res = await assistRepo(value);
        setResult(res.answer ?? JSON.stringify(res, null, 2));
        setLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center px-4 py-24">
      <Starfield />
      <FloatingWords />
      <Navbar communityUrl="#" />

      <motion.div
        initial={{ opacity: 0, y: 28, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-2xl rounded-[28px] border border-white/10
                   bg-white/[0.05] backdrop-blur-2xl
                   shadow-[0_0_80px_rgba(79,216,255,0.10)]
                   px-8 py-12 md:px-14 md:py-16
                   flex flex-col items-center gap-9 text-center"
      >
        <div className="space-y-4">
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.9 }}
            className="font-display font-semibold text-4xl md:text-6xl tracking-tight
                       bg-gradient-to-r from-[#eef1ff] via-[#4fd8ff] to-[#a78bfa]
                       bg-clip-text text-transparent
                       drop-shadow-[0_0_30px_rgba(79,216,255,0.35)]"
          >
            Sha3boly el Repo
          </motion.h1>

          <AnimatePresence mode="wait">
            <motion.p
              key={mode}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35 }}
              className="font-body text-muted text-sm md:text-base max-w-md mx-auto"
            >
              {TAGLINES[mode]}
            </motion.p>
          </AnimatePresence>
        </div>

        <ModeToggle mode={mode} onChange={setMode} />
        <SearchBar mode={mode} onSubmit={handleSubmit} loading={loading} />

        {error && (
          <p className="font-mono text-sm text-red-400 max-w-xl">{error}</p>
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