"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import FacebookLoginPrompt from "@/components/FacebookLoginPrompt";
import ListingCard from "@/components/ListingCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  API_URL,
  SAMPLE_RESULTS,
  fetchSessionResults,
  type SessionResults,
} from "@/lib/homie";
import { cn } from "@/lib/utils";
import { toQueryString } from "@/lib/utils";

export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [results, setResults] = useState<SessionResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<"score" | "price_asc" | "price_desc">("score");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [fbLoginRequired, setFbLoginRequired] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState<"idle" | "sending" | "done" | "error">("idle");

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const payload = await fetchSessionResults(id);
        if (!mounted) return;
        setResults(payload);
      } catch {
        if (!mounted) return;
        setResults({ ...SAMPLE_RESULTS, session_id: id });
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();

    return () => {
      mounted = false;
    };
  }, [id]);

  // Listen for fb_login_required SSE event from the pipeline
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`${API_URL}/api/search/${id}/stream`);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as { stage: string; status: string };
        if (data.stage === "fb_login_required") {
          setFbLoginRequired(true);
        }
        if (data.stage === "orchestrator" && (data.status === "complete" || data.status === "failed")) {
          es.close();
        }
      } catch {}
    };

    es.onerror = () => es.close();

    return () => es.close();
  }, [id]);

  const sources = useMemo(
    () =>
      Array.from(
        new Set((results?.listings ?? []).map((listing) => listing.source_primary)),
      ),
    [results],
  );

  const sortedListings = useMemo(() => {
    const listings = [...(results?.listings ?? [])];
    const filtered =
      sourceFilter === "all"
        ? listings
        : listings.filter((listing) => listing.source_primary === sourceFilter);

    return filtered.sort((a, b) => {
      if (sortBy === "score") return (b.match_score ?? 0) - (a.match_score ?? 0);
      if (sortBy === "price_asc") return (a.price_rm ?? 999999) - (b.price_rm ?? 999999);
      return (b.price_rm ?? 0) - (a.price_rm ?? 0);
    });
  }, [results, sortBy, sourceFilter]);

  async function handleStartTelegramOutreach() {
    setTelegramStatus("sending");
    try {
      const res = await fetch(`${API_URL}/api/outreach/telegram/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: id }),
      });
      if (res.ok) setTelegramStatus("done");
      else setTelegramStatus("error");
    } catch {
      setTelegramStatus("error");
    }
  }

  function handleAdjustSearch() {
    const filters = results?.filters ?? {};
    const query = toQueryString(filters);
    router.push(query ? `/search?${query}` : "/search");
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Badge variant="outline">Results board</Badge>
          <Badge variant="success">{results?.pipeline_status ?? "complete"}</Badge>
          <Badge variant="info">Session {id}</Badge>
          <Button variant="ghost" className="ml-auto" onClick={handleAdjustSearch}>
            Adjust search
          </Button>
          <button
            onClick={handleStartTelegramOutreach}
            disabled={telegramStatus === "sending" || telegramStatus === "done"}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition",
              telegramStatus === "done"
                ? "bg-emerald-100 text-emerald-700"
                : telegramStatus === "error"
                  ? "bg-red-100 text-red-600"
                  : "bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-60",
            )}
          >
            {telegramStatus === "done"
              ? "✓ Outreach sent"
              : telegramStatus === "error"
                ? "Outreach failed"
                : telegramStatus === "sending"
                  ? "Contacting agents…"
                  : "Start Telegram outreach"}
          </button>
        </div>

        <div className="mb-10 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div>
            <h1 className="font-display text-5xl leading-none text-stone-950 sm:text-6xl">
              {sortedListings.length} strong matches, ranked for action.
            </h1>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-stone-600">
              {results?.summary_report ??
                "Your shortlist is ready. Review the fit tags, inspect the score breakdown, then move into outreach from the best listing."}
            </p>
          </div>
          <Card className="border-stone-300 bg-white/90">
            <CardContent className="grid grid-cols-2 gap-4 p-6">
              <Stat label="Listings found" value={String(results?.listings.length ?? 0)} />
              <Stat label="Sources active" value={String(sources.length || 2)} />
              <Stat label="Top score" value={String(sortedListings[0]?.match_score ?? 0)} />
              <Stat
                label="Flags"
                value={String(
                  sortedListings.reduce(
                    (sum, item) => sum + item.low_confidence_flags.length,
                    0,
                  ),
                )}
              />
            </CardContent>
          </Card>
        </div>

        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Select
            className="w-48"
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
          >
            <option value="score">Best match</option>
            <option value="price_asc">Price low to high</option>
            <option value="price_desc">Price high to low</option>
          </Select>

          {sources.length > 1 ? (
            <Select
              className="w-44"
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value)}
            >
              <option value="all">All sources</option>
              {sources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </Select>
          ) : null}
        </div>

        <div className="space-y-5">
          {loading ? (
            <Card className="border-stone-300">
              <CardContent className="p-8 text-sm text-stone-500">
                Loading ranked listings...
              </CardContent>
            </Card>
          ) : null}

          {!loading && sortedListings.length === 0 ? (
            <Card className="border-stone-300">
              <CardContent className="p-8 text-sm text-stone-500">
                No listings matched the current filters.
              </CardContent>
            </Card>
          ) : null}

          {sortedListings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} sessionId={id} />
          ))}
        </div>
      </main>

      {fbLoginRequired && (
        <FacebookLoginPrompt onDismiss={() => setFbLoginRequired(false)} />
      )}
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-display text-4xl leading-none text-stone-950">{value}</div>
      <div className="mt-2 text-xs uppercase tracking-[0.24em] text-stone-400">
        {label}
      </div>
    </div>
  );
}
