"use client";

import { useEffect, useRef, useState } from "react";
import { Coffee, KeyRound, LockKeyhole } from "lucide-react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { Reveal } from "./MotionPrimitives";

export default function InteractiveLaptop() {
  const [distance, setDistance] = useState(24);
  const [trackWidth, setTrackWidth] = useState(280);
  const trackRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const inView = useInView(sectionRef, { margin: "100px" });
  const reduced = useReducedMotion();
  const isAway = distance >= 68;

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const observer = new ResizeObserver(([entry]) => setTrackWidth(entry.contentRect.width));
    observer.observe(track);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="demo" ref={sectionRef} className="demo-section" aria-labelledby="demo-title">
      <div className="demo-inner site-container">
        <Reveal className="section-center"><p className="eyebrow">POBAW SIĘ POMYSŁEM</p><h2 id="demo-title" className="display-heading">Idziesz po kawę?<br /><em>Przesuń brelok.</em></h2><p className="demo-intro">Oddal go od komputera i zobacz docelową reakcję.</p></Reveal>
        <Reveal className="simulation-stage" delay={0.15}>
          <div className="simulation-illustration" aria-hidden="true">
            <div className="laptop-illustration">
              <div className="laptop-display">
                <span className="laptop-camera" />
                <motion.div className="laptop-screen" animate={{ backgroundColor: isAway ? "#15263b" : "#25473d" }}>
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div className="screen-state" key={isAway ? "away" : "near"} initial={reduced ? false : { opacity: 0, y: 15, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10, scale: 0.95 }} transition={{ duration: reduced ? 0 : 0.3 }}>
                      {isAway ? <LockKeyhole size={44} strokeWidth={1.2} /> : <Coffee size={44} strokeWidth={1.2} />}
                      <span>{isAway ? "Ekran zablokowany" : "Przy biurku"}</span>
                    </motion.div>
                  </AnimatePresence>
                </motion.div>
              </div>
              <div className="laptop-base"><span /></div>
            </div>
            <div className="signal-ripples">
              {[0, 1, 2].map((index) => <motion.span key={index} initial={false} animate={inView && !isAway && !reduced ? { scale: [0.65, 1.5], opacity: [0.2, 0] } : { scale: 1, opacity: 0 }} transition={inView && !isAway && !reduced ? { duration: 3.6, delay: index * 1.2, repeat: Infinity, ease: "linear" } : { duration: 0.3 }} />)}
            </div>
            <div className="signal-track" ref={trackRef}>
              <motion.div className="signal-connection" animate={{ opacity: isAway ? 0.13 : 0.6, scaleX: distance / 100 }} transition={{ duration: reduced ? 0 : 0.25 }} />
              <motion.div className="moving-fob" animate={{ x: trackWidth * distance / 100, rotate: isAway ? 10 : -8 }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 170, damping: 26 }}>
                <span className="fob-ring" /><div className="fob-body"><KeyRound size={25} strokeWidth={1.4} /><motion.span className="fob-led" animate={{ backgroundColor: isAway ? "#f08080" : "#67d8ac" }} /></div>
              </motion.div>
            </div>
          </div>
        </Reveal>
        <Reveal className="demo-controls" delay={0.2}>
          <div className="range-heading"><label htmlFor="demo-distance">Odległość breloka</label><span role="status" aria-live="polite"><i className={isAway ? "is-away" : ""} />{isAway ? "Poza strefą" : "W zasięgu"}</span></div>
          <input id="demo-distance" className="distance-slider" type="range" min="0" max="100" step="1" value={distance} aria-label="Odległość breloka od komputera" aria-valuetext={isAway ? "Poza strefą, symulacja blokady ekranu" : "W zasięgu, komputer aktywny"} onChange={(event) => setDistance(Number(event.target.value))} />
          <div className="range-ends"><span>Przy komputerze</span><span>Poza strefą</span></div>
          <p className="demo-disclaimer">To symulacja. Rzeczywista blokada systemu jest kolejnym etapem projektu.</p>
        </Reveal>
      </div>
    </section>
  );
}
