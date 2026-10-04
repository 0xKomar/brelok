import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Bluetooth, SlidersHorizontal, ShieldCheck, Activity } from "lucide-react";
import { Reveal } from "@/components/MotionPrimitives";

const screens = [
  {
    id: "setup",
    number: "01",
    label: "TWÓJ BRELOK",
    title: "Połącz swój komputer z brelokiem.",
    description: "Aplikacja skanuje Bluetooth w tle. W Ustawieniach wybierasz ID swojego breloka, aby komputer analizował sygnał właśnie tego urządzenia.",
    detail: "Jeden komputer. Jeden brelok. Bez konta i bez panelu administratora.",
    caption: "Ustawienia · wybór urządzenia",
    alt: "Okno aplikacji breLock na macOS: ustawienia z polem ID breloka i listą wykrytych urządzeń.",
    icon: Bluetooth,
  },
  {
    id: "calibration",
    number: "02",
    label: "TWOJA STREFA",
    title: "Dopasuj ochronę do swojego biurka.",
    description: "Kreator kalibracji prowadzi przez punkty 1, 2 i 3 m od laptopa. W każdym punkcie potwierdzasz pozycję i pozostajesz w miejscu na czas pomiaru. Zebrane próbki dopasowują model sygnału i próg odejścia.",
    detail: "Na zrzucie widać zapisane parametry modelu. Dystans z Bluetooth jest szacunkiem i zależy od otoczenia.",
    caption: "Ustawienia · parametry po kalibracji",
    alt: "Okno breLock: zapisany próg ochrony, RSSI przy jednym metrze, współczynnik n, ostatni punkt kalibracji oraz czasy świeżości i utraty sygnału.",
    icon: SlidersHorizontal,
  },
  {
    id: "status",
    number: "03",
    label: "OCHRONA W TLE",
    title: "Włącz. Pracuj. Po prostu odejdź.",
    description: "Przycisk ON / OFF steruje ochroną. Aplikacja łączy zmiany sygnału Bluetooth z informacją o ruchu breloka i wysyła żądanie blokady do systemu. Zamknięcie okna chowa aplikację do ikony na pasku — analiza działa dalej.",
    detail: "Widoczny stan WAIT oznacza oczekiwanie na powrót breloka po wysłaniu żądania blokady. Po powrocie ochrona uzbraja się ponownie; komputer odblokowujesz samodzielnie.",
    caption: "Status · oczekiwanie na powrót breloka",
    alt: "Okno statusu breLock z centralnym przyciskiem WAIT i komunikatem Ochrona czeka na powrót po utracie świeżych pakietów breloka.",
    icon: ShieldCheck,
  },
  {
    id: "diagnostics",
    number: "04",
    label: "WGLĄD W POMIARY",
    title: "Zobacz, skąd bierze się decyzja.",
    description: "Diagnostyka pokazuje wykres surowego i filtrowanego RSSI, szacowany dystans, ruch, baterię oraz ostatnie zdarzenia. Przy blokadzie sprawdzisz regułę, która zadziałała, i wynik wysłania żądania do systemu.",
    detail: "Na tym zrzucie zadziałała reguła L1: brak świeżych pakietów. Pusty wykres oznacza brak aktualnych odczytów z breloka.",
    caption: "Diagnostyka · sygnał i reguły ochrony",
    alt: "Okno diagnostyki breLock z pustym wykresem RSSI i informacją, że brak świeżych pakietów wywołał żądanie blokady systemu.",
    icon: Activity,
  },
] as const;

const screenshotPath = (id: string) => `/screenshots/desktop-${id}.jpg`;

export function DesktopAppPreview() {
  return (
    <section id="aplikacja" className="app-preview-section site-container" aria-labelledby="app-preview-title">
      <Reveal className="app-preview-copy">
        <p className="eyebrow">APLIKACJA DESKTOPOWA</p>
        <h2 id="app-preview-title" className="display-heading">Małe okno.<br /><em>Wszystko pod ręką.</em></h2>
        <p>Status ochrony, konfiguracja breloka i pomiary w jednej aplikacji. Kiedy zamkniesz okno, breLock nadal działa w tle.</p>
        <Link href="/pobierz#aplikacja" className="quiet-link">Zobacz aplikację krok po kroku <ArrowUpRight size={16} /></Link>
        <span className="app-capture-note">Rzeczywiste zrzuty aplikacji na macOS · wersja PoC</span>
      </Reveal>
      <Reveal className="app-preview-images" delay={0.1}>
        {screens.filter(({ id }) => id === "setup" || id === "status").map(({ id, alt }) => (
          <Link key={id} href={`/pobierz#ekran-${id}`} className={`app-preview-window app-preview-${id}`} aria-label={`Zobacz ${id === "status" ? "status ochrony" : "konfigurację breloka"}`}>
            <Image src={screenshotPath(id)} alt={alt} width={760} height={1040} sizes="(max-width: 680px) 55vw, (max-width: 1000px) 30vw, 290px" />
          </Link>
        ))}
      </Reveal>
    </section>
  );
}

export function DesktopAppWalkthrough() {
  return (
    <section id="aplikacja" className="app-walkthrough" aria-labelledby="app-walkthrough-title">
      <Reveal className="app-walkthrough-intro">
        <p className="eyebrow">OD PIERWSZEGO POŁĄCZENIA DO OCHRONY</p>
        <h2 id="app-walkthrough-title" className="display-heading">Tak wygląda<br /><em>breLock na komputerze.</em></h2>
        <p>Cztery widoki, które prowadzą przez konfigurację i pomagają zrozumieć działanie prototypu.</p>
      </Reveal>
      <div className="app-walkthrough-steps">
        {screens.map(({ id, number, label, title, description, detail, caption, alt, icon: Icon }) => (
          <article key={id} id={`ekran-${id}`} className="app-walkthrough-step" aria-labelledby={`tytul-${id}`}>
            <Reveal className="app-step-image">
              <figure>
                <a href={screenshotPath(id)} target="_blank" rel="noopener noreferrer" className="app-screenshot-link" aria-label={`Powiększ zrzut: ${caption} (nowa karta)`}>
                  <Image src={screenshotPath(id)} alt={alt} width={760} height={1040} sizes="(max-width: 680px) calc(100vw - 88px), 340px" />
                  <span className="app-screenshot-zoom"><ArrowUpRight size={14} /> Powiększ</span>
                </a>
                <figcaption>{caption}</figcaption>
              </figure>
            </Reveal>
            <Reveal className="app-step-copy" delay={0.08}>
              <span className="app-step-number">{number} <span>/</span> 04</span>
              <p className="eyebrow"><Icon size={14} strokeWidth={1.5} /> {label}</p>
              <h3 id={`tytul-${id}`}>{title}</h3>
              <p>{description}</p>
              <p className="app-step-detail">{detail}</p>
            </Reveal>
          </article>
        ))}
      </div>
      <p className="app-walkthrough-note">Zrzuty pochodzą z uruchomionej aplikacji na macOS. Podczas ich wykonywania brelok był poza połączeniem, dlatego status pokazuje WAIT, a pomiary nie mają świeżych danych.</p>
    </section>
  );
}
