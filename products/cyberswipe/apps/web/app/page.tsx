"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiLogin, setToken, setNick } from "./lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [nick, setNickInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!nick.trim()) {
      setError("Wpisz swój nick, aby rozpocząć.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await apiLogin(nick.trim());
      setToken(res.token);
      setNick(res.nick);
      router.push("/game");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Błąd serwera. Spróbuj nownie.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8fafc] px-4">
      <div className="w-full max-w-sm text-center">
        {/* Simple Header */}
        <div className="mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#0ea5e9] text-white rounded-2xl mb-6 shadow-md">
            <svg
              className="w-8 h-8"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-[#1e293b] tracking-tight">CyberSwipe</h1>
          <p className="mt-3 text-sm text-[#64748b]">
            Platforma edukacyjna do rozpoznawania zagrożeń w sieci.
          </p>
        </div>

        {/* Clean Login Form */}
        <div className="clean-card p-6 md:p-8 text-left">
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label
                htmlFor="nick"
                className="block text-sm font-medium text-[#475569] mb-1.5"
              >
                Twój identyfikator
              </label>
              <input
                id="nick"
                type="text"
                value={nick}
                onChange={(e) => {
                  setNickInput(e.target.value);
                  setError("");
                }}
                placeholder="Wpisz nazwę"
                maxLength={20}
                autoFocus
                className="w-full px-4 py-3 bg-white border border-[#e2e8f0] rounded-xl text-[#1e293b] placeholder-[#94a3b8] focus:outline-none focus:border-[#0ea5e9] focus:ring-1 focus:ring-[#0ea5e9] transition-colors shadow-sm"
              />
            </div>

            {error && (
              <div className="text-[#ef4444] text-sm bg-[#fef2f2] border border-[#fca5a5] rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 px-4 rounded-xl font-semibold text-white bg-[#0ea5e9] hover:bg-[#0284c7] transition-colors disabled:opacity-50 shadow-sm flex items-center justify-center gap-2"
            >
              {loading ? (
                <span>Logowanie...</span>
              ) : (
                <span>Rozpocznij naukę</span>
              )}
            </button>
          </form>
        </div>

        <p className="text-center mt-8 text-xs text-[#94a3b8]">
          Gwarantujemy anonimowość platformy.
        </p>
      </div>
    </div>
  );
}
