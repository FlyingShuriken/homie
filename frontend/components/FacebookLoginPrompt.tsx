"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Status = "idle" | "connecting" | "done" | "error";

export default function FacebookLoginPrompt({ onDismiss }: { onDismiss: () => void }) {
  const [status, setStatus] = useState<Status>("idle");

  async function handleConnect() {
    setStatus("connecting");
    try {
      const res = await fetch(`${API}/api/facebook/login`, { method: "POST" });
      if (!res.ok) throw new Error();
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="fixed bottom-6 right-6 max-w-sm bg-white border border-gray-200 rounded-xl shadow-lg p-4 z-50">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-800">Unlock Facebook post search</p>
          <p className="text-xs text-gray-500 mt-1">
            Connect your Facebook account to search rental posts from groups and pages.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onDismiss}
          className="mt-0.5 h-auto px-1 text-sm leading-none text-gray-400 hover:bg-transparent hover:text-gray-600"
          aria-label="Dismiss"
        >
          x
        </Button>
      </div>

      <div className="mt-3">
        {status === "idle" && (
          <Button
            type="button"
            variant="default"
            onClick={handleConnect}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm text-white hover:bg-blue-700 focus-visible:ring-blue-600"
          >
            Connect Facebook
          </Button>
        )}
        {status === "connecting" && (
          <p className="text-xs text-center text-gray-500 py-1">
            A browser window will open. Log in to Facebook there.
          </p>
        )}
        {status === "done" && (
          <p className="text-xs text-center text-green-600 font-medium py-1">
            Connected! Run a new search to include Facebook posts.
          </p>
        )}
        {status === "error" && (
          <p className="text-xs text-center text-red-500 py-1">
            Connection failed. Make sure FB_COOKIES_PATH is configured.
          </p>
        )}
      </div>
    </div>
  );
}
