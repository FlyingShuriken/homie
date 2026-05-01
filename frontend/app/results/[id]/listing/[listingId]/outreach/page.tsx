"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import OutreachModal from "@/components/OutreachModal";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import {
  fetchSessionResults,
  type Listing,
  type SessionResults,
} from "@/lib/homie";

export default function OutreachPage() {
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

  if (fetchError) {
    return (
      <AppShell>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <p className="text-sm text-red-600">Could not load listing — the backend may be unavailable.</p>
        </main>
      </AppShell>
    );
  }

  if (!results) {
    return (
      <AppShell>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <div className="flex items-center gap-3 text-sm text-stone-500">
            <Spinner />
            Fetching listing…
          </div>
        </main>
      </AppShell>
    );
  }

  if (!listing) {
    return (
      <AppShell>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <p className="text-sm text-stone-500">Listing not found.</p>
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8">
          <Link href={`/results/${params.id}/listing/${params.listingId}`}>
            <Button variant="ghost">Back to listing</Button>
          </Link>
        </div>
        <OutreachModal listing={listing} sessionId={params.id} />
      </main>
    </AppShell>
  );
}
