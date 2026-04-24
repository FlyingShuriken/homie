"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ListingCard, { Listing } from "@/components/ListingCard";
import FacebookLoginPrompt from "@/components/FacebookLoginPrompt";
import OutreachModal from "@/components/OutreachModal";
import ProgressFeed, { ProgressEventData } from "@/components/ProgressFeed";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type PipelineStatus = "running" | "complete" | "partial" | "failed";

interface SessionResults {
  session_id: string;
  pipeline_status: PipelineStatus;
  summary_report: string | null;
  filters: Record<string, unknown>;
  listings: Listing[];
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [events, setEvents] = useState<ProgressEventData[]>([]);
  const [results, setResults] = useState<SessionResults | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>("running");
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [fbLoginRequired, setFbLoginRequired] = useState(false);
  const [sortBy, setSortBy] = useState<"score" | "price_asc" | "price_desc">("score");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const feedBottomRef = useRef<HTMLDivElement>(null);

  // Connect to SSE stream
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`${API}/api/search/${id}/stream`);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as ProgressEventData;
        setEvents((prev) => [...prev, data]);
        if (data.stage === "fb_login_required") {
          setFbLoginRequired(true);
        }
        // Orchestrator signals completion via complete or failed event
        if (data.stage === "orchestrator" && (data.status === "complete" || data.status === "failed")) {
          setPipelineStatus(data.status === "complete" ? "complete" : "failed");
          fetchResults();
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
      fetchResults();
    };

    return () => es.close();
  }, [id]);

  // Auto-scroll progress feed
  useEffect(() => {
    feedBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  async function fetchResults() {
    try {
      const res = await fetch(`${API}/api/search/${id}/results`);
      if (!res.ok) return;
      const data: SessionResults = await res.json();
      setResults(data);
      setPipelineStatus(data.pipeline_status);
    } catch {}
  }


  function sortedListings(): Listing[] {
    if (!results) return [];
    let list = results.listings;
    if (sourceFilter !== "all") list = list.filter((l) => l.source_primary === sourceFilter);
    return [...list].sort((a, b) => {
      if (sortBy === "score") return (b.match_score ?? 0) - (a.match_score ?? 0);
      if (sortBy === "price_asc") return (a.price_rm ?? 999999) - (b.price_rm ?? 999999);
      return (b.price_rm ?? 0) - (a.price_rm ?? 0);
    });
  }

  const sources = results
    ? [...new Set(results.listings.map((l) => l.source_primary))]
    : [];

  const isDone = pipelineStatus !== "running";

  function goToAdjustSearch() {
    const filters = results?.filters as Record<string, unknown> | undefined;
    if (!filters || Object.keys(filters).length === 0) {
      router.push("/");
      return;
    }
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v !== null && v !== undefined && v !== "") {
        params.set(k, String(v));
      }
    }
    router.push(`/?${params.toString()}`);
  }

  return (
    <main className="min-h-screen px-4 py-8 max-w-5xl mx-auto">
      {/* Nav */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={goToAdjustSearch}
          className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
        >
          ← Adjust search
        </button>
        <span className="text-gray-300">|</span>
        <span className="text-xs text-gray-400 font-mono">{id}</span>
        <span
          className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${
            pipelineStatus === "complete"
              ? "bg-green-100 text-green-700"
              : pipelineStatus === "failed"
              ? "bg-red-100 text-red-700"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {pipelineStatus}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: progress feed */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-gray-200 p-4 sticky top-6">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Pipeline progress
            </h2>
            <div className="max-h-80 overflow-y-auto">
              <ProgressFeed events={events} />
              <div ref={feedBottomRef} />
            </div>
          </div>
        </div>

        {/* Right: results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Summary report */}
          {results?.summary_report && (
            <div className="bg-brand-50 border border-brand-500/20 rounded-xl p-4">
              <p className="text-sm text-gray-700">{results.summary_report}</p>
            </div>
          )}

          {/* Controls */}
          {results && results.listings.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <select
                className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              >
                <option value="score">Sort: Best match</option>
                <option value="price_asc">Sort: Price low–high</option>
                <option value="price_desc">Sort: Price high–low</option>
              </select>
              {sources.length > 1 && (
                <select
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                >
                  <option value="all">All sources</option>
                  {sources.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                {sortedListings().length} listing{sortedListings().length !== 1 ? "s" : ""}
              </span>
            </div>
          )}

          {/* Listing cards */}
          {sortedListings().map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onPrepareInquiry={setSelectedListing}
            />
          ))}

          {/* Empty state */}
          {isDone && results && results.listings.length === 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <p className="text-gray-500 text-sm">No listings found for your filters.</p>
              <button
                onClick={goToAdjustSearch}
                className="mt-3 text-sm text-brand-600 hover:underline"
              >
                Try adjusting your search
              </button>
            </div>
          )}

          {/* Loading state */}
          {!isDone && results === null && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <div className="animate-pulse text-gray-400 text-sm">
                Searching across rental platforms…
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Outreach modal */}
      {selectedListing && (
        <OutreachModal
          listing={selectedListing}
          sessionId={id}
          onClose={() => setSelectedListing(null)}
        />
      )}

      {/* Facebook login prompt */}
      {fbLoginRequired && (
        <FacebookLoginPrompt onDismiss={() => setFbLoginRequired(false)} />
      )}
    </main>
  );
}
