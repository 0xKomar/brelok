"use client";
import Link from 'next/link';
import Image from 'next/image';
import { ArrowLeft, Monitor, Apple, Terminal } from 'lucide-react';

export default function DownloadPage() {
  return (
    <div className="min-h-screen bg-white text-brelock-darkest relative flex flex-col font-sans overflow-hidden selection:bg-brelock-primary/20 selection:text-brelock-darkest">
      
      <header className="absolute top-0 w-full p-6 z-50">
        <Link href="/" className="group relative inline-flex items-center justify-center w-14 h-14 rounded-full bg-gray-50 border border-gray-200 hover:bg-white transition-all hover:border-brelock-primary hover:shadow-[0_0_15px_rgba(46,204,113,0.2)]">
           <ArrowLeft size={24} className="text-gray-600 group-hover:text-brelock-primary transition-colors group-hover:-translate-x-1 duration-300" />
           <div className="absolute left-full ml-4 px-4 py-2 rounded-xl bg-white border border-gray-200 text-gray-800 text-sm font-medium whitespace-nowrap opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 pointer-events-none shadow-lg">
              Wróć do strony głównej
           </div>
        </Link>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center p-6 z-10 max-w-5xl mx-auto w-full relative animate-in fade-in slide-in-from-bottom-8 duration-700 pt-32 md:pt-40">
        <h1 className="text-5xl md:text-7xl font-bold mb-16 tracking-tight text-gray-900 text-center relative">
          Pobierz <span className="text-transparent bg-clip-text bg-gradient-to-r from-brelock-primary to-green-500 drop-shadow-sm">breLock</span>
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full z-10 relative">
          
          {/* Windows */}
          <div className="relative rounded-3xl p-8 flex flex-col items-center text-center transition-all duration-500 ease-out border-2 overflow-hidden bg-white border-gray-200 hover:border-brelock-primary hover:shadow-[0_15px_40px_rgba(46,204,113,0.15)] hover:-translate-y-2 group cursor-pointer">
             <div className="absolute inset-0 transition-opacity duration-500 opacity-0 group-hover:opacity-100 bg-brelock-glow/5"></div>
             
             <div className="relative h-20 w-20 flex items-center justify-center mb-6">
                 <Monitor size={56} className="text-gray-400 group-hover:text-brelock-primary transition-all duration-500 transform group-hover:scale-110" />
             </div>
             
             <div className="h-[140px] flex flex-col items-center justify-center w-full mb-6">
                 <h3 className="text-xl md:text-2xl font-bold mb-2 tracking-wide text-center text-gray-800 group-hover:text-brelock-darkest transition-colors duration-500">Windows</h3>
                 <p className="font-medium text-center px-4 text-gray-500">Wersja 10 & 11 (64-bit)</p>
             </div>
             
             <a href="/breLock_Setup.exe" download className="block w-full py-4 text-center rounded-full font-bold transition-all duration-500 shadow-sm overflow-hidden relative bg-gray-100 border border-gray-200 text-gray-600 group-hover:bg-brelock-primary group-hover:text-white group-hover:border-brelock-primary group-hover:shadow-[0_0_20px_rgba(46,204,113,0.4)]">
               Pobierz Instalator
             </a>
          </div>

          {/* macOS */}
          <div className="relative rounded-3xl p-8 flex flex-col items-center text-center transition-all duration-500 ease-out border-2 overflow-hidden bg-white border-gray-200 hover:border-brelock-primary hover:shadow-[0_15px_40px_rgba(46,204,113,0.15)] hover:-translate-y-2 group cursor-pointer">
             <div className="absolute inset-0 transition-opacity duration-500 opacity-0 group-hover:opacity-100 bg-brelock-glow/5"></div>
             
             <div className="relative h-20 w-20 flex items-center justify-center mb-6">
                 <Apple size={56} className="text-gray-400 group-hover:text-brelock-primary transition-all duration-500 transform group-hover:scale-110" />
             </div>
             
             <div className="h-[140px] flex flex-col items-center justify-center w-full mb-6">
                 <h3 className="text-xl md:text-2xl font-bold mb-2 tracking-wide text-center text-gray-800 group-hover:text-brelock-darkest transition-colors duration-500">macOS</h3>
                 <p className="font-medium text-center px-4 text-gray-500">Apple Silicon & Intel</p>
             </div>
             
             <a href="/breLock.dmg" download className="block w-full py-4 text-center rounded-full font-bold transition-all duration-500 shadow-sm overflow-hidden relative bg-gray-100 border border-gray-200 text-gray-600 group-hover:bg-brelock-primary group-hover:text-white group-hover:border-brelock-primary group-hover:shadow-[0_0_20px_rgba(46,204,113,0.4)]">
               Pobierz (.dmg)
             </a>
          </div>

          {/* Linux */}
          <div className="rounded-3xl p-8 flex flex-col items-center text-center border-2 border-gray-100 opacity-60 relative overflow-hidden grayscale bg-gray-50 h-full">
             <div className="relative h-20 w-20 flex items-center justify-center mb-6">
                 <Terminal size={56} className="text-gray-400" />
             </div>
             
             <div className="h-[140px] flex flex-col items-center justify-center w-full mb-6">
                 <h3 className="text-xl md:text-2xl font-bold mb-2 tracking-wide text-gray-600 text-center">Linux</h3>
                 <p className="font-medium text-center text-gray-400 px-4">Ubuntu, Debian, Arch</p>
             </div>
             
             <button disabled className="w-full py-4 rounded-full bg-gray-200 border border-transparent text-gray-400 font-bold cursor-not-allowed uppercase tracking-wider">
               Wkrótce...
             </button>
          </div>

        </div>
        
        <div className="mt-40 w-full relative pb-32">
          
          <div className="text-center mb-20 relative z-10">
            <h2 className="text-4xl md:text-5xl font-bold mb-6 text-gray-900">
              Jak to działa?
            </h2>
            <p className="text-xl text-gray-500 max-w-2xl mx-auto">
              Po instalacji klient rejestruje laptop automatycznie. Przypisaniem breLocka i polityką bezpieczeństwa zarządza administrator firmy.
            </p>
          </div>

          <div className="relative mt-20">
            {/* The Winding Line SVG */}
            <div className="absolute left-1/2 top-[10%] bottom-[10%] w-[50%] md:w-[60%] -translate-x-1/2 hidden md:block z-[1] pointer-events-none">
                 <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                     <style>
                       {`
                         @keyframes mapFlow {
                           from { stroke-dashoffset: 32; }
                           to { stroke-dashoffset: 0; }
                         }
                         .animate-map-flow {
                           animation: mapFlow 1.5s linear infinite;
                         }
                       `}
                     </style>
                     <defs>
                        <linearGradient id="mapGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                           <stop offset="0%" stopColor="rgba(46,204,113,0)" />
                           <stop offset="20%" stopColor="rgba(46,204,113,0.9)" />
                           <stop offset="80%" stopColor="rgba(46,204,113,0.9)" />
                           <stop offset="100%" stopColor="rgba(46,204,113,0)" />
                        </linearGradient>
                     </defs>
                     
                     {/* Solid thick base path */}
                     <path 
                        d="M 50 0 C 120 25, -20 75, 50 100" 
                        fill="none" 
                        stroke="rgba(46,204,113,0.15)" 
                        strokeWidth="5" 
                        vectorEffect="non-scaling-stroke"
                     />

                     {/* Animated dashed stream path */}
                     <path 
                        d="M 50 0 C 120 25, -20 75, 50 100" 
                        fill="none" 
                        stroke="url(#mapGradient)" 
                        strokeWidth="5" 
                        strokeDasharray="16,16" 
                        className="animate-map-flow drop-shadow-[0_0_8px_rgba(46,204,113,0.8)]"
                        vectorEffect="non-scaling-stroke"
                     />
                 </svg>
            </div>

            {/* Step 1: Left aligned image, right aligned text */}
            <div className="flex flex-col md:flex-row items-center justify-between mb-32 relative">
               <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full z-10 border-2 border-brelock-primary items-center justify-center shadow-[0_0_20px_rgba(46,204,113,0.3)]">
                  <div className="w-3 h-3 bg-brelock-primary rounded-full animate-ping"></div>
               </div>
               
               <div className="w-full md:w-[45%] mb-8 md:mb-0 h-[450px] md:h-[550px] relative group">
                  <Image src="/kalibracja.jpeg" alt="Ekran parowania i kalibracji" fill className="object-contain rounded-2xl drop-shadow-[0_20px_40px_rgba(0,0,0,0.15)] transition-transform duration-500 group-hover:scale-105 group-hover:-translate-y-2" />
               </div>
               
               <div className="w-full md:w-[45%] text-left md:pl-12 bg-white/80 backdrop-blur-sm p-6 rounded-2xl">
                  <h3 className="text-3xl font-bold mb-4 text-gray-800 transition-colors">1. Automatyczna rejestracja laptopa</h3>
                  <p className="text-gray-600 text-lg leading-relaxed">
                    Aplikacja pracownika łączy się z panelem firmy i wykrywa breLocki BLE w pobliżu. Użytkownik widzi wyłącznie czytelny status ochrony — bez technicznych ustawień i ręcznego parowania.
                  </p>
               </div>
            </div>

            {/* Step 2: Right aligned image, left aligned text */}
            <div className="flex flex-col md:flex-row-reverse items-center justify-between mb-32 relative">
               <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full z-10 border-2 border-brelock-primary items-center justify-center shadow-[0_0_20px_rgba(46,204,113,0.3)]">
                  <div className="w-3 h-3 bg-brelock-primary rounded-full animate-ping delay-150"></div>
               </div>

               <div className="w-full md:w-[45%] mb-8 md:mb-0 h-[450px] md:h-[550px] relative group">
                  <Image src="/kalibracjapowodzenie.jpeg" alt="Ekran pozytywnej kalibracji strefy" fill className="object-contain rounded-2xl drop-shadow-[0_20px_40px_rgba(0,0,0,0.15)] transition-transform duration-500 group-hover:scale-105 group-hover:-translate-y-2" />
               </div>
               
               <div className="w-full md:w-[45%] text-left md:pr-12 bg-white/80 backdrop-blur-sm p-6 rounded-2xl">
                  <h3 className="text-3xl font-bold mb-4 text-gray-800 transition-colors">2. Przypisanie przez administratora</h3>
                  <p className="text-gray-600 text-lg leading-relaxed">
                    Administrator wybiera laptop i przypisuje do niego unikalny breLock. W panelu ustawia próg sygnału, czas reakcji i watchdog oraz obserwuje wykres RSSI i estymowanej odległości na żywo.
                  </p>
               </div>
            </div>

            {/* Step 3: Left aligned image, right aligned text */}
            <div className="flex flex-col md:flex-row items-center justify-between relative">
               <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full z-10 border-2 border-brelock-primary items-center justify-center shadow-[0_0_20px_rgba(46,204,113,0.3)]">
                  <div className="w-3 h-3 bg-brelock-primary rounded-full animate-ping delay-300"></div>
               </div>

               <div className="w-full md:w-[45%] mb-8 md:mb-0 h-[450px] md:h-[550px] relative group">
                  <Image src="/wtrakciedzialania.jpeg" alt="Aktywna ochrona obwodowa" fill className="object-contain rounded-2xl drop-shadow-[0_20px_40px_rgba(0,0,0,0.15)] transition-transform duration-500 group-hover:scale-105 group-hover:-translate-y-2" />
               </div>
               
               <div className="w-full md:w-[45%] text-left md:pl-12 bg-white/80 backdrop-blur-sm p-6 rounded-2xl">
                  <h3 className="text-3xl font-bold mb-4 text-gray-800 transition-colors">3. Zyskaj wolność i bezpieczeństwo</h3>
                  <p className="text-gray-600 text-lg leading-relaxed">
                    Ochrona uruchamia się automatycznie po przypisaniu urządzenia i działa cicho w tle. Gdy system wykryje konsekwentne oddalanie breLocka lub utratę sygnału, komputer zostanie zablokowany bez udziału użytkownika.
                  </p>
               </div>
            </div>

          </div>
        </div>

      </main>
    </div>
  );
}
