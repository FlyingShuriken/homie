"use client";

export interface ProgressEventData {
  stage: string;
  status: "started" | "running" | "complete" | "failed";
  message: string;
  timestamp: string;
}

interface ProgressFeedProps {
  events: ProgressEventData[];
}

const STATUS_STYLES: Record<string, string> = {
  started: "text-blue-600",
  running: "text-gray-600",
  complete: "text-green-600",
  failed: "text-red-600",
};

const STATUS_ICONS: Record<string, string> = {
  started: "◷",
  running: "◌",
  complete: "✓",
  failed: "✗",
};

const STAGE_LABELS: Record<string, string> = {
  orchestrator: "GLM Orchestrator",
  validate: "Validate filters",
  scrape: "Gather listings",
  normalize: "Normalize data",
  score: "Score listings",
  report: "Generate report",
  outreach: "Prepare outreach",
};

export default function ProgressFeed({ events }: ProgressFeedProps) {
  if (events.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
        <span className="animate-spin">◌</span>
        Waiting for pipeline to start…
      </div>
    );
  }

  return (
    <div className="space-y-1 text-sm font-mono">
      {events.map((e, i) => (
        <div key={i} className={`flex items-start gap-2 ${STATUS_STYLES[e.status] ?? "text-gray-600"}`}>
          <span className="mt-0.5 shrink-0">{STATUS_ICONS[e.status] ?? "·"}</span>
          <span>
            <span className="font-semibold">[{STAGE_LABELS[e.stage] ?? e.stage}]</span>{" "}
            {e.message}
          </span>
        </div>
      ))}
    </div>
  );
}
