import { useEffect, useMemo, useRef, useState } from "react";

export const defaultWords = [
  "JavaScript", "TypeScript", "Python", "C++", "C", "Rust", "Go", "Java",
  "LLM", "RAG", "Embedding", "Vector", "Tensor", "Prompt", "Context",
  "Tokenizer", "Inference", "Transformer", "Dataset", "NeuralNet",
  "Git", "Repo", "Commit", "Branch", "Merge", "Rebase", "Diff",
  "Clone", "Pull", "Push", "Fork",
  "API", "REST", "GraphQL", "Endpoint", "Middleware", "Socket",
  "Runtime", "Server", "Database", "Cache", "Redis", "SQL", "NoSQL",
  "Stack", "Queue", "Heap", "Graph", "Tree", "Trie", "HashMap",
  "Matrix", "Array", "LinkedList",
  "DFS", "BFS", "BinarySearch", "DP", "Greedy",
  "Recursion", "Sorting", "Backtracking",
  "React", "Next.js", "Node.js", "Vite", "Tailwind",
  "HTML", "CSS", "DOM", "Hooks",
  "Compiler", "Parser", "Lexer", "Kernel", "Thread",
  "Process", "Memory", "Pointer", "Buffer",
  "Schema", "Index", "Syntax", "Regex",
  "Interface", "Class", "Module", "Package",
  "Docker", "Kubernetes", "CI/CD", "Pipeline",
  "Container", "Linux", "SSH"
];

const DEPTH_LAYERS = [
  {
    name: "far",
    fontSize: [10, 13],
    opacity: [0.08, 0.16],
    duration: [34, 46],
    range: 40,
    color: "#55756d",
  },
  {
    name: "mid",
    fontSize: [12, 16],
    opacity: [0.14, 0.24],
    duration: [24, 34],
    range: 70,
    color: "#669ba9",
  },
  {
    name: "near",
    fontSize: [14, 19],
    opacity: [0.2, 0.32],
    duration: [16, 24],
    range: 110,
    color: "#8e7ebc",
  },
];


const HERO_EXCLUSION = { top: 14, bottom: 72, left: 8, right: 92 };

const rand = (min, max) => Math.random() * (max - min) + min;
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];


const avoidHero = (left, top) => {
  const { top: t, bottom: b, left: l, right: r } = HERO_EXCLUSION;
  if (left < l || left > r || top < t || top > b) return { left, top };

  const distTop = top - t;
  const distBottom = b - top;
  const distLeft = left - l;
  const distRight = r - left;
  const minDist = Math.min(distTop, distBottom, distLeft, distRight);

  if (minDist === distTop) return { left, top: Math.max(2, t - 4) };
  if (minDist === distBottom) return { left, top: Math.min(98, b + 4) };
  if (minDist === distLeft) return { left: Math.max(2, l - 4), top };
  return { left: Math.min(98, r + 4), top };
};

//words elly fl props dy htb2a mn el dictionary (I expect ennaha htb2a array b2a)
export default function FloatingWords({ words, density = 22 }) {
  const [instances, setInstances] = useState([]);
  const gridRef = useRef({ cols: 1, rows: 1 });

  const pool = useMemo(() => {
    return Array.isArray(words) && words.length > 0 ? words : defaultWords;
  }, [words]);

  useEffect(() => {
    const aspect = typeof window !== "undefined" ? window.innerWidth / window.innerHeight : 1.6;

    const cols = Math.max(1, Math.round(Math.sqrt(density * aspect)));
    const rows = Math.max(1, Math.ceil(density / cols));

    gridRef.current = { cols, rows };

    let nextId = 0;

    const spawn = (cellIndex) => {
      const { cols, rows } = gridRef.current;

      const col = cellIndex % cols;
      const row = Math.floor(cellIndex / cols);

      const cellW = 100 / cols;
      const cellH = 100 / rows;

      const rawLeft = col * cellW + cellW / 2 + (Math.random() - 0.5) * cellW * 0.6;
      const rawTop = row * cellH + cellH / 2 + (Math.random() - 0.5) * cellH * 0.6;

      const { left, top } = avoidHero(rawLeft, rawTop);

      const layer = pick(DEPTH_LAYERS);
      const angle = rand(0, Math.PI * 2);
      const dist = rand(layer.range * 0.4, layer.range);

      return {
        id: nextId++,
        cellIndex,
        word: pick(pool),
        top,
        left,
        fontSize: rand(layer.fontSize[0], layer.fontSize[1]),
        duration: rand(layer.duration[0], layer.duration[1]),
        delay: rand(0, 6),
        dx: Math.cos(angle) * dist,
        dy: Math.sin(angle) * dist,
        opacity: rand(layer.opacity[0], layer.opacity[1]),
        color: layer.color,
      };
    };

    const count = cols * rows;

    setInstances(Array.from({ length: count }, (_, i) => spawn(i)));

    const interval = setInterval(() => {
      setInstances((prev) => {
        const next = [...prev];
        const idx = Math.floor(Math.random() * next.length);
        next[idx] = spawn(next[idx].cellIndex);
        return next;
      });
    }, 2600);

    return () => clearInterval(interval);
  }, [pool, density]);

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <style>{`
        @keyframes drift-natural-word {
          0% {
            transform: translate(0,0) rotate(0deg);
            opacity: 0;
          }
          10% {
            opacity: var(--op-max);
          }
          30% {
            transform: translate(calc(var(--dx) * 0.3), calc(var(--dy) * -0.5)) rotate(2deg);
          }
          55% {
            transform: translate(calc(var(--dx) * 0.7), calc(var(--dy) * 0.3)) rotate(-1.5deg);
          }
          75% {
            transform: translate(calc(var(--dx) * 0.5), calc(var(--dy) * 0.8)) rotate(1deg);
          }
          90% {
            opacity: var(--op-max);
          }
          100% {
            transform: translate(0,0) rotate(0deg);
            opacity: 0;
          }
        }
      `}</style>

      {instances.map((inst) => (
        <span
          key={inst.id}
          className="absolute font-mono select-none whitespace-nowrap"
          style={{
            top: `${inst.top}%`,
            left: `${inst.left}%`,
            fontSize: `${inst.fontSize}px`,
            color: inst.color,
            animationName: "drift-natural-word",
            animationDuration: `${inst.duration}s`,
            animationDelay: `${inst.delay}s`,
            animationTimingFunction: "ease-in-out",
            animationIterationCount: "infinite",
            "--dx": `${inst.dx}px`,
            "--dy": `${inst.dy}px`,
            "--op-max": inst.opacity,
          }}
        >
          {inst.word}
        </span>
      ))}
    </div>
  );
}