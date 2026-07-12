import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { startCharts, getCharts, startDocs, getDocs, ApiAuthError } from "../lib/api";
import { useAuth } from "../lib/auth";
import Navbar from "../components/Navbar";
import Starfield from "../components/Starfield";
import FloatingWords from "../components/FloatingWords";
import ChatWindow from "../components/ChatWindow";

function buildWordPool(charts) {
  if (!charts) return [];
  const words = [];
  const labels = charts.language_breakdown?.data?.labels || [];
  words.push(...labels);
  const nodes = charts.dependencies?.data?.nodes || [];
  nodes.forEach(n => { if (n.type === "package") words.push(n.label); });
  const table = charts.contributors?.data?.table || [];
  table.forEach(c => words.push(c.login));
  return words;
}

function HealthRing({ score }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="64" height="64" viewBox="0 0 64 64">
      <circle cx="32" cy="32" r={r} fill="none" stroke="#ffffff14" strokeWidth="5" />
      <circle
        cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={`${filled} ${circ - filled}`}
        strokeLinecap="round" transform="rotate(-90 32 32)"
      />
      <text x="32" y="36" textAnchor="middle" fill="#eef1ff" fontSize="15" fontFamily="monospace">{score}</text>
    </svg>
  );
}

function OverviewCard({ overview }) {
  const { summary, description, health, metrics, tech_stack } = overview;
  const langs = Object.entries(tech_stack || {}).sort((a, b) => b[1] - a[1]);
  const breakdown = health?.breakdown || {};

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-sm p-6 space-y-5">

      {}
      {(summary || description) && (
        <p className="font-sans text-sm text-star/80 leading-relaxed">
          {summary || description}
        </p>
      )}

      {}
      {langs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {langs.map(([lang, pct]) => (
            <span key={lang} className="font-mono text-xs px-2.5 py-1 rounded-full border border-cyan/30 bg-cyan/10 text-cyan">
              {pct}% {lang}
            </span>
          ))}
        </div>
      )}

      {}
      {health?.score !== undefined && (
        <div className="flex items-center gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <HealthRing score={health.score} />
          <div>
            <p className="font-display font-medium text-sm text-star">Repo health score: {health.score}/100</p>
            <p className="font-mono text-xs text-muted mt-1">
              stars {breakdown.stars} · recency {breakdown.recency} · issues {breakdown.issue_ratio} · ci/cd {breakdown.ci_cd} · tests {breakdown.tests} · contributors {breakdown.contributors} · docs {breakdown.documentation}
            </p>
          </div>
        </div>
      )}

      {}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric label="Stars" value={metrics.stars?.toLocaleString()} />
          <Metric label="Open issues" value={metrics.open_issues} sub={metrics.closed_issues ? `${metrics.closed_issues} closed` : null} />
          <Metric label="Last commit" value={metrics.last_commit} />
          <Metric label="Contributors" value={metrics.contributors} />
        </div>
      )}

    </div>
  );
}

