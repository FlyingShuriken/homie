"use client";

import { useRouter } from "next/navigation";
import FilterForm from "@/components/FilterForm";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const router = useRouter();

  async function handleSearch(form: Record<string, unknown>) {
    const body = {
      location: form.location,
      price_min: parseInt(form.price_min as string),
      price_max: parseInt(form.price_max as string),
      room_type: form.room_type,
      furnished_status: form.furnished_status,
      gender_restriction: form.gender_restriction,
      parking: form.parking,
      transport: form.transport,
      pet_friendly: form.pet_friendly,
      max_results: parseInt(form.max_results as string) || 30,
    };

    const res = await fetch(`${API}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? "Failed to start search.");
    }

    const { session_id } = await res.json();
    router.push(`/results/${session_id}`);
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 tracking-tight">Homie</h1>
          <p className="mt-2 text-gray-500 text-sm">
            AI-powered rental search across ibilik, iProperty, and Facebook —
            normalized, scored, and explained.
          </p>
        </div>

        {/* Form card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
            Search filters
          </h2>
          <FilterForm onSubmit={handleSearch} />
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          Powered by GLM-5.1 · UMHackathon 2026
        </p>
      </div>
    </main>
  );
}
