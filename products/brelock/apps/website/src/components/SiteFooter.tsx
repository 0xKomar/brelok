import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Reveal } from "./MotionPrimitives";

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-container">
        <Reveal className="footer-top"><h2>Mały brelok.<br /><em>Dużo spokoju.</em></h2><div><Link href="/pobierz">Poznaj prototyp <ArrowUpRight size={18} /></Link><Link href="/#demo">Zobacz demo</Link><Link href="/#pytania">O projekcie</Link></div></Reveal>
        <Reveal><p className="footer-wordmark" aria-hidden="true">breLock.</p></Reveal>
        <div className="footer-bottom"><Link href="/" className="brand" aria-label="breLock — strona główna">bre<span>Lock</span><i>.</i></Link><p>Lokalny projekt w fazie PoC.</p><span>© {new Date().getFullYear()} breLock</span></div>
      </div>
    </footer>
  );
}
