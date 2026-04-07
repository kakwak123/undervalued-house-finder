import { useState } from "react";

type TriggerKey = "scrape" | "ingest" | "valuation" | "reset";

interface TriggerState {
  scrape: boolean;
  ingest: boolean;
  valuation: boolean;
  reset: boolean;
}

async function callEndpoint(path: string): Promise<void> {
  const res = await fetch(path, { method: "POST" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
}

export default function TriggerPanel() {
  const [loading, setLoading] = useState<TriggerState>({
    scrape: false,
    ingest: false,
    valuation: false,
    reset: false,
  });
  const [lastError, setLastError] = useState<string | null>(null);

  async function trigger(key: TriggerKey, path: string) {
    setLoading((prev) => ({ ...prev, [key]: true }));
    setLastError(null);
    try {
      await callEndpoint(path);
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-t border-gray-700 flex-wrap">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide shrink-0">
        Manual Triggers
      </span>

      <button
        disabled={loading.scrape}
        onClick={() => trigger("scrape", "/api/scrape")}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
      >
        {loading.scrape ? (
          <span className="animate-spin">⟳</span>
        ) : (
          <span>▶</span>
        )}
        Run Scraper Now
      </button>

      <button
        disabled={loading.ingest}
        onClick={() => trigger("ingest", "/api/ingest")}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded bg-purple-700 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
      >
        {loading.ingest ? (
          <span className="animate-spin">⟳</span>
        ) : (
          <span>▶</span>
        )}
        Run Ingestion Now
      </button>

      <button
        disabled={loading.valuation}
        onClick={() => trigger("valuation", "/api/valuation")}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
      >
        {loading.valuation ? (
          <span className="animate-spin">⟳</span>
        ) : (
          <span>▶</span>
        )}
        Run Valuation Now
      </button>

      <button
        disabled={loading.reset}
        onClick={() => trigger("reset", "/api/reset-events")}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded bg-gray-600 hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
      >
        {loading.reset ? (
          <span className="animate-spin">⟳</span>
        ) : (
          <span>⟳</span>
        )}
        Reset Events
      </button>

      {lastError && (
        <span className="text-xs text-red-400 font-mono ml-2">
          Error: {lastError}
        </span>
      )}
    </div>
  );
}
