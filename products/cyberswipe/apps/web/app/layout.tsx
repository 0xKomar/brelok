import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CyberSwipe – Naucz się cyberbezpieczeństwa",
  description:
    "Interaktywna gra edukacyjna o cyberbezpieczeństwie. Rozpoznaj zagrożenia quishingowe przesuwając karty w stylu Tinder!",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pl">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-[Inter] antialiased">{children}</body>
    </html>
  );
}
