import type { CSSProperties } from "react";

export function FooterGarden() {
  return <div className="footer-garden" aria-hidden="true">
    <div className="garden-ground" />
    <svg className="garden-plants" viewBox="0 0 1200 180" fill="none">
      {Array.from({ length: 23 }, (_, i) => {
        const x = 28 + i * 52;
        const height = 42 + (i * 37) % 75;
        const bend = i % 2 ? 19 : -19;
        return <g key={i} transform={`translate(${x} 173)`}>
          <g className={`garden-sprig flower-tone-${i % 3}`} style={{ "--garden-delay": `${-i * 1.3}s` } as CSSProperties}>
            <path d={`M0 0 Q${bend} ${-height * .5} ${bend * .6} ${-height}`} className="garden-stem" />
            {[0, 1, 2].map(j => <g key={j} transform={`translate(${bend * .4} ${-15 - j * height * .22})`}>
              <path d="M0 0 C-24 1 -32 -12 -34 -22 C-15 -22 -3 -12 0 0Z" className="garden-leaf" />
              <path d="M0 -5 C21 -3 28 -16 29 -28 C12 -24 2 -15 0 -5Z" className="garden-leaf garden-leaf-light" />
              <path d="M-28 -18 L0 0 L24 -22" className="garden-vein" />
            </g>)}
            {i % 3 !== 0 && <g className="flower-blossom" transform={`translate(${bend * .6} ${-height})`}>
              {Array.from({ length: 5 }, (_, p) => <ellipse key={p} cx="0" cy="-5" rx="4" ry="6" transform={`rotate(${p * 72})`} />)}
              <circle r="2.7" className="flower-center" />
            </g>}
          </g>
        </g>;
      })}
    </svg>
    {[0, 1].map(i => <div key={i} className={`garden-butterfly butterfly-${i}`}>
      <svg viewBox="0 0 40 32" fill="none">
        <g className="butterfly-wings">
          <path d="M20 18 C4 -4 -5 5 7 19 C0 29 13 35 20 18Z" />
          <path d="M20 18 C36 -4 45 5 33 19 C40 29 27 35 20 18Z" />
          <path d="M18 18 L9 11 M22 18 L31 11" className="butterfly-detail" />
        </g>
        <path d="M20 25 L20 13 M20 14 L16 9 M20 14 L24 9" className="butterfly-body" />
      </svg>
    </div>)}
  </div>;
}
