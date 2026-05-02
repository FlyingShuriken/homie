"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat agent" },
  { href: "/search", label: "Manual search" },
];

export function AppShell({
  children,
  activePath,
}: {
  children: React.ReactNode;
  activePath?: string;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.16),_transparent_32%),linear-gradient(180deg,_#fffaf1_0%,_#f7f2e8_100%)]">
      <header className="sticky top-0 z-30 border-b border-stone-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto max-w-full px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-stone-950 text-base font-semibold text-stone-50">
                H
              </div>
              <div>
                <div className="font-display text-3xl leading-none text-stone-950">
                  Homie
                </div>
                <div className="text-sm uppercase tracking-[0.24em] text-stone-500">
                  Rental Agent
                </div>
              </div>
            </Link>

            <nav className="hidden items-center gap-2 md:flex">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "rounded-full px-5 py-2.5 text-base transition",
                    activePath === link.href
                      ? "bg-stone-950 text-stone-50"
                      : "text-stone-600 hover:bg-stone-100",
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            <div className="ml-auto hidden items-center gap-2 sm:flex">
              <Badge variant="success">Demo-ready workflow</Badge>
              <Badge variant="outline" className="hidden md:inline-flex">
                Klang Valley
              </Badge>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
              aria-label="Toggle navigation"
              className="ml-auto flex h-10 w-10 flex-col gap-1 rounded-full px-0 md:hidden"
              onClick={() => setMobileOpen((current) => !current)}
            >
              <span className="h-0.5 w-4 rounded-full bg-current" />
              <span className="h-0.5 w-4 rounded-full bg-current" />
              <span className="h-0.5 w-4 rounded-full bg-current" />
            </Button>
          </div>

          {mobileOpen ? (
            <nav
              id="mobile-navigation"
              className="mt-4 grid gap-2 border-t border-stone-200 pt-4 md:hidden"
            >
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "rounded-2xl px-4 py-3 text-base transition",
                    activePath === link.href
                      ? "bg-stone-950 text-stone-50"
                      : "text-stone-700 hover:bg-stone-100",
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </header>

      {children}
    </div>
  );
}
