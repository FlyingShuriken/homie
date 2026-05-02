import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Homie | AI Rental Search",
  description:
    "Next.js frontend for Homie's rental search, workflow tracking, ranking, and outreach flow.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-stone-50 font-sans text-stone-900 antialiased">
        {children}
      </body>
    </html>
  );
}
