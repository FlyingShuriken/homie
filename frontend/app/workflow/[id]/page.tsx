"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import ProgressFeed from "@/components/ProgressFeed";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  API_URL,
  type PipelineStatus,
  type ProgressEventData,
} from "@/lib/homie";

const STAGE_SEQUENCE = [
  "validate",
  "scrape",
  "normalize",
  "score",
  "report",
] as const;

const STAGE_LABELS: Record<string, string> = {
  validate: "Validate filters",
  scrape: "Scrape sources",
  normalize: "Normalize fields",
  score: "Score listings",
  report: "Write summary report",
};

function getDerivedStage(event: ProgressEventData): string | null {
  if (event.stage !== "orchestrator") return event.stage;

  const match = event.message.match(/^GLM\s+→\s+([a-z_]+)/);
  const toolName = match?.[1];

  switch (toolName) {
    case "validate_filters":
      return "validate";
    case "run_scraper":
      return "scrape";
    case "normalize_listings":
      return "normalize";
    case "score_listings":
      return "score";
    case "generate_report":
    case "finish":
      return "report";
    default:
      return null;
  }
}

export default function WorkflowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [events, setEvents] = useState<ProgressEventData[]>([]);
  const [status, setStatus] = useState<PipelineStatus>("running");
  const [streamSettled, setStreamSettled] = useState(false);

  useEffect(() => {
    if (!id) return;

    const source = new EventSource(`${API_URL}/api/search/${id}/stream`);
    let closed = false;

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as ProgressEventData;
        setEvents((current) => [...current, payload]);
        if (
          payload.stage === "orchestrator" &&
          (payload.status === "complete" || payload.status === "failed")
        ) {
          setStatus(payload.status === "complete" ? "complete" : "failed");
        }
      } catch {
        setStatus("failed");
      }
    };

    source.onerror = async () => {
      if (closed) return;
      closed = true;
      source.close();
      try {
        const res = await fetch(`${API_URL}/api/search/${id}/results`, {
          cache: "no-store",
        });
        if (res.ok) {
          const payload = (await res.json()) as { pipeline_status: PipelineStatus };
          setStatus(payload.pipeline_status);
        } else {
          setStatus("failed");
        }
      } catch {
        setStatus("failed");
      } finally {
        setStreamSettled(true);
      }
    };

    return () => {
      closed = true;
      source.close();
    };
  }, [id]);

  useEffect(() => {
    if (status === "complete" || status === "partial") {
      router.replace(`/results/${id}`);
    }
  }, [id, router, status]);

  const stageProgress = useMemo(() => {
    const completed = new Set<(typeof STAGE_SEQUENCE)[number]>();
    let activeStage: (typeof STAGE_SEQUENCE)[number] | null = null;
    let furthestStageIndex = -1;

    for (const event of events) {
      const derivedStage = getDerivedStage(event);
      if (!derivedStage) continue;

      const stageIndex = STAGE_SEQUENCE.indexOf(
        derivedStage as (typeof STAGE_SEQUENCE)[number],
      );
      if (stageIndex === -1) continue;

      if (event.status === "running" && stageIndex >= furthestStageIndex) {
        furthestStageIndex = stageIndex;
        activeStage = STAGE_SEQUENCE[stageIndex];
      }

      if (event.status === "complete" && event.stage === "orchestrator") {
        furthestStageIndex = STAGE_SEQUENCE.length - 1;
        activeStage = null;
      }
    }

    for (let index = 0; index < furthestStageIndex; index += 1) {
      completed.add(STAGE_SEQUENCE[index]);
    }

    if (status === "complete" || status === "partial") {
      for (const stage of STAGE_SEQUENCE) completed.add(stage);
      activeStage = null;
    }

    return { activeStage, completed };
  }, [events, status]);

  const progress = useMemo(() => {
    if (status === "failed") return 100;
    if (status === "complete" || status === "partial") return 100;

    const completedCount = stageProgress.completed.size;
    const activeBonus = stageProgress.activeStage ? 10 : 0;
    return Math.min(95, completedCount * 20 + activeBonus);
  }, [stageProgress, status]);

  const currentFocus = useMemo(() => {
    if (status === "failed") return "Pipeline failed";
    if (status === "complete" || status === "partial") return "Finalizing results";
    if (stageProgress.activeStage) {
      return STAGE_LABELS[stageProgress.activeStage] ?? stageProgress.activeStage;
    }
    return "Waiting for first backend event";
  }, [stageProgress.activeStage, status]);

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Badge variant="info">Workflow</Badge>
          <Badge variant="outline">Session {id}</Badge>
          <Badge variant={status === "failed" ? "warning" : "success"}>
            {status}
          </Badge>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card className="border-stone-300">
            <CardContent className="space-y-8 p-8">
              <div className="space-y-4">
                <h1 className="font-display text-5xl leading-none text-stone-950">
                  The agent is working.
                </h1>
                <p className="max-w-2xl text-lg leading-8 text-stone-600">
                  This view now reflects the live backend stream. When the pipeline completes, the app redirects to the results board.
                </p>
                <Progress value={progress} />
              </div>

              <ProgressFeed events={events} />
            </CardContent>
          </Card>

          <Card className="border-stone-300 bg-white/90">
            <CardContent className="space-y-5 p-6">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-stone-400">
                  Current focus
                </div>
                <div className="mt-2 text-lg font-semibold text-stone-950">
                  {currentFocus}
                </div>
              </div>
              <div className="space-y-4 text-sm text-stone-600">
                {STAGE_SEQUENCE.map((stage) => {
                  const isDone = stageProgress.completed.has(stage);
                  const isActive = stageProgress.activeStage === stage;

                  return (
                    <div
                      key={stage}
                      className={
                        isActive
                          ? "font-semibold text-orange-600"
                          : isDone
                            ? "text-stone-900"
                            : "text-stone-500"
                      }
                    >
                      {isDone ? "Done · " : isActive ? "Now · " : ""}
                      {STAGE_LABELS[stage]}
                    </div>
                  );
                })}
                {streamSettled && events.length === 0 ? (
                  <div className="text-amber-700">
                    No progress events were received before the stream closed.
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </AppShell>
  );
}
