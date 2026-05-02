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
  PIPELINE_STAGES,
  type PipelineStatus,
  type ProgressEventData,
} from "@/lib/homie";

const TRACKED_STAGE_KEYS = new Set(PIPELINE_STAGES.map((stage) => stage.key));

export default function WorkflowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [events, setEvents] = useState<ProgressEventData[]>([]);
  const [elapsed, setElapsed] = useState(0);
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
      const timer = window.setTimeout(() => {
        router.replace(`/results/${id}`);
      }, 500);
      return () => window.clearTimeout(timer);
    }
  }, [id, router, status]);

  useEffect(() => {
    setElapsed(0);
  }, [id]);

  useEffect(() => {
    if (status === "complete" || status === "partial" || status === "failed") {
      return;
    }

    const interval = window.setInterval(() => {
      setElapsed((current) => current + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [status]);

  const progress = useMemo(() => {
    if (status === "complete" || status === "partial") return 100;
    if (events.length === 0) return 8;
    const completed = new Set(
      events
        .filter(
          (event) =>
            TRACKED_STAGE_KEYS.has(event.stage) && event.status === "complete",
        )
        .map((event) => event.stage),
    ).size;
    return Math.min(90, 12 + completed * 16);
  }, [events, status]);

  const currentStage = useMemo(() => {
    const active = [...events].reverse().find(
      (e) =>
        TRACKED_STAGE_KEYS.has(e.stage) &&
        (e.status === "running" || e.status === "started"),
    );
    if (active) return active.stage;
    const last = [...events].reverse().find(
      (e) => TRACKED_STAGE_KEYS.has(e.stage) && e.status === "complete",
    );
    return last?.stage ?? PIPELINE_STAGES[0]?.key ?? "validate";
  }, [events]);

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
                  Homie is validating your filters, scraping sources, and ranking
                  matches in real time. You&apos;ll land on the results board as
                  soon as the shortlist is ready.
                </p>
                <Progress value={progress} />
                <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-400">
                  <span>{elapsed}s elapsed</span>
                  {elapsed > 35 ? (
                    <span className="text-amber-500">
                      Taking longer than usual. Still running...
                    </span>
                  ) : null}
                </div>
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
