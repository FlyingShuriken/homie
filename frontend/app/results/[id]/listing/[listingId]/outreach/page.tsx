"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import OutreachModal from "@/components/OutreachModal";
import { Button } from "@/components/ui/button";
import {
  SAMPLE_RESULTS,
  fetchSessionResults,
  type Listing,
  type SessionResults,
} from "@/lib/homie";

export default function OutreachPage() {
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
    return null;
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8">
          <Link href={`/results/${params.id}/listing/${params.listingId}`}>
            <Button variant="ghost">Back to listing</Button>
          </Link>
        </div>
        <OutreachModal listing={listing} />
      </main>
    </AppShell>
  );
}
