"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiGetTasks, apiSwipe, apiGetStats, Task, SwipeResult, Stats } from "../lib/api";

type ActionType = "scan" | "ignore" | "image_1" | "image_2" | "image_3" | "image_4" | "skip";

function QuishingCard({ task, onAnswer, answeredResult }: { task: Task; onAnswer: (a: ActionType) => void; answeredResult: SwipeResult | null }) {
  return (
    <div className="w-full h-full p-6 flex flex-col justify-center max-w-md mx-auto">
      <div className="clean-card p-6 flex-1 max-h-[70vh] flex flex-col overflow-y-auto">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-[#1e293b] leading-tight mb-1">{task.title}</h3>
            <span className="text-sm text-[#64748b]">{task.location}</span>
          </div>
          <span className={`px-3 py-1 text-xs font-semibold rounded-full border ${
            task.risk_level === 'high' ? 'bg-[#fef2f2] text-[#ef4444] border-[#fecaca]' : 
            task.risk_level === 'medium' ? 'bg-[#fffbeb] text-[#f59e0b] border-[#fde68a]' : 
            'bg-[#ecfdf5] text-[#10b981] border-[#a7f3d0]'
          }`}>
            {task.risk_level === "high" ? "Wysokie" : task.risk_level === "medium" ? "Średnie" : "Niskie"}
          </span>
        </div>

        <div className="flex-1">
          <p className="text-[#334155] text-base leading-relaxed mb-6">{task.description}</p>
          <div className="bg-[#f8fafc] border border-[#e2e8f0] rounded-xl p-4 mb-6">
            <p className="text-sm text-[#475569] leading-relaxed"><span className="font-semibold text-[#0ea5e9]">Wskazówka:</span> {task.hint}</p>
          </div>
        </div>

        {answeredResult ? (
          <div className={`p-4 rounded-xl border ${answeredResult.correct ? "bg-[#ecfdf5] border-[#10b981]" : "bg-[#fef2f2] border-[#ef4444]"}`}>
            <h4 className={`font-bold mb-1 ${answeredResult.correct ? "text-[#10b981]" : "text-[#ef4444]"}`}>
              {answeredResult.correct ? "Dobry wybór!" : "Zła decyzja"}
            </h4>
            <p className="text-sm text-[#334155]">{answeredResult.explanation}</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 mt-auto">
            <button
              onClick={() => onAnswer("ignore")}
              className="btn-outline py-4 w-full text-[#ef4444] border-[#fecaca] hover:bg-[#fef2f2]"
            >
              Ignoruj QR
            </button>
            <button
              onClick={() => onAnswer("scan")}
              className="btn-primary py-4 w-full bg-[#0ea5e9] hover:bg-[#0284c7]"
            >
              Zeskanuj
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function AIImageCard({ task, onAnswer, answeredResult }: { task: Task; onAnswer: (a: ActionType) => void; answeredResult: SwipeResult | null }) {
  return (
    <div className="w-full h-full p-6 flex flex-col justify-center max-w-md mx-auto">
      <div className="clean-card p-6 flex-1 max-h-[85vh] flex flex-col overflow-hidden">
        <div className="mb-4">
          <h3 className="text-xl font-bold text-[#1e293b] leading-tight mb-1">{task.title}</h3>
          <p className="text-[#475569] text-sm leading-relaxed">{task.description}</p>
        </div>

        {answeredResult ? (
          <div className={`p-3 mb-4 rounded-xl border overflow-y-auto max-h-[30vh] ${answeredResult.correct ? "bg-[#ecfdf5] border-[#10b981]" : "bg-[#fef2f2] border-[#ef4444]"}`}>
            <h4 className={`font-bold mb-1 ${answeredResult.correct ? "text-[#10b981]" : "text-[#ef4444]"}`}>
              {answeredResult.correct ? "Świetnie!" : "Pudło"}
            </h4>
            <p className="text-sm text-[#334155]">{answeredResult.explanation}</p>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-2 flex-1 mt-auto">
          {task.images?.map((url, idx) => (
            <button
              key={idx}
              disabled={!!answeredResult}
              onClick={() => onAnswer(`image_${idx + 1}` as ActionType)}
              className="relative aspect-square rounded-xl overflow-hidden border border-[#e2e8f0] focus:outline-none focus:ring-2 focus:ring-[#0ea5e9] transition-transform active:scale-95 disabled:scale-100 disabled:opacity-80"
            >
              {/* Using standard img tag, Next.js Image might require external domains config which isn't guaranteed here */}
              <img src={url} alt={`Opcja ${idx + 1}`} className="absolute inset-0 w-full h-full object-cover" />
              <div className="absolute top-2 left-2 w-6 h-6 bg-white/90 backdrop-blur-sm rounded-full flex items-center justify-center text-xs font-bold shadow-sm">
                {idx + 1}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function GamePage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState<Record<number, SwipeResult>>({});
  const [toast, setToast] = useState<{ msg: string; pts: number } | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const taskRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [t, s] = await Promise.all([apiGetTasks(), apiGetStats()]);
        setTasks(t);
        setStats(s);
      } catch {
        router.push("/");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  // We removed IntersectionObserver here because it was firing automatically on render/layout shifts.
  // We handle skips directly inside handleAnswer now.

  // Temp toast clearer
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleAnswer = async (task: Task, action: ActionType, idx: number) => {
    if (answers[task.id]) return; // Already answered

    // Find and skip previous tasks sequentially to reset combo if user skipped over them
    const previousUnanswered = tasks.slice(0, idx).filter(t => !answers[t.id]);
    if (previousUnanswered.length > 0) {
      setToast({ msg: "Obniżono kombo - pominięto poprzednie pytania", pts: 0 });
      for (const pt of previousUnanswered) {
        try {
          const skipRes = await apiSwipe(pt.id, "skip");
          // Safely set answer state for skipped items
          setAnswers(prev => ({ ...prev, [pt.id]: skipRes }));
        } catch (e) {
          console.error("Skip error", e);
        }
      }
    }

    try {
      const res = await apiSwipe(task.id, action);
      setAnswers(prev => ({ ...prev, [task.id]: res }));
      setStats(prev => prev ? { 
        ...prev, 
        score: res.total_score, 
        combo: res.combo, 
        answered: prev.answered + 1,
        progress_pct: Math.round(((prev.answered + 1) / prev.total_tasks) * 100) 
      } : prev);
      
      setToast({ msg: res.correct ? "Dobrze!" : "Źle!", pts: res.points_earned });

      // Auto scroll to next after short delay
      setTimeout(() => {
        const nextEl = taskRefs.current[idx + 1];
        if (nextEl) {
          nextEl.scrollIntoView({ behavior: "smooth" });
        }
      }, 1500);

    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8fafc]">
        <div className="animate-pulse text-[#0ea5e9]">Ładowanie...</div>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#f8fafc] px-4">
        <div className="clean-card p-8 text-center max-w-sm w-full">
          <div className="w-16 h-16 bg-[#f0f9ff] text-[#0ea5e9] rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-[#1e293b] mb-2">To już wszystko!</h2>
          <p className="text-[#64748b] mb-6">Ukończyłeś wszystkie dostępne zadania.</p>
          <div className="bg-[#f8fafc] rounded-xl p-4 mb-6">
            <p className="text-sm text-[#475569]">Twój końcowy wynik:</p>
            <p className="text-3xl font-bold text-[#0ea5e9] mt-1">{stats?.score}</p>
          </div>
          <button
            onClick={() => router.push("/leaderboard")}
            className="btn-primary w-full py-3.5"
          >
            Zobacz Ranking
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#f8fafc]">
      {/* Absolute overlay header */}
      <header className="fixed top-0 left-0 right-0 p-4 z-50 flex items-center justify-between pointer-events-none">
        <button
          onClick={() => router.push("/leaderboard")}
          className="pointer-events-auto bg-white/90 backdrop-blur shadow-sm p-2 rounded-full text-[#334155] border border-[#e2e8f0]"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.672a.375.375 0 01-.375.375H7.875a.375.375 0 01-.375-.375v-10.5a.375.375 0 01.375-.375h8.25a.375.375 0 01.375.375v10.5z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 5.25h3m-3 0V3m3 2.25V3" />
          </svg>
        </button>
        
        {stats && (
          <div className="flex gap-2 pointer-events-auto">
            <div className="bg-white/90 backdrop-blur shadow-sm px-4 py-1.5 rounded-full border border-[#e2e8f0] text-sm font-semibold text-[#1e293b]">
              Wynik: <span className="text-[#0ea5e9]">{stats.score}</span>
            </div>
            {stats.combo > 1 && (
              <div className="bg-[#fffbeb]/90 backdrop-blur shadow-sm px-3 py-1.5 rounded-full border border-[#fde68a] text-sm font-bold text-[#d97706]">
                Combo {stats.combo}x
              </div>
            )}
          </div>
        )}
      </header>

      {/* Reels scroll container */}
      <div 
        className="h-full w-full overflow-y-auto snap-y snap-mandatory" 
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        ref={containerRef}
      >
        {tasks.map((task, idx) => (
          <div 
            key={task.id} 
            data-idx={idx}
            className="h-full w-full flex-shrink-0 snap-start snap-always"
            ref={(el) => { taskRefs.current[idx] = el; }}
          >
            {task.type === "ai_image" ? (
              <AIImageCard task={task} onAnswer={(a) => handleAnswer(task, a, idx)} answeredResult={answers[task.id]} />
            ) : (
              <QuishingCard task={task} onAnswer={(a) => handleAnswer(task, a, idx)} answeredResult={answers[task.id]} />
            )}
          </div>
        ))}

        {/* End of tasks spacer */}
        <div className="h-full w-full flex-shrink-0 snap-start snap-always flex items-center justify-center">
           <div className="clean-card p-8 text-center max-w-sm w-full mx-4">
             <h2 className="text-xl font-bold mb-4">Koniec nowości</h2>
             <button onClick={() => router.push("/leaderboard")} className="btn-primary py-3 w-full border border-[#e2e8f0] font-semibold text-white">Przejdź do rankingu</button>
           </div>
        </div>
      </div>

      {/* Minimal Toast overlay */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-bounce">
          <div className="bg-[#1e293b] text-white px-6 py-3 rounded-full shadow-lg font-medium flex items-center gap-3">
            <span>{toast.msg}</span>
            {toast.pts > 0 && <span className="text-[#38bdf8]">+{toast.pts}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
