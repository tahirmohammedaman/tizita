// Tizita Studio frontend shell (M0). Pages land in M7 (SPEC §14.2).
// Rule: every <input>/<textarea> gets spellCheck={false}.
export default function App() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <header className="border-b border-stone-800 px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">Tizita Studio</h1>
        <p className="text-sm text-stone-400">Storyboard-driven AI short films</p>
      </header>
      <main className="px-6 py-8 text-stone-400">Coming in M7.</main>
    </div>
  );
}
