import { useEffect, useState } from "react";
import type { ActivityEvent } from "../types";

interface DbEventRow {
  id: string;
  timestamp: string;
  event_type: string;
  listing_id: string;
}

interface DbViewProps {
  recentEvents: ActivityEvent[];
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-AU", { hour12: false });
  } catch {
    return iso;
  }
}

export default function DbView({ recentEvents }: DbViewProps) {
  const [totalListings, setTotalListings] = useState<number | null>(null);
  const [eventsToday, setEventsToday] = useState(0);
  const [undervaluedCount, setUndervaluedCount] = useState(0);
  const [dbRows, setDbRows] = useState<DbEventRow[]>([]);

  // Derive live counters from incoming events.
  useEffect(() => {
    const relevant = recentEvents.filter(
      (e) => e.category === "DB_WRITE" || e.category === "EVENT",
    );
    if (relevant.length === 0) return;

    const todayPrefix = new Date().toISOString().slice(0, 10);
    const todayCount = recentEvents.filter(
      (e) => e.category === "EVENT" && e.timestamp.startsWith(todayPrefix),
    ).length;
    setEventsToday(todayCount);

    // Tally undervalued from VALUATION events.
    const undervalued = recentEvents
      .filter((e) => e.category === "VALUATION" && e.detail)
      .reduce(
        (sum, e) =>
          sum + ((e.detail as Record<string, number>)["undervalued"] ?? 0),
        0,
      );
    setUndervaluedCount(undervalued);

    // Build the live events table rows from EVENT-category messages.
    const rows: DbEventRow[] = recentEvents
      .filter((e) => e.category === "EVENT" && e.detail)
      .slice(-20)
      .map((e) => ({
        id: e.id,
        timestamp: e.timestamp,
        event_type: String(
          (e.detail as Record<string, unknown>)["event_type"] ?? "UNKNOWN",
        ),
        listing_id: String(
          (e.detail as Record<string, unknown>)["listing_id"] ?? "—",
        ),
      }))
      .reverse();
    setDbRows(rows);

    // Estimate total listings from DB_WRITE inserts (rough proxy).
    const insertCount = recentEvents.filter(
      (e) =>
        e.category === "DB_WRITE" &&
        e.detail &&
        (e.detail as Record<string, string>)["table"] === "listings",
    ).length;
    setTotalListings((prev) =>
      prev === null ? insertCount : prev + insertCount,
    );
  }, [recentEvents]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
          DB Live View
        </span>
      </div>

      {/* Counters */}
      <div className="grid grid-cols-3 gap-2 px-3 py-3 border-b border-gray-700">
        <div className="bg-gray-800 rounded p-2 text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">
            Total Listings
          </p>
          <p className="text-lg font-bold text-white font-mono">
            {totalListings ?? "—"}
          </p>
        </div>
        <div className="bg-gray-800 rounded p-2 text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">
            Events Today
          </p>
          <p className="text-lg font-bold text-yellow-400 font-mono">
            {eventsToday}
          </p>
        </div>
        <div className="bg-gray-800 rounded p-2 text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">
            Undervalued
          </p>
          <p className="text-lg font-bold text-green-400 font-mono">
            {undervaluedCount}
          </p>
        </div>
      </div>

      {/* Live events table */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="text-gray-500 uppercase text-[9px] border-b border-gray-700">
              <th className="px-3 py-1 text-left">Time</th>
              <th className="px-3 py-1 text-left">Type</th>
              <th className="px-3 py-1 text-left">Listing ID</th>
            </tr>
          </thead>
          <tbody>
            {dbRows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-gray-600 text-center">
                  No events yet
                </td>
              </tr>
            )}
            {dbRows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-gray-800 hover:bg-gray-800"
              >
                <td className="px-3 py-1 text-gray-400">
                  {formatTime(row.timestamp)}
                </td>
                <td className="px-3 py-1 text-yellow-300">{row.event_type}</td>
                <td className="px-3 py-1 text-gray-300">{row.listing_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
