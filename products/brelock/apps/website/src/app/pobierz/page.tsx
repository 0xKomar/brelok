import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import { Reveal } from "@/components/MotionPrimitives";
import { DesktopAppWalkthrough } from "@/components/DesktopAppShowcase";

const platforms = ["Windows", "macOS"];

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
          <p>Wersje dla Windows i macOS są w przygotowaniu. Zobacz aktualne widoki aplikacji poniżej. breLock to prototyp sprzętowy — testowanie ochrony wymaga fizycznego breloka.</p>
          </Reveal>
        </section>
        <div className="download-list" aria-label="Dostępność aplikacji breLock">
          {platforms.map((name, index) => (
            <Reveal key={name} delay={index * 0.1}>
            <article className="download-row" key={name}>
              <h2>{name}</h2>
              <span className="download-status">Coming soon</span>
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
