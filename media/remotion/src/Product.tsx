import React, { type ReactNode, type CSSProperties } from "react";
import evidence from "../../fixtures/ecopetrol.json";
import { theme as C, money, dt } from "./theme";
import {
  Logo,
  Icon,
  Pill,
  Enter,
  Focus,
  Source,
  Cursor,
  ease,
  lerp,
  clamp,
} from "./Motion";
export const D = evidence;
export const company = D.profile;
export const summary = D.secop.summary;
export const fullNit = `${company.nit}-${company.verification_digit}`;
const card: CSSProperties = {
  background: C.surface,
  border: `1.5px solid ${C.border}`,
  borderRadius: 12,
};
const label: CSSProperties = { fontSize: 27, color: C.muted, marginBottom: 10 };
export function Browser({
  children,
  tab,
  style = {},
  t = 1,
}: {
  children: ReactNode;
  tab?: "identity" | "markets" | "contracts";
  style?: CSSProperties;
  t?: number;
}) {
  return (
    <div
      data-safe="browser"
      style={{ ...card, overflow: "hidden", position: "relative", ...style }}
    >
      <div
        style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "0 30px",
          background: C.subtle,
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <Logo size={43} />
        <span style={{ fontSize: 23, fontWeight: 600 }}>
          Colombia Company Intelligence
        </span>
        <span style={{ marginLeft: "auto", fontSize: 21, color: C.muted }}>
          {tab ? `${company.legal_name} · ${fullNit}` : "Búsqueda de empresas"}
        </span>
        <div style={{ display: "flex", gap: 8, marginLeft: 18 }}>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              style={{
                width: 7,
                height: 7,
                borderRadius: 10,
                background: C.muted,
              }}
            />
          ))}
        </div>
      </div>
      {tab && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 48,
            height: 67,
            padding: "0 32px",
            borderBottom: `1px solid ${C.border}`,
          }}
        >
          {[
            ["identity", "Descripción general"],
            ["markets", "Mercado de capitales"],
            ["contracts", "Contratos con el Gobierno"],
          ].map(([key, name]) => (
            <div
              key={key}
              style={{
                height: "100%",
                display: "flex",
                alignItems: "center",
                position: "relative",
                fontSize: 26,
                color: tab === key ? C.green : C.muted,
                fontWeight: tab === key ? 600 : 400,
              }}
            >
              {name}
              {tab === key && (
                <span
                  style={{
                    position: "absolute",
                    height: 3,
                    bottom: 0,
                    left: 0,
                    right: 0,
                    background: C.green,
                    transform: `scaleX(${ease(t, 0, 0.55)})`,
                    transformOrigin: "left",
                  }}
                />
              )}
            </div>
          ))}
        </div>
      )}
      {children}
    </div>
  );
}
export function SearchInput({
  t,
  compact = false,
}: {
  t: number;
  compact?: boolean;
}) {
  const chars = Math.round(lerp(0, 9, ease(t, 0.35, 1.1)));
  const typed = "Ecopetrol".slice(0, chars);
  return (
    <div
      style={{
        position: "relative",
        height: compact ? 100 : 116,
        ...card,
        borderColor: C.focus,
        display: "flex",
        alignItems: "center",
        gap: 22,
        padding: "0 18px 0 30px",
        boxShadow: `0 0 0 4px ${C.selected}`,
      }}
    >
      <Icon name="search" size={38} />
      <span style={{ fontSize: compact ? 40 : 44, flex: 1 }}>
        {typed || <span style={{ color: C.muted }}>Nombre o NIT</span>}
        <span
          style={{
            opacity: t < 1.7 ? 1 : 0,
            borderRight: `2px solid ${C.focus}`,
            marginLeft: 5,
          }}
        >
          &nbsp;
        </span>
      </span>
      <div
        style={{
          background: C.action,
          color: "white",
          borderRadius: 7,
          padding: "20px 28px",
          display: "flex",
          gap: 18,
          fontSize: 30,
          fontWeight: 600,
          alignItems: "center",
          transform: `scale(${1 - 0.025 * Math.sin(Math.PI * ease(t, 1.5, 0.25))})`,
        }}
      >
        Buscar
        <Icon name="arrow" size={32} />
      </div>
    </div>
  );
}
export function Identity({
  t,
  focus = true,
  small = false,
}: {
  t: number;
  focus?: boolean;
  small?: boolean;
}) {
  return (
    <div style={{ padding: small ? 24 : 28 }}>
      <Enter t={t}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 30,
            marginBottom: 22,
          }}
        >
          <div
            style={{
              fontSize: small ? 45 : 58,
              fontWeight: 600,
              letterSpacing: -1,
            }}
          >
            {company.legal_name}
          </div>
          <Pill>{company.registration_status}</Pill>
        </div>
      </Enter>
      <div
        style={{
          display: "inline-flex",
          position: "relative",
          gap: 18,
          padding: "10px 16px",
          marginLeft: -16,
          alignItems: "center",
          background: C.subtle,
          borderRadius: 8,
        }}
      >
        <span style={{ fontSize: small ? 32 : 38, color: C.muted }}>NIT</span>
        <span
          data-evidence="nit"
          style={{
            fontSize: small ? 40 : 49,
            fontWeight: 500,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {fullNit}
        </span>
        {focus && <Focus t={t} start={0.55} />}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: small ? "1fr 1fr" : "1fr 1fr 1fr",
          gap: 24,
          marginTop: 24,
        }}
      >
        {[
          ["Matrícula", company.registration.registration_number],
          ["Cámara de Comercio", company.registration.chamber],
          ["Actividad económica · CIIU", company.primary_ciiu],
        ].map(([k, v], i) => (
          <Enter
            key={k}
            t={t}
            delay={0.4 + i * 0.18}
            style={{
              position: "relative",
              padding: "12px 24px",
              borderLeft: `2px solid ${C.border}`,
              gridColumn: small && i === 2 ? "1 / -1" : undefined,
            }}
          >
            <div style={{ ...label, fontSize: small ? 26 : 27 }}>{k}</div>
            <div style={{ fontSize: small ? 35 : 38, fontWeight: 500 }}>
              {v}
            </div>
            {i !== 1 && (
              <Focus
                t={t}
                start={i === 0 ? 2.7 : 4.8}
                style={{
                  inset: 0,
                  opacity: 1 - ease(t, i === 0 ? 4.4 : 6.6, 0.5),
                }}
              />
            )}
          </Enter>
        ))}
      </div>
      {!small && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: 20,
            borderTop: `1px solid ${C.border}`,
            paddingTop: 18,
          }}
        >
          <span style={{ fontSize: 27, color: C.muted }}>
            Fecha de matrícula{" "}
            <strong style={{ color: C.ink, fontWeight: 500, marginLeft: 18 }}>
              {dt(company.registration.registration_date!)}
            </strong>
          </span>
          <span
            style={{
              position: "relative",
              fontSize: 27,
              color: C.green,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            RUES · Confecámaras
            <Icon name="link" size={26} />
            <span
              style={{
                position: "absolute",
                bottom: -7,
                left: 0,
                height: 2,
                width: `${100 * ease(t, 6.7, 0.8)}%`,
                background: C.green,
              }}
            />
          </span>
        </div>
      )}
    </div>
  );
}
export function SearchJourney({ t }: { t: number }) {
  const selected = ease(t, 5.0, 0.7);
  const opened = ease(t, 8.1, 0.7);
  return (
    <Browser
      style={{ height: 620 }}
      tab={opened > 0.5 ? "identity" : undefined}
      t={t - 8.1}
    >
      <div
        style={{
          position: "absolute",
          inset: "94px 34px auto",
          opacity: 1 - opened,
          transform: `translateY(${-24 * opened}px)`,
        }}
      >
        <SearchInput t={t} compact />
        <div
          style={{
            ...card,
            marginTop: 24,
            overflow: "hidden",
            opacity: ease(t, 1.85, 0.45),
            transform: `translateY(${18 * (1 - ease(t, 1.85, 0.6))}px)`,
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 340px",
              padding: "15px 24px",
              background: C.subtle,
              fontSize: 25,
              color: C.muted,
            }}
          >
            <span>Entidad jurídica</span>
            <span>NIT</span>
          </div>
          {D.search.items
            .filter(
              (r) =>
                [
                  "1bd03742-c759-403c-8498-dc2b4f55d8af",
                  "b02c94b3-d93f-4d9f-8ab9-f0ff51d97052",
                ].includes(r.id) ||
                r.legal_name === "ECOPETROL ENERGIA SAS ESP",
            )
            .slice(0, 3)
            .map((r, i) => {
              const hit = r.id === company.id;
              return (
                <div
                  key={r.id}
                  style={{
                    position: "relative",
                    display: "grid",
                    gridTemplateColumns: "1fr 340px",
                    gap: 24,
                    padding: "22px 24px",
                    borderTop: `1px solid ${C.border}`,
                    background: hit && selected > 0 ? C.selected : "white",
                    minHeight: 88,
                    alignItems: "center",
                    opacity: hit ? 1 : 1 - selected * 0.42,
                  }}
                >
                  <span style={{ fontSize: 29, fontWeight: hit ? 600 : 500 }}>
                    {r.legal_name}
                  </span>
                  <span
                    style={{ fontSize: 31, fontVariantNumeric: "tabular-nums" }}
                  >
                    {r.nit}-{r.verification_digit}
                  </span>
                  {hit && (
                    <Focus
                      t={t}
                      start={5.1}
                      style={{ inset: 2, borderRadius: 4 }}
                    />
                  )}
                </div>
              );
            })}
        </div>
      </div>
      {opened > 0 && (
        <div
          style={{
            position: "absolute",
            inset: "132px 0 0",
            opacity: opened,
            transform: `translateY(${25 * (1 - opened)}px)`,
          }}
        >
          <Identity t={t - 8.05} focus={false} />
        </div>
      )}
      {t < 8 && (
        <Cursor
          t={t}
          path={[
            [0, 1180, 145],
            [1.25, 1640, 145],
            [1.9, 1640, 145],
            [4.6, 220, 485],
            [5.4, 220, 485],
            [6.5, 1270, 516],
          ]}
          clickAt={[1.65, 5.6]}
        />
      )}
    </Browser>
  );
}
export function SecurityRows({
  t,
  compact = false,
}: {
  t: number;
  compact?: boolean;
}) {
  const rows = D.securities.items.slice(0, 2);
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <span style={{ fontSize: 34, fontWeight: 600 }}>
          Valores registrados
        </span>
        <span style={{ fontSize: 26, color: C.green }}>
          {D.securities.unfiltered_total} registros
        </span>
      </div>
      {rows.map((r, i) => (
        <div
          key={r.id}
          style={{
            position: "relative",
            ...card,
            marginTop: 14,
            padding: "12px 24px",
            opacity: ease(t, i * 0.3, 0.5),
            clipPath: `inset(0 ${(1 - ease(t, i * 0.3, 0.7)) * 100}% 0 0 round 10px)`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              marginBottom: 4,
              color: C.green,
              fontSize: 24,
            }}
          >
            <Icon name={i === 0 ? "chart" : "building"} size={26} />
            <span>
              {i === 0 ? "Acciones ordinarias" : "Otros valores de deuda"}
            </span>
          </div>
          <div
            data-evidence="security"
            style={{
              fontSize: 38,
              fontWeight: 600,
              lineHeight: 1.3,
              whiteSpace: "nowrap",
            }}
          >
            {r.security_name}
          </div>
          <Focus
            t={t}
            start={i === 0 ? 2.5 : 5.0}
            style={{ inset: 0, opacity: 1 - ease(t, i === 0 ? 4.8 : 8.5, 0.6) }}
          />
        </div>
      ))}
    </div>
  );
}
export function Markets({
  t,
  compact = false,
}: {
  t: number;
  compact?: boolean;
}) {
  return (
    <div
      style={{
        padding: 24,
        display: "grid",
        gridTemplateColumns: compact ? "1fr" : "480px 1fr",
        gap: 34,
      }}
    >
      {!compact && (
        <div
          style={{
            ...card,
            background: C.subtle,
            padding: 30,
            display: "flex",
            flexDirection: "column",
            gap: 22,
          }}
        >
          <div style={{ fontSize: 28, fontWeight: 600 }}>
            Registro de emisor
          </div>
          <div style={{ fontSize: 39, fontWeight: 600, lineHeight: 1.25 }}>
            {D.markets.rnve.issuer_name}
          </div>
          <Pill>
            <Icon name="check" size={26} />
            Inscrito en RNVE
          </Pill>
          <div style={{ fontSize: 27, color: C.muted, marginTop: 8 }}>
            NIT normalizado
          </div>
          <div style={{ fontSize: 34, fontWeight: 500 }}>{fullNit}</div>
          <div style={{ fontSize: 26, color: C.green, marginTop: 10 }}>
            Identidad verificada
          </div>
        </div>
      )}
      <div>
        <SecurityRows t={t - 0.3} compact={compact} />
        <div style={{ marginTop: 24 }}>
          <Source
            label="Fuente oficial SFC"
            t={t - 1}
            url={D.securities.items[0].source_url}
            compact={compact}
          />
        </div>
      </div>
    </div>
  );
}
export function Annual({
  t,
  compact = false,
}: {
  t: number;
  compact?: boolean;
}) {
  const vals = summary.annual;
  const max = BigInt("7535289727");
  return (
    <div style={{ ...card, padding: 22, height: "100%" }}>
      <div style={{ fontSize: 28, fontWeight: 600, marginBottom: 22 }}>
        Valor contractual anual (COP)
      </div>
      {vals.map((r, i) => (
        <div key={r.label} style={{ marginBottom: 14 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              fontSize: 24,
              marginBottom: 8,
            }}
          >
            <span style={{ color: C.muted }}>{r.label}</span>
            <strong style={{ fontWeight: 500, whiteSpace: "nowrap" }}>
              {money(r.values.COP)}
            </strong>
          </div>
          <div
            style={{
              height: 8,
              background: C.subtle,
              borderRadius: 4,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${(Number((BigInt(r.values.COP) * 10000n) / max) / 100) * ease(t, 0.25 + i * 0.12, 0.85)}%`,
                background: C.chart,
                transformOrigin: "left",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
export function Metrics({ t, gif = false }: { t: number; gif?: boolean }) {
  const metrics = [
    ["Total contratos", String(summary.total_contracts)],
    ["Valor contractual total (COP)", money(summary.total_values.COP)],
    ["Entidades contratantes", String(summary.distinct_buyers)],
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
      {metrics.map(([k, v], i) => (
        <div
          data-safe="metric"
          key={k}
          style={{
            ...card,
            padding: "18px 26px",
            gridColumn: i === 1 ? "1 / -1" : undefined,
            gridRow: i === 1 ? 2 : 1,
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ fontSize: 26, color: C.muted, marginBottom: 10 }}>
            {k}
          </div>
          <div
            data-evidence="metric"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: i === 1 ? (gif ? 72 : 76) : 78,
              fontWeight: 500,
              lineHeight: 1.1,
              whiteSpace: "nowrap",
              clipPath: `inset(0 ${(1 - ease(t, 0.15 + i * 0.18, 0.8)) * 100}% 0 0)`,
            }}
          >
            {v}
          </div>
          <div
            style={{
              height: 3,
              width: `${100 * ease(t, 0.3 + i * 0.18, 0.9)}%`,
              background: C.green,
              position: "absolute",
              bottom: 0,
              left: 0,
            }}
          />
        </div>
      ))}
    </div>
  );
}
export function Contracts({
  t,
  compact = false,
}: {
  t: number;
  compact?: boolean;
}) {
  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: compact ? 30 : 34, fontWeight: 600 }}>
          SECOP II · Contratación Pública
        </div>
        <span style={{ fontSize: compact ? 23 : 26, color: C.green }}>
          NIT del proveedor · {company.nit}
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: compact ? "1fr" : "1.1fr 1fr",
          gap: 30,
        }}
      >
        <Metrics t={t} gif={compact} />
        {!compact && <Annual t={t - 0.3} />}
      </div>
    </div>
  );
}
export function EvidenceView({ t }: { t: number }) {
  const slide = ease(t, 0.6, 0.9);
  const c = D.detail;
  return (
    <div style={{ padding: 32, position: "relative", height: 480 }}>
      <div style={{ width: 740, opacity: 1 - slide * 0.12 }}>
        <div style={{ fontSize: 29, fontWeight: 600, marginBottom: 20 }}>
          Top entidades por valor contractual (COP)
        </div>
        <div style={{ ...card, padding: 28 }}>
          <div style={{ fontSize: 29, fontWeight: 600, lineHeight: 1.4 }}>
            {summary.top_buyers[0].label.toLocaleUpperCase("es-CO")}
          </div>
          <div style={{ fontSize: 52, fontWeight: 500, marginTop: 18 }}>
            {money(summary.top_buyers[0].values.COP)}
          </div>
          <div style={{ fontSize: 26, color: C.muted, marginTop: 12 }}>
            2 contratos
          </div>
        </div>
        <div
          style={{
            ...card,
            padding: 25,
            marginTop: 22,
            fontSize: 28,
            display: "flex",
            justifyContent: "space-between",
            color: C.green,
          }}
        >
          <span>{c.contract_id}</span>
          <Icon name="arrow" size={30} />
        </div>
      </div>
      <div
        data-safe="detail"
        style={{
          ...card,
          position: "absolute",
          width: 880,
          top: 20,
          right: 30,
          padding: "20px 28px",
          transform: `translateX(${(1 - slide) * 980}px)`,
          opacity: slide,
          borderLeft: `4px solid ${C.green}`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 20,
            marginBottom: 14,
          }}
        >
          <span style={{ fontSize: 30, fontWeight: 600 }}>{c.contract_id}</span>
          <Pill>{c.raw_status.toLocaleUpperCase("es-CO")}</Pill>
        </div>
        <div style={{ fontSize: 27, color: C.muted }}>Entidad contratante</div>
        <div style={{ fontSize: 30, fontWeight: 500, marginTop: 7 }}>
          {c.buyer.toLocaleUpperCase("es-CO")}
        </div>
        <div
          style={{ display: "flex", gap: 44, marginTop: 16, alignItems: "end" }}
        >
          <div>
            <div style={{ fontSize: 26, color: C.muted }}>
              Valor reportado (COP)
            </div>
            <div
              style={{
                fontSize: 56,
                fontWeight: 500,
                whiteSpace: "nowrap",
                marginTop: 5,
              }}
            >
              {money(c.value!)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 26, color: C.muted }}>Firma</div>
            <div style={{ fontSize: 31, marginTop: 12 }}>
              {dt(c.signature_date!)}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <Source
            label={c.source_link_label}
            url={c.source_url}
            t={t - 2}
            compact
          />
        </div>
      </div>
      <Cursor
        t={t}
        path={[
          [0, 1230, 390],
          [0.6, 650, 365],
          [1.1, 650, 365],
          [2.2, 1430, 390],
          [4.8, 1480, 408],
        ]}
        clickAt={0.6}
      />
    </div>
  );
}
