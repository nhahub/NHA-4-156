import { motion } from "framer-motion";
import AuthButton from "./AuthButton";

function Flame({ delay, duration, side = "center", scale = 1 }) {
  const xDrift = side === "left" ? -6 : side === "right" ? 6 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, scaleY: 0.2, scaleX: 0.6, y: 0 }}
      animate={{
        opacity: [0, 1, 1, 0.9, 0],
        scaleY: [0.2, 1.3, 1.8, 1.1, 0.3],
        scaleX: [0.6, 1, 0.85, 0.6, 0.3],
        y: [0, 4, 10, 16, 22],
        x: [0, xDrift * 0.3, xDrift * 0.6, xDrift, xDrift * 1.2],
      }}
      transition={{
        delay,
        duration,
        ease: "easeOut",
        times: [0, 0.25, 0.5, 0.8, 1],
      }}
      style={{ transformOrigin: "top center", scale }}
      className="absolute top-0 left-1/2 -translate-x-1/2 w-6 h-10 pointer-events-none"
    >
      <div
        className="absolute inset-0 rounded-full blur-md"
        style={{
          background:
            "radial-gradient(circle at 50% 15%, rgba(139,92,246,0.55), rgba(6,182,212,0.4) 45%, transparent 75%)",
        }}
      />
      <div
        className="absolute inset-x-1 top-0 bottom-1 rounded-full blur-[2px]"
        style={{
          background:
            "radial-gradient(circle at 50% 10%, rgba(125,235,255,0.95), rgba(6,182,212,0.85) 40%, rgba(6,182,212,0) 80%)",
        }}
      />
      <div
        className="absolute inset-x-2 top-0 h-5 rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 5%, rgba(255,255,255,0.95), rgba(200,245,255,0.7) 50%, transparent 80%)",
        }}
      />
    </motion.div>
  );
}

function Embers({ delay, count = 8 }) {
  return (
    <>
      {[...Array(count)].map((_, i) => {
        const angle = (Math.random() - 0.5) * 140;
        const dist = 14 + Math.random() * 22;
        const rad = (angle * Math.PI) / 180;
        const ex = Math.sin(rad) * dist;
        const ey = Math.cos(rad) * dist * 0.7 + 10;

        return (
          <motion.span
            key={i}
            initial={{ opacity: 0, x: 0, y: 0, scale: 0.6 }}
            animate={{
              opacity: [0, 1, 0],
              x: [0, ex],
              y: [0, ey],
              scale: [0.8, 0.3],
            }}
            transition={{
              delay: delay + Math.random() * 0.15,
              duration: 0.35 + Math.random() * 0.25,
              ease: "easeOut",
            }}
            className="absolute top-0 left-1/2 w-1 h-1 rounded-full bg-cyan-100 shadow-[0_0_6px_2px_rgba(125,235,255,0.9)] pointer-events-none"
          />
        );
      })}
    </>
  );
}

function Stardust({ delay, count = 16 }) {
  return (
    <>
      {[...Array(count)].map((_, i) => {
        const x = (Math.random() - 0.5) * 180; 
        const y = 2 + Math.random() * 6;
        const size = 1.5 + Math.random() * 2;
        const riseDelay = delay + Math.random() * 0.4;

        return (
          <motion.span
            key={i}
            initial={{ opacity: 0, scale: 0.2, y }}
            animate={{
              opacity: [0, 1, 0.8, 0],
              scale: [0.2, 1.2, 0.9, 0],
              y: [y, y - 1, y - 4, y - 8],
            }}
            transition={{
              delay: riseDelay,
              duration: 0.9 + Math.random() * 0.4,
              ease: "easeOut",
              times: [0, 0.1, 0.5, 1],
            }}
            style={{ left: `calc(50% + ${x}px)`, width: size, height: size }}
            className="absolute top-0 rounded-full bg-white shadow-[0_0_6px_3px_rgba(255,255,255,1),0_0_12px_4px_rgba(125,235,255,0.6)] pointer-events-none"
          />
        );
      })}
    </>
  );
}

export default function Navbar({ communityUrl = "https://code-book-e6e0cdeke2cfgkgz.polandcentral-01.azurewebsites.net/HTML/HomePage.html" }) {
  const HOLD = 0.45;
  const FALL = 0.55;
  const SETTLE = 0.25;
  const TOTAL = HOLD + FALL + SETTLE;

  const t1 = HOLD / TOTAL;
  const t2 = (HOLD + FALL) / TOTAL;
  const t3 = (HOLD + FALL + SETTLE * 0.4) / TOTAL;

  const BURN_START = HOLD + FALL * 0.45;
  const BURN_PEAK = HOLD + FALL;
  const BURN_DURATION = TOTAL - BURN_START;
  const DUST_START = BURN_PEAK + 0.02;

  return (
    <nav className="fixed top-0 left-0 right-0 z-30 flex items-center justify-end px-6 md:px-10 py-5">
      {/* Auth button pinned to the left edge. Teammate can reposition freely. */}
      <div className="mr-auto">
        <AuthButton />
      </div>

      <div className="relative inline-flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scaleX: 0.2, scaleY: 0.2 }}
          animate={{ opacity: [0, 0.6, 0], scaleX: [0.2, 2, 2.4], scaleY: [0.2, 0.7, 0.9] }}
          transition={{ delay: BURN_PEAK, duration: 0.5, ease: "easeOut" }}
          className="absolute left-1/2 bottom-0 -translate-x-1/2 w-20 h-4 rounded-full bg-cyan/25 blur-md pointer-events-none z-0"
        />

        <div className="absolute left-1/2 -translate-x-1/2 bottom-0 z-0 pointer-events-none">
          <Flame delay={BURN_START} duration={BURN_DURATION} side="center" scale={1.6} />
          <Flame delay={BURN_START + 0.03} duration={BURN_DURATION} side="left" scale={1.1} />
          <Flame delay={BURN_START + 0.05} duration={BURN_DURATION} side="right" scale={1.1} />
          <Embers delay={BURN_PEAK - 0.05} count={10} />
        </div>

        <div className="absolute left-1/2 -translate-x-1/2 bottom-0 z-0 pointer-events-none w-0 h-0">
          <Stardust delay={DUST_START} count={18} />
        </div>

        <motion.a
          href={communityUrl}
          target="_blank"
          rel="noopener noreferrer"
          initial={{ opacity: 0, y: -70, scaleX: 1, scaleY: 1 }}
          animate={{
            opacity: [0, 1, 1, 1, 1],
            y: [-70, -70, 0, 3, 0],
            scaleY: [1, 1, 1, 0.85, 1],
            scaleX: [1, 1, 1, 1.12, 1],
          }}
          transition={{
            duration: TOTAL,
            times: [0, t1, t2, t3, 1],
            ease: ["linear", "easeIn", "easeOut", "easeOut"],
          }}
          className="relative z-10 font-body text-sm px-4 py-2 rounded-full border border-nebula bg-deep/80 backdrop-blur-md text-star/80 hover:text-star hover:border-cyan/60 hover:shadow-[0_0_16px_rgba(79,216,255,0.25)] transition-all duration-300"
        >
          Join our community
        </motion.a>
      </div>
    </nav>
  );
}