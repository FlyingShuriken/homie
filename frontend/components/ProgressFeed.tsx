"use client";

import type { ProgressEventData } from "@/lib/homie";
import { Badge } from "@/components/ui/badge";

const labels: Record<string, string> = {
  orchestrator: "Orchestrator",
  validate: "Validate",
  scrape: "Scrape",
  normalize: "Normalize",
  score: "Score",
  report: "Report",
  outreach: "Outreach",
};

export default function ProgressFeed({ events }: { events: ProgressEventData[] }) {
  if (events.length === 0) {
    return (
      <div className="text-sm text-stone-500">
        Waiting for the backend to emit the first pipeline event.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {events.map((event, index) => (
        <div key={`${event.timestamp}-${index}`} className="relative pl-10">
          {index < events.length - 1 ? (
            <div className="absolute left-[13px] top-8 h-[calc(100%+20px)] w-px bg-stone-200" />
          ) : null}
          <div className="absolute left-0 top-1 flex h-7 w-7 items-center justify-center rounded-full border border-stone-300 bg-white text-xs font-semibold text-stone-700">
            {event.status === "complete"
              ? "✓"
              : event.status === "failed"
              ? "×"
              : "•"}
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Badge
                variant={
                  event.status === "complete"
                    ? "success"
                    : event.status === "failed"
                    ? "warning"
                    : "info"
                }
              >
                {labels[event.stage] ?? event.stage}
              </Badge>
              <span className="text-xs uppercase tracking-[0.24em] text-stone-400">
                {event.timestamp}
              </span>
            </div>
            <p className="text-sm leading-6 text-stone-700">{event.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
