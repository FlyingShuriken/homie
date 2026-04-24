"use client";

import { useState } from "react";

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
        <button
          onClick={onDismiss}
          className="text-gray-400 hover:text-gray-600 text-sm leading-none mt-0.5"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>

      <div className="mt-3">
        {status === "idle" && (
          <button
            onClick={handleConnect}
            className="w-full bg-blue-600 text-white text-sm py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Connect Facebook
          </button>
        )}
        {status === "connecting" && (
          <p className="text-xs text-center text-gray-500 py-1">
            A browser window will open — log in to Facebook there.
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
