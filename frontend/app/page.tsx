import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SAMPLE_LISTINGS } from "@/lib/homie";

export default function Home() {
  const featured = SAMPLE_LISTINGS[0];

  return (
    <AppShell activePath="/">
      <main className="mx-auto flex max-w-full flex-col gap-20 px-4 py-10 sm:px-6 lg:px-8 lg:py-16">
        <section className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
          <div className="max-w-3xl">
            <div className="mb-6 flex flex-wrap gap-3">
              <Badge variant="info">Read every listing across ibilik and iProperty</Badge>
              <Badge variant="outline">English, Bahasa, and Chinese</Badge>
            </div>
            <h1 className="font-display text-balance text-6xl leading-none text-stone-950 sm:text-7xl lg:text-[6.5rem]">
              Find your next home without the chaos.
            </h1>
            <p className="mt-6 max-w-2xl text-xl leading-8 text-stone-600">
              Homie sends an agent across rental platforms, normalizes the mess,
              scores every match against your constraints, and shows the reasoning
              before you contact anyone.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link href="/search">
                <Button variant="secondary" size="lg">
                  Start manual search
                </Button>
              </Link>
              <Link href="/chat">
                <Button variant="outline" size="lg">
                  Talk to the intake agent
                </Button>
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-3 text-base text-stone-500">
              <Badge variant="success">ibilik connected</Badge>
              <Badge variant="success">iProperty connected</Badge>
              <Badge variant="warning">Facebook limited</Badge>
            </div>
          </div>

          <Card className="overflow-hidden border-stone-300 bg-white/90">
            <div className="border-b border-stone-200 bg-[linear-gradient(160deg,_rgba(251,146,60,0.94),_rgba(249,115,22,0.72)),radial-gradient(circle_at_top_left,_rgba(255,255,255,0.35),_transparent_35%)] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm uppercase tracking-[0.24em] text-white/80">
                    Top pick preview
                  </div>
                  <div className="mt-2 font-display text-5xl leading-none text-white">
                    {featured.location_area}
                  </div>
                </div>
                <div className="rounded-full bg-stone-950 px-4 py-2 text-sm font-semibold text-white">
                  {featured.match_score}/100
                </div>
              </div>
            </div>
            <CardContent className="space-y-6 p-6">
              <div>
                <div className="font-display text-5xl leading-none text-stone-950">
                  RM{featured.price_rm}
                </div>
                <p className="mt-3 text-base leading-6 text-stone-600">
                  {featured.title}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(featured.rtb ?? []).map((item) => (
                  <Badge
                    key={item.text}
                    variant={item.tone === "warn" ? "warning" : "success"}
                  >
                    {item.text}
                  </Badge>
                ))}
              </div>
              <div className="rounded-[24px] bg-stone-50 p-5">
                <div className="text-sm uppercase tracking-[0.24em] text-stone-400">
                  Agent trace
                </div>
                <div className="mt-3 space-y-2 font-mono text-base text-stone-600">
                  <div>✓ validate_filters</div>
                  <div>✓ run_scraper(ibilik)</div>
                  <div>✓ normalize(21)</div>
                  <div>• score → current top: 94</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-5 md:grid-cols-3">
          {[
            {
              title: "Show the thinking",
              body: "Every rank carries an explanation, confidence flags, and source provenance instead of a black-box score.",
            },
            {
              title: "Unify different listing styles",
              body: "Homie standardizes price, furnishing, transport, and contact details across inconsistent pages.",
            },
            {
              title: "Move from shortlist to outreach",
              body: "Inspect one listing deeply, then jump into a dedicated outreach page with draft messaging.",
            },
          ].map((item) => (
            <Card key={item.title} className="border-stone-300">
              <CardContent className="space-y-3 p-6">
                <div className="text-sm uppercase tracking-[0.24em] text-orange-500">
                  Feature
                </div>
                <h2 className="text-xl font-semibold text-stone-950">{item.title}</h2>
                <p className="text-base leading-6 text-stone-600">{item.body}</p>
              </CardContent>
            </Card>
          ))}
        </section>
      </main>
    </AppShell>
  );
}
