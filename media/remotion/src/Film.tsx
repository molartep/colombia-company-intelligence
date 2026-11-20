import React, { type CSSProperties } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import story from "../../src/story.json";
import promoCues from "../../captions/promo.json";
import walkthroughCues from "../../captions/walkthrough.json";
import { theme as C } from "./theme";
import { Logo, Icon, Pill, Enter, Cursor, ease, lerp, clamp } from "./Motion";
import {
  D,
  company,
  fullNit,
  summary,
  Browser,
  SearchInput,
  Identity,
  SearchJourney,
  Markets,
  Contracts,
  Metrics,
  EvidenceView,
  SecurityRows,
} from "./Product";
export type Asset = "promo" | "walkthrough" | "gif";
const TABS = {
  identity: "Descripción general",
  markets: "Mercado de capitales",
  contracts: "Contratos con el Gobierno",
};
const headings = {
  hero: "Búsqueda de empresas",
  search: "Búsqueda por nombre o NIT",
  identity: "Información empresarial",
  markets: "Mercado de capitales",
  contracts: "Contratos con el Gobierno",
  evidence: "Evidencia del contrato",
  unified: "Contexto para investigar",
  closing: "Código abierto · Explora el proyecto",
};
type Scene = { start: number; end: number; layout: string; title: string };
function Header({ layout, gif }: { layout: string; gif: boolean }) {
  return (
    <div
      style={{
        height: 110,
        background: C.black,
        color: "white",
        display: "flex",
        alignItems: "center",
        padding: "0 80px",
        gap: 24,
        position: "absolute",
        inset: "0 0 auto",
        zIndex: 30,
      }}
    >
      <Logo size={82} />
      <div
        style={{
          fontSize: gif ? 38 : 40,
          fontWeight: 600,
          letterSpacing: -0.5,
        }}
      >
        Colombia Company Intelligence
      </div>
      <div
        style={{
          marginLeft: "auto",
          textAlign: "right",
          fontSize: 20,
          color: "#b8b8b8",
        }}
      >
        {!gif && (
          <div style={{ fontSize: 23, color: "white", marginBottom: 6 }}>
            {headings[layout as keyof typeof headings]}
          </div>
        )}
        Registros al 19 nov 2026
      </div>
    </div>
  );
}
function Hero({
  t,
  title,
  gif = false,
  returning = false,
}: {
  t: number;
  title: string;
  gif?: boolean;
  returning?: boolean;
}) {
  const phase = returning ? 0 : t;
  const resolve = ease(phase, 1.55, 0.8);
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 90,
          top: gif ? 220 : 225,
          width: 680,
        }}
      >
        <Enter t={gif ? 4 : t}>
          <h1
            style={{
              fontSize: gif ? 82 : 76,
              lineHeight: 1.12,
              letterSpacing: -2.3,
              margin: "0 0 30px",
              whiteSpace: "pre-line",
              fontWeight: 600,
            }}
          >
            {title}
          </h1>
        </Enter>
        <div
          style={{
            fontSize: 32,
            color: C.muted,
            lineHeight: 1.6,
            maxWidth: 600,
          }}
        >
          Identidad empresarial.
          <br />
          Valores registrados.
          <br />
          Contratos con el Gobierno.
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 38 }}>
          {["RUES", "SFC", "SECOP II"].map((s, i) => (
            <Enter key={s} t={gif ? 4 : t} delay={0.3 + i * 0.12}>
              <Pill>{s}</Pill>
            </Enter>
          ))}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 830,
          top: 210,
          width: 1000,
          transform: `translateY(${18 * (1 - ease(gif ? 4 : t, 0, 0.7))}px) scale(${lerp(0.98, 1, ease(gif ? 4 : t, 0, 1))})`,
          transformOrigin: "right center",
        }}
      >
        <Browser style={{ height: lerp(305, 565, resolve) }}>
          <div style={{ padding: "30px 28px" }}>
            <div style={{ fontSize: 29, fontWeight: 600, marginBottom: 24 }}>
              Encuentra una empresa colombiana
            </div>
            <SearchInput t={phase} compact />
            <div
              style={{
                height: 235,
                marginTop: 24,
                opacity: resolve,
                transform: `translateY(${18 * (1 - resolve)}px)`,
              }}
            >
              <div
                style={{
                  padding: "24px 28px",
                  border: `2px solid ${C.focus}`,
                  background: C.selected,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{ fontSize: 46, fontWeight: 600, marginBottom: 14 }}
                >
                  {company.legal_name}
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 20,
                    fontSize: 32,
                  }}
                >
                  <span>NIT {fullNit}</span>
                  <Icon name="check" size={31} />
                </div>
                <div style={{ fontSize: 26, color: C.muted, marginTop: 17 }}>
                  BOGOTA · Matrícula {company.registration.registration_number}
                </div>
              </div>
            </div>
          </div>
        </Browser>
        {!returning && phase > 0.3 && phase < 3 && (
          <Cursor
            t={phase}
            path={[
              [0, 750, 230],
              [1.2, 810, 195],
              [1.7, 810, 195],
              [2.6, 650, 390],
            ]}
            clickAt={1.65}
          />
        )}
      </div>
    </>
  );
}
function Unified({ t, title }: { t: number; title: string }) {
  const p = ease(t, 0.15, 1.0);
  return (
    <>
      <div style={{ position: "absolute", left: 90, top: 170, width: 750 }}>
        <h1
          style={{
            fontSize: 72,
            lineHeight: 1.14,
            letterSpacing: -1.8,
            whiteSpace: "pre-line",
            fontWeight: 600,
            margin: 0,
          }}
        >
          {title}
        </h1>
      </div>
      <svg
        width="1920"
        height="1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <g
          fill="none"
          stroke={C.green}
          strokeWidth="3"
          strokeDasharray="1000"
          strokeDashoffset={1000 * (1 - p)}
        >
          <path d="M460 672 C560 672 650 622 760 622" />
          <path d="M1450 430 C1300 430 1340 590 1190 620" />
          <path d="M1450 780 C1300 780 1330 650 1190 630" />
        </g>
      </svg>
      {[
        {
          x: 90,
          y: 550,
          name: "RUES",
          label: "Identidad y registro",
          value: company.legal_name,
        },
        {
          x: 1390,
          y: 300,
          name: "SFC · RNVE",
          label: "Valores registrados",
          value: "5 registros",
        },
        {
          x: 1390,
          y: 650,
          name: "SECOP II",
          label: "Contratos verificados",
          value: `${summary.total_contracts} contratos`,
        },
      ].map((r, i) => (
        <Enter
          t={t}
          delay={i * 0.08}
          key={r.name}
          style={{
            position: "absolute",
            left: r.x,
            top: r.y,
            width: 430,
            padding: 32,
            border: `1px solid ${C.border}`,
            borderRadius: 12,
            background: "white",
          }}
        >
          <div style={{ fontSize: 31, fontWeight: 600, color: C.green }}>
            {r.name}
          </div>
          <div style={{ fontSize: 27, color: C.muted, margin: "17px 0" }}>
            {r.label}
          </div>
          <div style={{ fontSize: 34, fontWeight: 500 }}>{r.value}</div>
        </Enter>
      ))}
      <div
        style={{
          position: "absolute",
          left: 750,
          top: 465,
          width: 570,
          padding: 32,
          border: `2px solid ${C.green}`,
          borderRadius: 12,
          background: C.subtle,
          textAlign: "center",
          transform: `scale(${lerp(0.94, 1, p)})`,
        }}
      >
        <Logo size={120} />
        <div style={{ fontSize: 42, fontWeight: 600, marginTop: 16 }}>
          {company.legal_name}
        </div>
        <div style={{ fontSize: 30, color: C.muted, marginTop: 16 }}>
          NIT {fullNit}
        </div>
      </div>
    </>
  );
}
function Closing({ t, title }: { t: number; title: string }) {
  const p = ease(t, 0, 0.7);
  return (
    <div
      style={{
        position: "absolute",
        inset: "145px 80px 190px",
        borderRadius: 16,
        background: C.ink,
        color: "white",
        display: "flex",
        alignItems: "center",
        padding: 60,
        gap: 80,
        transform: `scale(${lerp(0.98, 1, p)})`,
        opacity: p,
      }}
    >
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 47,
            fontWeight: 600,
            marginBottom: 34,
            letterSpacing: -1,
          }}
        >
          Colombia Company Intelligence
        </div>
        <h1
          style={{
            fontSize: 76,
            lineHeight: 1.13,
            fontWeight: 600,
            letterSpacing: -2,
            margin: 0,
            whiteSpace: "pre-line",
          }}
        >
          {title}
        </h1>
        <div
          style={{
            display: "flex",
            gap: 14,
            alignItems: "center",
            fontSize: 29,
            color: "#dce3df",
            marginTop: 46,
          }}
        >
          <Icon name="link" size={30} />
          <span>github.com/molartep/colombia-company-intelligence</span>
        </div>
      </div>
      <Logo size={330} style={{ marginRight: 30 }} />
    </div>
  );
}
function Showcase({
  scene,
  t,
  asset,
}: {
  scene: Scene;
  t: number;
  asset: Asset;
}) {
  const { layout, title } = scene;
  const gif = asset === "gif";
  if (layout === "hero")
    return (
      <Hero
        t={t}
        title={title}
        gif={gif}
        returning={gif && scene.start === 10}
      />
    );
  if (layout === "closing") return <Closing t={t} title={title} />;
  if (layout === "unified") return <Unified t={t} title={title} />;
  const isPromo = asset === "promo";
  return (
    <>
      <div style={{ position: "absolute", left: 80, top: 140, right: 80 }}>
        <h1
          style={{
            fontSize: gif ? 76 : 64,
            lineHeight: 1.13,
            fontWeight: 600,
            letterSpacing: -1.6,
            whiteSpace: "pre-line",
            margin: 0,
          }}
        >
          {title.replace(isPromo ? "\n" : "\u0000", isPromo ? " " : "\u0000")}
        </h1>
      </div>
      <div
        style={{
          position: "absolute",
          left: 80,
          top: gif ? 260 : 245,
          width: 1760,
          transform: `translateY(${12 * (1 - ease(t, 0, 0.65))}px)`,
        }}
      >
        {layout === "search" ? (
          <SearchJourney t={t} />
        ) : layout === "identity" ? (
          <Browser tab="identity" style={{ height: 630 }} t={t}>
            <Identity t={t} small={false} />
          </Browser>
        ) : layout === "markets" ? (
          <Browser tab="markets" style={{ height: 630 }} t={t}>
            <Markets t={t} />
          </Browser>
        ) : layout === "contracts" ? (
          <Browser tab="contracts" style={{ height: 630 }} t={t}>
            <Contracts t={t} />
          </Browser>
        ) : (
          <Browser tab="contracts" style={{ height: 630 }} t={t}>
            <EvidenceView t={t} />
          </Browser>
        )}
      </div>
      {layout === "markets" && t > 1 && (
        <Cursor
          t={t}
          path={[
            [1, 1070, 400],
            [2.3, 1390, 585],
            [4, 1390, 585],
            [6.2, 1150, 800],
            [9, 1150, 800],
          ]}
          clickAt={6.4}
        />
      )}
    </>
  );
}
export function Film({ asset }: { asset: Asset }) {
  const frame = useCurrentFrame(),
    { fps } = useVideoConfig();
  const t = frame / fps;
  const spec = story[asset];
  const scenes = spec.scenes as Scene[];
  const index = Math.max(
    0,
    scenes.findIndex((s) => t >= s.start && t < s.end),
  );
  const current = scenes[index];
  const local = t - current.start;
  const transition = 0.65;
  const cues = asset === "promo" ? promoCues : walkthroughCues;
  const cue =
    asset === "gif" ? null : cues.find((c) => t >= c.start && t < c.end);
  const gif = asset === "gif";
  // A continuous fixed brand / company anchor survives every source change.
  return (
    <AbsoluteFill
      style={{
        background: C.canvas,
        fontFamily: C.font,
        color: C.ink,
        overflow: "hidden",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      <style>{`* {box-sizing: border-box;} body {margin:0;}`}</style>
      <Header layout={current.layout} gif={gif} />
      {index > 0 && local < transition && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 1 - ease(local, 0, 0.28),
            transform: `translateX(${-14 * ease(local, 0, 0.28)}px)`,
          }}
        >
          <Showcase
            scene={scenes[index - 1]}
            t={scenes[index - 1].end - scenes[index - 1].start}
            asset={asset}
          />
        </div>
      )}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: index === 0 ? 1 : ease(local, 0.28, 0.37),
          transform: `translateX(${index === 0 ? 0 : 14 * (1 - ease(local, 0.28, 0.37))}px)`,
        }}
      >
        <Showcase
          scene={current}
          t={gif && current.start === 10 ? 3 : local}
          asset={asset}
        />
      </div>
      {!gif && (
        <div
          style={{
            position: "absolute",
            bottom: 64,
            left: 80,
            right: 80,
            minHeight: 95,
            display: "flex",
            alignItems: "end",
            justifyContent: "center",
          }}
        >
          {cue && (
            <div
              data-safe="captions"
              style={{
                background: C.ink,
                color: "white",
                padding: "12px 24px",
                borderRadius: 7,
                fontSize: 34,
                lineHeight: 1.25,
                textAlign: "center",
                maxWidth: 1660,
              }}
            >
              {cue.text}
            </div>
          )}
        </div>
      )}
    </AbsoluteFill>
  );
}
