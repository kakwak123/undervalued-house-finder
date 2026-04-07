/** Shared TypeScript types for the dashboard. */

export type EventCategory =
  | "SCRAPING"
  | "INGESTING"
  | "VALUATION"
  | "EVENT"
  | "DB_WRITE"
  | "RETRY"
  | "ERROR"
  | "SYSTEM";

export interface ActivityEvent {
  id: string;
  timestamp: string; // ISO 8601
  category: EventCategory;
  message: string;
  detail?: Record<string, unknown> | null;
}

export interface ScrapingDetail {
  url: string;
  status: number;
  ms: number;
  count: number;
}

export interface ServiceStatus {
  name: string;
  status: "ok" | "degraded" | "error" | "unknown";
  detail?: string | null;
}

export interface SchedulerInfo {
  next_run: string; // ISO 8601
  interval_minutes: number;
}

export interface HealthState {
  scraper: ServiceStatus;
  supabase: ServiceStatus;
  scrapfly_credits: number;
  scheduler: SchedulerInfo;
}
