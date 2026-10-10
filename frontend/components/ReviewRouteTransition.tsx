"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";

type Phase = "idle" | "crack" | "waiting" | "shatter";
type Fragment = { id: number; x: number; y: number; width: number; height: number; dx: number; dy: number; rotate: number; delay: number; cut: string };

async function captureScreen() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  const sourceBody = document.body;
  const clone = sourceBody.cloneNode(true) as HTMLElement;
  const copyStyles = (source: Element, target: Element) => {
    const computed = window.getComputedStyle(source);
    let css = "";
    for (let index = 0; index < computed.length; index += 1) {
      const property = computed[index];
      css += `${property}:${computed.getPropertyValue(property)};`;
    }
    (target as HTMLElement).style.cssText = css;
    if (source instanceof HTMLCanvasElement && target instanceof HTMLCanvasElement) {
      try {
        const image = document.createElement("img");
        image.src = source.toDataURL("image/png");
        image.style.cssText = (target as HTMLElement).style.cssText;
        target.replaceWith(image);
        return;
      } catch { /* Canvas snapshot is optional; the rest of the visible UI is preserved. */ }
    }
    const sourceChildren = Array.from(source.children);
    const targetChildren = Array.from(target.children);
    sourceChildren.forEach((child, index) => {
      const counterpart = targetChildren[index];
      if (counterpart) copyStyles(child, counterpart);
    });
  };
  copyStyles(sourceBody, clone);
  clone.style.cssText += `;position:relative!important;inset:auto!important;width:${width}px!important;height:${height}px!important;min-height:${height}px!important;max-height:${height}px!important;overflow:hidden!important;margin:0!important;`;
  clone.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><foreignObject width="100%" height="100%">${new XMLSerializer().serializeToString(clone)}</foreignObject></svg>`;
  const blobUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.src = blobUrl;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = width * Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.height = height * Math.min(window.devicePixelRatio || 1, 1.5);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not capture the dashboard screen.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return { dataUrl: canvas.toDataURL("image/png"), width, height };
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

export function ReviewRouteTransition() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [screenImage, setScreenImage] = useState("");
  const phaseRef = useRef<Phase>("idle");
  const readyRef = useRef(false);
  const reducedRef = useRef(false);
  const timingsRef = useRef({ crack: 0.28, shatter: 0.8 });

  useEffect(() => {
    const setCurrentPhase = (next: Phase) => {
      phaseRef.current = next;
      setPhase(next);
    };
    const start = async () => {
      if (phaseRef.current !== "idle") return;
      readyRef.current = false;
      reducedRef.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      timingsRef.current = reducedRef.current ? { crack: 0.2, shatter: 0.6 } : { crack: 0.3, shatter: 0.92 };
      try {
        const snapshot = await captureScreen();
        const cols = 9;
        const rows = 7;
        setScreenImage(snapshot.dataUrl);
        setFragments(Array.from({ length: cols * rows }, (_, id) => {
          const col = id % cols;
          const row = Math.floor(id / cols);
          const x = col * snapshot.width / cols;
          const y = row * snapshot.height / rows;
          const cx = (x + snapshot.width / cols / 2 - snapshot.width / 2) / snapshot.width;
          const cy = (y + snapshot.height / rows / 2 - snapshot.height / 2) / snapshot.height;
          const left = col === 0 ? 0 : 6 + Math.random() * 7;
          const right = col === cols - 1 ? 0 : 6 + Math.random() * 7;
          const cut = `polygon(${left}% 0, 100% ${5 + Math.random() * 8}%, ${100 - right}% 100%, 0 ${88 + Math.random() * 10}%)`;
          return {
            id, x, y, width: snapshot.width / cols + 1, height: snapshot.height / rows + 1,
            dx: cx * snapshot.width * (reducedRef.current ? 0.62 : 1.05) + (Math.random() - 0.5) * 140,
            dy: cy * snapshot.height * (reducedRef.current ? 0.62 : 1.05) + (Math.random() - 0.5) * 140,
            rotate: (Math.random() - 0.5) * (reducedRef.current ? 90 : 190),
            delay: id / (cols * rows - 1) * (reducedRef.current ? 0.08 : 0.2), cut,
          };
        }));
        setCurrentPhase("crack");
      } catch (error) {
        console.error("Could not create the dashboard shatter snapshot", error);
        router.push("/review");
      }
    };
    const ready = () => {
      readyRef.current = true;
      if (phaseRef.current === "waiting") setCurrentPhase("shatter");
    };
    window.addEventListener("nexyra:review-shatter", start);
    window.addEventListener("nexyra:review-ready", ready);
    return () => {
      window.removeEventListener("nexyra:review-shatter", start);
      window.removeEventListener("nexyra:review-ready", ready);
    };
  }, [router]);

  if (phase === "idle" || typeof document === "undefined") return null;
  const crackDuration = timingsRef.current.crack;
  const shatterDuration = timingsRef.current.shatter;
  return createPortal(
    <div className="review-screen-shatter" data-phase={phase} aria-hidden="true">
      {fragments.map(fragment => (
        <motion.span
          key={fragment.id}
          className="review-screen-fragment"
          style={{
            left: fragment.x, top: fragment.y, width: fragment.width, height: fragment.height,
            backgroundImage: `url("${screenImage}")`, backgroundSize: `${window.innerWidth}px ${window.innerHeight}px`,
            backgroundPosition: `-${fragment.x}px -${fragment.y}px`, clipPath: fragment.cut,
          }}
          initial={{ x: 0, y: 0, rotate: 0, scale: 1 }}
          animate={phase !== "shatter" ? {
            x: (fragment.x / window.innerWidth - 0.5) * 5,
            y: (fragment.y / window.innerHeight - 0.5) * 5,
            rotate: fragment.id % 2 ? 0.6 : -0.6,
            scale: 0.995,
          } : phase === "shatter" ? {
            x: fragment.dx, y: fragment.dy, rotate: fragment.rotate, opacity: 0, scale: 0.72,
          } : { x: 0, y: 0, rotate: 0, scale: 1, opacity: 1 }}
          transition={{
            duration: phase === "crack" ? crackDuration : shatterDuration,
            delay: phase === "shatter" ? fragment.delay : 0,
            ease: [0.16, 1, 0.3, 1],
          }}
          onAnimationComplete={() => {
            if (phase === "crack" && fragment.id === 0 && phaseRef.current === "crack") {
              phaseRef.current = "waiting";
              setPhase("waiting");
              router.push("/review");
              if (readyRef.current) {
                phaseRef.current = "shatter";
                setPhase("shatter");
              }
            } else if (phase === "shatter" && fragment.id === fragments.length - 1 && phaseRef.current === "shatter") {
              phaseRef.current = "idle";
              setPhase("idle");
              setFragments([]);
              setScreenImage("");
            }
          }}
        />
      ))}
    </div>, document.body,
  );
}
