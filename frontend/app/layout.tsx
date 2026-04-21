import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Homie — Find Your Next Home",
  description: "AI-powered rental aggregation across Malaysian platforms",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
