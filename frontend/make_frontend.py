import os

layout_content = """import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "NEXYRA \u2014 Personal Financial Decision Assistant",
  description: "Phase 1: Deterministic purchase simulation and financial consequence evaluation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrains.variable} font-sans antialiased min-h-screen`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
"""

with open("app/layout.tsx", "w", encoding="utf-8") as f:
    f.write(layout_content)
print("app/layout.tsx written successfully")
