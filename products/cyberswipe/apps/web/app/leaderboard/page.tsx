"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiGetLeaderboard, LeaderboardEntry, getNick } from "../lib/api";

export default function LeaderboardPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const nick = typeof window !== "undefined" ? getNick() : null;

  useEffect(() => {
    async function load() {
      try {
        const data = await apiGetLeaderboard();
        setEntries(data);
      } catch {
        router.push("/");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8fafc]">
        <div className="text-[#0ea5e9] font-medium">Ładowanie...</div>
      </div>
    );
  }

  const currentUser = entries.find((e) => e.is_current_user);

  return (
    <div className="min-h-screen bg-[#f8fafc] text-[#1e293b] flex flex-col pb-8">
      {/* Header */}
      <header className="bg-white border-b border-[#e2e8f0] sticky top-0 z-10 px-4 py-4 flex items-center justify-between shadow-sm">
        <button
          onClick={() => router.push("/game")}
          className="text-[#64748b] hover:text-[#0ea5e9] transition-colors p-2 -ml-2"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
        <h1 className="text-lg font-semibold tracking-tight">Ranking Główny</h1>
        <div className="w-6" /> {/* Spacer for centering */}
      </header>

      <div className="flex-1 px-4 sm:px-6 max-w-lg mx-auto w-full pt-6">
        
        {/* Your position highlight */}
        {currentUser && (
          <div className="clean-card bg-[#f0f9ff] border-[#bae6fd] p-4 mb-6 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-[#0ea5e9] text-white flex items-center justify-center font-bold shadow-sm">
              {currentUser.rank}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[#0369a1] truncate">{currentUser.nick} (Ty)</p>
            </div>
            <p className="text-lg font-bold text-[#0ea5e9]">{currentUser.score}</p>
          </div>
        )}

        {/* Full list */}
        <div className="clean-card overflow-hidden">
          {entries.map((entry, idx) => (
            <div
              key={entry.nick}
              className={`flex items-center gap-4 px-4 py-3 border-b border-[#f1f5f9] last:border-0 ${
                entry.is_current_user ? "bg-[#f0f9ff]" : "bg-white"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  idx < 3
                    ? "bg-[#1e293b] text-white"
                    : "bg-[#f1f5f9] text-[#64748b]"
                }`}
              >
                {entry.rank}
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${entry.is_current_user ? "text-[#0ea5e9]" : "text-[#334155]"}`}>
                  {entry.nick}
                </p>
              </div>
              <p className={`text-sm font-semibold ${entry.is_current_user ? "text-[#0ea5e9]" : "text-[#64748b]"}`}>
                {entry.score}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
