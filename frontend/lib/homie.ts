export type PipelineStatus = "running" | "complete" | "partial" | "failed";

export interface ProgressEventData {
  stage: string;
  status: "started" | "running" | "complete" | "failed";
  message: string;
  timestamp: string;
}

export interface FilterFormData {
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
  must_haves: string[];
  enable_telegram_outreach: boolean;
}

export type FilterConfidence = "confirmed" | "inferred" | "soft" | "missing";

export interface ChatFilters {
  location?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  room_type?: string | null;
  furnished_status?: string | null;
  gender_restriction?: string | null;
  parking?: boolean | null;
  transport?: string | null;
  pet_friendly?: boolean | null;
  max_results?: number;
  must_haves?: string[];
}

export interface ChatConfidence {
  location?: FilterConfidence;
  price?: FilterConfidence;
  room_type?: FilterConfidence;
  furnished_status?: FilterConfidence;
  gender_restriction?: FilterConfidence;
  parking?: FilterConfidence;
  transport?: FilterConfidence;
  must_haves?: FilterConfidence;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  filters: ChatFilters;
  confidence: ChatConfidence;
  ready_to_search: boolean;
  suggested_chips: string[];
}

export interface ScoreBreakdown {
  price?: number;
  location?: number;
  room_type?: number;
  transport?: number;
  furnished?: number;
  parking?: number;
  pet?: number;
  gender?: number;
}

export interface ReasonToBelieve {
  text: string;
  tone: "strong" | "warn" | "info";
}

export interface Listing {
  id: string;
  source_primary: string;
  source_variants: string[];
  url: string;
  title: string;
  price_rm: number | null;
  deposit_rm?: number | null;
  location_area: string;
  location_city: string;
  room_type: string;
  furnished_status: string;
  gender_restriction?: string;
  parking: string;
  nearby_transport: string[];
  facilities?: string[];
  match_score: number | null;
  score_explanation: string | null;
  score_breakdown?: ScoreBreakdown;
  contact_phone: string | null;
  contact_telegram: string | null;
  outreach_status: string;
  low_confidence_flags: string[];
  needs_verification?: string[];
  rtb?: ReasonToBelieve[];
}

export interface SessionResults {
  session_id: string;
  pipeline_status: PipelineStatus;
  summary_report: string | null;
  filters: Record<string, unknown>;
  listings: Listing[];
}

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const ROOM_TYPES = ["any", "single", "master", "studio", "whole_unit"];
export const FURNISHED_OPTIONS = ["any", "fully", "partially", "unfurnished"];
export const GENDER_OPTIONS = ["any", "male", "female", "mixed"];

export const SAMPLE_EVENTS: ProgressEventData[] = [
  {
    stage: "validate",
    status: "complete",
    message: "Validated Cheras filters and expanded budget tolerance by 15%.",
    timestamp: "00:02",
  },
  {
    stage: "scrape",
    status: "complete",
    message: "Gathered 14 listings from ibilik and 9 from iProperty.",
    timestamp: "00:09",
  },
  {
    stage: "normalize",
    status: "complete",
    message: "Merged duplicates and translated Bahasa snippets into one schema.",
    timestamp: "00:18",
  },
  {
    stage: "score",
    status: "running",
    message: "Ranking 21 listings against budget, transit, furnishing, and fit.",
    timestamp: "00:26",
  },
];

