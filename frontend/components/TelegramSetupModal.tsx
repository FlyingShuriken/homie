"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onDismiss}
            className="h-auto px-1 text-sm text-stone-400 hover:bg-transparent hover:text-stone-600"
          >
            x
          </Button>
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
              <Input
                type="number"
                required
                placeholder="12345678"
                value={apiId}
                onChange={(e) => setApiId(e.target.value)}
                className="rounded-lg focus:border-blue-500 focus:ring-blue-100"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">API Hash</label>
              <Input
                type="text"
                required
                placeholder="0abc123def..."
                value={apiHash}
                onChange={(e) => setApiHash(e.target.value)}
                className="rounded-lg font-mono focus:border-blue-500 focus:ring-blue-100"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Phone number (with country code)</label>
              <Input
                type="tel"
                required
                placeholder="+60123456789"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="rounded-lg focus:border-blue-500 focus:ring-blue-100"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              variant="default"
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 focus-visible:ring-blue-600"
            >
              {loading ? "Sending code..." : "Send verification code"}
            </Button>
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={handleVerify} className="space-y-4">
            <p className="text-sm text-stone-600">
              A verification code was sent to <strong>{phone}</strong> via Telegram. Enter it below.
            </p>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Verification code</label>
              <Input
                type="text"
                required
                autoFocus
                placeholder="12345"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                className="rounded-lg text-center tracking-widest font-mono focus:border-blue-500 focus:ring-blue-100"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              variant="default"
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 focus-visible:ring-blue-600"
            >
              {loading ? "Verifying..." : "Verify"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep("form")}
              className="w-full text-xs text-stone-400 hover:text-stone-600"
            >
              Back
            </Button>
          </form>
        )}

        {step === "2fa" && (
          <form onSubmit={handleVerify} className="space-y-4">
            <p className="text-sm text-stone-600">
              Your account has two-step verification enabled. Enter your cloud password.
            </p>
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Cloud password</label>
              <Input
                type="password"
                required
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-lg focus:border-blue-500 focus:ring-blue-100"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              variant="default"
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 focus-visible:ring-blue-600"
            >
              {loading ? "Verifying..." : "Confirm"}
            </Button>
          </form>
        )}

        {step === "done" && (
          <div className="text-center py-4 space-y-3">
            <p className="text-2xl">✓</p>
            <p className="text-sm font-medium text-emerald-700">Telegram connected successfully.</p>
            <p className="text-xs text-stone-500">You can now start automated outreach.</p>
            <Button
              type="button"
              onClick={onDismiss}
              variant="outline"
              className="mt-2 rounded-lg"
            >
              Close
            </Button>
          </div>
        )}

        {step === "error" && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">{errorMsg}</p>
            <Button
              type="button"
              onClick={() => { setStep("form"); setErrorMsg(""); }}
              variant="outline"
              className="w-full rounded-lg"
            >
              Try again
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
