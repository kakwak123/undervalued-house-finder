import { useEffect, useState } from "react";
import type { HealthState, ServiceStatus } from "../types";

const STATUS_COLORS: Record<string, string> = {
  ok: "bg-green-500 text-white",
  degraded: "bg-yellow-400 text-gray-900",
  error: "bg-red-500 text-white",
  unknown: "bg-gray-600 text-gray-300",
};

function StatusPill({ service }: { service: ServiceStatus }) {
  const colorClass = STATUS_COLORS[service.status] ?? STATUS_COLORS["unknown"];
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${colorClass}`}
      title={service.detail ?? undefined}
    >
      <span>{service.name}</span>
      <span className="opacity-75">{service.status}</span>
    </span>
  );
}

function countdown(isoString: string): string {
  const diff = new Date(isoString).getTime() - Date.now();
  if (diff <= 0) return "now";
  const totalMinutes = Math.floor(diff / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

export default function HealthBar() {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          const data: HealthState = await res.json();
          setHealth(data);
        }
      } catch {
        // Health endpoint unreachable — show nothing.
      }
    }
    void fetchHealth();
  }, []);

  // Re-render every 60s to keep the countdown fresh without re-fetching.
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  // tick is consumed by the countdown display; suppress lint warning.
  void tick;

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border-b border-gray-700 text-sm font-mono">
      <span className="text-gray-400 font-semibold tracking-wide">
        SYSTEM HEALTH
      </span>
      {health ? (
        <>
          <StatusPill service={health.scraper} />
          <StatusPill service={health.supabase} />
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-700 text-white">
            Scrapfly {health.scrapfly_credits.toLocaleString()} credits
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-700 text-gray-200">
            Next run in {countdown(health.scheduler.next_run)}
          </span>
        </>
      ) : (
        <span className="text-gray-500 text-xs">Connecting to backend…</span>
      )}
    </div>
  );
}
