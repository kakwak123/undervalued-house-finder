import { useCallback, useState } from "react";
import ActivityFeed from "../components/ActivityFeed";
import BrowserPreview from "../components/BrowserPreview";
import DbView from "../components/DbView";
import HealthBar from "../components/HealthBar";
import TriggerPanel from "../components/TriggerPanel";
import type { ActivityEvent } from "../types";

export default function DebugPage() {
  const [allEvents, setAllEvents] = useState<ActivityEvent[]>([]);

  const handleEvent = useCallback((event: ActivityEvent) => {
    setAllEvents((prev) => [...prev, event]);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* TOP BAR — System Health */}
      <HealthBar />

      {/* MIDDLE — Activity Feed + DB View */}
      <div className="flex flex-1 min-h-0 divide-x divide-gray-700">
        {/* LEFT: Activity Feed */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <ActivityFeed onEvent={handleEvent} />
        </div>

        {/* RIGHT: DB Live View */}
        <div className="w-80 shrink-0 overflow-hidden">
          <DbView recentEvents={allEvents} />
        </div>
      </div>

      {/* BOTTOM — Browser Preview (scraper fetch log) */}
      <div className="h-48 shrink-0 border-t border-gray-700 overflow-hidden">
        <BrowserPreview recentEvents={allEvents} />
      </div>

      {/* TRIGGER PANEL */}
      <TriggerPanel />
    </div>
  );
}
