"use client";

import { Button } from "@/components/ui/button";
import { ChatConfidence, ChatFilters, FilterConfidence } from "@/lib/homie";
import { cn } from "@/lib/utils";

interface Props {
  filters: ChatFilters;
  confidence: ChatConfidence;
  onStartSearch: () => void;
  isSearching: boolean;
  telegramEnabled: boolean;
  onToggleTelegram: (v: boolean) => void;
}

function ConfidenceDot({ level }: { level: FilterConfidence | undefined }) {
  if (!level || level === "missing") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-stone-300 text-xs text-stone-400">
        ?
      </span>
    );
  }
  return (
    <span
      className={cn(
        "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold",
        level === "confirmed" && "bg-emerald-500 text-white",
        level === "inferred" && "bg-blue-500 text-white",
        level === "soft" && "bg-amber-400 text-white",
      )}
    >
      {level === "confirmed" ? "✓" : level === "inferred" ? "•" : "○"}
    </span>
  );
}

interface FieldRowProps {
  label: string;
  value: string | null | undefined;
  sub?: string;
  confidence?: FilterConfidence;
}

function FieldRow({ label, value, sub, confidence }: FieldRowProps) {
  const empty = !value || value === "any" || value === "null";
  return (
    <div className="border-b border-stone-100 pb-4 last:border-0 last:pb-0">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-stone-400">
          {label}
        </span>
        <ConfidenceDot level={empty ? "missing" : confidence} />
      </div>
      <div className={cn("mt-1 text-sm font-medium", empty ? "text-stone-300" : "text-stone-800")}>
        {empty ? "—" : value}
      </div>
      {sub && !empty && (
        <div className="mt-0.5 text-xs text-stone-400 italic">{sub}</div>
      )}
    </div>
  );
}

export function ChatFilterSidebar({
  filters,
  confidence,
  onStartSearch,
  isSearching,
  telegramEnabled,
  onToggleTelegram,
}: Props) {
  const priceValue =
    filters.price_min != null && filters.price_max != null
      ? `RM ${filters.price_min} - RM ${filters.price_max}`
      : filters.price_max != null
        ? `up to RM ${filters.price_max}`
        : null;

  const roomValue = [
    filters.room_type && filters.room_type !== "any"
      ? filters.room_type.replace("_", " ")
      : null,
    filters.furnished_status && filters.furnished_status !== "any"
      ? filters.furnished_status
      : null,
  ]
    .filter(Boolean)
    .join(" · ") || null;

  const mustHaveValue =
    filters.must_haves && filters.must_haves.length > 0
      ? filters.must_haves.join(", ")
      : null;

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-500">
          Agent is building
        </span>
      </div>

      {/* Fields */}
      <div className="flex-1 space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
        <FieldRow
          label="Location"
          value={filters.location}
          confidence={confidence.location}
        />
        <FieldRow
          label="Price"
          value={priceValue}
          sub={confidence.price === "inferred" ? "stretched from input" : undefined}
          confidence={confidence.price}
        />
        <FieldRow
          label="Room"
          value={roomValue}
          confidence={
            confidence.room_type === "confirmed" || confidence.furnished_status === "confirmed"
              ? "confirmed"
              : confidence.room_type === "inferred" || confidence.furnished_status === "inferred"
                ? "inferred"
                : confidence.room_type
          }
        />
        <FieldRow
          label="Transport"
          value={filters.transport}
          sub={confidence.transport === "inferred" ? "inferred" : undefined}
          confidence={confidence.transport}
        />
        <FieldRow
          label="Gender"
          value={
            filters.gender_restriction && filters.gender_restriction !== "any"
              ? `${filters.gender_restriction.charAt(0).toUpperCase()}${filters.gender_restriction.slice(1)} (preferred)`
              : null
          }
          sub={confidence.gender_restriction === "soft" ? "soft" : undefined}
          confidence={confidence.gender_restriction}
        />
        <FieldRow
          label="Parking"
          value={filters.parking === true ? "Required" : filters.parking === false ? "Not required" : null}
          confidence={confidence.parking}
        />
        <FieldRow
          label="Must-haves"
          value={mustHaveValue}
          confidence={confidence.must_haves}
        />
      </div>

      {/* Telegram toggle */}
      <div className="flex items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3">
        <button
          type="button"
          role="switch"
          aria-checked={telegramEnabled}
          aria-label="Auto-contact agents via Telegram"
          onClick={() => onToggleTelegram(!telegramEnabled)}
          className={cn(
            "relative h-5 w-9 rounded-full transition-colors",
            telegramEnabled ? "bg-blue-500" : "bg-stone-300",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
              telegramEnabled ? "translate-x-4" : "translate-x-0.5",
            )}
          />
        </button>
        <span className="text-sm text-stone-700">
          Auto-contact agents via Telegram
        </span>
      </div>

      {/* Start button */}
      <Button
        type="button"
        onClick={onStartSearch}
        disabled={isSearching}
        variant="secondary"
        size="lg"
        className="h-auto w-full rounded-2xl px-6 py-4 text-base font-semibold"
      >
        {isSearching ? "Starting search..." : "Start agent search ->"}
      </Button>
    </div>
  );
}