export const SAMPLE_LISTINGS: Listing[] = [
  {
    id: "ibl_7e4a",
    source_primary: "ibilik",
    source_variants: ["ibilik", "facebook"],
    url: "https://example.com/listing/ibl_7e4a",
    title: "Female single room with aircond and WiFi near MRT Taman Connaught",
    price_rm: 550,
    deposit_rm: 1100,
    location_area: "Taman Connaught",
    location_city: "Cheras",
    room_type: "single",
    furnished_status: "fully",
    gender_restriction: "female",
    parking: "yes",
    nearby_transport: ["MRT Taman Connaught (400m)"],
    facilities: ["WiFi", "Aircond", "Washer", "Desk", "Kitchen access"],
    match_score: 94,
    score_explanation:
      "Strong budget fit, clear female-only signal, furnished, and within walking distance of the MRT. Deposit is the main tradeoff.",
    score_breakdown: {
      price: 25,
      location: 18,
      room_type: 15,
      transport: 14,
      furnished: 10,
      parking: 6,
      pet: 0,
      gender: 3,
    },
    contact_phone: "012-555 1288",
    contact_telegram: "@auntysarah_connaught",
    outreach_status: "ready",
    low_confidence_flags: ["parking"],
    rtb: [
      { text: "Under budget cap", tone: "strong" },
      { text: "Female-only listing", tone: "strong" },
      { text: "400m to MRT", tone: "strong" },
      { text: "Deposit not clearly negotiable", tone: "warn" },
    ],
  },
  {
    id: "ipr_2bf1",
    source_primary: "iproperty",
    source_variants: ["iproperty"],
    url: "https://example.com/listing/ipr_2bf1",
    title: "Fully furnished master room at Taman Midah with shared kitchen",
    price_rm: 620,
    deposit_rm: 1240,
    location_area: "Taman Midah",
    location_city: "Cheras",
    room_type: "master",
    furnished_status: "fully",
    gender_restriction: "mixed",
    parking: "unknown",
    nearby_transport: ["MRT Taman Midah (650m)"],
    facilities: ["Wardrobe", "Aircond", "Washer"],
    match_score: 81,
    score_explanation:
      "Slightly above the target price but still competitive due to furnishing quality and good transit access.",
    score_breakdown: {
      price: 18,
      location: 16,
      room_type: 8,
      transport: 12,
      furnished: 10,
      parking: 0,
      pet: 0,
      gender: 1,
    },
    contact_phone: "016-332 0912",
    contact_telegram: null,
    outreach_status: "drafted",
    low_confidence_flags: ["gender_restriction", "parking"],
    rtb: [
      { text: "Fully furnished", tone: "strong" },
      { text: "Near MRT", tone: "strong" },
      { text: "Above target budget", tone: "warn" },
    ],
  },
  {
    id: "ibl_9cd2",
    source_primary: "ibilik",
    source_variants: ["ibilik"],
    url: "https://example.com/listing/ibl_9cd2",
    title: "Budget single room near Cheras South with WiFi and aircond",
    price_rm: 480,
    deposit_rm: 960,
    location_area: "Cheras South",
    location_city: "Cheras",
    room_type: "single",
    furnished_status: "partially",
    gender_restriction: "female",
    parking: "no",
    nearby_transport: ["MRT Bandar Tun Hussein Onn (900m)"],
    facilities: ["WiFi", "Aircond"],
    match_score: 76,
    score_explanation:
      "Excellent price fit and acceptable transport proximity, but the furnishing package is only partial and there is no parking.",
    score_breakdown: {
      price: 24,
      location: 13,
      room_type: 15,
      transport: 9,
      furnished: 6,
      parking: 0,
      pet: 0,
      gender: 3,
    },
    contact_phone: null,
    contact_telegram: "@cherassouth_room",
    outreach_status: "not_started",
    low_confidence_flags: [],
    rtb: [
      { text: "Under RM500", tone: "strong" },
      { text: "Female-only", tone: "strong" },
      { text: "Partial furnishing", tone: "warn" },
    ],
  },
];

export const SAMPLE_RESULTS: SessionResults = {
  session_id: "demo-session",
  pipeline_status: "complete",
  summary_report:
    "Strongest matches cluster in Taman Connaught and Taman Midah, where furnished rooms stay close to budget while keeping MRT access practical.",
  filters: {
    location: "Cheras",
    price_min: 400,
    price_max: 600,
    room_type: "single",
    furnished_status: "fully",
    gender_restriction: "female",
    parking: false,
    transport: "MRT",
    pet_friendly: false,
    max_results: 30,
  },
  listings: SAMPLE_LISTINGS,
};

export function getInitialFilters(
  params: URLSearchParams,
): Partial<FilterFormData> | undefined {
  if (Array.from(params.keys()).length === 0) return undefined;

  return {
    location: params.get("location") ?? "",
    price_min: params.get("price_min") ?? "",
    price_max: params.get("price_max") ?? "",
    room_type: params.get("room_type") ?? "any",
    furnished_status: params.get("furnished_status") ?? "any",
    gender_restriction: params.get("gender_restriction") ?? "any",
    parking: params.get("parking") === "true",
    transport: params.get("transport") ?? "",
    pet_friendly: params.get("pet_friendly") === "true",
    max_results: params.get("max_results") ?? "30",
    must_haves: [],
    enable_telegram_outreach: true,
  };
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/api/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) throw new Error("Chat API error");
  return res.json() as Promise<ChatResponse>;
}

export async function checkFacebookStatus(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/facebook/status`);
    if (!res.ok) return false;
    const data = await res.json();
    return data.logged_in as boolean;
  } catch {
    return false;
  }
}

export async function startSearch(filters: Record<string, unknown>): Promise<{ session_id: string }> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}

export async function fetchSessionResults(id: string) {
  const res = await fetch(`${API_URL}/api/search/${id}/results`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to fetch results.");
  }

  return (await res.json()) as SessionResults;
}