function Metric({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <p className="font-mono text-xs text-muted">{label}</p>
      <p className="font-display font-semibold text-xl text-star mt-1">{value ?? "—"}</p>
      {sub && <p className="font-mono text-[10px] text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

function AnalyticsCard({ analytics }) {
  const levelColor = { High: "text-red-400 border-red-400/30 bg-red-400/10", Med: "text-amber-400 border-amber-400/30 bg-amber-400/10", Low: "text-green-400 border-green-400/30 bg-green-400/10" };

  return (
    <div className="space-y-5">

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Total files" value={analytics.total_files} />
        <Metric label="Lines of code" value={analytics.lines_of_code > 1000 ? `${(analytics.lines_of_code / 1000).toFixed(1)}k` : analytics.lines_of_code} />
        <Metric label="TODOs / FIXMEs" value={analytics.todos} />
        <Metric label="Test coverage" value={`~${analytics.test_coverage_estimate}%`} />
      </div>

      {analytics.complex_files?.length > 0 && (
        <div>
          <p className="font-mono text-xs text-muted uppercase tracking-wide mb-2">Most complex files</p>
          <div className="space-y-1.5">
            {analytics.complex_files.map(f => (
              <div key={f.file} className="flex items-center justify-between">
                <span className="font-mono text-xs text-star/70 truncate">{f.file}</span>
                <span className={`font-mono text-[10px] px-2 py-0.5 rounded border ${levelColor[f.level]}`}>{f.level}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {analytics.hot_files?.length > 0 && (
        <div>
          <p className="font-mono text-xs text-muted uppercase tracking-wide mb-2">Hot files (most changed in git history)</p>
          <div className="flex flex-wrap gap-2">
            {analytics.hot_files.map(f => (
              <span key={f.file} className="font-mono text-xs px-2 py-1 rounded-lg border border-emerald-400/30 bg-emerald-400/10 text-emerald-300">
                {f.file} · {f.changes}
              </span>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

function DocsSection({ repoId }) {
  const [status, setStatus] = useState("idle"); // status
  const [docs, setDocs]     = useState(null);
  const [search, setSearch] = useState("");

  async function handleGenerate() {
    setStatus("loading");
    let interval = null;

    try {
      await startDocs(repoId);
    } catch {
      setStatus("error");
      return;
    }

    interval = setInterval(async () => {
      try {
        const data = await getDocs(repoId);
        if (data.status === "ready") {
          clearInterval(interval);
          setDocs(data.docs);
          setStatus("ready");
        } else if (data.status.startsWith("error")) {
          clearInterval(interval);
          setStatus("error");
        }
      } catch { clearInterval(interval); setStatus("error"); }
    }, 4000);
  }

  const methodColor = {
    GET: "bg-green-500/20 text-green-400", POST: "bg-blue-500/20 text-blue-400",
    PUT: "bg-amber-500/20 text-amber-400", DELETE: "bg-red-500/20 text-red-400",
    PATCH: "bg-purple-500/20 text-purple-400",
  };

  if (status === "idle") {
    return (
      <Card title="Auto-Generated Documentation">
        <p className="font-mono text-xs text-muted mb-3">
          Generate function summaries and an API endpoint explorer for this repo.
        </p>
        <button
          onClick={handleGenerate}
          className="font-mono text-xs px-4 py-2 rounded-lg bg-cyan/20 border border-cyan/30 text-cyan hover:bg-cyan/30 transition-colors"
        >
          Generate documentation
        </button>
      </Card>
    );
  }

  if (status === "loading") {
    return (
      <Card title="Auto-Generated Documentation">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 rounded-full border-2 border-cyan border-t-transparent animate-spin" />
          <p className="font-mono text-xs text-muted">Generating docs...</p>
        </div>
      </Card>
    );
  }

  if (status === "error") {
    return (
      <Card title="Auto-Generated Documentation">
        <p className="font-mono text-xs text-red-400 mb-3">Docs generation failed.</p>
        <button
          onClick={handleGenerate}
          className="font-mono text-xs px-4 py-2 rounded-lg bg-cyan/20 border border-cyan/30 text-cyan hover:bg-cyan/30 transition-colors"
        >
          Try again
        </button>
      </Card>
    );
  }

  const functions = (docs?.functions || []).filter(f =>
    !search || f.name.toLowerCase().includes(search.toLowerCase()) || f.summary.toLowerCase().includes(search.toLowerCase())
  );
  const endpoints = docs?.endpoints || [];

  return (
    <div className="space-y-6">

      {endpoints.length > 0 && (
        <Card title="API Endpoint Explorer">
          <div className="space-y-2">
            {endpoints.map((e, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                <span className={`font-mono text-[10px] font-semibold px-2 py-0.5 rounded ${methodColor[e.method] || "bg-white/10 text-star"}`}>{e.method}</span>
                <span className="font-mono text-xs text-star/90">{e.path}</span>
                <span className="font-mono text-xs text-muted ml-auto text-right">{e.description}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {docs?.functions?.length > 0 && (
        <Card title="Function / Class Summaries">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search functions..."
            className="w-full mb-4 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-xs text-star placeholder-muted outline-none focus:border-cyan/40"
          />
          <div className="space-y-4">
            {functions.map((f, i) => (
              <div key={i}>
                <p className="font-mono text-sm text-cyan">{f.signature || f.name} <span className="text-muted text-xs">— {f.file}</span></p>
                <p className="font-sans text-xs text-star/70 mt-1">{f.summary}</p>
              </div>
            ))}
            {functions.length === 0 && <p className="font-mono text-xs text-muted">No matches.</p>}
          </div>
        </Card>
      )}

    </div>
  );
}

function PieChart({ labels, values, colors }) {
  const size = 180, cx = 90, cy = 90, r = 70, innerR = 42;

  const slices = [];

  if (labels.length === 1) {
    slices.push({
      circle: true,
      color: colors[0],
      label: labels[0],
      value: values[0],
    });
  } else {
    let startAngle = -Math.PI / 2;
    labels.forEach((label, i) => {
      const angle = (values[i] / 100) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      const x1 = cx + r * Math.cos(startAngle), y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle),   y2 = cy + r * Math.sin(endAngle);
      const ix1 = cx + innerR * Math.cos(startAngle), iy1 = cy + innerR * Math.sin(startAngle);
      const ix2 = cx + innerR * Math.cos(endAngle),   iy2 = cy + innerR * Math.sin(endAngle);
      const large = angle > Math.PI ? 1 : 0;
      const path = `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${innerR} ${innerR} 0 ${large} 0 ${ix1} ${iy1} Z`;
      slices.push({ path, color: colors[i], label, value: values[i] });
      startAngle = endAngle;
    });
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {slices.map((s, i) =>
          s.circle ? (
            <g key={i}>
              <circle cx={cx} cy={cy} r={r} fill={s.color} opacity={0.9} />
              <circle cx={cx} cy={cy} r={innerR} fill="#04060f" />
            </g>
          ) : (
            <path key={i} d={s.path} fill={s.color} opacity={0.9}><title>{s.label}: {s.value}%</title></path>
          )
        )}
        <text x={cx} y={cy - 6} textAnchor="middle" fill="#eef1ff" fontSize="11" fontFamily="monospace">languages</text>
        <text x={cx} y={cy + 10} textAnchor="middle" fill="#eef1ff99" fontSize="10" fontFamily="monospace">{labels.length} total</text>
      </svg>
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-2">
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

function ContributorsHistogram({ table }) {
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
            <a href={c.profile_url} target="_blank" rel="noopener noreferrer"
               className="font-mono text-sm text-star/90 hover:text-cyan transition-colors">{c.login}</a>
            <div className="mt-1 h-2 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full rounded-full transition-all duration-700"
                   style={{ width: `${(c.commits / max) * 100}%`, background: "linear-gradient(90deg, #4fd8ff, #a78bfa)" }} />
            </div>
          </div>
          <span className="font-mono text-xs text-muted shrink-0">{c.commits}</span>
        </div>
      ))}
    </div>
  );
}

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
                <span key={pkg.id}
                      className="font-mono text-xs px-2 py-1 rounded-lg border border-white/10 bg-white/5 text-star/70"
                      style={{ borderColor: `${eco.color}40` }}>{pkg.label}</span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-sm p-6 space-y-4">
      <h2 className="font-display font-semibold text-base text-star/90 tracking-wide">{title}</h2>
      {children}
    </div>
  );
}

export default function RepoIllustrationPage() {
  const { repoId } = useParams();
  const { user, login } = useAuth();

  const [status, setStatus] = useState("idle");
  const [charts, setCharts] = useState(null);
  const [error, setError]   = useState(null);
  const [accessDenied, setAccessDenied] = useState(false);

  useEffect(() => {
    if (!repoId) return;
    let interval = null;

    async function init() {
      setStatus("loading");
      try { await startCharts(repoId); }
      catch (e) {
        if (e instanceof ApiAuthError) { setAccessDenied(true); setError(e.message); setStatus("error"); return; }
        setError(e.message); setStatus("error"); return;
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
          if (e instanceof ApiAuthError) { setAccessDenied(true); }
          clearInterval(interval); setError(e.message); setStatus("error");
        }
      }, 3000);
    }

    init();
    return () => clearInterval(interval);
  }, [repoId]);

  if (status === "idle" || status === "loading") {
    return (
      <div className="relative min-h-screen flex flex-col items-center justify-center gap-4">
        <Starfield /><FloatingWords /><Navbar />
        <div className="relative z-10 flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-cyan border-t-transparent animate-spin" />
          <p className="font-mono text-sm text-muted">Analyzing repository...</p>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="relative min-h-screen flex flex-col items-center justify-center gap-4">
        <Starfield /><FloatingWords /><Navbar />
        <div className="relative z-10 text-center space-y-3 max-w-md px-4">
          {accessDenied ? (
            <>
              <p className="font-display text-lg text-star">Access denied</p>
              <p className="font-mono text-sm text-muted">
                {error || "You don't have access to this repository."}
              </p>
              {!user && (
                <button
                  onClick={login}
                  className="font-body text-sm px-4 py-2 rounded-full border border-cyan/40 bg-cyan/10 text-cyan hover:bg-cyan/20 transition-colors mt-2"
                >
                  Sign in with GitHub
                </button>
              )}
            </>
          ) : (
            <>
              <p className="font-mono text-sm text-red-400">{error}</p>
              <button onClick={() => window.location.reload()} className="font-mono text-xs text-cyan hover:underline">try again</button>
            </>
          )}
        </div>
      </div>
    );
  }

  const overview  = charts?.overview?.data;
  const lang      = charts?.language_breakdown;
  const deps      = charts?.dependencies;
  const contribs  = charts?.contributors;
  const analytics = charts?.analytics?.data;

  const wordPool = buildWordPool(charts);

  return (
    <div className="relative min-h-screen px-4 py-24">
      <Starfield />
      <FloatingWords words={wordPool} />
      <Navbar />

      <div className="relative z-10 max-w-4xl mx-auto space-y-6">

        <div className="mb-8">
          <h1 className="font-display font-semibold text-3xl md:text-4xl bg-gradient-to-r from-[#eef1ff] via-[#4fd8ff] to-[#a78bfa] bg-clip-text text-transparent">
            {repoId.replace(/__/g, " / ").replace(/_/g, "-")}
          </h1>
          <p className="font-mono text-sm text-muted mt-1">repo illustration</p>
        </div>

        {overview && <OverviewCard overview={overview} />}

        {lang?.data?.labels?.length > 0 && (
          <Card title="Language Breakdown">
            <PieChart labels={lang.data.labels} values={lang.data.datasets[0].data} colors={lang.data.datasets[0].backgroundColor} />
          </Card>
        )}

        {contribs?.data?.table?.length > 0 && (
          <Card title="Contributors">
            <ContributorsHistogram table={contribs.data.table} />
          </Card>
        )}

        {analytics && Object.keys(analytics).length > 0 && (
          <Card title="Codebase Analytics">
            <AnalyticsCard analytics={analytics} />
          </Card>
        )}

        {deps?.data?.nodes?.length > 0 && (
          <Card title="Dependencies">
            <DependencyList nodes={deps.data.nodes} summary={deps.data.summary} />
          </Card>
        )}

        <DocsSection repoId={repoId} />

      </div>
      <ChatWindow repoId={repoId} />
    </div>
  );
}