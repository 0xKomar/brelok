import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import { Reveal } from "@/components/MotionPrimitives";
import { DesktopAppWalkthrough } from "@/components/DesktopAppShowcase";

const downloads = [
  { name: "Windows", format: "Instalator .exe", href: "/breLock_Setup.exe" },
  { name: "macOS", format: "Obraz dysku .dmg", href: "/breLock.dmg" },
];

export default function DownloadPage() {
  return (
    <>
      <SiteHeader />
      <main id="main-content" className="download-main site-container">
        <Link href="/" className="back-link"><ArrowLeft size={15} /> Strona główna</Link>
        <section className="download-heading" aria-labelledby="download-title">
          <Reveal>
          <p className="eyebrow">BRELOCK&nbsp; / &nbsp;POC</p>
          <h1 id="download-title">Zobacz, nad czym<br /><span>pracujemy.</span></h1>
          <p>Wybierz pakiet dla swojego komputera i zobacz aktualne widoki aplikacji poniżej. breLock to prototyp sprzętowy — testowanie ochrony wymaga fizycznego breloka.</p>
          </Reveal>
        </section>
        <div className="download-list" aria-label="Pakiety breLock">
          {downloads.map(({ name, format, href }, index) => (
            <Reveal key={name} delay={index * 0.1}>
            <article className="download-row" key={name}>
              <div><h2>{name}</h2><p>{format}</p></div>
              <a href={href} download className="quiet-link">Pobierz <ArrowUpRight size={16} /><span className="sr-only"> breLock dla {name}</span></a>
            </article>
            </Reveal>
          ))}
        </div>
        <p className="platform-note">Linux <span>—</span> pakiet jeszcze niedostępny</p>
        <DesktopAppWalkthrough />
      </main>
      <SiteFooter />
    </>
  );
}
