import { useEffect, useRef, useState } from "react";
import type { ActivityEvent, EventCategory } from "../types";

const CATEGORY_BADGE: Record<EventCategory, string> = {
  SCRAPING: "bg-blue-700 text-blue-100",
  INGESTING: "bg-purple-700 text-purple-100",
  VALUATION: "bg-green-700 text-green-100",
  EVENT: "bg-yellow-600 text-yellow-100",
  DB_WRITE: "bg-gray-600 text-gray-200",
  RETRY: "bg-orange-600 text-orange-100",
  ERROR: "bg-red-700 text-red-100",
  SYSTEM: "bg-slate-600 text-slate-200",
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-AU", { hour12: false });
  } catch {
    return iso;
  }
}

interface FeedLineProps {
  event: ActivityEvent;
}

function FeedLine({ event }: FeedLineProps) {
  const [expanded, setExpanded] = useState(false);
  const badgeClass =
    CATEGORY_BADGE[event.category] ?? "bg-gray-600 text-gray-200";

  return (
    <div
      className="group cursor-pointer hover:bg-gray-800 px-3 py-1 rounded"
      onClick={() => event.detail && setExpanded((e) => !e)}
      title={event.detail ? "Click to expand detail" : undefined}
    >
      <div className="flex items-baseline gap-2 text-xs font-mono">
        <span className="text-gray-500 shrink-0">
          [{formatTime(event.timestamp)}]
        </span>
        <span
          className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${badgeClass}`}
        >
          {event.category}
        </span>
        <span className="text-gray-200 break-all">{event.message}</span>
        {event.detail && (
          <span className="text-gray-600 text-[10px] shrink-0">
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </div>
      {expanded && event.detail && (
        <pre className="mt-1 ml-32 text-[10px] text-gray-400 bg-gray-900 rounded p-2 overflow-x-auto">
          {JSON.stringify(event.detail, null, 2)}
        </pre>
      )}
    </div>
  );
}

interface ActivityFeedProps {
  onEvent: (event: ActivityEvent) => void;
}

export default function ActivityFeed({ onEvent }: ActivityFeedProps) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(
        `${protocol}://${window.location.host}/ws/activity`,
      );
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (msg: MessageEvent<string>) => {
        try {
          const event: ActivityEvent = JSON.parse(msg.data);
          setEvents((prev) => [...prev, event]);
          onEventRef.current(event);
        } catch {
          // Ignore malformed messages.
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 3 seconds.
        setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => wsRef.current?.close();
  }, []);

  // Auto-scroll to bottom on new messages.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
          Activity Feed
        </span>
        <span
          className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
            connected
              ? "bg-green-800 text-green-300"
              : "bg-red-900 text-red-400"
          }`}
        >
          {connected ? "LIVE" : "RECONNECTING…"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto py-1 space-y-0.5">
        {events.length === 0 && (
          <p className="text-gray-600 text-xs font-mono px-3 py-2">
            Waiting for events…
          </p>
        )}
        {events.map((e) => (
          <FeedLine key={e.id} event={e} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
