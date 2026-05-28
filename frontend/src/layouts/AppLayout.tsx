import { Outlet, Link } from "react-router-dom";
import { Target } from "lucide-react";

export function AppLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Topbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-ink-100 py-4 text-center text-xs text-ink-500">
        ScrapperGMB · Media Fast — POC React + FastAPI
      </footer>
    </div>
  );
}

function Topbar() {
  return (
    <header className="bg-white border-b border-ink-100 sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-sm">
            <Target className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-serif text-lg font-semibold text-ink-900 leading-tight">
              ScrapperGMB
            </div>
            <div className="text-[11px] text-ink-500 leading-tight">
              Prospection B2B · Media Fast
            </div>
          </div>
        </Link>
        <div className="text-xs text-ink-500">
          <span className="font-semibold text-brand-700">POC</span> React + FastAPI
        </div>
      </div>
    </header>
  );
}
