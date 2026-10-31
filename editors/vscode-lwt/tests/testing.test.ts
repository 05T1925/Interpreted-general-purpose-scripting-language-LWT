import assert from "node:assert/strict";
import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test } from "node:test";
import {
  isLwtRepository,
  parseInventory,
  parseRunPayload,
  selectCaseIds,
  TestInventory,
} from "../src/testing";

const extensionRoot = path.resolve(__dirname, "..", "..");
const repositoryRoot = path.resolve(extensionRoot, "..", "..");
const python = process.env.LWT_TEST_PYTHON || "python";

function runRunner(args: string[]): SpawnSyncReturns<string> {
  return spawnSync(python, ["tools/run_tests.py", ...args], {
    cwd: repositoryRoot,
    encoding: "utf8",
    timeout: 20000,
    shell: false,
    windowsHide: true,
  }) as SpawnSyncReturns<string>;
}

function realInventory(): TestInventory {
  const result = runRunner(["--list-json"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
  return parseInventory(JSON.parse(result.stdout));
}

test("official runner inventory is 287 validated cases grouped into categories", () => {
  const inventory = realInventory();
  assert.equal(inventory.case_count, 287);
  assert.equal(inventory.categories.length, 9);
  assert.deepEqual(realInventory().cases.map((item) => item.id), inventory.cases.map((item) => item.id));
  assert.ok(inventory.cases.every((item) => item.source.startsWith("tests/cases/") && item.source.endsWith(".lwt")));
});

test("debug availability excludes CLI overrides, expected errors and invalid UTF-8 stdin", () => {
  const inventory = realInventory();
  const overrides = inventory.cases.filter((item) => item.cli_args_override !== null);
  assert.equal(overrides.length, 5);
  assert.ok(overrides.every((item) => !item.debug.available));
  assert.ok(inventory.cases.filter((item) => item.expected.exit_code !== 0).every((item) => !item.debug.available));
  const invalidUtf8 = inventory.cases.filter((item) => {
    try { new TextDecoder("utf-8", { fatal: true }).decode(Buffer.from(item.stdin_base64, "base64")); return false; }
    catch { return true; }
  });
  assert.ok(invalidUtf8.length > 0);
  assert.ok(invalidUtf8.every((item) => !item.debug.available));
});

test("invalid inventory schema, duplicate IDs, paths and Base64 fail closed", () => {
  const inventory = realInventory();
  assert.throws(() => parseInventory({ ...inventory, schema_version: 2 }), /unsupported inventory schema/);
  const duplicate = structuredClone(inventory) as unknown as { cases: unknown[] } & Record<string, unknown>;
  duplicate.cases[1] = duplicate.cases[0];
  assert.throws(() => parseInventory(duplicate), /duplicate case ID/);
  const absolutePath = structuredClone(inventory) as unknown as { cases: Array<Record<string, unknown>> } & Record<string, unknown>;
  absolutePath.cases[0].source = "C:\\private\\case.lwt";
  assert.throws(() => parseInventory(absolutePath), /repository-relative/);
  const badBase64 = structuredClone(inventory) as unknown as { cases: Array<Record<string, unknown>> } & Record<string, unknown>;
  badBase64.cases[0].stdin_base64 = "%%%";
  assert.throws(() => parseInventory(badBase64), /canonical Base64/);
});

test("TestRunRequest selection handles categories, duplicate includes and exclusions", () => {
  const inventory = realInventory();
  const cases = new Map(inventory.cases.map((item) => [`case:${item.id}`, item]));
  const categories = new Map(inventory.categories.map((category) => [
    `category:${category.name}`, category.case_ids.map((id) => `case:${id}`),
  ]));
  const selected = selectCaseIds(
    cases,
    categories,
    ["category:modules", "case:module-unicode-space-module-path", "case:module-unicode-space-module-path"],
    ["case:module-unicode-space-module-path"],
  );
  assert.equal(selected.length, inventory.categories.find((item) => item.name === "modules")!.case_ids.length - 1);
  assert.equal(new Set(selected).size, selected.length);
  assert.throws(() => selectCaseIds(cases, categories, ["case:missing"], []), /no longer present/);
  assert.throws(() => selectCaseIds(cases, categories, [], []), /contains no LWT cases/);
});

test("result parser verifies one exact runner batch and retains arbitrary output bytes", () => {
  const result = runRunner(["--case", "module-unicode-space-module-path", "--format", "json"]);
  assert.equal(result.status, 0, result.stderr);
  const payload = parseRunPayload(JSON.parse(result.stdout));
  assert.equal(payload.summary.selected, 1);
  assert.equal(payload.summary.passed, 1);
  assert.equal(payload.results[0].status, "passed");
  assert.equal(Buffer.from(payload.results[0].actual.stdout_base64, "base64").toString("utf8"), "雪\n");

  const falsePass = structuredClone(JSON.parse(result.stdout)) as { results: Array<Record<string, unknown>> };
  (falsePass.results[0].actual as Record<string, unknown>).stdout_base64 = "/wCA";
  assert.throws(() => parseRunPayload(falsePass), /inconsistent status/);

  const invalidBytes = structuredClone(JSON.parse(result.stdout)) as {
    summary: Record<string, number>;
    results: Array<Record<string, unknown>>;
  };
  const resultCase = invalidBytes.results[0];
  (resultCase.actual as Record<string, unknown>).stdout_base64 = "/wCA";
  resultCase.status = "failed";
  resultCase.failure_kind = "assertion_failure";
  resultCase.differences = ["stdout mismatch"];
  invalidBytes.summary.passed = 0;
  invalidBytes.summary.failed = 1;
  const parsedBytes = parseRunPayload(invalidBytes);
  assert.deepEqual(Buffer.from(parsedBytes.results[0].actual.stdout_base64, "base64"), Buffer.from([0xff, 0x00, 0x80]));

  invalidBytes.summary.failed = 0;
  assert.throws(() => parseRunPayload(invalidBytes), /summary disagrees/);
});

test("runner selection errors never look like empty success", () => {
  for (const args of [
    ["--case", "missing-case", "--format", "json"],
    ["--category", "missing-category", "--format", "json"],
    ["--case", "args-empty", "--case", "args-empty", "--format", "json"],
  ]) {
    const result = runRunner(args);
    assert.notEqual(result.status, 0);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /CONFIGURATION ERROR|error:/);
  }
});

test("LWT root recognition requires runner, interpreter and test inventory", () => {
  assert.ok(isLwtRepository(repositoryRoot));
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "not-lwt-workspace "));
  try { assert.equal(isLwtRepository(directory), false); }
  finally { fs.rmSync(directory, { recursive: true, force: true }); }
});
