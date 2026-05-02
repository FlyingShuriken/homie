"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  SCORE_MAX_POINTS,
  SCORE_DIMENSION_LABELS,
  fetchSessionResults,
  type Listing,
  type SessionResults,
} from "@/lib/homie";
import ListingMap from "@/components/ListingMap";
import { formatCurrency, titleCase } from "@/lib/utils";

export default function ListingDetailPage() {
  const params = useParams<{ id: string; listingId: string }>();
  const [results, setResults] = useState<SessionResults | null>(null);
  const [fetchError, setFetchError] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const payload = await fetchSessionResults(params.id);
        if (mounted) setResults(payload);
      } catch {
        if (mounted) setFetchError(true);
      }
    }

    void load();

    return () => {
      mounted = false;
    };
  }, [params.id]);

  const listing = useMemo<Listing | undefined>(
    () => results?.listings.find((item) => item.id === params.listingId),
    [params.listingId, results],
  );
  const roundedScore =
    listing?.match_score === null || listing?.match_score === undefined
      ? null
      : Math.round(listing.match_score);

  if (fetchError) {
    return (
      <AppShell>
        <main className="mx-auto max-w-4xl px-4 py-14">
          <Card className="border-red-200 bg-red-50">
            <CardContent className="p-8 text-sm text-red-700">
              Could not load listing — the backend may be unavailable.
            </CardContent>
          </Card>
        </main>
      </AppShell>
    );
  }

  if (!results) {
    return (
      <AppShell>
        <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <div className="mb-8 flex gap-3">
            <div className="h-9 w-32 animate-pulse rounded-lg bg-stone-300" />
            <div className="h-9 w-24 animate-pulse rounded-full bg-stone-300" />
          </div>
          <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
            <div className="space-y-8">
              <div className="space-y-4">
                <div className="h-14 w-3/4 animate-pulse rounded-xl bg-stone-300" />
                <div className="h-5 w-full animate-pulse rounded bg-stone-200" />
                <div className="h-5 w-2/3 animate-pulse rounded bg-stone-200" />
                <div className="flex gap-2">
                  <div className="h-6 w-20 animate-pulse rounded-full bg-stone-300" />
                  <div className="h-6 w-24 animate-pulse rounded-full bg-stone-300" />
                  <div className="h-6 w-28 animate-pulse rounded-full bg-stone-300" />
                </div>
              </div>
              <div className="h-72 animate-pulse rounded-2xl bg-stone-300" />
              <div className="space-y-4 rounded-2xl border border-stone-300 bg-white/60 p-6">
                <div className="h-7 w-40 animate-pulse rounded bg-stone-300" />
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <div className="h-4 w-28 animate-pulse rounded bg-stone-200" />
                    <div className="h-3 flex-1 animate-pulse rounded-full bg-stone-300" />
                    <div className="h-4 w-10 animate-pulse rounded bg-stone-200" />
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-4 rounded-2xl border border-stone-300 bg-white/60 p-6">
              <div className="h-4 w-24 animate-pulse rounded bg-stone-200" />
              <div className="h-12 w-36 animate-pulse rounded-xl bg-stone-300" />
              <div className="h-4 w-40 animate-pulse rounded bg-stone-200" />
              <div className="mt-4 space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex justify-between">
                    <div className="h-4 w-20 animate-pulse rounded bg-stone-200" />
                    <div className="h-4 w-28 animate-pulse rounded bg-stone-200" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </AppShell>
    );
  }

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
          <Badge
            variant={
              listing.match_score !== null && listing.match_score >= 75
                ? "success"
                : "outline"
            }
          >
            Score {roundedScore ?? "—"}/100
          </Badge>
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
              {listing.images && listing.images.length > 0 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={listing.images[0]}
                  alt={listing.title}
                  className="h-72 w-full object-cover"
                />
              ) : (
                <div className="h-72 bg-[linear-gradient(150deg,_rgba(249,115,22,0.9),_rgba(251,191,36,0.5)),radial-gradient(circle_at_top,_rgba(255,255,255,0.38),_transparent_42%)]" />
              )}
            </Card>

            {listing.lat && listing.lng && (
              <ListingMap
                lat={listing.lat}
                lng={listing.lng}
                title={listing.title}
                transportStops={listing.transport_stops}
              />
            )}

            {listing.google_place?.rating !== null &&
              listing.google_place?.rating !== undefined && (
                <GoogleReviewsCard listing={listing} />
              )}

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
                    const max = SCORE_MAX_POINTS[key] ?? 10;
                    const width = Math.min(100, Math.round((value / max) * 100));
                    const pct = value / max;
                    const barColor =
                      pct >= 0.7
                        ? "bg-green-500"
                        : pct >= 0.3
                          ? "bg-yellow-400"
                          : "bg-red-400";
                    const comment =
                      listing.score_breakdown_comments?.[key];
                    return (
                      <div key={key} className="space-y-1">
                        <div className="grid gap-3 sm:grid-cols-[140px_1fr_60px] sm:items-center">
                          <div className="text-sm font-medium text-stone-800">
                            {SCORE_DIMENSION_LABELS[key] ?? key.replace(/_/g, " ")}
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                            <div
                              className={`h-full rounded-full ${barColor}`}
                              style={{ width: `${width}%` }}
                            />
                          </div>
                          <div className="text-sm text-stone-500">
                            {value}/{max}
                          </div>
                        </div>
                        {comment && (
                          <div className="text-xs text-stone-400 sm:pl-[calc(140px+0.75rem)]">
                            {comment}
                          </div>
                        )}
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

function GoogleReviewsCard({ listing }: { listing: Listing }) {
  const place = listing.google_place;
  if (!place || place.rating === null || place.rating === undefined) return null;

  const reviewCount =
    place.user_rating_count === null || place.user_rating_count === undefined
      ? "Review count unavailable"
      : `${place.user_rating_count.toLocaleString()} Google reviews`;
  const placeName = place.name || listing.location_area;
  const reviews = (place.reviews ?? []).slice(0, 3);

  return (
    <Card className="border-stone-300">
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-stone-400">
              Reviews from Google
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-stone-950">
              {place.google_maps_uri ? (
                <a
                  href={place.google_maps_uri}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-orange-600"
                >
                  {placeName}
                </a>
              ) : (
                placeName
              )}
            </h2>
          </div>
          <div className="min-w-32 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-right">
            <div className="text-3xl font-semibold leading-none text-stone-950">
              {place.rating.toFixed(1)}
            </div>
            <div className="mt-1 text-xs font-medium uppercase tracking-[0.18em] text-stone-400">
              out of 5
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm text-stone-500">
          <span>{reviewCount}</span>
          {place.match_confidence !== null && place.match_confidence !== undefined ? (
            <span>Match confidence {Math.round(place.match_confidence * 100)}%</span>
          ) : null}
        </div>

        {reviews.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-3">
            {reviews.map((review, index) => (
              <div
                key={`${review.author_name}-${index}`}
                className="rounded-2xl border border-stone-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    {review.author_uri ? (
                      <a
                        href={review.author_uri}
                        target="_blank"
                        rel="noreferrer"
                        className="block truncate text-sm font-semibold text-stone-900 hover:text-orange-600"
                      >
                        {review.author_name || "Google reviewer"}
                      </a>
                    ) : (
                      <div className="truncate text-sm font-semibold text-stone-900">
                        {review.author_name || "Google reviewer"}
                      </div>
                    )}
                    <div className="mt-1 text-xs text-stone-400">
                      {review.relative_publish_time_description}
                    </div>
                  </div>
                  {review.rating !== null && review.rating !== undefined ? (
                    <div className="shrink-0 rounded-full bg-orange-50 px-2 py-1 text-xs font-semibold text-orange-700">
                      {review.rating.toFixed(0)}/5
                    </div>
                  ) : null}
                </div>
                <p className="mt-3 max-h-28 overflow-hidden break-words text-sm leading-6 text-stone-600">
                  {review.text}
                </p>
                {review.google_maps_uri ? (
                  <a
                    href={review.google_maps_uri}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-block text-xs font-semibold text-orange-700 hover:text-orange-600"
                  >
                    Open on Google Maps
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
