import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Great_Vibes } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { ReviewRouteTransition } from "@/components/ReviewRouteTransition";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });
const calligraphy = Great_Vibes({ subsets: ["latin"], weight: "400", variable: "--font-calligraphy" });

export const metadata: Metadata = {
  title: "NEXYRA - AgriSense Market Intelligence",
  description: "Agricultural wholesale market intelligence, evaluated forecasts and semantic evidence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-motion-preview={process.env.NODE_ENV !== "production" ? "true" : undefined} suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrains.variable} ${calligraphy.variable} font-sans antialiased min-h-screen`}>
        <ThemeProvider>{children}<ReviewRouteTransition /></ThemeProvider>
      </body>
    </html>
  );
}
