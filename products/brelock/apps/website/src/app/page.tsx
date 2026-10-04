import { LandingHero, LocalFirst, ProcessStory, Questions } from "@/components/LandingSections";
import { DownloadDock } from "@/components/MotionPrimitives";
import InteractiveLaptop from "@/components/InteractiveLaptop";
import { DesktopAppPreview } from "@/components/DesktopAppShowcase";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main id="main-content">
        <LandingHero />
        <ProcessStory />
        <InteractiveLaptop />
        <DesktopAppPreview />
        <LocalFirst />
        <Questions />
      </main>
      <SiteFooter />
      <DownloadDock />
    </>
  );
}
