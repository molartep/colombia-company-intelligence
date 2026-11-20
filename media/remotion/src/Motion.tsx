import React, { type CSSProperties, type ReactNode } from "react";
import { Img, staticFile, spring, useVideoConfig } from "remotion";
import { theme as C } from "./theme";
export const clamp = (v: number) => Math.max(0, Math.min(1, v));
export const smooth = (v: number) => {
  v = clamp(v);
  return v * v * (3 - 2 * v);
};
export const ease = (t: number, start = 0, duration = 0.7) =>
  smooth((t - start) / duration);
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export function Enter({
  t,
  delay = 0,
  children,
  style = {},
}: {
  t: number;
  delay?: number;
  children: ReactNode;
  style?: CSSProperties;
}) {
  const { fps } = useVideoConfig();
  const v = spring({
    fps,
    frame: Math.max(0, (t - delay) * fps),
    config: { damping: 26, stiffness: 150, mass: 0.9 },
    durationInFrames: Math.round(fps * 0.65),
  });
  return (
    <div
      style={{
        opacity: ease(t, delay, 0.35),
        transform: `translateY(${18 * (1 - v)}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
export function Logo({
  size = 86,
  style = {},
}: {
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <Img
      src={staticFile("colombia-network-logo.png")}
      style={{
        width: size,
        height: size,
        objectFit: "contain",
        flexShrink: 0,
        ...style,
      }}
    />
  );
}
export function Icon({
  name,
  size = 30,
}: {
  name: "search" | "arrow" | "check" | "link" | "building" | "chart";
  size?: number;
}) {
  const paths = {
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    check: <path d="m5 12 4 4L20 5" />,
    link: (
      <>
        <path d="M14 4h6v6m0-6L10 14" />
        <path d="M10 4H4v16h16v-6" />
      </>
    ),
    building: (
      <>
        <path d="m3 9 9-6 9 6H3ZM4 21h16M6 11v7m6-7v7m6-7v7" />
      </>
    ),
    chart: (
      <>
        <path d="M4 3v17h17M8 16v-5m5 5V7m5 9V3" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      {paths[name]}
    </svg>
  );
}
export function Pill({
  children,
  dark = false,
}: {
  children: ReactNode;
  dark?: boolean;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        border: `1px solid ${C.border}`,
        background: dark ? C.action : C.selected,
        color: dark ? "white" : C.green,
        padding: "10px 18px",
        borderRadius: 6,
        fontSize: 25,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}
export function Cursor({
  t,
  path,
  clickAt = -100,
}: {
  t: number;
  path: [number, number, number][];
  clickAt?: number | number[];
}) {
  let a = path[0],
    b = path[path.length - 1];
  for (let i = 0; i < path.length - 1; i++)
    if (t >= path[i][0] && t <= path[i + 1][0]) {
      a = path[i];
      b = path[i + 1];
      break;
    }
  if (t < path[0][0]) a = b = path[0];
  if (t > path[path.length - 1][0]) a = b = path[path.length - 1];
  const p = ease(t, a[0], Math.max(0.001, b[0] - a[0]));
  const x = lerp(a[1], b[1], p),
    y = lerp(a[2], b[2], p) - Math.sin(Math.PI * p) * 24;
  const hit = (Array.isArray(clickAt) ? clickAt : [clickAt]).find(
    (x) => t >= x && t < x + 0.38,
  );
  const q = clamp((t - (hit ?? -100)) / 0.38),
    active = hit !== undefined;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 40,
        height: 50,
        zIndex: 10,
        pointerEvents: "none",
      }}
    >
      {active && (
        <div
          style={{
            position: "absolute",
            left: -28 * q,
            top: -28 * q,
            width: 56 * q,
            height: 56 * q,
            border: `3px solid ${C.focus}`,
            borderRadius: 100,
            opacity: 1 - q,
          }}
        />
      )}
      <svg width="34" height="42" viewBox="0 0 34 42">
        <path
          d="M2 2 7 32l8-8 8 14 7-4-9-13 11-2Z"
          fill="white"
          stroke={C.ink}
          strokeWidth="2.5"
        />
      </svg>
    </div>
  );
}
export function Focus({
  t,
  start = 0,
  style = {},
}: {
  t: number;
  start?: number;
  style?: CSSProperties;
}) {
  const p = ease(t, start, 0.45);
  return (
    <div
      style={{
        position: "absolute",
        inset: -5,
        border: `3px solid ${C.focus}`,
        borderRadius: 12,
        opacity: p,
        clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`,
        pointerEvents: "none",
        ...style,
      }}
    />
  );
}
export function Source({
  label,
  t = 1,
  url,
  compact = false,
}: {
  label: string;
  t?: number;
  url: string;
  compact?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 24,
        paddingTop: 22,
        borderTop: `1px solid ${C.border}`,
        fontSize: compact ? 24 : 28,
        color: C.green,
      }}
    >
      <span
        style={{
          position: "relative",
          display: "inline-flex",
          gap: 12,
          alignItems: "center",
        }}
      >
        {label}
        <Icon name="link" size={26} />
        <span
          style={{
            position: "absolute",
            height: 2,
            background: C.green,
            bottom: -7,
            left: 0,
            width: `${ease(t, 0.4, 0.6) * 100}%`,
          }}
        />
      </span>
      <span style={{ fontSize: compact ? 20 : 23, color: C.muted }}>
        {new URL(url).hostname}
      </span>
    </div>
  );
}
