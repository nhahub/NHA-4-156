import { useState } from "react";
export default function SearchBar({ mode, onSubmit, onStop, loading = false }) {
    const [value, setValue] = useState("");
    const placeholder = mode === "illustrate"
        ? "Share your repo URL"
        : "Ready to team up?"; //el 7tta dy h3dlha oddam ka sentences y3ny bs lamma azbot 7war yb2a m3aya login
    const handleSubmit = (e) => {
        e.preventDefault();
        if (!value.trim() || loading)
            return;
        onSubmit(value.trim());
    };
    const handleButtonClick = (e) => {
        if (loading) {
            e.preventDefault();
            onStop?.();
        }
        // otherwise let the form's normal onSubmit handle it
    };
    return (<form onSubmit={handleSubmit} className="w-full max-w-2xl flex items-center gap-2 rounded-2xl
                 border border-nebula bg-deep/70 backdrop-blur-sm
                 px-5 py-4 focus-within:border-cyan/70
                 focus-within:shadow-[0_0_30px_rgba(79,216,255,0.15)]
                 transition-all duration-300">
      <input type="text" value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} disabled={loading} className="flex-1 bg-transparent outline-none font-mono text-sm
                   text-star placeholder:text-muted disabled:opacity-60"/>
      <button type={loading ? "button" : "submit"} onClick={handleButtonClick} className="shrink-0 rounded-xl bg-cyan text-void font-body font-medium
                   text-sm px-4 py-2 hover:brightness-110
                   transition-all duration-200">
        {loading ? "Stop" : mode === "illustrate" ? "Illustrate" : "Assist"}
      </button>
    </form>);
}