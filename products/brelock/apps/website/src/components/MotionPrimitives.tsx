"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowDown } from "lucide-react";
import { motion, MotionConfig, useReducedMotion } from "motion/react";

export const gentleEase = [0.22, 1, 0.36, 1] as const;

export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user" transition={{ duration: 0.75, ease: gentleEase }}>{children}</MotionConfig>;
}

export function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 34 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: reduced ? 0 : 0.85, delay, ease: gentleEase }}
    >{children}</motion.div>
  );
}

export function DownloadDock() {
  const reduced = useReducedMotion();
  return (
    <motion.aside
      className="download-dock"
      aria-label="Pobierz aplikację breLock"
      initial={reduced ? false : { y: 110, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 130, damping: 24, delay: reduced ? 0 : 1 }}
    >
      <motion.div whileHover={reduced ? undefined : { y: -3 }} whileTap={{ scale: 0.98 }}>
        <Link href="/pobierz" className="dock-link">Pobierz breLock <ArrowDown size={18} strokeWidth={1.6} /></Link>
      </motion.div>
      <p>macOS · Windows <span>—</span> wersja prototypowa</p>
    </motion.aside>
  );
}
