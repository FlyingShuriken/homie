"use client";

import { useEffect, useState } from "react";
import type { Listing } from "@/lib/homie";
import { API_URL } from "@/lib/homie";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency } from "@/lib/utils";

function buildFallbackDraft(listing: Listing) {
  return `Hi, I saw your listing for ${listing.location_area} (${formatCurrency(
    listing.price_rm,
  )}/month) and I'm interested.\n\nCould I check if it is still available, whether viewing this weekend is possible, and if the deposit is fixed?\n\nThank you.`;
}

interface OutreachDraftResponse {
  drafts: Array<{
    listing_id: string;
    draft_text: string;
  }>;
}

export default function OutreachModal({
  listing,
  sessionId,
}: {
  listing: Listing;
  sessionId: string;
}) {
  const [draft, setDraft] = useState(() => buildFallbackDraft(listing));
  const [loading, setLoading] = useState(true);
  const [usingFallback, setUsingFallback] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    const fallbackDraft = buildFallbackDraft(listing);

    setLoading(true);
    setUsingFallback(false);
    setCopied(false);
    setDraft(fallbackDraft);

    async function loadDraft() {
      try {
        const res = await fetch(`${API_URL}/api/outreach/draft`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            listing_ids: [listing.id],
          }),
        });

        if (!res.ok) {
          throw new Error("Draft request failed.");
        }

        const payload = (await res.json()) as OutreachDraftResponse;
        const nextDraft = payload.drafts.find(
          (item) => item.listing_id === listing.id,
        )?.draft_text;

        if (!mounted) return;

        if (nextDraft?.trim()) {
          setDraft(nextDraft.trim());
          setUsingFallback(false);
        } else {
          setDraft(fallbackDraft);
          setUsingFallback(true);
        }
      } catch {
        if (!mounted) return;
        setDraft(fallbackDraft);
        setUsingFallback(true);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadDraft();

    return () => {
      mounted = false;
    };
  }, [listing, sessionId]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard failures and keep the draft editable.
    }
  }

  return (
    <Card className="border-stone-300 bg-white">
      <CardContent className="space-y-6 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="info">Drafted outreach</Badge>
          <Badge variant="outline">
            {listing.contact_telegram ?? listing.contact_phone ?? "Manual follow-up"}
          </Badge>
        </div>

        <div>
          <h2 className="text-2xl font-semibold text-stone-950">
            Prepare inquiry for {listing.location_area}
          </h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Review the AI-drafted message, edit it if needed, then send it
            directly to the landlord.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center gap-3 rounded-[24px] border border-stone-200 bg-stone-50 p-5 text-sm text-stone-600">
            <Spinner />
            Drafting your message…
          </div>
        ) : null}

        {usingFallback ? (
          <div className="rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            Using a standard fallback draft for now. You can still edit it before
            sending.
          </div>
        ) : null}

        {!loading ? (
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="min-h-[220px] rounded-[24px] bg-stone-50 leading-7"
          />
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => void handleCopy()}
            disabled={loading}
          >
            {copied ? "Copied" : "Copy draft"}
          </Button>
          {listing.contact_telegram ? (
            <a
              href={`https://t.me/${listing.contact_telegram.replace("@", "")}`}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="secondary">Open Telegram</Button>
            </a>
          ) : null}
          {listing.contact_phone ? (
            <a href={`tel:${listing.contact_phone}`}>
              <Button variant="outline">Call landlord</Button>
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
