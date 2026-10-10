import type { CSSProperties } from "react";

/** Fine branching stems and tiny ivory blossoms, like dried baby's breath. */
function FlowerStem({ index }: { index: number }) {
  const tipX = 35 + (index * 67) % 230;
  const tipY = 35 + (index * 83) % 230;
  const baseX = 120 + index * 16;
  return <g className={`flower-stem flower-tone-${index % 3}`} style={{ "--stem-delay": `${-index * 2.3}s`, "--stem-duration": `${9 + index % 4 * 1.5}s` } as CSSProperties}>
    <path d={`M ${baseX} 760 Q ${tipX + 65} 420 ${tipX} ${tipY}`} />
    {Array.from({ length: 8 }, (_, branch) => {
      const t = .16 + branch * .105;
      const x = (1-t) ** 2 * baseX + 2 * (1-t) * t * (tipX + 65) + t*t * tipX;
      const y = (1-t) ** 2 * 760 + 2 * (1-t) * t * 420 + t*t * tipY;
      const direction = branch % 2 ? 1 : -1;
      const endX = x + direction * (28 + (branch * 13 + index * 7) % 46);
      const endY = y - 40 - (branch * 7) % 27;
      return <g key={branch}>
        <path d={`M ${x} ${y} Q ${endX} ${y + 5} ${endX} ${endY}`} />
        {branch % 2 === 0 && <path className="flower-leaf" d={`M ${x} ${y} Q ${x + direction * 30} ${y - 6} ${x + direction * 35} ${y - 35} Q ${x + direction * 8} ${y - 30} ${x} ${y}Z`} />}
        {Array.from({ length: 4 }, (_, bud) => {
          const bx = endX + (bud - 1.5) * 12;
          const by = endY - 9 - (bud * 13 + index * 5) % 28;
          return <g key={bud}>
            <path d={`M ${endX} ${endY + 22} Q ${bx} ${endY} ${bx} ${by}`} />
            <g className="flower-blossom" transform={`translate(${bx} ${by}) rotate(${bud * 35}) scale(${.8 + (index + bud) % 3 * .24})`}>
              {Array.from({ length: 5 }, (_, petal) => <ellipse key={petal} cx="0" cy="-3" rx="2.8" ry="4" transform={`rotate(${petal * 72})`} />)}
              <circle className="flower-center" r="1.7" />
              <circle cx="-.5" cy="-.6" r=".6" fill="#fff7da" stroke="none" />
            </g>
          </g>;
        })}
      </g>;
    })}
  </g>;
}

export function BotanicalBackground() {
  return <div className="botanical-background" aria-hidden="true">
    {["left", "right"].map(side => <div key={side} className={`flower-arrangement flowers-${side}`}>
      <svg viewBox="0 0 360 780" fill="none">
        {Array.from({ length: 7 }, (_, i) => <FlowerStem key={i} index={i} />)}
      </svg>
    </div>)}
  </div>;
}

export function LotusArt() {
  return <svg className="lotus-art" viewBox="0 0 320 260" fill="none" aria-hidden="true">
    <g className="lotus-outer">
      {Array.from({ length: 12 }, (_, i) => <path key={i} transform={`rotate(${i * 30} 160 130)`}
        d="M160 130 C118 106 129 54 160 25 C191 54 202 106 160 130Z" />)}
    </g>
    <g className="lotus-inner">
      {Array.from({ length: 8 }, (_, i) => <path key={i} transform={`rotate(${i * 45} 160 130)`}
        d="M160 130 C136 111 139 82 160 62 C181 82 184 111 160 130Z" />)}
    </g>
    <circle cx="160" cy="130" r="10" className="lotus-heart" />
    <circle cx="160" cy="130" r="3" fill="currentColor" stroke="none" />
  </svg>;
}
