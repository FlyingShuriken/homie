"use client";

import { cn } from "@/lib/utils";
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

function EventDot({ status }: { status: ProgressEventData["status"] }) {
  const isRunning = status === "running" || status === "started";

  if (isRunning) {
    return (
      <div className="absolute left-0 top-1 flex h-7 w-7 items-center justify-center rounded-full border border-orange-300 bg-orange-50">
        <span className="relative flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-75" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-orange-500" />
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "absolute left-0 top-1 flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold",
        status === "complete"
          ? "border-emerald-300 bg-emerald-50 text-emerald-700"
          : status === "failed"
          ? "border-red-300 bg-red-50 text-red-600"
          : "border-stone-300 bg-white text-stone-700",
      )}
    >
      {status === "complete" ? "✓" : status === "failed" ? "×" : "•"}
    </div>
  );
}

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
      {events.map((event, index) => {
        const isRunning = event.status === "running" || event.status === "started";
        return (
          <div
            key={`${event.timestamp}-${index}`}
            className="relative pl-10 animate-fade-in-up"
            style={{ animationDelay: `${Math.min(index * 40, 200)}ms` }}
          >
            {index < events.length - 1 ? (
              <div className="absolute left-[13px] top-8 h-[calc(100%+20px)] w-px bg-stone-200" />
            ) : null}
            <EventDot status={event.status} />
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
                {isRunning && (
                  <span className="text-xs text-orange-500 animate-pulse">Processing…</span>
                )}
              </div>
              <p className="text-sm leading-6 text-stone-700">{event.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
