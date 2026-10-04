import type { Metadata } from "next";
import { MotionProvider } from "@/components/MotionPrimitives";
import "./globals.css";

export const metadata: Metadata = {
  title: "breLock — lokalny projekt bezpieczeństwa",
  description: "Poznaj breLock: lokalny prototyp aplikacji komputerowej i breloka Bluetooth, który ma pomagać chronić stanowisko pracy.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pl" className="h-full antialiased" data-scroll-behavior="smooth">
      <body className="font-sans min-h-full selection:bg-brelock-glow/30">
        <a href="#main-content" className="skip-link">Przejdź do treści</a>
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
