import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { startCharts, getCharts } from "../lib/api";
import Navbar from "../components/Navbar";
import Starfield from "../components/Starfield";


/*
=== LanguageBar ===
  Renders a stacked horizontal bar showing language breakdown
  Each segment is one language colored and sized by its percentage
  Below the bar is a legend with color dot + name + percentage
  Props: labels, values, colors (all arrays, same order)
*/
function LanguageBar({ labels, values, colors }) {
  return (
    <div className="space-y-3">

      <div className="flex h-4 rounded-full overflow-hidden w-full">
        {labels.map((lang, i) => (
          <div
            key={lang}
            style={{ width: `${values[i]}%`, background: colors[i] }}
            title={`${lang}: ${values[i]}%`}
          />
        ))}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {labels.map((lang, i) => (
          <div key={lang} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colors[i] }} />
            <span className="font-mono text-xs text-star/70">{lang}</span>
            <span className="font-mono text-xs text-muted">{values[i]}%</span>
          </div>
        ))}
      </div>

    </div>
  );
}


/*
=== DependencyList ===
  Renders dependencies grouped by ecosystem
  Each ecosystem shows its packages as pill badges
  Props:
    nodes   => array of ecosystem and package node objects
    summary => { total_packages, by_ecosystem }
*/
function DependencyList({ nodes, summary }) {
  const ecosystems = nodes.filter(n => n.type === "ecosystem");
  const packages   = nodes.filter(n => n.type === "package");

  return (
    <div className="space-y-4">

      <p className="font-mono text-xs text-muted">
        {summary.total_packages} packages across {Object.keys(summary.by_ecosystem).length} ecosystems
      </p>

      {ecosystems.map(eco => {
        const pkgs = packages.filter(p => p.ecosystem === eco.id);
        return (
          <div key={eco.id}>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2 h-2 rounded-full" style={{ background: eco.color }} />
              <span className="font-mono text-sm font-medium text-star">{eco.label}</span>
              <span className="font-mono text-xs text-muted">({pkgs.length})</span>
            </div>
            <div className="flex flex-wrap gap-2 pl-4">
              {pkgs.map(pkg => (
                <span
                  key={pkg.id}
                  className="font-mono text-xs px-2 py-1 rounded-lg border border-white/10 bg-white/5 text-star/70"
                  style={{ borderColor: `${eco.color}40` }}
                >
                  {pkg.label}
                </span>
              ))}
            </div>
          </div>
        );
      })}

    </div>
  );
}


/*
=== ContributorsList ===
  Renders top 10 contributors as a leaderboard
  Each row has: rank, avatar, username linked to github, activity bar, commit count
  Activity bar width is relative to the top contributor
  Props: table => sorted array of contributor objects
*/
function ContributorsList({ table }) {
  const top = table.slice(0, 10);
  const max = top[0]?.commits || 1;

  return (
    <div className="space-y-3">
      {top.map((c, i) => (
        <div key={c.login} className="flex items-center gap-3">

          <span className="font-mono text-xs text-muted w-4 shrink-0">{i + 1}</span>

          <img
            src={c.avatar_url || `https://github.com/${c.login}.png`}
            alt={c.login}
            className="w-7 h-7 rounded-full border border-white/10 shrink-0"
            onError={e => { e.target.style.display = "none"; }}
          />

          <div className="flex-1 min-w-0">
            <a
              href={c.profile_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm text-star/90 hover:text-cyan transition-colors"
            >
              {c.login}
            </a>
            <div className="mt-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full bg-cyan/60"
                style={{ width: `${(c.commits / max) * 100}%` }}
              />
            </div>
          </div>

          <span className="font-mono text-xs text-muted shrink-0">{c.commits} commits</span>

        </div>
      ))}
    </div>
  );
}


/*
=== Card ===
  Reusable dark glass wrapper for each chart section
  Props:
    title    => card header text
    children => content inside
*/
function Card({ title, children }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-sm p-6 space-y-4">
      <h2 className="font-display font-semibold text-base text-star/90 tracking-wide">
        {title}
      </h2>
      {children}
    </div>
  );
}


/*
=== RepoIllustrationPage ===
  Main page at /repo/:repoId/illustration
  On load: triggers chart generation (POST) then polls every 3s (GET)
  3 states:
    loading => spinner while charts are generating
    error   => error message with retry button
    ready   => renders the 3 chart cards
  Each card only renders if its data is not empty
  Shows fallback message if all 3 are empty
*/
export default function RepoIllustrationPage() {
  const { repoId } = useParams();

  const [status, setStatus] = useState("idle");
  const [charts, setCharts] = useState(null);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!repoId) return;
    let interval = null;

    async function init() {
      setStatus("loading");
      try {
        await startCharts(repoId);
      } catch (e) {
        setError(e.message);
        setStatus("error");
        return;
      }

      interval = setInterval(async () => {
        try {
          const data = await getCharts(repoId);
          if (data.status === "ready") {
            clearInterval(interval);
            setCharts(data.charts);
            setStatus("ready");
          } else if (data.status.startsWith("error")) {
            clearInterval(interval);
            setError(data.status);
            setStatus("error");
          }
        } catch (e) {
          clearInterval(interval);
          setError(e.message);
          setStatus("error");
        }
      }, 3000);
    }

    init();
    return () => clearInterval(interval);
  }, [repoId]);


  if (status === "idle" || status === "loading") {
    return (
      <div className="relative min-h-screen flex flex-col items-center justify-center gap-4">
        <Starfield />
        <Navbar />
        <div className="relative z-10 flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-cyan border-t-transparent animate-spin" />
          <p className="font-mono text-sm text-muted">Generating charts...</p>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="relative min-h-screen flex flex-col items-center justify-center gap-4">
        <Starfield />
        <Navbar />
        <div className="relative z-10 text-center space-y-2">
          <p className="font-mono text-sm text-red-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="font-mono text-xs text-cyan hover:underline"
          >
            try again
          </button>
        </div>
      </div>
    );
  }

  const lang     = charts?.language_breakdown;
  const deps     = charts?.dependencies;
  const contribs = charts?.contributors;

  return (
    <div className="relative min-h-screen px-4 py-24">
      <Starfield />
      <Navbar />

      <div className="relative z-10 max-w-4xl mx-auto space-y-6">

        <div className="mb-8">
          <h1 className="font-display font-semibold text-3xl md:text-4xl bg-gradient-to-r from-[#eef1ff] via-[#4fd8ff] to-[#a78bfa] bg-clip-text text-transparent">
            {repoId.replace(/__/g, " / ").replace(/_/g, "-")}
          </h1>
          <p className="font-mono text-sm text-muted mt-1">repo illustration</p>
        </div>

        {lang?.data?.labels?.length > 0 && (
          <Card title="Language Breakdown">
            <LanguageBar
              labels={lang.data.labels}
              values={lang.data.datasets[0].data}
              colors={lang.data.datasets[0].backgroundColor}
            />
          </Card>
        )}

        {deps?.data?.nodes?.length > 0 && (
          <Card title="Dependencies">
            <DependencyList nodes={deps.data.nodes} summary={deps.data.summary} />
          </Card>
        )}

        {contribs?.data?.table?.length > 0 && (
          <Card title="Contributors">
            <ContributorsList table={contribs.data.table} />
          </Card>
        )}

        {!lang?.data?.labels?.length && !deps?.data?.nodes?.length && !contribs?.data?.table?.length && (
          <Card title="No data">
            <p className="font-mono text-sm text-muted">
              The LLM couldn't extract chart data for this repo. Try re-ingesting.
            </p>
          </Card>
        )}

      </div>
    </div>
  );
}