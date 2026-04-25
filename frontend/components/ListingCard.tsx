"use client";

import Link from "next/link";
import { useState } from "react";
import type { Listing } from "@/lib/homie";
import { API_URL } from "@/lib/homie";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn, formatCurrency, titleCase } from "@/lib/utils";

const SOURCE_LABELS: Record<string, string> = {
  ibilik: "ibilik",
  iproperty: "iProperty",
  propertyguru: "PropertyGuru",
  facebook: "Facebook",
};

export default function ListingCard({
  listing,
  sessionId,
}: {
  listing: Listing;
  sessionId: string;
}) {
  const [outreachStatus, setOutreachStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [outreachError, setOutreachError] = useState<string | null>(null);

  const hasContact = Boolean(listing.contact_phone || listing.contact_telegram);

  async function handleTelegramOutreach() {
    setOutreachStatus("sending");
    setOutreachError(null);
    try {
      const res = await fetch(`${API_URL}/api/outreach/telegram/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, listing_ids: [listing.id] }),
      });
      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
        setOutreachError(payload?.detail ?? "Outreach failed.");
        setOutreachStatus("error");
        return;
      }
      setOutreachStatus("done");
    } catch {
      setOutreachError("Request failed.");
      setOutreachStatus("error");
    }
  }
  const score = Math.round(listing.match_score ?? 0);

  return (
    <Card className="overflow-hidden border-stone-300">
      <div className="grid gap-0 lg:grid-cols-[280px_1fr_220px]">
        <div className="relative min-h-64 border-b border-stone-200 bg-[linear-gradient(145deg,_rgba(249,115,22,0.9),_rgba(251,191,36,0.55)),radial-gradient(circle_at_top,_rgba(255,255,255,0.45),_transparent_48%)] p-5 lg:border-b-0 lg:border-r">
          <div className="absolute inset-x-5 top-5 flex items-start justify-between">
            <Badge variant="outline" className="border-white/50 bg-white/70 backdrop-blur">
              {SOURCE_LABELS[listing.source_primary] ?? listing.source_primary}
            </Badge>
            <div
              className={`rounded-full px-4 py-2 text-sm font-semibold ${
                score >= 75
                  ? "bg-emerald-600 text-white"
                  : score >= 50
                  ? "bg-amber-400 text-stone-900"
                  : "bg-red-500 text-white"
              }`}
            >
              {score}/100
            </div>
          </div>
          <div className="absolute bottom-5 left-5 right-5 rounded-[24px] bg-white/85 p-4 backdrop-blur">
            <div className="font-display text-3xl leading-none text-stone-950">
              {listing.location_area}
            </div>
            <div className="mt-2 text-sm text-stone-600">{listing.location_city}</div>
          </div>
        </div>

        <CardContent className="space-y-5 p-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">{titleCase(listing.room_type)}</Badge>
              <Badge variant="outline">{titleCase(listing.furnished_status)}</Badge>
              {listing.gender_restriction && listing.gender_restriction !== "any" ? (
                <Badge variant="success">{titleCase(listing.gender_restriction)} only</Badge>
              ) : null}
            </div>
            <h3 className="text-xl font-semibold text-stone-950">{listing.title}</h3>
            <p className="max-w-2xl text-sm leading-6 text-stone-600">
              {listing.score_explanation ??
                "The agent ranked this listing based on budget fit, commute, furnishing, and contact quality."}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {(listing.rtb ?? []).slice(0, 4).map((item) => (
              <Badge
                key={item.text}
                variant={
                  item.tone === "strong"
                    ? "success"
                    : item.tone === "warn"
                    ? "warning"
                    : "info"
                }
              >
                {item.text}
              </Badge>
            ))}
            {listing.low_confidence_flags.map((flag) => (
              <Badge key={flag} variant="warning">
                Unverified: {flag}
              </Badge>
            ))}
            {(listing.needs_verification ?? []).map((req) => (
              <Badge key={req} variant="info">
                Ask agent: {req}
              </Badge>
            ))}
          </div>

          <div className="grid gap-4 text-sm text-stone-600 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label="Transport" value={listing.nearby_transport[0] ?? "Unknown"} />
            <Fact label="Parking" value={titleCase(listing.parking)} />
            <Fact
              label="Sources"
              value={`${listing.source_variants.length} checked`}
            />
            <Fact label="Outreach" value={titleCase(listing.outreach_status)} />
          </div>
        </CardContent>

        <div className="flex flex-col gap-4 border-t border-stone-200 bg-stone-50 p-6 lg:border-l lg:border-t-0">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-stone-500">
              Monthly rent
            </div>
            <div className="mt-2 font-display text-5xl leading-none text-stone-950">
              {listing.price_rm === null ? "Nego" : `RM${listing.price_rm}`}
            </div>
            <div className="mt-2 text-sm text-stone-500">
              {listing.deposit_rm
                ? `Deposit ${formatCurrency(listing.deposit_rm)}`
                : "Deposit not specified"}
            </div>
          </div>

          <div className="mt-auto space-y-3">
            <Link href={`/results/${sessionId}/listing/${listing.id}`} className="block">
              <Button variant="secondary" size="lg" className="w-full justify-center">
                View details
              </Button>
            </Link>
            <a href={listing.url} target="_blank" rel="noreferrer" className="block">
              <Button variant="outline" size="lg" className="w-full justify-center">
                Open source listing
              </Button>
            </a>
            {hasContact ? (
              <>
                <button
                  onClick={() => void handleTelegramOutreach()}
                  disabled={outreachStatus === "sending" || outreachStatus === "done"}
                  className={cn(
                    "flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    outreachStatus === "done"
                      ? "bg-emerald-100 text-emerald-700"
                      : outreachStatus === "error"
                      ? "bg-red-100 text-red-600 hover:bg-red-200"
                      : "bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-60",
                  )}
                >
                  {outreachStatus !== "done" && (
                    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 fill-current" aria-hidden="true">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.94z" />
                    </svg>
                  )}
                  {outreachStatus === "done"
                    ? "✓ Message sent"
                    : outreachStatus === "sending"
                    ? "Sending…"
                    : outreachStatus === "error"
                    ? "Retry outreach"
                    : "Message on Telegram"}
                </button>
                {outreachError && (
                  <p className="text-center text-xs text-red-500">{outreachError}</p>
                )}
              </>
            ) : (
              <div className="text-center text-xs text-stone-400">
                No contact details captured
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.22em] text-stone-400">{label}</div>
      <div className="mt-1 font-medium text-stone-800">{value}</div>
    </div>
  );
}
