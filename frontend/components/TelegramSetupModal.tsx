"use client";

import { useState } from "react";
import { API_URL } from "@/lib/homie";

type Step = "form" | "otp" | "2fa" | "done" | "error";

interface Props {
  onSuccess: () => void;
  onDismiss: () => void;
}

export default function TelegramSetupModal({ onSuccess, onDismiss }: Props) {
  const [step, setStep] = useState<Step>("form");
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleConfigure(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await fetch(`${API_URL}/api/telegram/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_id: Number(apiId), api_hash: apiHash, phone }),
      });
      const data = (await res.json()) as { otp_sent?: boolean; already_authorized?: boolean; detail?: string };
      if (!res.ok) throw new Error(data.detail ?? "Configuration failed.");
      if (data.already_authorized) {
        setStep("done");
        onSuccess();
      } else {
        setStep("otp");
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
      setStep("error");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await fetch(`${API_URL}/api/telegram/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, code: otp, password }),
      });
      const data = (await res.json()) as { success?: boolean; detail?: string };
      if (!res.ok) {
        if (data.detail === "two_factor_required") {
          setStep("2fa");
          return;
        }
        throw new Error(data.detail ?? "Verification failed.");
      }
      setStep("done");
      onSuccess();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
      setStep("error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="text-base font-semibold text-stone-900">Set up Telegram outreach</p>
            <p className="mt-1 text-xs text-stone-500">
              Connects your personal Telegram account to send automated inquiries.
            </p>
          </div>
          <button onClick={onDismiss} className="text-stone-400 hover:text-stone-600 text-sm">✕</button>
        </div>

        {step === "form" && (
          <form onSubmit={handleConfigure} className="space-y-4">
            <div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-xs text-blue-700 space-y-1 leading-5">
              <p className="font-medium">How to get your API credentials:</p>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>Go to <span className="font-mono">my.telegram.org</span> and log in</li>
                <li>Click <strong>API development tools</strong></li>
                <li>Create an app — copy the <strong>App api_id</strong> and <strong>App api_hash</strong></li>
              </ol>
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">API ID</label>
              <input
                type="number"
                required
                placeholder="12345678"
                value={apiId}
                onChange={(e) => setApiId(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">API Hash</label>
              <input
                type="text"
                required
                placeholder="0abc123def..."
                value={apiHash}
                onChange={(e) => setApiHash(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm font-mono outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Phone number (with country code)</label>
              <input
                type="tel"
                required
                placeholder="+60123456789"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {loading ? "Sending code…" : "Send verification code"}
            </button>
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={handleVerify} className="space-y-4">
            <p className="text-sm text-stone-600">
              A verification code was sent to <strong>{phone}</strong> via Telegram. Enter it below.
            </p>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Verification code</label>
              <input
                type="text"
                required
                autoFocus
                placeholder="12345"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-center tracking-widest font-mono outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {loading ? "Verifying…" : "Verify"}
            </button>
            <button type="button" onClick={() => setStep("form")} className="w-full text-xs text-stone-400 hover:text-stone-600">
              Back
            </button>
          </form>
        )}

        {step === "2fa" && (
          <form onSubmit={handleVerify} className="space-y-4">
            <p className="text-sm text-stone-600">
              Your account has two-step verification enabled. Enter your cloud password.
            </p>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Cloud password</label>
              <input
                type="password"
                required
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {loading ? "Verifying…" : "Confirm"}
            </button>
          </form>
        )}

        {step === "done" && (
          <div className="text-center py-4 space-y-3">
            <p className="text-2xl">✓</p>
            <p className="text-sm font-medium text-emerald-700">Telegram connected successfully.</p>
            <p className="text-xs text-stone-500">You can now start automated outreach.</p>
            <button
              onClick={onDismiss}
              className="mt-2 rounded-lg bg-stone-100 px-4 py-2 text-sm text-stone-700 hover:bg-stone-200 transition-colors"
            >
              Close
            </button>
          </div>
        )}

        {step === "error" && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">{errorMsg}</p>
            <button
              onClick={() => { setStep("form"); setErrorMsg(""); }}
              className="w-full rounded-lg bg-stone-100 py-2 text-sm text-stone-700 hover:bg-stone-200 transition-colors"
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
