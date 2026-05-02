"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import FacebookLoginPrompt from "@/components/FacebookLoginPrompt";
import TelegramSetupModal from "@/components/TelegramSetupModal";
import ListingCard from "@/components/ListingCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  API_URL,
  fetchSessionResults,
  getTelegramStatus,
  type SessionResults,
  type TelegramStatus,
} from "@/lib/homie";
import { toQueryString } from "@/lib/utils";

export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [results, setResults] = useState<SessionResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [sortBy, setSortBy] = useState<"score" | "price_asc" | "price_desc">(
    "score",
  );
  const [sourceFilter, setSourceFilter] = useState("all");
  const [fbLoginRequired, setFbLoginRequired] = useState(false);
  const [showTelegramSetup, setShowTelegramSetup] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);

  useEffect(() => {
    getTelegramStatus()
      .then((status) => setTelegramStatus(status))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const payload = await fetchSessionResults(id);
        if (!mounted) return;
        setResults(payload);
      } catch {
        if (!mounted) return;
        setFetchError(true);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();

    return () => {
      mounted = false;
    };
  }, [id]);

  // Check if Facebook login is required via dedicated endpoint (avoids competing SSE consumer)
  useEffect(() => {
    if (!id) return;
    void fetch(`${API_URL}/api/search/${id}/fb_status`)
      .then((res) =>
        res.ok ? (res.json() as Promise<{ fb_login_required: boolean }>) : null,
      )
      .then((data) => {
        if (data?.fb_login_required) setFbLoginRequired(true);
      })
      .catch(() => {});
  }, [id]);

  const sources = useMemo(
    () =>
      Array.from(
        new Set(
          (results?.listings ?? []).map((listing) => listing.source_primary),
        ),
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
      if (sortBy === "score")
        return (b.match_score ?? 0) - (a.match_score ?? 0);
      if (sortBy === "price_asc")
        return (a.price_rm ?? 999999) - (b.price_rm ?? 999999);
      return (b.price_rm ?? 0) - (a.price_rm ?? 0);
    });
  }, [results, sortBy, sourceFilter]);

  function handleAdjustSearch() {
    const filters = results?.filters ?? {};
    const query = toQueryString(filters);
    router.push(query ? `/search?${query}` : "/search");
  }

  const telegramDemoRequested = results?.filters?.enable_telegram_outreach !== false;
  const telegramStatusReady = Boolean(
    telegramStatus?.configured &&
      telegramStatus.demo_target_configured &&
      telegramStatus.authenticated,
  );
  const telegramOutreachAvailable = Boolean(
    telegramDemoRequested &&
      ((results?.capabilities.telegram_outreach ?? false) || telegramStatusReady),
  );
  const resultsHeadline = loading
    ? "Loading results..."
    : sortedListings.length === 0
      ? "No matches found."
      : sortedListings.length === 1
        ? "One match found."
        : `${sortedListings.length} listings, ranked by fit.`;
  const searchLocation = results?.filters?.location;
  const sessionLabel =
    typeof searchLocation === "string" && searchLocation.trim()
      ? `Search · ${searchLocation}`
      : `Session ${id.slice(0, 8)}`;

  if (fetchError) {
    return (
      <AppShell>
        <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <Card className="border-red-200 bg-red-50">
            <CardContent className="p-8 text-sm text-red-700">
              Could not load results — the backend may be unavailable. Check
              that the server is running and try again.
            </CardContent>
          </Card>
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Badge variant="outline">Results board</Badge>
          <Badge variant="success">
            {results?.pipeline_status ?? "complete"}
          </Badge>
          <Badge variant="info">{sessionLabel}</Badge>
          <Button
            variant="ghost"
            className="ml-auto"
            onClick={handleAdjustSearch}
          >
            Adjust search
          </Button>
        </div>

        {results?.pipeline_status === "failed" ? (
          <Card className="mb-8 border-amber-200 bg-amber-50">
            <CardContent className="p-4 text-sm text-amber-800">
              The pipeline encountered an error — results shown may be
              incomplete. Check backend logs for details.
            </CardContent>
          </Card>
        ) : null}

        <div className="mb-10 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div>
            <h1 className="font-display text-5xl leading-none text-stone-950 sm:text-6xl">
              {resultsHeadline}
            </h1>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-stone-600">
              {results?.summary_report ??
                "Your shortlist is ready. Review the fit tags, inspect the score breakdown, then move into outreach from the best listing."}
            </p>
          </div>
          <Card className="border-stone-300 bg-white/90">
            <CardContent className="space-y-4 p-6">
              <div className="grid grid-cols-2 gap-4">
                <Stat
                  label="Listings found"
                  value={String(results?.listings.length ?? 0)}
                />
                <Stat label="Sources active" value={String(sources.length)} />
                <Stat
                  label="Top score"
                  value={String(sortedListings[0]?.match_score ?? 0)}
                />
                <Stat
                  label="Flags"
                  value={String(
                    sortedListings.reduce(
                      (sum, item) => sum + item.low_confidence_flags.length,
                      0,
                    ),
                  )}
                />
              </div>
              {!loading &&
              telegramDemoRequested &&
              !telegramOutreachAvailable &&
              telegramStatus?.runtime_setup_enabled ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-auto justify-start px-0 text-sm text-blue-600 hover:bg-transparent hover:text-blue-700"
                  onClick={() => setShowTelegramSetup(true)}
                >
                  Set up Telegram demo
                </Button>
              ) : null}
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

        <div className="mb-6 flex flex-wrap items-center gap-4 text-xs text-stone-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-score-high" />
            Strong match (75-100)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-score-mid" />
            Partial match (50-74)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-score-low" />
            Weak match (&lt;50)
          </span>
        </div>

        <div className="space-y-5">
          {loading ? (
            <>
              {[0, 1, 2, 3].map((i) => (
                <Card key={i} className="overflow-hidden border-stone-300">
                  <div className="grid animate-pulse gap-0 lg:grid-cols-[280px_1fr_220px]">
                    <div className="min-h-64 bg-stone-200" />
                    <div className="space-y-4 p-6">
                      <div className="h-4 w-1/3 rounded bg-stone-200" />
                      <div className="h-5 w-3/4 rounded bg-stone-200" />
                      <div className="h-4 w-full rounded bg-stone-200" />
                      <div className="h-4 w-5/6 rounded bg-stone-200" />
                    </div>
                    <div className="space-y-3 border-t border-stone-200 bg-stone-50 p-6 lg:border-l lg:border-t-0">
                      <div className="h-10 w-2/3 rounded bg-stone-200" />
                      <div className="h-8 rounded bg-stone-200" />
                      <div className="h-8 rounded bg-stone-200" />
                    </div>
                  </div>
                </Card>
              ))}
            </>
          ) : null}

          {!loading && sortedListings.length === 0 ? (
            <Card className="border-stone-300">
              <CardContent className="p-8 text-sm text-stone-500">
                No listings matched the current filters.
              </CardContent>
            </Card>
          ) : null}

          {sortedListings.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              sessionId={id}
              telegramDemoAvailable={telegramOutreachAvailable}
            />
          ))}
        </div>
      </main>

      {fbLoginRequired && (
        <FacebookLoginPrompt onDismiss={() => setFbLoginRequired(false)} />
      )}

      {showTelegramSetup && (
        <TelegramSetupModal
          onSuccess={() => {
            setTelegramStatus((current) =>
              current
                ? {
                    ...current,
                    configured: true,
                    authenticated: true,
                    demo_target_configured: true,
                  }
                : {
                    configured: true,
                    authenticated: true,
                    demo_target_configured: true,
                    runtime_setup_enabled: true,
                    operator_token_required: false,
                  },
            );
            setShowTelegramSetup(false);
          }}
          onDismiss={() => setShowTelegramSetup(false)}
          operatorTokenRequired={telegramStatus?.operator_token_required ?? false}
          demoTargetConfigured={telegramStatus?.demo_target_configured ?? false}
        />
      )}
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-display text-4xl leading-none text-stone-950">
        {value}
      </div>
      <div className="mt-2 text-xs uppercase tracking-[0.24em] text-stone-400">
        {label}
      </div>
    </div>
  );
}
