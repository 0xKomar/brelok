"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { Bluetooth, KeyRound, Laptop, LockKeyhole, Plus } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { gentleEase, Reveal } from "./MotionPrimitives";

export { default as LandingHero } from "./HeroLaptop";

const chapters = [
  { title: "Połącz brelok.", description: "Jeden brelok Bluetooth, jedna lokalna aplikacja. Wszystko zaczyna się od prostego połączenia." },
  { title: "Znajdź swoją strefę.", description: "Sygnał Bluetooth i informacja o ruchu pomagają rozpoznać, czy jesteś jeszcze przy biurku." },
  { title: "Po prostu odejdź.", description: "Przy włączonej ochronie wykrycie odejścia uruchamia żądanie blokady sesji. Wracasz i logujesz się tak, jak zawsze." },
];

function ChapterScene({ chapter }: { chapter: number }) {
  const reduced = useReducedMotion();
  if (chapter === 0) return <div className="chapter-photo"><Image src="/viz2.png" alt="Wizualizacja breloka w pobliżu komputera" width={2816} height={1536} sizes="(max-width: 760px) 92vw, 54vw" loading="eager" /><span>Bliżej niż myślisz.</span></div>;
  if (chapter === 1) return (
    <div className="calibration-scene" aria-label="Ilustracja łączenia sygnału Bluetooth z informacją o ruchu">
      <svg className="calibration-rings" viewBox="0 0 600 460" fill="none" aria-hidden="true">
        {[70, 120, 172].map((radius, index) => <motion.circle key={radius} cx="300" cy="230" r={radius} stroke="#528c79" strokeWidth="1" initial={reduced ? false : { pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 0.18 + index * 0.09 }} transition={{ duration: 1.4, delay: index * 0.16 }} />)}
        <motion.path d="M 105 230 H 495" stroke="#528c79" strokeWidth="1" strokeDasharray="4 7" initial={reduced ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.5 }} />
      </svg>
      <motion.div className="signal-core" initial={reduced ? false : { scale: 0.7 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 160, damping: 18 }}><Bluetooth size={34} strokeWidth={1.4} /></motion.div>
      <div className="signal-node node-left"><KeyRound size={22} /><span>RUCH</span></div>
      <div className="signal-node node-right"><Laptop size={22} /><span>SYGNAŁ</span></div>
      <p>Bluetooth + ruch.<br /><em>Lepszy obraz obecności.</em></p>
    </div>
  );
  return (
    <div className="departure-scene" aria-label="Ilustracja blokady po odejściu z brelokiem">
      <div className="departure-line" />
      <motion.div className="departure-laptop" initial={reduced ? false : { scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}><Laptop size={110} strokeWidth={0.8} /><motion.span initial={reduced ? false : { opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: reduced ? 0 : 1, type: "spring" }}><LockKeyhole size={30} strokeWidth={1.4} /></motion.span></motion.div>
      <motion.div className="departure-key" initial={reduced ? false : { x: -110 }} animate={{ x: 75 }} transition={{ duration: 1.8, ease: gentleEase }}><KeyRound size={33} strokeWidth={1.4} /></motion.div>
      <p>Ty idziesz dalej.<br /><em>Ochrona działa w tle.</em></p>
      <span className="scene-note">DOCELOWY SCENARIUSZ</span>
    </div>
  );
}

