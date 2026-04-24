import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

const extracted = [
  ["Location", "Cheras"],
  ["Budget", "RM 400 - RM 700"],
  ["Room type", "Single room"],
  ["Furnishing", "Fully furnished"],
  ["Gender", "Female preferred"],
  ["Transport", "Near MRT"],
  ["Must-haves", "Aircond, WiFi"],
];

export default function ChatPage() {
  return (
    <AppShell activePath="/chat">
      <main className="mx-auto max-w-full px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <Card className="overflow-hidden border-stone-300">
            <div className="border-b border-stone-200 px-6 py-5">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="info">Chat intake</Badge>
                <Link href="/search" className="ml-auto">
                  <Button variant="ghost">Switch to manual</Button>
                </Link>
              </div>
            </div>
            <CardContent className="space-y-6 p-6">
              <ChatBubble
                speaker="You"
                text="Find me a furnished single room under RM600 near MRT in Cheras, female-only if possible."
              />
              <ChatBubble
                speaker="Homie"
                text="Searching Cheras with a furnished single-room preference under RM600. I can stretch your budget to RM690 if the match quality is significantly better."
              />
              <ChatBubble
                speaker="You"
                text="Stretch to RM700 is fine. Skip parking. Aircond and WiFi are must-haves."
              />
              <div className="rounded-[28px] border border-stone-300 bg-stone-50 p-5">
                <Textarea
                  className="min-h-28 border-none bg-transparent p-0 shadow-none focus:ring-0"
                  placeholder="Refine the brief, ask for a wider radius, or just say go..."
                />
                <div className="mt-4 flex justify-end">
                  <Button variant="secondary">Start search</Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-300 bg-white/90">
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <Badge variant="success">Live extraction</Badge>
                <span className="text-sm uppercase tracking-[0.24em] text-stone-400">
                  Parsed intent
                </span>
              </div>
              <div className="space-y-4">
                {extracted.map(([label, value]) => (
                  <div key={label} className="border-b border-stone-200 pb-4 last:border-b-0 last:pb-0">
                    <div className="text-sm uppercase tracking-[0.24em] text-stone-400">
                      {label}
                    </div>
                    <div className="mt-1 text-base font-medium text-stone-800">
                      {value}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </AppShell>
  );
}

function ChatBubble({ speaker, text }: { speaker: string; text: string }) {
  const user = speaker === "You";

  return (
    <div className="flex gap-4">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-base font-semibold ${
          user ? "bg-stone-200 text-stone-700" : "bg-orange-500 text-white"
        }`}
      >
        {user ? "Y" : "H"}
      </div>
      <div className="space-y-2">
        <div className="text-base font-semibold text-stone-900">{speaker}</div>
        <div className="max-w-2xl rounded-[24px] bg-stone-50 px-5 py-4 text-base leading-8 text-stone-700">
          {text}
        </div>
      </div>
    </div>
  );
}
