import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { money } from "../src/theme.ts";
const data = JSON.parse(
  fs.readFileSync(new URL("../../fixtures/ecopetrol.json", import.meta.url)),
);
test("large and fractional money strings retain every digit", () => {
  assert.equal(money("8137440199"), "8.137.440.199");
  assert.equal(money("9007199254740993.0001"), "9.007.199.254.740.993,0001");
  assert.equal(money("602150472.00"), "602.150.472,00");
  assert.throws(() => money("not a value"));
});
test("featured source records belong to the selected supplier", () => {
  const rows = [...data.contracts.items, ...data.contracts_page2.items];
  assert.equal(new Set(rows.map((x) => x.contract_id)).size, 7);
  assert.ok(
    rows.every(
      (x) =>
        x.normalized_supplier_identifier === data.profile.nit &&
        x.match_status === "verified",
    ),
  );
  assert.notEqual(data.detail.buyer_nit, data.profile.nit);
  assert.ok(rows.some((x) => x.contract_id === data.detail.contract_id));
});
test("missing-signature bucket is retained in annual value totals", () => {
  const sum = data.secop.summary.annual.reduce(
    (s, x) => s + BigInt(x.values.COP),
    0n,
  );
  assert.equal(String(sum), data.secop.summary.total_values.COP);
  assert.equal(
    data.secop.summary.annual.find((x) => x.label === "Sin fecha de firma")
      .count,
    2,
  );
});
