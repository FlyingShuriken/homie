"use client";

import type { FormEvent, ReactNode } from "react";
import { useState } from "react";
import {
  FURNISHED_OPTIONS,
  GENDER_OPTIONS,
  ROOM_TYPES,
  type FilterFormData,
} from "@/lib/homie";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

interface FilterFormProps {
  onSubmit: (data: FilterFormData) => Promise<void>;
  initialValues?: Partial<FilterFormData>;
}

export default function FilterForm({
  onSubmit,
  initialValues,
}: FilterFormProps) {
  const [form, setForm] = useState<FilterFormData>({
    location: "",
    price_min: "",
    price_max: "",
    room_type: "any",
    furnished_status: "any",
    gender_restriction: "any",
    parking: false,
    transport: "",
    pet_friendly: false,
    max_results: "30",
    must_haves: [],
    enable_telegram_outreach: true,
    ...initialValues,
  });
  const [errors, setErrors] = useState<Partial<Record<keyof FilterFormData, string>>>({});
  const [loading, setLoading] = useState(false);

  function validate() {
    const nextErrors: Partial<Record<keyof FilterFormData, string>> = {};
    const min = Number.parseInt(form.price_min, 10);
    const max = Number.parseInt(form.price_max, 10);

    if (!form.location.trim()) nextErrors.location = "Location is required.";
    if (!form.price_min) nextErrors.price_min = "Minimum budget is required.";
    if (!form.price_max) nextErrors.price_max = "Maximum budget is required.";
    if (Number.isNaN(min) || min < 0) nextErrors.price_min = "Enter a valid amount.";
    if (Number.isNaN(max) || max < 0) nextErrors.price_max = "Enter a valid amount.";
    if (!Number.isNaN(min) && !Number.isNaN(max) && min >= max) {
      nextErrors.price_max = "Maximum price must be higher than minimum price.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      await onSubmit(form);
    } finally {
      setLoading(false);
    }
  }

  function update<K extends keyof FilterFormData>(key: K, value: FilterFormData[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateMustHaves(value: string) {
    update(
      "must_haves",
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    );
  }

  return (
    <Card className="overflow-hidden border-stone-300 bg-white/95">
      <CardContent className="p-0">
        <form onSubmit={handleSubmit}>
          <div className="grid gap-0 md:grid-cols-[72px_1fr]">
            <FieldBlock
              step="01"
              title="Where"
              hint="Area, neighbourhood, or landmark"
              error={errors.location}
            >
              <Input
                value={form.location}
                onChange={(event) => update("location", event.target.value)}
                placeholder="Cheras, Taman Connaught, Bangsar South"
              />
            </FieldBlock>

            <div className="col-span-full"><Separator /></div>

            <FieldBlock
              step="02"
              title="Budget per month"
              hint="Homie gives partial credit up to 20% above your max when matches are strong."
              error={errors.price_min ?? errors.price_max}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  type="number"
                  min={0}
                  value={form.price_min}
                  onChange={(event) => update("price_min", event.target.value)}
                  placeholder="RM 400"
                />
                <Input
                  type="number"
                  min={0}
                  value={form.price_max}
                  onChange={(event) => update("price_max", event.target.value)}
                  placeholder="RM 600"
                />
              </div>
            </FieldBlock>

            <div className="col-span-full"><Separator /></div>

            <FieldBlock step="03" title="Room type">
              <div className="grid gap-3 sm:grid-cols-2">
                <Select
                  value={form.room_type}
                  onChange={(event) => update("room_type", event.target.value)}
                >
                  {ROOM_TYPES.map((option) => (
                    <option key={option} value={option}>
                      {option === "any" ? "Any" : option.replace("_", " ")}
                    </option>
                  ))}
                </Select>
                <Select
                  value={form.furnished_status}
                  onChange={(event) =>
                    update("furnished_status", event.target.value)
                  }
                >
                  {FURNISHED_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option === "any"
                        ? "Any furnishing"
                        : option.charAt(0).toUpperCase() + option.slice(1)}
                    </option>
                  ))}
                </Select>
              </div>
            </FieldBlock>

            <div className="col-span-full"><Separator /></div>

            <FieldBlock step="04" title="Commute and restrictions">
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  value={form.transport}
                  onChange={(event) => update("transport", event.target.value)}
                  placeholder="MRT Taman Connaught"
                />
                <Select
                  value={form.gender_restriction}
                  onChange={(event) =>
                    update("gender_restriction", event.target.value)
                  }
                >
                  {GENDER_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option === "any"
                        ? "Any / no restriction"
                        : option.charAt(0).toUpperCase() + option.slice(1)}
                    </option>
                  ))}
                </Select>
              </div>
            </FieldBlock>

            <div className="col-span-full"><Separator /></div>

            <FieldBlock step="05" title="Must-haves">
              <div className="grid gap-5">
                <div className="flex flex-wrap items-center gap-6">
                  <label className="flex items-center gap-3 text-base text-stone-700">
                    <Checkbox
                      checked={form.parking}
                      onChange={(event) => update("parking", event.target.checked)}
                    />
                    Parking required
                  </label>
                  <label className="flex items-center gap-3 text-base text-stone-700">
                    <Checkbox
                      checked={form.pet_friendly}
                      onChange={(event) =>
                        update("pet_friendly", event.target.checked)
                      }
                    />
                    Pet-friendly
                  </label>
                  <label className="flex items-center gap-3 text-base text-stone-700">
                    <Checkbox
                      checked={form.enable_telegram_outreach}
                      onChange={(event) =>
                        update("enable_telegram_outreach", event.target.checked)
                      }
                    />
                    Send Telegram demo preview
                  </label>
                  <div className="ml-auto flex items-center gap-3">
                    <span className="text-base text-stone-500">Max results</span>
                    <Input
                      type="number"
                      min={5}
                      max={100}
                      className="w-24"
                      value={form.max_results}
                      onChange={(event) =>
                        update("max_results", event.target.value)
                      }
                    />
                  </div>
                </div>
                <Input
                  value={form.must_haves.join(", ")}
                  onChange={(event) => updateMustHaves(event.target.value)}
                  placeholder="Extra must-haves, separated by commas"
                />
              </div>
            </FieldBlock>
          </div>

          <div className="flex flex-col gap-4 border-t border-stone-200 bg-stone-50 px-6 py-5 sm:flex-row sm:items-center">
            <div className="text-base text-stone-500">
              Core filters plus optional must-haves. The agent handles the scraping, ranking, and explanation.
            </div>
            <Button
              type="submit"
              variant="secondary"
              size="lg"
              disabled={loading}
              className="sm:ml-auto"
            >
              {loading ? "Starting search..." : "Start agent search"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function FieldBlock({
  step,
  title,
  hint,
  error,
  children,
}: {
  step: string;
  title: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="contents">
      <div className="border-b border-stone-200 px-6 py-6 text-sm font-semibold uppercase tracking-[0.24em] text-orange-500 md:border-b-0 md:border-r">
        {step}
      </div>
      <div className="space-y-4 border-b border-stone-200 px-6 py-6 last:border-b-0">
        <div className="space-y-1">
          <div className="text-xl font-semibold text-stone-900">{title}</div>
          {hint ? <div className="text-base text-stone-500">{hint}</div> : null}
          {error ? <div className="text-base text-red-600">{error}</div> : null}
        </div>
        {children}
      </div>
    </div>
  );
}
