"use client";

import Link from "next/link";
import type { Listing } from "@/lib/homie";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, titleCase } from "@/lib/utils";

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
  const score = Math.round(listing.match_score ?? 0);
  const hasContact = Boolean(listing.contact_phone || listing.contact_telegram);

  return (
    <Card className="overflow-hidden border-stone-300">
      <div className="grid gap-0 lg:grid-cols-[280px_1fr_220px]">
        <div className="relative min-h-64 border-b border-stone-200 bg-[linear-gradient(145deg,_rgba(249,115,22,0.9),_rgba(251,191,36,0.55)),radial-gradient(circle_at_top,_rgba(255,255,255,0.45),_transparent_48%)] p-5 lg:border-b-0 lg:border-r">
          <div className="absolute inset-x-5 top-5 flex items-start justify-between">
            <Badge variant="outline" className="border-white/50 bg-white/70 backdrop-blur">
              {SOURCE_LABELS[listing.source_primary] ?? listing.source_primary}
            </Badge>
            <div className="rounded-full bg-stone-950 px-4 py-2 text-sm font-semibold text-white">
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
              <Link
                href={`/results/${sessionId}/listing/${listing.id}/outreach`}
                className="block"
              >
                <Button variant="ghost" size="md" className="w-full justify-center">
                  Prepare inquiry
                </Button>
              </Link>
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
