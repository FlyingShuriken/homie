"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ChatFilterSidebar } from "@/components/ChatFilterSidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  API_URL,
  ChatFilters,
  ChatConfidence,
  ChatMessage,
  sendChatMessage,
  startSearch,
  checkFacebookStatus,
} from "@/lib/homie";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  loading?: boolean;
}

const INITIAL_MESSAGE: DisplayMessage = {
  role: "assistant",
  content:
    "Hi! I'm Homie. Tell me what you're looking for — area, budget, room type — and I'll find + rank it across ibilik, iProperty, and Facebook.",
};

const EMPTY_FILTERS: ChatFilters = { max_results: 30, must_haves: [] };
const EMPTY_CONFIDENCE: ChatConfidence = {};

export default function ChatPage() {
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [messages, setMessages] = useState<DisplayMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [searching, setSearching] = useState(false);
  const [chips, setChips] = useState<string[]>(["Single room", "Near MRT", "Under RM700"]);
  const [filters, setFilters] = useState<ChatFilters>(EMPTY_FILTERS);
  const [confidence, setConfidence] = useState<ChatConfidence>(EMPTY_CONFIDENCE);
  const [telegramEnabled, setTelegramEnabled] = useState(true);
  const [readyToSearch, setReadyToSearch] = useState(false);
  const [fbGate, setFbGate] = useState<"hidden" | "prompt" | "connecting" | "done">("hidden");
  const pendingSearchRef = useRef<Record<string, unknown> | null>(null);

  // Build history for the API — skip index 0 (hardcoded initial greeting, not a real backend turn)
  const apiHistory: ChatMessage[] = messages
    .slice(1)
    .filter((m) => !m.loading)
    .map((m) => ({ role: m.role, content: m.content }));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || sending) return;
    setInput("");

    const userMsg: DisplayMessage = { role: "user", content: msg };
    const loadingMsg: DisplayMessage = { role: "assistant", content: "", loading: true };
    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setSending(true);

    try {
      const response = await sendChatMessage(msg, apiHistory);

      setMessages((prev) => [
        ...prev.slice(0, -1), // remove loading stub
        { role: "assistant", content: response.reply },
      ]);
      setFilters(response.filters ?? EMPTY_FILTERS);
      setConfidence(response.confidence ?? EMPTY_CONFIDENCE);
      setChips(response.suggested_chips ?? []);
      setReadyToSearch(response.ready_to_search ?? false);
    } catch {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          role: "assistant",
          content: "Sorry, I hit a snag. Try again in a moment.",
        },
      ]);
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  async function doStartSearch(payload: Record<string, unknown>) {
    try {
      const { session_id } = await startSearch(payload);
      router.push(`/workflow/${session_id}`);
    } catch {
      setSearching(false);
    }
  }

  async function handleStartSearch() {
    if (!filters.location || !filters.price_max) return;
    setSearching(true);

    const payload = {
      location: filters.location,
      price_min: filters.price_min ?? 0,
      price_max: filters.price_max,
      room_type: filters.room_type ?? "any",
      furnished_status: filters.furnished_status ?? "any",
      gender_restriction: filters.gender_restriction ?? "any",
      parking: filters.parking ?? false,
      transport: filters.transport ?? "",
      pet_friendly: filters.pet_friendly ?? false,
      max_results: filters.max_results ?? 30,
      must_haves: filters.must_haves ?? [],
      enable_telegram_outreach: telegramEnabled,
    };

    const fbLoggedIn = await checkFacebookStatus();
    if (!fbLoggedIn) {
      pendingSearchRef.current = payload;
      setSearching(false);
      setFbGate("prompt");
      return;
    }

    await doStartSearch(payload);
  }

  async function handleFbConnect() {
    setFbGate("connecting");
    try {
      const res = await fetch(`${API_URL}/api/facebook/login`, { method: "POST" });
      if (!res.ok) throw new Error();
      setFbGate("done");
    } catch {
      setFbGate("prompt");
    }
  }

  async function handleFbSkip() {
    setFbGate("hidden");
    if (!pendingSearchRef.current) return;
    setSearching(true);
    await doStartSearch(pendingSearchRef.current);
    pendingSearchRef.current = null;
  }

  async function handleFbContinueAfterConnect() {
    setFbGate("hidden");
    if (!pendingSearchRef.current) return;
    setSearching(true);
    await doStartSearch(pendingSearchRef.current);
    pendingSearchRef.current = null;
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const canSearch = Boolean(filters.location && filters.price_max);

  return (
    <AppShell activePath="/chat">
      {/* Facebook login gate modal */}
      {fbGate !== "hidden" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-lg">f</div>
              <div>
                <p className="font-semibold text-gray-900">Connect Facebook</p>
                <p className="text-xs text-gray-500">Unlock rental posts from Facebook groups</p>
              </div>
            </div>

            {fbGate === "prompt" && (
              <>
                <p className="text-sm text-gray-600 mb-5">
                  Facebook has the most listings from local rental groups. Connect your account to include them in your search.
                </p>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={handleFbConnect}
                    className="w-full bg-blue-600 text-white text-sm font-medium py-2.5 rounded-xl hover:bg-blue-700 transition-colors"
                  >
                    Connect Facebook
                  </button>
                  <button
                    onClick={handleFbSkip}
                    className="w-full text-gray-500 text-sm py-2 hover:text-gray-700 transition-colors"
                  >
                    Skip, search without Facebook
                  </button>
                </div>
              </>
            )}

            {fbGate === "connecting" && (
              <p className="text-sm text-center text-gray-500 py-4">
                A browser window will open — log in to Facebook there. This may take a moment.
              </p>
            )}

            {fbGate === "done" && (
              <>
                <p className="text-sm text-center text-green-600 font-medium py-2 mb-4">
                  Facebook connected! Your search will include Facebook posts.
                </p>
                <button
                  onClick={handleFbContinueAfterConnect}
                  className="w-full bg-orange-500 text-white text-sm font-medium py-2.5 rounded-xl hover:bg-orange-600 transition-colors"
                >
                  Start Search
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <main className="mx-auto max-w-full px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
        {/* Page header */}
        <div className="mb-6">
          <div className="mb-1 text-xs font-semibold uppercase tracking-[0.24em] text-orange-500">
            New search
          </div>
          <h1 className="font-display text-5xl leading-none text-stone-950">
            Talk to the <span className="text-orange-500">agent.</span>
          </h1>
          <p className="mt-2 text-base text-stone-500">
            Describe it in plain words. The agent asks back, extracts filters live.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          {/* Chat panel */}
          <Card className="flex flex-col overflow-hidden border-stone-200">
            {/* Toggle bar */}
            <div className="flex items-center gap-3 border-b border-stone-200 px-5 py-4">
              <Badge variant="info">Chat agent</Badge>
              <Link href="/search" className="ml-auto">
                <Button variant="ghost" size="sm">
                  ⊞ Manual form
                </Button>
              </Link>
            </div>

            {/* Messages */}
            <CardContent className="flex flex-1 flex-col gap-5 overflow-y-auto p-5">
              {messages.map((msg, i) => (
                <ChatBubble key={i} message={msg} />
              ))}
              <div ref={bottomRef} />
            </CardContent>

            {/* Input area */}
            <div className="border-t border-stone-200 p-4">
              <div className="rounded-2xl border border-stone-300 bg-stone-50 p-4">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="min-h-14 resize-none border-none bg-transparent p-0 shadow-none focus-visible:ring-0"
                  placeholder="Refine, ask, or say 'go'…"
                  disabled={sending}
                />
                <div className="mt-3 flex items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    {chips.map((chip) => (
                      <button
                        key={chip}
                        onClick={() => handleSend(chip)}
                        disabled={sending}
                        className="rounded-full border border-stone-300 bg-white px-3 py-1 text-xs text-stone-600 transition hover:border-stone-400 hover:bg-stone-100 disabled:opacity-40"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                  <Button
                    onClick={() => handleSend()}
                    disabled={!input.trim() || sending}
                    variant="secondary"
                    size="sm"
                  >
                    Send →
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* Filter sidebar */}
          <div className="lg:sticky lg:top-24 lg:self-start">
            <ChatFilterSidebar
              filters={filters}
              confidence={confidence}
              onStartSearch={handleStartSearch}
              isSearching={searching}
              telegramEnabled={telegramEnabled}
              onToggleTelegram={setTelegramEnabled}
            />
            {!canSearch && (
              <p className="mt-2 text-center text-xs text-stone-400">
                Tell me the area and budget to enable search
              </p>
            )}
          </div>
        </div>
      </main>
    </AppShell>
  );
}

function ChatBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === "user";

  return (
    <div className="flex gap-3">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl text-sm font-semibold ${
          isUser
            ? "bg-stone-200 text-stone-700"
            : "bg-orange-500 text-white"
        }`}
      >
        {isUser ? "You" : "H"}
      </div>
      <div className="min-w-0 flex-1 pt-1">
        {message.loading ? (
          <div className="flex gap-1 py-3">
            <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 [animation-delay:0ms]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 [animation-delay:150ms]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 [animation-delay:300ms]" />
          </div>
        ) : (
          <div className="rounded-2xl bg-stone-50 px-4 py-3 text-sm leading-7 text-stone-700 whitespace-pre-wrap">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}
