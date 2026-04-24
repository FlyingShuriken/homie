"use client";

import { useEffect, useState } from "react";
import { Listing } from "./ListingCard";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface OutreachModalProps {
  listing: Listing;
  sessionId: string;
  onClose: () => void;
}

interface HandoffResult {
  telegramLink?: string;
  phoneFallback?: string;
}

export default function OutreachModal({ listing, sessionId, onClose }: OutreachModalProps) {
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [hasTelegram, setHasTelegram] = useState(false);
  const [contactPhone, setContactPhone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HandoffResult | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function fetchDraft() {
      try {
        const res = await fetch(`${API}/api/outreach/draft`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, listing_ids: [listing.id] }),
        });
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const data = await res.json();
        const d = data.drafts?.[0];
        if (!d) throw new Error("No draft returned");
        setDraft(d.draft_text);
        setHasTelegram(d.has_telegram);
        setContactPhone(d.contact_phone ?? null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to generate inquiry draft.");
      } finally {
        setLoading(false);
      }
    }
    fetchDraft();
  }, [listing.id, sessionId]);

  async function handleConfirm() {
    setConfirming(true);
    try {
      const res = await fetch(`${API}/api/outreach/handoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listing_id: listing.id, confirmed_draft: draft }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      const r: HandoffResult = {
        telegramLink: data.telegram_link,
        phoneFallback: data.phone_fallback,
      };
      setResult(r);
      if (r.telegramLink) window.open(r.telegramLink, "_blank");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Handoff failed.");
    } finally {
      setConfirming(false);
    }
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-lg w-full mx-4 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Prepare Inquiry</h2>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{listing.title}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-4 text-lg leading-none">✕</button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="py-6 flex items-center justify-center">
            <span className="animate-pulse text-sm text-gray-500">Generating inquiry message…</span>
          </div>
        )}

        {/* Error (no result yet) */}
        {!loading && error && !result && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={onClose}
              className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm"
            >
              Close
            </button>
          </div>
        )}

        {/* Draft editor */}
        {!loading && !error && !result && (
          <>
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">
                Message — review and edit before sending
              </label>
              <textarea
                className="w-full border border-gray-200 rounded-lg p-3 text-sm text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
                rows={6}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
            </div>

            {!hasTelegram && contactPhone && (
              <p className="text-xs text-amber-600">
                Telegram unavailable — contact via phone:{" "}
                <span className="font-mono font-semibold">{contactPhone}</span>
              </p>
            )}
            {!hasTelegram && !contactPhone && (
              <p className="text-xs text-gray-400">No direct contact — copy the message to use manually.</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => handleCopy(draft)}
                className="flex-1 py-2 border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg text-sm transition-colors"
              >
                {copied ? "Copied!" : "Copy message"}
              </button>
              {hasTelegram ? (
                <button
                  onClick={handleConfirm}
                  disabled={confirming}
                  className="flex-1 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-60 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {confirming ? "Opening…" : "Open in Telegram"}
                </button>
              ) : (
                <button
                  onClick={handleConfirm}
                  disabled={confirming}
                  className="flex-1 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {confirming ? "Confirming…" : "Confirm"}
                </button>
              )}
            </div>
          </>
        )}

        {/* Post-handoff result */}
        {result && (
          <div className="space-y-3">
            {result.telegramLink && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-medium text-blue-800">Opened in Telegram</p>
                <p className="text-xs text-blue-600 mt-1">
                  Your draft has been pre-filled in the landlord&apos;s chat.
                </p>
                <button
                  onClick={() => window.open(result.telegramLink, "_blank")}
                  className="mt-2 text-xs text-blue-600 hover:underline"
                >
                  Open again →
                </button>
              </div>
            )}
            {result.phoneFallback && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700">Contact via phone</p>
                <p className="text-xs font-mono text-gray-900 mt-1">{result.phoneFallback}</p>
                <button
                  onClick={() => handleCopy(result.phoneFallback!)}
                  className="mt-2 text-xs text-brand-600 hover:underline"
                >
                  {copied ? "Copied!" : "Copy number"}
                </button>
              </div>
            )}
            <button
              onClick={onClose}
              className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
