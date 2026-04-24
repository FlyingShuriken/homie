"use client";

import type { Listing } from "@/lib/homie";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";

export default function OutreachModal({ listing }: { listing: Listing }) {
  const draft = `Hi, I saw your listing for ${listing.location_area} (${formatCurrency(
    listing.price_rm,
  )}/month) and I'm interested.\n\nCould I check if it is still available, whether viewing this weekend is possible, and if the deposit is fixed?\n\nThank you.`;

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
            This route replaces the old placeholder modal. It is ready to host generated copy and a Telegram handoff later, but already works as a clear inquiry page.
          </p>
        </div>

        <div className="whitespace-pre-line rounded-[24px] border border-stone-200 bg-stone-50 p-5 text-sm leading-7 text-stone-700">
          {draft}
        </div>

        <div className="flex flex-wrap gap-3">
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
