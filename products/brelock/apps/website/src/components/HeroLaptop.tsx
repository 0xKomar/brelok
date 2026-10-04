"use client";

import { useRef, useState, type PointerEvent } from "react";
import { Bluetooth, LockKeyhole, UnlockKeyhole } from "lucide-react";
import { AnimatePresence, motion, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform, useVelocity } from "motion/react";
import { gentleEase } from "./MotionPrimitives";

function BrelockFob({ away }: { away: boolean }) {
  return (
    <span className="hero-fob" aria-hidden="true">
      <span className="hero-fob-ring" />
      <span className="hero-fob-case">
        <span className="hero-fob-screw screw-left" />
        <span className="hero-fob-screw screw-right" />
        <span className="hero-fob-brand">bre<strong>Lock</strong></span>
        <span className="hero-fob-display"><LockKeyhole size={16} strokeWidth={1.5} /></span>
        <motion.span className="hero-fob-indicator" animate={{ backgroundColor: away ? "#ff7779" : "#67d8ac" }} transition={{ duration: 0.3 }} style={{ boxShadow: away ? "0 0 6px #fb636870" : "0 0 6px #67d8ac70" }} />
      </span>
    </span>
  );
}

export default function HeroLaptop() {
  const heroRef = useRef<HTMLElement>(null);
  const screenRef = useRef<HTMLDivElement>(null);
  const [pointerVisible, setPointerVisible] = useState(false);
  const [isAway, setIsAway] = useState(false);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const deviceY = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const deviceScale = useTransform(scrollYProgress, [0, 0.75], [1, 0.93]);
  const titleY = useTransform(scrollYProgress, [0, 1], [0, -90]);
  const titleOpacity = useTransform(scrollYProgress, [0, 0.58], [1, 0]);
  const cursorX = useMotionValue(0);
  const cursorY = useMotionValue(0);
  const cursorVelocity = useVelocity(cursorX);
  const cursorSwing = useTransform(cursorVelocity, [-1800, 1800], [-19, 19]);
  const fobRotation = useSpring(cursorSwing, { stiffness: 200, damping: 24 });
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);
  const rotateX = useSpring(tiltX, { stiffness: 110, damping: 28 });
  const rotateY = useSpring(tiltY, { stiffness: 110, damping: 28 });

  const followPointer = (event: PointerEvent<HTMLElement>) => {
    if (event.pointerType !== "mouse" || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    cursorX.set(event.clientX - bounds.left);
    cursorY.set(event.clientY - bounds.top);
    tiltX.set(((event.clientY - bounds.top) / bounds.height - 0.5) * -3);
    tiltY.set(((event.clientX - bounds.left) / bounds.width - 0.5) * 4);

    if ((event.target as Element).closest("a, button")) {
      setPointerVisible(false);
      return;
    }
    setPointerVisible(true);
    const screen = screenRef.current?.getBoundingClientRect();
    if (!screen) return;
    const dx = Math.max(screen.left - event.clientX, 0, event.clientX - screen.right);
    const dy = Math.max(screen.top - event.clientY, 0, event.clientY - screen.bottom);
    const distance = Math.hypot(dx, dy);
    // A little margin keeps the connection stable around the edge of the screen.
    setIsAway((wasAway) => distance > Math.min(80, screen.width * (wasAway ? 0.07 : 0.1)));
  };

  const leaveHero = () => {
    if (pointerVisible) setIsAway(true);
    setPointerVisible(false);
    tiltX.set(0);
    tiltY.set(0);
  };

  return (
    <section
      ref={heroRef}
      className={`landing-hero ${pointerVisible ? "is-pointer-active" : ""}`}
      aria-labelledby="hero-title"
      onPointerMove={followPointer}
      onPointerLeave={leaveHero}
      onPointerCancel={leaveHero}
    >
      <div className="hero-atmosphere" aria-hidden="true">
        <motion.div className="hero-light light-one" animate={reduced ? undefined : { x: [0, 90, -45, 0], y: [0, -55, 40, 0], scale: [1, 1.15, 0.96, 1] }} transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }} />
        <motion.div className="hero-light light-two" animate={reduced ? undefined : { x: [0, -80, 45, 0], y: [0, 60, -45, 0], rotate: [0, 24, -12, 0] }} transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }} />
        <motion.div className="hero-shadow" animate={reduced ? undefined : { rotate: [-8, 8, -8], x: [-25, 30, -25] }} transition={{ duration: 19, repeat: Infinity, ease: "easeInOut" }} />
      </div>

      <motion.div className="hero-heading" style={{ y: reduced ? 0 : titleY, opacity: reduced ? 1 : titleOpacity }}>
        <motion.p className="hero-intro" initial={reduced ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 1 }}>Twoja obecność jest kluczem.</motion.p>
        <h1 id="hero-title" className="hero-wordmark">
          <motion.span initial={reduced ? false : { opacity: 0, y: 55, rotate: -3 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ delay: 0.22, duration: 1.15, ease: gentleEase }}>bre</motion.span><motion.span initial={reduced ? false : { opacity: 0, y: 55, rotate: 3 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ delay: 0.34, duration: 1.15, ease: gentleEase }}>Lock.</motion.span>
        </h1>
      </motion.div>

      <div className="hero-laptop-position">
        <motion.div style={{ y: reduced ? 0 : deviceY, scale: reduced ? 1 : deviceScale }}>
          <motion.div initial={reduced ? false : { y: 110, opacity: 0, rotateX: 9 }} animate={{ y: 0, opacity: 1, rotateX: 0 }} transition={{ delay: 0.45, duration: 1.4, ease: gentleEase }}>
            <motion.div className="hero-laptop-lid" style={{ rotateX: reduced ? 0 : rotateX, rotateY: reduced ? 0 : rotateY, transformPerspective: 1400 }}>
              <span className="hero-laptop-camera" aria-hidden="true" />
              <div id="hero-screen-demo" ref={screenRef} className={`hero-laptop-screen ${isAway ? "is-locked" : ""}`} role="group" aria-label="Symulacja ekranu laptopa">
                <motion.div className="hero-desktop-wallpaper" aria-hidden="true" animate={{ opacity: isAway ? 0.38 : 1, scale: isAway ? 1.06 : 1 }} transition={{ duration: reduced ? 0 : 1.1 }} />
                <motion.div className="hero-lock-wash" aria-hidden="true" style={{ position: "absolute", zIndex: 0, inset: 0, pointerEvents: "none", backgroundImage: "none" }} animate={{ backgroundColor: isAway ? "#b92f43" : "rgba(0, 0, 0, 0)", opacity: isAway ? 0.94 : 0 }} transition={{ duration: reduced ? 0 : 0.65, ease: gentleEase }} />
                <div className="hero-desktop-bar" aria-hidden="true"><span className="desktop-brand">breLock<span>.</span></span><span><Bluetooth size={12} strokeWidth={1.4} /><i style={isAway ? { backgroundColor: "#ff9b99", boxShadow: "0 0 7px #fb636870" } : undefined} />{isAway ? "Poza zasięgiem" : "Brelok w pobliżu"}</span></div>
                <div className="hero-screen-content">
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div className="hero-screen-message" key={isAway ? "locked" : "active"} initial={reduced ? false : { opacity: 0, y: 13, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -9, filter: "blur(6px)" }} transition={{ duration: reduced ? 0 : 0.32 }}>
                      <span className="hero-screen-icon" style={isAway ? { borderColor: "#ffc0bf50", color: "#ffd9d5", background: "#d345523d", boxShadow: "0 8px 26px #c839482e, inset 0 1px 0 #fff1ed20" } : undefined}>{isAway ? <LockKeyhole size={27} strokeWidth={1.15} /> : <UnlockKeyhole size={27} strokeWidth={1.15} />}</span>
                      <p>{isAway ? "Chwila dla Ciebie." : "Działaj spokojnie."}</p>
                      <span className="hero-screen-status" style={isAway ? { color: "#f0b9b7" } : undefined}>{isAway ? "Ekran zablokowany" : "Jesteś blisko. Wszystko pod kontrolą."}</span>
                    </motion.div>
                  </AnimatePresence>
                  <span className="hero-prototype-note">SYMULACJA PROTOTYPU</span>
                </div>
                <span className="sr-only" role="status" aria-live="polite">{isAway ? "Brelok oddalony. Symulacja blokady ekranu." : "Brelok w pobliżu. Ekran aktywny."}</span>
              </div>
            </motion.div>
          </motion.div>
        </motion.div>
      </div>

      <motion.button
        type="button"
        className="hero-fob-toggle"
        aria-label={isAway ? "Przybliż brelok — przywróć aktywny ekran" : "Oddal brelok — pokaż symulację blokady"}
        aria-controls="hero-screen-demo"
        aria-pressed={isAway}
        onFocus={() => setPointerVisible(false)}
        onClick={() => setIsAway(!isAway)}
        initial={reduced ? false : { opacity: 0, y: 30 }}
        animate={{ opacity: pointerVisible ? 0 : 1, y: 0, rotate: isAway ? 8 : -10 }}
        transition={{ duration: reduced ? 0 : 0.5, delay: pointerVisible ? 0 : 0.1 }}
        whileHover={reduced ? undefined : { scale: 1.08 }}
      >
        <BrelockFob away={isAway} />
        <span className="fob-touch-instruction">{isAway ? "Przybliż brelok" : "Dotknij breloka"}</span>
      </motion.button>

      <div className="hero-curve" aria-hidden="true" />
      <motion.p className="hero-scroll-hint" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.4 }}><span className="hero-pointer-instruction">Porusz kursorem. Twój brelok jest kluczem.</span><span className="hero-touch-instruction">Mały brelok. Dużo spokoju.</span></motion.p>

      <motion.div className="hero-fob-cursor" aria-hidden="true" style={{ x: cursorX, y: cursorY }} animate={{ opacity: pointerVisible ? 1 : 0 }} transition={{ duration: 0.12 }}>
        <span className="hero-cursor-anchor"><motion.span className="hero-cursor-swing" style={{ rotate: reduced ? 0 : fobRotation }}><BrelockFob away={isAway} /></motion.span></span>
      </motion.div>
    </section>
  );
}
