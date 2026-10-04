"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

export default function SiteHeader() {
  const reduced = useReducedMotion();
  return (
    <header className="site-header">
      <motion.div className="header-inner" initial={reduced ? false : { opacity: 0, y: -22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 0.1 }}>
        <Link href="/" className="brand" aria-label="breLock — strona główna">bre<span>Lock</span><i>.</i></Link>
        <nav aria-label="Nawigacja główna" className="header-navigation">
          <Link href="/#dzialanie" className="nav-how">Jak działa</Link>
          <Link href="/#demo">Demo</Link>
          <Link href="/pobierz" className="download-link">Pobierz <ArrowUpRight size={14} /></Link>
        </nav>
      </motion.div>
    </header>
  );
}
