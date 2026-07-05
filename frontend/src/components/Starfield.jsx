import { useEffect, useRef } from "react";
export default function Starfield() {
    const canvasRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas)
            return;
        const ctx = canvas.getContext("2d");
        if (!ctx)
            return;
        let width = window.innerWidth;
        let height = window.innerHeight;
        let stars = [];
        let rafId;
        const resize = () => {
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = width;
            canvas.height = height;
            const count = Math.floor((width * height) / 3500);
            stars = Array.from({ length: count }, () => ({
                x: Math.random() * width,
                y: Math.random() * height,
                radius: Math.random() * 1.3 + 0.2,
                baseAlpha: Math.random() * 0.6 + 0.2,
                twinkleSpeed: Math.random() * 0.015 + 0.003,
                phase: Math.random() * Math.PI * 2,
            }));
        };
        const draw = (time) => {
            ctx.clearRect(0, 0, width, height);
            const grad1 = ctx.createRadialGradient(width * 0.2, height * 0.15, 0, width * 0.2, height * 0.15, width * 0.4);
            grad1.addColorStop(0, "rgba(139, 123, 255, 0.10)");
            grad1.addColorStop(1, "rgba(139, 123, 255, 0)");
            ctx.fillStyle = grad1;
            ctx.fillRect(0, 0, width, height);
            const grad2 = ctx.createRadialGradient(width * 0.8, height * 0.75, 0, width * 0.8, height * 0.75, width * 0.45);
            grad2.addColorStop(0, "rgba(79, 216, 255, 0.08)");
            grad2.addColorStop(1, "rgba(79, 216, 255, 0)");
            ctx.fillStyle = grad2;
            ctx.fillRect(0, 0, width, height);
            for (const s of stars) {
                const alpha = s.baseAlpha * (0.5 + 0.5 * Math.sin(time * s.twinkleSpeed + s.phase));
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(238, 241, 255, ${alpha})`;
                ctx.fill();
            }
            rafId = requestAnimationFrame(draw);
        };
        resize();
        window.addEventListener("resize", resize);
        rafId = requestAnimationFrame(draw);
        return () => {
            window.removeEventListener("resize", resize);
            cancelAnimationFrame(rafId);
        };
    }, []);
    return (<canvas ref={canvasRef} className="fixed inset-0 -z-20 pointer-events-none" aria-hidden="true"/>);
}
