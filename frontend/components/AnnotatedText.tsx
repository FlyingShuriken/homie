"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Claim {
  claimed_text: string;
  claimed_walk_minutes: number | null;
  actual_walk_minutes: number | null;
  walk_verified: boolean | null;
  name: string;
}

interface Segment {
  type: "plain" | "claim";
  text: string;
  claim?: Claim;
}

function buildSegments(text: string, claims: Claim[]): Segment[] {
  if (!claims.length) return [{ type: "plain", text }];

  // Sort claims by their first occurrence in text so we process left-to-right
  const positioned = claims
    .map((c) => ({ claim: c, index: text.indexOf(c.claimed_text) }))
    .filter((p) => p.index !== -1)
    .sort((a, b) => a.index - b.index);

  if (!positioned.length) return [{ type: "plain", text }];

  const segments: Segment[] = [];
  let cursor = 0;

  for (const { claim, index } of positioned) {
    if (index < cursor) continue; // overlapping — skip
    if (index > cursor) {
      segments.push({ type: "plain", text: text.slice(cursor, index) });
    }
    segments.push({ type: "claim", text: claim.claimed_text, claim });
    cursor = index + claim.claimed_text.length;
  }

  if (cursor < text.length) {
    segments.push({ type: "plain", text: text.slice(cursor) });
  }

  return segments;
}

function TooltipBody({ claim }: { claim: Claim }) {
  const { claimed_walk_minutes, actual_walk_minutes, walk_verified, name } = claim;

  if (actual_walk_minutes !== null && walk_verified === true) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="text-green-400">✓</span>
        <span>Verified — actual ~{actual_walk_minutes}min walk to {name}</span>
      </span>
    );
  }

  if (actual_walk_minutes !== null && walk_verified === false && claimed_walk_minutes !== null) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="text-amber-400">⚠</span>
        <span>
          Claimed {claimed_walk_minutes}min, estimated ~{actual_walk_minutes}min walk to {name}
        </span>
      </span>
    );
  }

  if (claimed_walk_minutes !== null) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="text-stone-400">○</span>
        <span>Claimed {claimed_walk_minutes}min walk to {name} (unverified)</span>
      </span>
    );
  }

  return null;
}

interface Props {
  text: string;
  claims: Claim[];
  className?: string;
}

export default function AnnotatedText({ text, claims, className }: Props) {
  const segments = buildSegments(text, claims);

  return (
    <span className={["whitespace-pre-line", className].filter(Boolean).join(" ")}>
      <TooltipProvider delayDuration={150}>
        {segments.map((seg, i) => {
          if (seg.type === "plain" || !seg.claim) {
            return <span key={i}>{seg.text}</span>;
          }
          const body = <TooltipBody claim={seg.claim} />;
          if (!body) return <span key={i}>{seg.text}</span>;

          const isVerified = seg.claim.walk_verified === true;
          const isFlagged =
            seg.claim.walk_verified === false &&
            seg.claim.actual_walk_minutes !== null;

          return (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <span
                  className={[
                    "cursor-help border-b border-dotted",
                    isVerified
                      ? "border-green-500 text-green-700"
                      : isFlagged
                        ? "border-amber-500 text-amber-700"
                        : "border-stone-400 text-stone-600",
                  ].join(" ")}
                >
                  {seg.text}
                </span>
              </TooltipTrigger>
              <TooltipContent>{body}</TooltipContent>
            </Tooltip>
          );
        })}
      </TooltipProvider>
    </span>
  );
}
