"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import FilterForm from "@/components/FilterForm";
import TelegramSetupModal from "@/components/TelegramSetupModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  API_URL,
  getInitialFilters,
  getTelegramStatus,
  type FilterFormData,
  type TelegramStatus,
} from "@/lib/homie";

const PRESETS: Record<string, Partial<FilterFormData>> = {
  "Student near MRT": {
    room_type: "single",
    furnished_status: "fully",
    transport: "MRT",
    price_max: "700",
    max_results: "30",
  },
  "Working adult in PJ": {
    location: "Petaling Jaya",
    room_type: "master",
    furnished_status: "fully",
    parking: true,
    max_results: "30",
  },
  "Couple furnished": {
    room_type: "whole_unit",
    furnished_status: "fully",
    gender_restriction: "any",
    max_results: "30",
  },
  "Low-budget studio": {
    room_type: "studio",
    price_max: "600",
    max_results: "30",
  },
};

function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  const initialValues = getInitialFilters(searchParams) ?? {};
  const [activeInitialValues, setActiveInitialValues] =
    useState<Partial<FilterFormData>>(initialValues);
  const [formKey, setFormKey] = useState(0);
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [showTelegramSetup, setShowTelegramSetup] = useState(false);

  useEffect(() => {
    getTelegramStatus()
      .then((status) => setTelegramStatus(status))
      .catch(() =>
        setTelegramStatus({
          configured: false,
          authenticated: false,
          demo_target_configured: false,
          runtime_setup_enabled: false,
          operator_token_required: false,
        }),
      );
  }, []);

  function handlePreset(preset: keyof typeof PRESETS) {
    setActiveInitialValues((current) => ({
      ...current,
      ...PRESETS[preset],
    }));
    setFormKey((current) => current + 1);
  }

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
        must_haves: form.must_haves,
        enable_telegram_outreach: form.enable_telegram_outreach,
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
          <Badge variant="info">Full filters</Badge>
          <Badge variant="success">Designed for fast adjustment</Badge>
        </div>

        <div className="mb-10 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <h1 className="font-display text-6xl leading-none text-stone-950 sm:text-7xl">
              Tell Homie what you need.
            </h1>
            <p className="mt-5 max-w-2xl text-xl leading-8 text-stone-600">
              Fill in what matters to you. Homie handles the scraping,
              deduplication, and ranking so you get a shortlist with scores and
              reasoning in under a minute.
            </p>
            <p className="mt-2 text-sm text-stone-400">
              Listings in Bahasa Malaysia and Chinese are normalized
              automatically.
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
                <Button
                  key={preset}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="px-5 py-2.5 text-base"
                  onClick={() => handlePreset(preset)}
                >
                  {preset}
                </Button>
              ))}
            </div>
            <div className="mt-6">
              <Link href="/chat">
                <Button variant="ghost">Switch to chat intake</Button>
              </Link>
            </div>
          </div>
        </div>

        {telegramStatus &&
          (!telegramStatus.configured || !telegramStatus.demo_target_configured) && (
          <div className="mb-6 flex items-center justify-between rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-stone-700">
                Telegram demo outreach not fully configured
              </p>
              <p className="text-xs text-stone-500 mt-0.5">
                Provide Telegram credentials and a demo target through PM2 or the runtime setup form before demo-message sending is available.
              </p>
            </div>
            {telegramStatus.runtime_setup_enabled ? (
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={() => setShowTelegramSetup(true)}
                className="ml-4 h-auto shrink-0 rounded-lg px-3 py-1.5 text-xs"
              >
                Set up
              </Button>
            ) : null}
          </div>
        )}

        {telegramStatus?.configured &&
          telegramStatus.demo_target_configured &&
          !telegramStatus.authenticated && (
            <div className="mb-6 flex items-center justify-between rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-amber-800">
                  Telegram session needs operator setup
                </p>
                <p className="mt-0.5 text-xs text-amber-700">
                  Credentials are present, but the Telethon session file has not been authenticated.
                </p>
              </div>
              {telegramStatus.runtime_setup_enabled ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowTelegramSetup(true)}
                  className="ml-4 h-auto shrink-0 rounded-lg px-3 py-1.5 text-xs"
                >
                  Authenticate
                </Button>
              ) : null}
            </div>
          )}

        {telegramStatus?.configured &&
          telegramStatus.demo_target_configured &&
          telegramStatus.authenticated && (
          <div className="mb-6 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
            <span className="text-emerald-600 text-sm">✓</span>
            <p className="text-sm text-emerald-700">
              Telegram demo outreach is ready.
            </p>
          </div>
        )}

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <FilterForm
          key={formKey}
          onSubmit={handleSubmit}
          initialValues={activeInitialValues}
        />

        {showTelegramSetup && (
          <TelegramSetupModal
            onSuccess={() => {
              setTelegramStatus((current) =>
                current
                  ? {
                      ...current,
                      configured: true,
                      authenticated: true,
                      demo_target_configured: true,
                    }
                  : {
                      configured: true,
                      authenticated: true,
                      demo_target_configured: true,
                      runtime_setup_enabled: true,
                      operator_token_required: false,
                    },
              );
              setShowTelegramSetup(false);
            }}
            onDismiss={() => setShowTelegramSetup(false)}
            operatorTokenRequired={telegramStatus?.operator_token_required ?? false}
            demoTargetConfigured={telegramStatus?.demo_target_configured ?? false}
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
