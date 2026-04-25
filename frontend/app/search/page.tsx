"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import FilterForm from "@/components/FilterForm";
import TelegramSetupModal from "@/components/TelegramSetupModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API_URL, getInitialFilters, type FilterFormData } from "@/lib/homie";

function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  const initialValues = getInitialFilters(searchParams);
  const [telegramReady, setTelegramReady] = useState<boolean | null>(null);
  const [showTelegramSetup, setShowTelegramSetup] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/telegram/status`)
      .then((r) => r.json())
      .then((d: { configured: boolean }) => setTelegramReady(d.configured))
      .catch(() => setTelegramReady(false));
  }, []);

  async function handleSubmit(form: FilterFormData) {
    setError(null);

    const res = await fetch(`${API_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        location: form.location,
        price_min: Number.parseInt(form.price_min, 10),
        price_max: Number.parseInt(form.price_max, 10),
        room_type: form.room_type,
        furnished_status: form.furnished_status,
        gender_restriction: form.gender_restriction,
        parking: form.parking,
        transport: form.transport,
        pet_friendly: form.pet_friendly,
        max_results: Number.parseInt(form.max_results, 10) || 30,
      }),
    });

    if (!res.ok) {
      const payload = await res.json().catch(() => null);
      setError(payload?.detail ?? "Unable to start the search.");
      return;
    }

    const { session_id } = (await res.json()) as { session_id: string };
    router.push(`/workflow/${session_id}`);
  }

  return (
    <AppShell activePath="/search">
      <main className="mx-auto max-w-full px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Badge variant="outline">Manual intake</Badge>
          <Badge variant="info">Nine fields</Badge>
          <Badge variant="success">Designed for fast adjustment</Badge>
        </div>

        <div className="mb-10 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <h1 className="font-display text-6xl leading-none text-stone-950 sm:text-7xl">
              Tell Homie what you need.
            </h1>
            <p className="mt-5 max-w-2xl text-xl leading-8 text-stone-600">
              This route replaces the old single-card home page. It is now the dedicated manual search page, with cleaner field grouping and room to expand filters without cluttering the landing route.
            </p>
          </div>
          <div className="rounded-[32px] border border-stone-300 bg-white/70 p-6">
            <div className="text-sm uppercase tracking-[0.24em] text-stone-500">
              Quick presets
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              {[
                "Student near MRT",
                "Working adult in PJ",
                "Couple furnished",
                "Low-budget studio",
              ].map((preset) => (
                <Badge key={preset} variant="outline" className="px-5 py-2.5 text-base">
                  {preset}
                </Badge>
              ))}
            </div>
            <div className="mt-6">
              <Link href="/chat">
                <Button variant="ghost">Switch to chat intake</Button>
              </Link>
            </div>
          </div>
        </div>

        {telegramReady === false && (
          <div className="mb-6 flex items-center justify-between rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-stone-700">Telegram outreach not set up</p>
              <p className="text-xs text-stone-500 mt-0.5">Connect your account to let Homie send inquiries automatically.</p>
            </div>
            <button
              onClick={() => setShowTelegramSetup(true)}
              className="ml-4 shrink-0 rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 transition-colors"
            >
              Set up
            </button>
          </div>
        )}

        {telegramReady === true && (
          <div className="mb-6 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
            <span className="text-emerald-600 text-sm">✓</span>
            <p className="text-sm text-emerald-700">Telegram outreach is ready.</p>
          </div>
        )}

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <FilterForm onSubmit={handleSubmit} initialValues={initialValues} />

        {showTelegramSetup && (
          <TelegramSetupModal
            onSuccess={() => { setTelegramReady(true); setShowTelegramSetup(false); }}
            onDismiss={() => setShowTelegramSetup(false)}
          />
        )}
      </main>
    </AppShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchPageContent />
    </Suspense>
  );
}
