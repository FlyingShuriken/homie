"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  SAMPLE_RESULTS,
  fetchSessionResults,
  type Listing,
  type SessionResults,
} from "@/lib/homie";
import { formatCurrency, titleCase } from "@/lib/utils";

const maxPoints: Record<string, number> = {
  price: 30,
  location: 20,
  room_type: 15,
  transport: 5,
  furnished: 10,
  contact: 10,
  images: 5,
  gender: 5,
  parking: 8,
  pet: 4,
};

export default function ListingDetailPage() {
  const params = useParams<{ id: string; listingId: string }>();
  const [results, setResults] = useState<SessionResults | null>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const payload = await fetchSessionResults(params.id);
        if (mounted) setResults(payload);
      } catch {
        if (mounted) setResults(SAMPLE_RESULTS);
      }
    }

    void load();

    return () => {
      mounted = false;
    };
  }, [params.id]);

  const listing = useMemo<Listing | undefined>(
    () =>
      (results?.listings ?? SAMPLE_RESULTS.listings).find(
        (item) => item.id === params.listingId,
      ),
    [params.listingId, results],
  );

  if (!listing) {
    return (
      <AppShell>
        <main className="mx-auto max-w-4xl px-4 py-14 text-sm text-stone-500">
          Listing not found.
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href={`/results/${params.id}`}>
            <Button variant="ghost">Back to results</Button>
          </Link>
          <Badge variant="success">Top pick view</Badge>
          <Badge variant="outline">{listing.id}</Badge>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          <div className="space-y-8">
            <section>
              <h1 className="font-display text-6xl leading-none text-stone-950">
                {listing.location_area}
              </h1>
              <p className="mt-4 max-w-3xl text-lg leading-8 text-stone-600">
                {listing.title}
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Badge variant="default">{titleCase(listing.room_type)}</Badge>
                <Badge variant="outline">{titleCase(listing.furnished_status)}</Badge>
                <Badge variant="info">
                  {listing.nearby_transport[0] ?? "Transport unknown"}
                </Badge>
              </div>
            </section>

            <Card className="overflow-hidden border-stone-300">
              <div className="h-72 bg-[linear-gradient(150deg,_rgba(249,115,22,0.9),_rgba(251,191,36,0.5)),radial-gradient(circle_at_top,_rgba(255,255,255,0.38),_transparent_42%)]" />
            </Card>

            <Card className="border-stone-300">
              <CardContent className="space-y-5 p-6">
                <div>
                  <h2 className="text-2xl font-semibold text-stone-950">
                    Score breakdown
                  </h2>
                  <p className="mt-2 text-sm text-stone-500">
                    Each dimension maps back to the backend scoring model.
                  </p>
                </div>

                <div className="space-y-4">
                  {Object.entries(listing.score_breakdown ?? {}).map(([key, value]) => {
                    const max = maxPoints[key] ?? 10;
                    const width = Math.min(100, Math.round((value / max) * 100));
                    return (
                      <div
                        key={key}
                        className="grid gap-3 sm:grid-cols-[140px_1fr_60px] sm:items-center"
                      >
                        <div className="text-sm font-medium capitalize text-stone-800">
                          {key.replace("_", " ")}
                        </div>
                        <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                          <div
                            className="h-full rounded-full bg-orange-500"
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <div className="text-sm text-stone-500">
                          {value}/{max}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card className="border-stone-300 bg-orange-50">
              <CardContent className="space-y-3 p-6">
                <div className="text-xs uppercase tracking-[0.24em] text-orange-600">
                  Agent explanation
                </div>
                <p className="text-sm leading-7 text-stone-700">
                  {listing.score_explanation}
                </p>
              </CardContent>
            </Card>
          </div>

          <aside>
            <Card className="sticky top-24 border-stone-300 bg-white/95">
              <CardContent className="space-y-6 p-6">
                <div>
                  <div className="text-xs uppercase tracking-[0.24em] text-stone-400">
                    Monthly rent
                  </div>
                  <div className="mt-2 font-display text-5xl leading-none text-stone-950">
                    {listing.price_rm === null ? "Nego" : `RM${listing.price_rm}`}
                  </div>
                  <div className="mt-2 text-sm text-stone-500">
                    {listing.deposit_rm
                      ? `Deposit ${formatCurrency(listing.deposit_rm)}`
                      : "Deposit not provided"}
                  </div>
                </div>

                <div className="space-y-3 text-sm text-stone-600">
                  <DetailRow
                    label="Gender"
                    value={titleCase(listing.gender_restriction)}
                  />
                  <DetailRow label="Parking" value={titleCase(listing.parking)} />
                  <DetailRow
                    label="Facilities"
                    value={(listing.facilities ?? []).join(", ") || "Unknown"}
                  />
                </div>

                <Link href={`/results/${params.id}/listing/${listing.id}/outreach`}>
                  <Button variant="secondary" size="lg" className="w-full justify-center">
                    Prepare inquiry
                  </Button>
                </Link>
                <a href={listing.url} target="_blank" rel="noreferrer">
                  <Button variant="outline" size="lg" className="w-full justify-center">
                    Open source listing
                  </Button>
                </a>
              </CardContent>
            </Card>
          </aside>
        </div>
      </main>
    </AppShell>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[90px_1fr] gap-3">
      <div className="text-stone-400">{label}</div>
      <div className="font-medium text-stone-800">{value}</div>
    </div>
  );
}
