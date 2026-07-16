"use client";
import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { Lock, Unlock } from "lucide-react";

export default function InteractiveLaptop() {
  const [isInside, setIsInside] = useState(false);
  const [isLocked, setIsLocked] = useState(false);
  const laptopRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  const laptopCenterRef = useRef<{x: number, y: number} | null>(null);

  useEffect(() => {
    const updateCenter = () => {
      if (laptopRef.current) {
        const rect = laptopRef.current.getBoundingClientRect();
        laptopCenterRef.current = {
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
        };
      }
    };
    
    // Initial and deferred calculations
    updateCenter();
    // In case fonts/images load late
    const timeoutId = setTimeout(updateCenter, 500);
    
    window.addEventListener('resize', updateCenter);
    window.addEventListener('scroll', updateCenter, { passive: true });
    
    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', updateCenter);
      window.removeEventListener('scroll', updateCenter);
    };
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    // Direct DOM manipulation for zero-lag cursor tracking via GPU transform
    if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0) translate(-50%, -50%)`;
    }

    if (laptopCenterRef.current) {
        const center = laptopCenterRef.current;
        const dist = Math.sqrt(
            Math.pow(e.clientX - center.x, 2) + Math.pow(e.clientY - center.y, 2)
        );
        
        // Prevent React re-rendering 60 times a second
        // Only update state if the lock status actually crosses the threshold
        const newLockState = dist > 350;
        if (newLockState !== isLocked) {
            setIsLocked(newLockState);
        }
    }
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLElement>) => {
    if (e.touches.length > 0) {
        const touch = e.touches[0];
        if (cursorRef.current) {
            cursorRef.current.style.transform = `translate3d(${touch.clientX}px, ${touch.clientY}px, 0) translate(-50%, -50%)`;
        }

        if (laptopCenterRef.current) {
            const center = laptopCenterRef.current;
            const dist = Math.sqrt(
                Math.pow(touch.clientX - center.x, 2) + Math.pow(touch.clientY - center.y, 2)
            );
            
            // Smaller threshold for mobile screens
            const threshold = typeof window !== 'undefined' && window.innerWidth < 640 ? 150 : 350;
            const newLockState = dist > threshold;
            if (newLockState !== isLocked) {
                setIsLocked(newLockState);
            }
        }
    }
  };

  return (
    <section 
      className="w-full relative py-32 bg-[#021008] overflow-hidden border-t border-white/5 md:cursor-none"
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsInside(true)}
      onMouseLeave={() => setIsInside(false)}
      onTouchMove={handleTouchMove}
      onTouchStart={(e) => { setIsInside(true); handleTouchMove(e); }}
      onTouchEnd={() => setIsInside(false)}
    >
      <div className="max-w-6xl mx-auto px-6 flex flex-col items-center">
        <h2 className="text-4xl md:text-5xl font-bold text-white mb-6 text-center tracking-tight">
          Przetestuj na własnej skórze.
        </h2>
        <p className="text-white/60 text-center max-w-2xl text-lg mb-20 pointer-events-none">
          Twój kursor (lub palec na urządzeniach mobilnych) zachowuje się teraz jak urządzenie breLock. Spróbuj "odejść" nim powoli od komputera, żeby na własne oczy przekonać się o bezlitosnej blokadzie ekranu.
        </p>
        
        {/* Laptop Container */}
        <div className="relative mb-20 perspective">
            <div 
            ref={laptopRef}
            className="relative w-[320px] sm:w-[500px] h-[200px] sm:h-[320px] bg-black rounded-t-2xl sm:rounded-t-3xl border-4 sm:border-[8px] border-gray-800 shadow-[0_0_50px_rgba(0,0,0,1)] flex items-center justify-center transition-all duration-300 z-10 pointer-events-none"
            >
                <div className="absolute inset-0 bg-[#042413] flex flex-col items-center justify-center overflow-hidden rounded-t-xl sm:rounded-t-2xl transition-colors duration-500">
                    {isLocked ? (
                    <div className="flex flex-col items-center justify-center w-full h-full bg-red-950/40 transition-opacity duration-300">
                        <div className="absolute inset-0 bg-red-500/10 blur-xl animate-pulse" />
                        <Lock size={80} className="mb-4 text-red-500 animate-pulse drop-shadow-[0_0_15px_rgba(239,68,68,0.8)]" />
                        <span className="text-2xl sm:text-4xl font-bold tracking-widest text-red-500/90 [text-shadow:_0_2px_10px_rgba(239,68,68,0.5)]">ZABLOKOWANE</span>
                        <span className="text-sm text-red-500/60 mt-2 font-medium">Brak dostępu</span>
                    </div>
                    ) : (
                    <div className="flex flex-col items-center justify-center w-full h-full bg-brelock-darker transition-opacity duration-300">
                        <div className="absolute inset-0 bg-brelock-glow/10 blur-xl animate-pulse" />
                        <Unlock size={80} className="mb-4 text-brelock-glow drop-shadow-[0_0_15px_rgba(46,204,113,0.8)]" />
                        <span className="text-2xl sm:text-4xl font-bold tracking-widest text-white [text-shadow:_0_2px_10px_rgba(255,255,255,0.3)]">AKTYWNY</span>
                        <span className="text-sm text-white/50 mt-2 font-medium">Praca w toku...</span>
                    </div>
                    )}
                </div>
            
                {/* Keyboard base */}
                <div className="absolute -bottom-12 sm:-bottom-16 -left-[10%] w-[120%] h-12 sm:h-16 bg-gray-800 rounded-b-2xl shadow-2xl flex justify-center [transform:rotateX(45deg)] z-0">
                    <div className="w-20 h-2 sm:h-3 bg-gray-600 rounded-full mt-2 sm:mt-3 opacity-50"></div>
                </div>
            </div>
        </div>

      </div>

      {/* Custom Cursor */}
       <div 
           ref={cursorRef}
           className={`fixed pointer-events-none z-50 left-0 top-0 ${isInside ? 'opacity-100' : 'opacity-0'} transition-opacity duration-200`}
           style={{ transform: 'translate3d(-100px, -100px, 0) translate(-50%, -50%)' }} // Initial off-screen
       >
           <div className="relative flex items-center justify-center">
               <div className={`absolute inset-0 rounded-full blur-[20px] opacity-60 animate-pulse w-32 h-32 -m-8 transition-colors duration-500 ${isLocked ? 'bg-red-500' : 'bg-brelock-glow'}`}></div>
               <Image src="/logo2.png" alt="brelock cursor" width={64} height={64} className={`relative z-10 drop-shadow-[0_0_20px_rgba(0,0,0,0.5)] transition-all duration-500 ${isLocked ? 'brightness-50 sepia hue-rotate-[-50deg] saturate-200' : ''}`} />
           </div>
       </div>
    </section>
  );
}