export function ProcessStory() {
  const [active, setActive] = useState(0);
  const reduced = useReducedMotion();
  const choose = (index: number, focus = false) => {
    setActive(index);
    if (focus) document.getElementById(`story-tab-${index}`)?.focus();
  };
  return (
    <section id="dzialanie" className="process-section site-container" aria-labelledby="process-title">
      <Reveal className="section-center"><p className="eyebrow">MAŁY RYTUAŁ. DUŻA RÓŻNICA.</p><h2 id="process-title" className="display-heading">Spokój zaczyna się<br /><em>od małej rzeczy.</em></h2></Reveal>
      <div className="process-grid">
        <Reveal className="chapter-tabs" delay={0.12}>
          <div role="tablist" aria-label="Docelowy sposób działania breLock" aria-orientation="vertical">
            {chapters.map((chapter, index) => (
              <motion.button
                layout
                type="button"
                role="tab"
                id={`story-tab-${index}`}
                aria-controls="story-panel"
                aria-selected={active === index}
                tabIndex={active === index ? 0 : -1}
                className={`chapter-tab ${active === index ? "is-active" : ""}`}
                key={chapter.title}
                onClick={() => choose(index)}
                onKeyDown={(event) => {
                  let next = active;
                  if (event.key === "ArrowDown") next = (active + 1) % chapters.length;
                  else if (event.key === "ArrowUp") next = (active + chapters.length - 1) % chapters.length;
                  else if (event.key === "Home") next = 0;
                  else if (event.key === "End") next = chapters.length - 1;
                  else return;
                  event.preventDefault(); choose(next, true);
                }}
              >
                <span className="chapter-number">0{index + 1}</span>
                <span className="chapter-title">{chapter.title}</span>
                <AnimatePresence initial={false}>{active === index && <motion.span className="chapter-description" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: reduced ? 0 : 0.4 }}>{chapter.description}</motion.span>}</AnimatePresence>
                {active === index && <motion.span className="chapter-rule" layoutId="chapter-rule" transition={{ type: "spring", stiffness: 160, damping: 24 }} />}
              </motion.button>
            ))}
          </div>
          <p className="process-note">Projekt sprzętowy w fazie PoC. Ochrona wymaga breloka, kalibracji i uprawnień systemowych.</p>
        </Reveal>
        <Reveal className="story-visual" delay={0.2}>
          <div id="story-panel" role="tabpanel" aria-labelledby={`story-tab-${active}`}>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div className="chapter-scene" key={active} initial={reduced ? false : { opacity: 0, y: 18, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -12, scale: 1.02 }} transition={{ duration: reduced ? 0 : 0.42, ease: gentleEase }}><ChapterScene chapter={active} /></motion.div>
            </AnimatePresence>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function LocalFirst() {
  const ref = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.4"] });
  const first = useTransform(scrollYProgress, [0, 0.25], ["#bbc5ce", "#0c1525"]);
  const second = useTransform(scrollYProgress, [0.2, 0.55], ["#bbc5ce", "#0c1525"]);
  const third = useTransform(scrollYProgress, [0.45, 0.85], ["#bbc5ce", "#33785f"]);
  return (
    <section ref={ref} className="local-section site-container" aria-labelledby="local-title">
      <Reveal><p className="eyebrow">BLIŻEJ CIEBIE. Z DALA OD CHMURY.</p></Reveal>
      <h2 id="local-title" className="local-heading">
        <motion.span style={{ color: reduced ? "#0c1525" : first }}>Twój komputer.</motion.span>
        <motion.span style={{ color: reduced ? "#0c1525" : second }}>Twoje dane.</motion.span>
        <motion.span className="local-emphasis" style={{ color: reduced ? "#33785f" : third }}>Twoja kontrola.</motion.span>
      </h2>
      <Reveal><p className="local-description">breLock powstaje jako lokalna aplikacja połączona z jednym brelokiem BLE. Bez konta i dodatkowego serwera.</p></Reveal>
    </section>
  );
}

const questions = [
  { question: "Czy breLock już blokuje komputer?", answer: "Prototyp aplikacji obsługuje systemową blokadę po wykryciu odejścia z brelokiem. Ochronę uruchamiasz po wybraniu urządzenia, kalibracji i nadaniu uprawnień systemowych. Animacja na tej stronie ilustruje zasadę działania; rzeczywiste testy wymagają fizycznego sprzętu." },
  { question: "Na jakich systemach powstaje aplikacja?", answer: "Projekt rozwijamy dla macOS i Windows. Pakiety dla obu systemów udostępnimy wkrótce." },
  { question: "Czy potrzebuję konta lub internetu?", answer: "Do lokalnego działania nie potrzebujesz konta ani serwera. Brelok komunikuje się z aplikacją przez Bluetooth, a dane zostają na komputerze." },
];

export function Questions() {
  const [open, setOpen] = useState<number | null>(null);
  const reduced = useReducedMotion();
  return (
    <section id="pytania" className="questions-section site-container" aria-labelledby="questions-title">
      <Reveal><h2 id="questions-title" className="display-heading">Dobrze wiedzieć.</h2><p className="questions-intro">Mały projekt. Konkretne odpowiedzi.</p></Reveal>
      <div className="questions-list">
        {questions.map(({ question, answer }, index) => <Reveal key={question} delay={index * 0.07}>
          <article className="question-item">
            <button type="button" aria-expanded={open === index} aria-controls={`answer-${index}`} onClick={() => setOpen(open === index ? null : index)}>
              <span>{question}</span><motion.span animate={{ rotate: open === index ? 45 : 0 }} transition={{ duration: reduced ? 0 : 0.3 }}><Plus size={21} strokeWidth={1.3} /></motion.span>
            </button>
            <motion.div id={`answer-${index}`} className="question-answer" aria-hidden={open !== index} initial={false} animate={{ height: open === index ? "auto" : 0, opacity: open === index ? 1 : 0 }} transition={{ duration: reduced ? 0 : 0.38, ease: gentleEase }}><p>{answer}</p></motion.div>
          </article>
        </Reveal>)}
      </div>
    </section>
  );
}
