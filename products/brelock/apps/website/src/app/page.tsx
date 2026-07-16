"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { TypeAnimation } from "react-type-animation";
import { KeyRound, ShieldCheck, LockKeyhole, Lock, RadioTower } from "lucide-react";
import InteractiveLaptop from "@/components/InteractiveLaptop";

export default function Home() {
  const vantaRef = useRef<HTMLDivElement>(null);
  const [vantaEffect, setVantaEffect] = useState<any>(null);
  const [activeCard, setActiveCard] = useState<number | null>(null);

  useEffect(() => {
    // We try to initialize Vanta topology, retrying shortly if window.VANTA isn't injected yet by next/script
    let interval: NodeJS.Timeout;
    
    const initVanta = () => {
      if (!vantaEffect && typeof window !== "undefined" && (window as any).VANTA) {
        setVantaEffect(
          (window as any).VANTA.TOPOLOGY({
            el: vantaRef.current,
            mouseControls: true,
            touchControls: true,
            gyroControls: false,
            minHeight: 200.00,
            minWidth: 200.00,
            scale: 1.50,
            scaleMobile: 2.00,
            color: 0x1b994d, // just a tiny bit darker
            backgroundColor: 0x010a05 // brelock-darkest
          })
        );
        return true;
      }
      return false;
    };

    if (!initVanta()) {
      interval = setInterval(() => {
        if (initVanta()) clearInterval(interval);
      }, 200);
    }

    return () => {
      if (interval) clearInterval(interval);
      if (vantaEffect) vantaEffect.destroy();
    };
  }, [vantaEffect]);

  return (
    <div className="flex flex-col min-h-screen">
      
      {/* Top section with Vanta Background */}
      <div ref={vantaRef} className="w-full min-h-screen flex flex-col relative text-white">
        
        {/* Header - now relative, no longer sticky */}
        <header className="w-full py-8 flex justify-center items-center z-10 p-4 relative">
          <div className="text-3xl font-[family-name:var(--font-playfair)] tracking-wider font-semibold text-white">
            brelock
          </div>
        </header>

        {/* Hero Section */}
        <main className="flex-1 flex flex-col items-center justify-center p-6 text-center z-10 max-w-4xl mx-auto">

          <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold mb-12 tracking-tight text-white drop-shadow-[0_4px_25px_rgba(0,0,0,1)] flex flex-col items-center justify-center gap-4 lg:gap-6 z-10 h-40 md:h-64">
            <span>Bezpieczeństwo</span>
            <div className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl">
              <TypeAnimation
                sequence={[
                  'działa z automatu.',
                  3000,
                  'zaczyna się z brelock.',
                  3000,
                  'nie wymaga wysiłku.',
                  3000,
                  'chroni samo.',
                  3000,
                ]}
                wrapper="span"
                speed={60}
                repeat={Infinity}
                className="inline-block"
              />
            </div>
          </h1>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-6 mt-4">
            <Link href="/pobierz" className="relative overflow-hidden group rounded-full border border-brelock-glow bg-brelock-darkest/40 px-10 py-4 z-10 shadow-[0_0_20px_rgba(46,204,113,0.15)] block text-center">
               <div className="absolute left-[-25%] top-[100%] w-[150%] h-[250%] bg-brelock-glow rounded-[40%] group-hover:top-[-50%] transition-all duration-700 ease-in-out -z-10 group-hover:rotate-[15deg]"></div>
               <span className="relative z-10 group-hover:text-brelock-darkest font-semibold transition-colors duration-300 text-lg tracking-wide text-white">
                 Pobierz
               </span>
            </Link>

             <Link href="/pobierz" className="relative overflow-hidden group rounded-full border border-white/30 bg-transparent px-10 py-4 z-10 hover:border-white/50 transition-colors block text-center">
               <div className="absolute left-[-25%] top-[100%] w-[150%] h-[250%] bg-white rounded-[40%] group-hover:top-[-50%] transition-all duration-700 ease-in-out -z-10 group-hover:rotate-[15deg]"></div>
               <span className="relative z-10 group-hover:text-brelock-darkest font-semibold transition-colors duration-300 text-lg tracking-wide text-white/90">
                 Dowiedz się więcej
               </span>
            </Link>
          </div>
        </main>
      </div>

      {/* Product Visualizations & Action Animation */}
      <section className="w-full bg-brelock-darkest pt-16 pb-40 sm:py-24 relative overflow-hidden z-10 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col-reverse lg:flex-row items-center gap-12 lg:gap-16">
          
          {/* Visualizations Side */}
          <div className="flex-1 w-full relative h-[380px] sm:h-[450px] lg:h-[600px] flex items-center justify-center group perspective mt-24 sm:mt-32 lg:mt-0">
             {/* Ambient Backing (Optimized to avoid heavy CSS generic blur) */}
             <div className="absolute inset-[-20%] rounded-full opacity-40 mix-blend-screen pointer-events-none" style={{ background: 'radial-gradient(circle, rgba(46,204,113,0.45) 0%, rgba(0,0,0,0) 70%)' }}></div>
             
             {/* Image 1: floating slow */}
             <div className="absolute left-0 bottom-4 sm:bottom-10 w-[65%] sm:w-[60%] transform-gpu group-hover:-translate-x-4 sm:group-hover:-translate-x-6 group-hover:-rotate-2 transition-all duration-1000 ease-in-out z-20 will-change-transform">
               <Image src="/viz2.png" alt="breLock Device" width={600} height={600} className="rounded-2xl sm:rounded-3xl shadow-2xl object-cover animate-float transform-gpu will-change-transform border border-white/5" priority />
             </div>
             
             {/* Image 2: floating offset */}
             <div className="absolute right-0 top-4 sm:top-10 w-[75%] sm:w-[70%] transform-gpu group-hover:translate-x-4 sm:group-hover:translate-x-6 group-hover:rotate-1 transition-all duration-1000 ease-in-out z-10 will-change-transform">
               <Image src="/viz1.png" alt="breLock Action" width={600} height={600} className="rounded-2xl sm:rounded-3xl shadow-xl object-cover animate-float-delayed transform-gpu will-change-transform border border-white/5 opacity-80 group-hover:opacity-100" priority />
             </div>

             {/* Distance indicator (The "How it works" animation) */}
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 sm:w-40 sm:h-40 flex items-center justify-center z-30 pointer-events-none">
                <div className="absolute inset-0 rounded-full border border-brelock-glow opacity-0 animate-[ping_3s_ease-in-out_infinite]"></div>
                <div className="absolute inset-[-30%] rounded-full border border-brelock-glow opacity-0 animate-[ping_3s_ease-in-out_infinite_1.5s]"></div>
                <div className="bg-brelock-darkest/90 glass-border backdrop-blur-md rounded-full w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center group-hover:bg-red-500/10 group-hover:border-red-500/50 group-hover:shadow-[0_0_30px_rgba(239,68,68,0.3)] transition-all duration-1000">
                   <Lock className="text-brelock-glow group-hover:text-red-500 transition-colors duration-1000 w-6 h-6 sm:w-8 sm:h-8" />
                </div>
             </div>
          </div>

          {/* Text Side */}
          <div className="flex-1 w-full flex flex-col gap-6 lg:pl-10">
            <h2 className="text-4xl md:text-5xl font-bold text-white tracking-tight">
              Błyskawiczna<br />reakcja.
            </h2>
            <p className="text-lg text-white/60 leading-relaxed">
              breLock to o wiele więcej niż tylko inteligentne oprogramowanie. To elegancki element hardware'owy w Twojej kieszeni, który na bieżąco analizuje dystans od biurka lub komputera firmowego.
            </p>
            
            <div className="bg-white/5 border border-white/10 p-6 rounded-2xl mt-4 relative overflow-hidden backdrop-blur-sm group/card hover:bg-white/10 transition-colors duration-500">
              <div className="absolute top-0 left-0 w-1 h-full bg-brelock-glow group-hover/card:bg-red-500 transition-colors duration-1000"></div>
              <h4 className="text-white font-semibold text-lg mb-2 flex items-center gap-3">
                 <RadioTower className="text-brelock-glow group-hover/card:text-red-500 transition-colors duration-1000" size={20} /> 
                 Inteligentna Topologia Bluetooth
              </h4>
              <p className="text-white/60 text-sm leading-relaxed">
                 System z chirurgiczną precyzją monitoruje Twoje oddalenie od stacji roboczej. Najedź kursorem na wizualizację obok, żeby zobaczyć co się dzieje, gdy opuszczasz biuro! Zamek natychmiast zmienia status na zablokowany, chroniąc Twoje dane.
              </p>
            </div>
          </div>
          
        </div>
      </section>

      {/* Interactive breLock vs Laptop Simulation */}
      <InteractiveLaptop />

      <section className="w-full bg-white text-brelock-darkest py-32 z-10 relative">
        <div className="max-w-6xl mx-auto px-6 flex flex-col gap-20">
          
          <div className="text-center max-w-3xl mx-auto">
            <h2 className="text-4xl md:text-5xl font-semibold mb-6 tracking-tight text-brelock-darkest">
              Na czym to polega?
            </h2>
            <p className="text-lg text-gray-600 leading-relaxed">
              Odkryj innowacyjną technologię, która dba o bezpieczeństwo Twojej firmy bez angażowania uwagi pracowników. Niezawodne blokowanie ekranów staje się integralną częścią biura. 
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            
            {/* Flip Card 1 */}
            <div className="group w-full h-[360px] perspective" onClick={() => setActiveCard(activeCard === 1 ? null : 1)} onMouseLeave={() => setActiveCard(null)}>
              <div className={`relative w-full h-full transition-transform duration-700 preserve-3d lg:group-hover:rotate-y-180 cursor-pointer shadow-xl rounded-3xl ${activeCard === 1 ? 'rotate-y-180' : ''}`}>
                
                {/* Front */}
                <div className="absolute inset-0 backface-hidden bg-brelock-darkest text-white rounded-3xl p-10 flex flex-col items-center justify-center text-center">
                  <div className="w-20 h-20 rounded-2xl bg-[#042413] flex items-center justify-center mb-8 shadow-inner shadow-black/50">
                    <KeyRound size={36} className="text-brelock-glow" />
                  </div>
                  <h3 className="text-2xl font-medium">Przypnij brelok</h3>
                  <p className="mt-4 text-white/50 text-sm hidden lg:block">Najedź, aby dowiedzieć się więcej</p>
                  <p className="mt-4 text-white/50 text-sm lg:hidden">Dotknij, aby dowiedzieć się więcej</p>
                </div>
                
                {/* Back */}
                <div className="absolute inset-0 backface-hidden rotate-y-180 bg-[#188248] text-white rounded-3xl p-8 flex flex-col items-center justify-center text-center shadow-inner shadow-black/20">
                  <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center mb-4">
                    <KeyRound size={24} className="text-white" />
                  </div>
                  <h3 className="text-xl font-medium mb-3">Minimalny wysiłek</h3>
                  <p className="text-white/90 text-[15px] leading-relaxed">
                    Jeden, niewielki gadżet, który z łatwością przypniesz do kluczy, kurtki lub paska. Zawsze przy Tobie, paruje się automatycznie.
                  </p>
                </div>

              </div>
            </div>

            {/* Flip Card 2 */}
            <div className="group w-full h-[360px] perspective" onClick={() => setActiveCard(activeCard === 2 ? null : 2)} onMouseLeave={() => setActiveCard(null)}>
              <div className={`relative w-full h-full transition-transform duration-700 preserve-3d lg:group-hover:rotate-y-180 cursor-pointer shadow-xl rounded-3xl ${activeCard === 2 ? 'rotate-y-180' : ''}`}>
                
                {/* Front */}
                <div className="absolute inset-0 backface-hidden bg-brelock-darkest text-white rounded-3xl p-10 flex flex-col items-center justify-center text-center">
                  <div className="w-20 h-20 rounded-2xl bg-[#042413] flex items-center justify-center mb-8 shadow-inner shadow-black/50">
                    <ShieldCheck size={36} className="text-brelock-glow" />
                  </div>
                  <h3 className="text-2xl font-medium">Pracuj swobodnie</h3>
                  <p className="mt-4 text-white/50 text-sm hidden lg:block">Najedź, aby dowiedzieć się więcej</p>
                  <p className="mt-4 text-white/50 text-sm lg:hidden">Dotknij, aby dowiedzieć się więcej</p>
                </div>
                
                {/* Back */}
                <div className="absolute inset-0 backface-hidden rotate-y-180 bg-[#188248] text-white rounded-3xl p-8 flex flex-col items-center justify-center text-center shadow-inner shadow-black/20">
                  <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center mb-4">
                    <ShieldCheck size={24} className="text-white" />
                  </div>
                  <h3 className="text-xl font-medium mb-3">Pełna aktywność</h3>
                  <p className="text-white/90 text-[15px] leading-relaxed">
                    Nie musisz myśleć o procedurach bezpieczeństwa. Dopóki znajdujesz się w pobliżu swojego stanowiska, sprzęt pozostaje w pełni gotowy do pracy.
                  </p>
                </div>

              </div>
            </div>

            {/* Flip Card 3 */}
            <div className="group w-full h-[360px] perspective" onClick={() => setActiveCard(activeCard === 3 ? null : 3)} onMouseLeave={() => setActiveCard(null)}>
              <div className={`relative w-full h-full transition-transform duration-700 preserve-3d lg:group-hover:rotate-y-180 cursor-pointer shadow-xl rounded-3xl ${activeCard === 3 ? 'rotate-y-180' : ''}`}>
                
                {/* Front */}
                <div className="absolute inset-0 backface-hidden bg-brelock-darkest text-white rounded-3xl p-10 flex flex-col items-center justify-center text-center">
                  <div className="w-20 h-20 rounded-2xl bg-[#042413] flex items-center justify-center mb-8 shadow-inner shadow-black/50">
                    <LockKeyhole size={36} className="text-brelock-glow" />
                  </div>
                  <h3 className="text-2xl font-medium">Auto-blokada</h3>
                  <p className="mt-4 text-white/50 text-sm hidden lg:block">Najedź, aby dowiedzieć się więcej</p>
                  <p className="mt-4 text-white/50 text-sm lg:hidden">Dotknij, aby dowiedzieć się więcej</p>
                </div>
                
                {/* Back */}
                <div className="absolute inset-0 backface-hidden rotate-y-180 bg-[#188248] text-white rounded-3xl p-8 flex flex-col items-center justify-center text-center shadow-inner shadow-black/20">
                  <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center mb-4">
                    <LockKeyhole size={24} className="text-white" />
                  </div>
                  <h3 className="text-xl font-medium mb-3">Ochrona w sekundę</h3>
                  <p className="text-white/90 text-[15px] leading-relaxed">
                    Gdy tylko odchodzisz od biurka, urządzenia breLock mierzą odchylenie sygnału. Komputer blokuje się bez żadnej fizycznej interakcji.
                  </p>
                </div>

              </div>
            </div>

          </div>
        </div>
      </section>


      {/* Footer */}
      <footer className="w-full py-12 flex flex-col items-center justify-center z-10 bg-brelock-darkest text-white border-t border-white/10 mt-auto">
        <div className="text-2xl font-[family-name:var(--font-playfair)] tracking-wider font-semibold text-white/40 mb-4 hover:text-white/80 transition-colors">
          brelock
        </div>
        <div className="text-white/40 text-sm">
          &copy; {new Date().getFullYear()} breLock. Wszelkie prawa zastrzeżone.
        </div>
      </footer>
    </div>
  );
}
