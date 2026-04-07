import type { ActivityEvent, ScrapingDetail } from "../types";

interface FetchRow {
  id: string;
  timestamp: string;
  url: string;
  status: number;
  ms: number;
  count: number;
}

interface BrowserPreviewProps {
  recentEvents: ActivityEvent[];
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-AU", { hour12: false });
  } catch {
    return iso;
  }
}

function statusColor(code: number): string {
  if (code >= 200 && code < 300) return "text-green-400";
  if (code >= 300 && code < 400) return "text-yellow-400";
  return "text-red-400";
}

export default function BrowserPreview({ recentEvents }: BrowserPreviewProps) {
  const rows: FetchRow[] = recentEvents
    .filter(
      (e) =>
        e.category === "SCRAPING" && e.detail && "url" in (e.detail as object),
    )
    .slice(-50)
    .map((e) => {
      const d = e.detail as ScrapingDetail;
      return {
        id: e.id,
        timestamp: e.timestamp,
        url: d.url,
        status: d.status,
        ms: d.ms,
        count: d.count,
      };
    })
    .reverse();

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
          Browser Preview — Scraper Fetch Log
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="text-gray-500 uppercase text-[9px] border-b border-gray-700 sticky top-0 bg-gray-900">
              <th className="px-3 py-1 text-left">Time</th>
              <th className="px-3 py-1 text-left">URL</th>
              <th className="px-3 py-1 text-right">Status</th>
              <th className="px-3 py-1 text-right">ms</th>
              <th className="px-3 py-1 text-right">Listings</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-gray-600 text-center">
                  No scrape fetches recorded yet — run the scraper to see
                  entries here.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-gray-800 hover:bg-gray-800"
              >
                <td className="px-3 py-1 text-gray-500 whitespace-nowrap">
                  {formatTime(row.timestamp)}
                </td>
                <td
                  className="px-3 py-1 text-blue-300 max-w-xs truncate"
                  title={row.url}
                >
                  {row.url}
                </td>
                <td
                  className={`px-3 py-1 text-right font-bold ${statusColor(row.status)}`}
                >
                  {row.status}
                </td>
                <td className="px-3 py-1 text-right text-gray-300">{row.ms}</td>
                <td className="px-3 py-1 text-right text-green-300">
                  {row.count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
