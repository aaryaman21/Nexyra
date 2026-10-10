import { useEffect, useRef, useState } from "react";

/**
 * Animated counter that counts from 0 to `target` when mounted or when
 * `target` changes. Returns the current display value (number).
 */
export function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(0);
  const frameRef = useRef<number>(0);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef<number>(0);

  useEffect(() => {
    fromRef.current = value;
    startRef.current = null;

    cancelAnimationFrame(frameRef.current);

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      /* ease-out cubic */
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(fromRef.current + (target - fromRef.current) * eased));
      if (progress < 1) frameRef.current = requestAnimationFrame(step);
    };

    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration]);

  return value;
}
