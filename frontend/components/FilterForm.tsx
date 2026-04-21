"use client";

import { useState, FormEvent } from "react";

interface FilterFormData {
  location: string;
  price_min: string;
  price_max: string;
  room_type: string;
  furnished_status: string;
  gender_restriction: string;
  parking: boolean;
  transport: string;
  pet_friendly: boolean;
  max_results: string;
}

interface FilterFormProps {
  onSubmit: (data: FilterFormData) => Promise<void>;
}

const ROOM_TYPES = ["any", "single", "master", "studio", "whole_unit"];
const FURNISHED = ["any", "fully", "partially", "unfurnished"];
const GENDER = ["any", "male", "female", "mixed"];

export default function FilterForm({ onSubmit }: FilterFormProps) {
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
  });
  const [errors, setErrors] = useState<Partial<FilterFormData>>({});
  const [loading, setLoading] = useState(false);

  function validate(): boolean {
    const e: Partial<FilterFormData> = {};
    if (!form.location.trim()) e.location = "Location is required.";
    if (!form.price_min) e.price_min = "Required.";
    if (!form.price_max) e.price_max = "Required.";
    const min = parseInt(form.price_min);
    const max = parseInt(form.price_max);
    if (min < 0) e.price_min = "Must be positive.";
    if (max < 0) e.price_max = "Must be positive.";
    if (min >= max) e.price_max = "Must be greater than min price.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await onSubmit(form);
    } finally {
      setLoading(false);
    }
  }

  function field(
    label: string,
    key: keyof FilterFormData,
    element: React.ReactNode,
    hint?: string
  ) {
    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
        {element}
        {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
        {errors[key] && (
          <p className="text-xs text-red-500 mt-1">{errors[key]}</p>
        )}
      </div>
    );
  }

  const inputCls =
    "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent";
  const selectCls = inputCls;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Location */}
      {field(
        "Location *",
        "location",
        <input
          type="text"
          className={inputCls}
          placeholder="e.g. Cheras, Petaling Jaya, Bangsar"
          value={form.location}
          onChange={(e) => setForm({ ...form, location: e.target.value })}
        />,
        "Area, city, or landmark"
      )}

      {/* Price range */}
      <div className="grid grid-cols-2 gap-3">
        {field(
          "Min price (RM) *",
          "price_min",
          <input
            type="number"
            min={0}
            className={inputCls}
            placeholder="e.g. 400"
            value={form.price_min}
            onChange={(e) => setForm({ ...form, price_min: e.target.value })}
          />
        )}
        {field(
          "Max price (RM) *",
          "price_max",
          <input
            type="number"
            min={0}
            className={inputCls}
            placeholder="e.g. 800"
            value={form.price_max}
            onChange={(e) => setForm({ ...form, price_max: e.target.value })}
          />
        )}
      </div>

      {/* Room type + Furnished */}
      <div className="grid grid-cols-2 gap-3">
        {field(
          "Room / unit type",
          "room_type",
          <select
            className={selectCls}
            value={form.room_type}
            onChange={(e) => setForm({ ...form, room_type: e.target.value })}
          >
            {ROOM_TYPES.map((t) => (
              <option key={t} value={t}>
                {t === "any" ? "Any" : t.replace("_", " ")}
              </option>
            ))}
          </select>
        )}
        {field(
          "Furnished status",
          "furnished_status",
          <select
            className={selectCls}
            value={form.furnished_status}
            onChange={(e) => setForm({ ...form, furnished_status: e.target.value })}
          >
            {FURNISHED.map((f) => (
              <option key={f} value={f}>
                {f === "any" ? "Any" : f.charAt(0).toUpperCase() + f.slice(1)}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Transport + Gender */}
      <div className="grid grid-cols-2 gap-3">
        {field(
          "Nearby transport",
          "transport",
          <input
            type="text"
            className={inputCls}
            placeholder="e.g. MRT Taman Connaught"
            value={form.transport}
            onChange={(e) => setForm({ ...form, transport: e.target.value })}
          />,
          "LRT / MRT / BRT line or station"
        )}
        {field(
          "Gender restriction",
          "gender_restriction",
          <select
            className={selectCls}
            value={form.gender_restriction}
            onChange={(e) =>
              setForm({ ...form, gender_restriction: e.target.value })
            }
          >
            {GENDER.map((g) => (
              <option key={g} value={g}>
                {g === "any" ? "Any / No restriction" : g.charAt(0).toUpperCase() + g.slice(1)}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Checkboxes + max results */}
      <div className="flex flex-wrap items-center gap-6">
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            checked={form.parking}
            onChange={(e) => setForm({ ...form, parking: e.target.checked })}
          />
          Parking required
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            checked={form.pet_friendly}
            onChange={(e) => setForm({ ...form, pet_friendly: e.target.checked })}
          />
          Pet-friendly
        </label>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-sm text-gray-700 whitespace-nowrap">Max results</label>
          <input
            type="number"
            min={5}
            max={100}
            className="w-20 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={form.max_results}
            onChange={(e) => setForm({ ...form, max_results: e.target.value })}
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 px-6 bg-brand-600 hover:bg-brand-700 disabled:bg-gray-400
                   text-white font-semibold rounded-lg transition-colors text-sm"
      >
        {loading ? "Starting search…" : "Search rentals"}
      </button>
    </form>
  );
}
