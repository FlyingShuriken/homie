"use client";

import { useState } from "react";

export interface Listing {
  id: string;
  source_primary: string;
  source_variants: string[];
  url: string;
  title: string;
  price_rm: number | null;
  location_area: string;
  location_city: string;
  room_type: string;
  furnished_status: string;
  parking: string;
  nearby_transport: string[];
  match_score: number | null;
  score_explanation: string | null;
  contact_phone: string | null;
  contact_telegram: string | null;
  outreach_status: string;
  low_confidence_flags: string[];
}

interface ListingCardProps {
  listing: Listing;
  onPrepareInquiry: (listing: Listing) => void;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const rounded = Math.round(score);
  const cls =
    rounded >= 75
      ? "bg-green-100 text-green-700 border-green-200"
      : rounded >= 50
      ? "bg-yellow-100 text-yellow-700 border-yellow-200"
      : "bg-red-100 text-red-700 border-red-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold border ${cls}`}>
      {rounded}/100
    </span>
  );
}

const SOURCE_LABELS: Record<string, string> = {
  ibilik: "ibilik",
  iproperty: "iProperty",
  facebook: "Facebook",
};

export default function ListingCard({ listing, onPrepareInquiry }: ListingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasContact = !!(listing.contact_telegram || listing.contact_phone);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 space-y-3 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-gray-900 hover:text-brand-600 line-clamp-2"
          >
            {listing.title || "Untitled listing"}
          </a>
          <p className="text-xs text-gray-400 mt-0.5">
            {SOURCE_LABELS[listing.source_primary] ?? listing.source_primary}
            {listing.source_variants.length > 1 && (
              <span className="ml-1">+{listing.source_variants.length - 1} sources</span>
            )}
          </p>
        </div>
        <ScoreBadge score={listing.match_score} />
      </div>

      {/* Key details */}
      <div className="flex flex-wrap gap-2 text-xs">
        {listing.price_rm !== null ? (
          <span className="font-semibold text-gray-900">RM {listing.price_rm}/mo</span>
        ) : (
          <span className="text-gray-400">Price unknown</span>
        )}
        {listing.location_area !== "unknown" && (
          <span className="text-gray-500">{listing.location_area}, {listing.location_city}</span>
        )}
        {listing.room_type !== "unknown" && (
          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
            {listing.room_type.replace("_", " ")}
          </span>
        )}
        {listing.furnished_status !== "unknown" && (
          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
            {listing.furnished_status}
          </span>
        )}
        {listing.parking === "yes" && (
          <span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">Parking</span>
        )}
      </div>

      {/* Transport */}
      {listing.nearby_transport.length > 0 && (
        <p className="text-xs text-gray-500">
          🚇 {listing.nearby_transport.slice(0, 2).join(", ")}
        </p>
      )}

      {/* Score explanation */}
      {listing.score_explanation && (
        <p className="text-xs text-gray-600 leading-relaxed border-l-2 border-gray-200 pl-2">
          {listing.score_explanation}
        </p>
      )}

      {/* Low confidence flags */}
      {listing.low_confidence_flags.length > 0 && (
        <p className="text-xs text-amber-600">
          ⚠ Unverified fields: {listing.low_confidence_flags.join(", ")}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-brand-600 hover:underline"
        >
          View listing →
        </a>
        {hasContact && (
          <button
            onClick={() => onPrepareInquiry(listing)}
            className="ml-auto text-xs bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            Prepare inquiry
          </button>
        )}
        {!hasContact && (
          <span className="ml-auto text-xs text-gray-400">No contact info</span>
        )}
      </div>
    </div>
  );
}
