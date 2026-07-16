import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "brelock",
  description: "Z Brelockiem jesteś bezpieczny. Inteligentny sprzęt, który automatycznie blokuje komputer pracownika, gdy ten odejdzie od biurka.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pl"
      className={`${inter.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className={`font-sans min-h-full flex flex-col bg-brelock-darkest text-white selection:bg-brelock-primary/50 relative overflow-x-hidden`}>
        {children}

        <Script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.1.9/p5.min.js" strategy="beforeInteractive" />
        <Script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.topology.min.js" strategy="beforeInteractive" />
      </body>
    </html>
  );
}
