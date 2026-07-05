import { motion } from "framer-motion";

export default function Navbar({ communityUrl = "#" }) {
  const landDuration = 1.1;
  const numSparks = 5; 
  const thrusterDuration = 0.3; 
  const landDelay = landDuration - 0.05; 
  const getThrusterVariants = (side) => {
    const distanceY = 25 + Math.random() * 20; 
    const distanceX = side === "right" ? (5 + Math.random() * 8) : (-5 - Math.random() * 8); 

    return {
      animate: {
        opacity: [0, 1, 0], 
        x: [0, distanceX],
        y: [0, distanceY],
        scaleY: [0.5, 2.5, 0.1], 
        scaleX: [0.8, 0.8, 0.1],
      },
    };
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-30 flex items-center justify-end px-6 md:px-10 py-5">
      <div className="relative inline-flex items-center justify-center">
        <div className="absolute left-4 bottom-0 w-0 h-0 z-0 pointer-events-none">
          {[...Array(numSparks)].map((_, i) => (
            <motion.span
              key={`thruster-left-${i}`}
              variants={getThrusterVariants("left")}
              initial={{ opacity: 0, x: 0, y: 0, scaleY: 0.5 }}
              animate="animate"
              transition={{
                delay: landDelay + (Math.random() * 0.06),
                duration: thrusterDuration + (Math.random() * 0.1),
                ease: "easeOut",
              }}
              className="absolute top-0 left-0 w-[2px] h-4 bg-cyan origin-top rounded-full shadow-[0_0_8px_rgba(6,182,212,0.8),_0_0_16px_rgba(139,92,246,0.4)]"
            />
          ))}
        </div>
        <div className="absolute right-4 bottom-0 w-0 h-0 z-0 pointer-events-none">
          {[...Array(numSparks)].map((_, i) => (
            <motion.span
              key={`thruster-right-${i}`}
              variants={getThrusterVariants("right")}
              initial={{ opacity: 0, x: 0, y: 0, scaleY: 0.5 }}
              animate="animate"
              transition={{
                delay: landDelay + (Math.random() * 0.06),
                duration: thrusterDuration + (Math.random() * 0.1),
                ease: "easeOut",
              }}
              className="absolute top-0 left-0 w-[1px] h-3 bg-cyan/50 origin-top rounded-full shadow-[0_0_4px_rgba(79,216,255,0.4)]"
            />
          ))}
        </div>
        <motion.a
          href={communityUrl}
          target="_blank"
          rel="noopener noreferrer"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: landDuration, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 font-body text-sm px-4 py-2 rounded-full border border-nebula
                     bg-deep/80 backdrop-blur-md
                     text-star/80 hover:text-star hover:border-cyan/60
                     hover:shadow-[0_0_16px_rgba(79,216,255,0.25)]
                     transition-all duration-300"
        >
          Join our community
        </motion.a>
      </div>
    </nav>
  );
}