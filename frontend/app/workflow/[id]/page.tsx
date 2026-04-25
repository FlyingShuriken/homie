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
  SAMPLE_EVENTS,
  type PipelineStatus,
  type ProgressEventData,
} from "@/lib/homie";

export default function WorkflowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [events, setEvents] = useState<ProgressEventData[]>([]);
  const [status, setStatus] = useState<PipelineStatus>("running");

  useEffect(() => {
    if (!id) return;

    const source = new EventSource(`${API_URL}/api/search/${id}/stream`);

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
        // skip malformed frame
      }
    };

    source.onerror = async () => {
      source.close();
      try {
        const res = await fetch(`${API_URL}/api/search/${id}/results`, {
          cache: "no-store",
        });
        if (res.ok) {
          const payload = (await res.json()) as { pipeline_status: PipelineStatus };
          setStatus(payload.pipeline_status);
        }
      } catch {
        // leave events as-is
      }
    };

    return () => source.close();
  }, [id]);

  useEffect(() => {
    if (status === "complete" || status === "partial") {
      router.replace(`/results/${id}`);
    }
  }, [id, router, status]);

  const progress = useMemo(() => {
    if (events.length === 0) return 18;
    const completed = events.filter((event) => event.status === "complete").length;
    return Math.min(92, 24 + completed * 16);
  }, [events]);

  const currentStage = useMemo(() => {
    const active = [...events].reverse().find(
      (e) => e.status === "running" || e.status === "started",
    );
    if (active) return active.stage;
    const last = [...events].reverse().find((e) => e.status === "complete");
    return last?.stage ?? "validate";
  }, [events]);

  const PIPELINE_STAGES: { key: string; label: string }[] = [
    { key: "validate", label: "Validate filters" },
    { key: "scrape", label: "Scrape sources" },
    { key: "normalize", label: "Normalize fields" },
    { key: "score", label: "Score listings" },
    { key: "report", label: "Write summary report" },
  ];

  const items = events.length > 0 ? events : SAMPLE_EVENTS;

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
                  This route is now dedicated to the live pipeline state instead of mixing progress and results into one view. When scoring completes, the app redirects to the results board.
                </p>
                <Progress value={progress} />
              </div>

              <ProgressFeed events={items} />
            </CardContent>
          </Card>

          <Card className="border-stone-300 bg-white/90">
            <CardContent className="space-y-5 p-6">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-stone-400">
                  Current focus
                </div>
                <div className="mt-2 text-lg font-semibold text-stone-950">
                  {PIPELINE_STAGES.find((s) => s.key === currentStage)?.label ?? "Processing"}
                </div>
              </div>
              <div className="space-y-4 text-sm text-stone-600">
                {PIPELINE_STAGES.map((stage) => {
                  const isCurrent = stage.key === currentStage;
                  const isDone = events.some(
                    (e) => e.stage === stage.key && e.status === "complete",
                  );
                  return (
                    <div
                      key={stage.key}
                      className={`flex items-center gap-2 transition-colors duration-300 ${
                        isCurrent
                          ? "font-semibold text-orange-600"
                          : isDone
                          ? "text-emerald-600"
                          : ""
                      }`}
                    >
                      {isCurrent ? (
                        <span className="relative flex h-2 w-2 shrink-0">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-75" />
                          <span className="relative inline-flex h-2 w-2 rounded-full bg-orange-500" />
                        </span>
                      ) : isDone ? (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400" />
                      ) : (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-stone-200" />
                      )}
                      {stage.label}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </AppShell>
  );
}
