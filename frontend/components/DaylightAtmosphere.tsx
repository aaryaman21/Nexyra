"use client";

import { useTheme } from "@/context/ThemeContext";
import { CelestialBackground } from "./CelestialBackground";
import { BotanicalBackground } from "./BotanicalArt";

export function AmbientBackground() {
  const { resolvedTheme } = useTheme();
  if (resolvedTheme === "dark") return <CelestialBackground />;
  return <div className="daylight-field" aria-hidden="true">
    <div className="daylight-wash" />
    <div className="linen-light"><i /></div>
    <BotanicalBackground />
  </div>;
}
