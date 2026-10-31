import { spawn, type ChildProcess } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type * as vscode from "vscode";

export interface InventoryCase {
  readonly id: string;
  readonly category: string;
  readonly source: string;
  readonly spec_refs: readonly string[];
  readonly tags: readonly string[];
  readonly args: readonly string[];
  readonly stdin_base64: string;
  readonly expected: {
    readonly exit_code: number;
    readonly stdout_base64: string;
    readonly stderr_base64: string;
  };
  readonly timeout_seconds: number;
  readonly cli_args_override: readonly string[] | null;
  readonly debug: { readonly available: boolean; readonly reason: string | null };
}

export interface TestInventory {
  readonly schema: "lwt.test-inventory";
  readonly schema_version: 1;
  readonly case_count: number;
  readonly categories: readonly { readonly name: string; readonly case_ids: readonly string[] }[];
  readonly cases: readonly InventoryCase[];
}

export interface RunCaseResult extends InventoryCase {
  readonly status: "passed" | "failed" | "timeout" | "start_failed" | "cancelled" | "not_executed";
  readonly failure_kind: "assertion_failure" | "runtime_error" | "timeout" | "start_failure" | null;
  readonly actual: {
    readonly exit_code: number | null;
    readonly stdout_base64: string;
    readonly stderr_base64: string;
  };
  readonly duration_seconds: number;
  readonly differences: readonly string[];
}

export interface RunPayload {
  readonly schema: "lwt.test-results";
  readonly schema_version: 1;
  readonly status: "completed" | "cancelled";
  readonly summary: Record<string, number>;
  readonly results: readonly RunCaseResult[];
}

export class TestingWorkbenchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TestingWorkbenchError";
  }
}

export function isLwtRepository(root: string): boolean {
  try {
    return fs.existsSync(path.join(root, "tools", "run_tests.py"))
      && fs.existsSync(path.join(root, "lwt", "__main__.py"))
      && fs.existsSync(path.join(root, "tests", "cases"))
      && fs.statSync(path.join(root, "tests", "cases")).isDirectory();
  } catch {
    return false;
  }
}

function requireObject(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TestingWorkbenchError(`${label} must be an object.`);
  }
  return value as Record<string, unknown>;
}

function requireString(value: unknown, label: string, nonempty = false): string {
  if (typeof value !== "string" || (nonempty && value.length === 0)) {
    throw new TestingWorkbenchError(`${label} must be ${nonempty ? "a non-empty string" : "a string"}.`);
  }
  return value;
}

function requireStringArray(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new TestingWorkbenchError(`${label} must be an array of strings.`);
  }
  return value as string[];
}

function requireBase64(value: unknown, label: string): string {
  const encoded = requireString(value, label);
  const decoded = Buffer.from(encoded, "base64");
  if (decoded.toString("base64") !== encoded) {
    throw new TestingWorkbenchError(`${label} must contain canonical Base64.`);
  }
  return encoded;
}

function validateSource(source: string): void {
  const components = source.replaceAll("\\", "/").split("/");
  if (path.posix.isAbsolute(source) || path.win32.isAbsolute(source)
      || components.some((part) => part === ".." || part === ".")
      || !source.startsWith("tests/cases/") || !source.endsWith(".lwt")) {
    throw new TestingWorkbenchError(`case source must be a repository-relative tests/cases .lwt path: ${source}`);
  }
}

function isStrictUtf8(data: Buffer): boolean {
  try {
    new TextDecoder("utf-8", { fatal: true }).decode(data);
    return true;
  } catch {
    return false;
  }
}

function normalizeCrLf(data: Buffer): Buffer {
  return Buffer.from(data.toString("latin1").replace(/\r\n/g, "\n"), "latin1");
}

export function parseInventory(value: unknown): TestInventory {
  const object = requireObject(value, "inventory");
  if (object.schema !== "lwt.test-inventory" || object.schema_version !== 1) {
    throw new TestingWorkbenchError("runner returned an unsupported inventory schema.");
  }
  if (!Array.isArray(object.cases) || !Array.isArray(object.categories)) {
    throw new TestingWorkbenchError("inventory must contain cases and categories arrays.");
  }
  if (!Number.isSafeInteger(object.case_count) || object.case_count !== object.cases.length) {
    throw new TestingWorkbenchError("inventory case_count does not match the cases array.");
  }

  const ids = new Set<string>();
  const cases: InventoryCase[] = object.cases.map((raw, index) => {
    const item = requireObject(raw, `cases[${index}]`);
    const id = requireString(item.id, `cases[${index}].id`, true);
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id) || ids.has(id)) {
      throw new TestingWorkbenchError(`inventory contains an invalid or duplicate case ID: ${id}`);
    }
    ids.add(id);
    const category = requireString(item.category, `cases[${index}].category`, true);
    const source = requireString(item.source, `cases[${index}].source`, true);
    validateSource(source);
    const specRefs = requireStringArray(item.spec_refs, `cases[${index}].spec_refs`);
    const tags = requireStringArray(item.tags, `cases[${index}].tags`);
    const args = requireStringArray(item.args, `cases[${index}].args`);
    const stdinBase64 = requireBase64(item.stdin_base64, `cases[${index}].stdin_base64`);
    const expected = requireObject(item.expected, `cases[${index}].expected`);
    if (!Number.isSafeInteger(expected.exit_code) || Number(expected.exit_code) < 0 || Number(expected.exit_code) > 255) {
      throw new TestingWorkbenchError(`cases[${index}].expected.exit_code is invalid.`);
    }
    const expectedOutput = requireBase64(expected.stdout_base64, `cases[${index}].expected.stdout_base64`);
    const expectedError = requireBase64(expected.stderr_base64, `cases[${index}].expected.stderr_base64`);
    const timeout = item.timeout_seconds;
    if (typeof timeout !== "number" || !Number.isFinite(timeout) || timeout <= 0 || timeout > 30) {
      throw new TestingWorkbenchError(`cases[${index}].timeout_seconds is invalid.`);
    }
    let override: readonly string[] | null;
    if (item.cli_args_override === null) override = null;
    else override = requireStringArray(item.cli_args_override, `cases[${index}].cli_args_override`);
    const debug = requireObject(item.debug, `cases[${index}].debug`);
    if (typeof debug.available !== "boolean" || (debug.reason !== null && typeof debug.reason !== "string")) {
      throw new TestingWorkbenchError(`cases[${index}].debug is invalid.`);
    }
    const debugAvailable = override === null
      && expected.exit_code === 0
      && isStrictUtf8(Buffer.from(stdinBase64, "base64"));
    const debugReason = override !== null
      ? "case uses cli_args_override rather than a standard source entry"
      : expected.exit_code !== 0
        ? "case expects a non-zero exit code"
        : !isStrictUtf8(Buffer.from(stdinBase64, "base64"))
          ? "case stdin is not strict UTF-8"
          : null;
    if (debug.available !== debugAvailable || debug.reason !== debugReason) {
      throw new TestingWorkbenchError(`cases[${index}].debug.available disagrees with validated case metadata.`);
    }
    return {
      id,
      category,
      source,
      spec_refs: specRefs,
      tags,
      args,
      stdin_base64: stdinBase64,
      expected: { exit_code: Number(expected.exit_code), stdout_base64: expectedOutput, stderr_base64: expectedError },
      timeout_seconds: timeout,
      cli_args_override: override,
      debug: { available: debug.available, reason: debug.reason as string | null },
    };
  });

  const categoryIds = new Set<string>();
  const categoryNames = new Set<string>();
  const categories = object.categories.map((raw, index) => {
    const category = requireObject(raw, `categories[${index}]`);
    const name = requireString(category.name, `categories[${index}].name`, true);
    if (categoryNames.has(name)) throw new TestingWorkbenchError(`inventory contains a duplicate category: ${name}`);
    categoryNames.add(name);
    const caseIds = requireStringArray(category.case_ids, `categories[${index}].case_ids`);
    for (const id of caseIds) {
      const found = cases.find((testCase) => testCase.id === id);
      if (!found || found.category !== name || categoryIds.has(id)) {
        throw new TestingWorkbenchError(`category inventory has an unknown, mismatched, or repeated case ID: ${id}`);
      }
      categoryIds.add(id);
    }
    return { name, case_ids: caseIds };
  });
  if (categoryIds.size !== cases.length) {
    throw new TestingWorkbenchError("category inventory does not reference every case exactly once.");
  }
  return { schema: "lwt.test-inventory", schema_version: 1, case_count: cases.length, categories, cases };
}

export function parseRunPayload(value: unknown): RunPayload {
  const object = requireObject(value, "result");
  if (object.schema !== "lwt.test-results" || object.schema_version !== 1
      || !Array.isArray(object.results) || (object.status !== "completed" && object.status !== "cancelled")) {
    throw new TestingWorkbenchError("runner returned an unsupported result schema.");
  }
  const summary = requireObject(object.summary, "result.summary");
  const summaryKeys = ["selected", "passed", "failed", "timeout", "start_failed", "cancelled", "not_executed"];
  if (Object.keys(summary).length !== summaryKeys.length || summaryKeys.some((key) => !(key in summary))) {
    throw new TestingWorkbenchError("result.summary has missing or unknown status counts.");
  }
  for (const [name, count] of Object.entries(summary)) {
    if (!Number.isSafeInteger(count) || Number(count) < 0) {
      throw new TestingWorkbenchError(`result.summary.${name} must be a non-negative integer.`);
    }
  }
  const results: RunCaseResult[] = object.results.map((raw, index) => {
    const item = requireObject(raw, `results[${index}]`);
    const status = item.status;
    if (!["passed", "failed", "timeout", "start_failed", "cancelled", "not_executed"].includes(String(status))) {
      throw new TestingWorkbenchError(`results[${index}].status is invalid.`);
    }
    const actual = requireObject(item.actual, `results[${index}].actual`);
    if (actual.exit_code !== null && !Number.isSafeInteger(actual.exit_code)) {
      throw new TestingWorkbenchError(`results[${index}].actual.exit_code is invalid.`);
    }
    const failureKind = item.failure_kind;
    if (failureKind !== null && !["assertion_failure", "runtime_error", "timeout", "start_failure"].includes(String(failureKind))) {
      throw new TestingWorkbenchError(`results[${index}].failure_kind is invalid.`);
    }
    const actualExitCode = actual.exit_code as number | null;
    const differences = requireStringArray(item.differences, `results[${index}].differences`);
    const expected = requireObject(item.expected, `results[${index}].expected`);
    const expectedExitCode = expected.exit_code;
    if (!Number.isSafeInteger(expectedExitCode)) {
      throw new TestingWorkbenchError(`results[${index}].expected.exit_code is invalid.`);
    }
    const expectedStdout = Buffer.from(requireBase64(expected.stdout_base64, `results[${index}].expected.stdout_base64`), "base64");
    const expectedStderr = Buffer.from(requireBase64(expected.stderr_base64, `results[${index}].expected.stderr_base64`), "base64");
    const actualStdout = Buffer.from(requireBase64(actual.stdout_base64, `results[${index}].actual.stdout_base64`), "base64");
    const actualStderr = Buffer.from(requireBase64(actual.stderr_base64, `results[${index}].actual.stderr_base64`), "base64");
    const stdoutMatches = normalizeCrLf(expectedStdout).equals(normalizeCrLf(actualStdout));
    const stderrMatches = normalizeCrLf(expectedStderr).equals(normalizeCrLf(actualStderr));
    const validOutcome = status === "passed"
      ? failureKind === null && actualExitCode === expectedExitCode && stdoutMatches && stderrMatches && differences.length === 0
      : status === "failed"
        ? differences.length > 0 && ((failureKind === "assertion_failure" && actualExitCode === expectedExitCode && (!stdoutMatches || !stderrMatches))
          || (failureKind === "runtime_error" && actualExitCode !== null && actualExitCode !== expectedExitCode))
        : status === "timeout"
          ? failureKind === "timeout" && actualExitCode === null && differences.length > 0
          : status === "start_failed"
            ? failureKind === "start_failure" && actualExitCode === null && differences.length > 0
            : failureKind === null && differences.length === 0;
    if (!validOutcome) throw new TestingWorkbenchError(`results[${index}] has inconsistent status, failure kind, exit code or differences.`);
    return {
      ...parseInventoryCaseFromResult(item, index),
      status: status as RunCaseResult["status"],
      failure_kind: failureKind as RunCaseResult["failure_kind"],
      actual: {
        exit_code: actualExitCode,
        stdout_base64: actualStdout.toString("base64"),
        stderr_base64: actualStderr.toString("base64"),
      },
      duration_seconds: typeof item.duration_seconds === "number" && Number.isFinite(item.duration_seconds) && item.duration_seconds >= 0
        ? item.duration_seconds : (() => { throw new TestingWorkbenchError(`results[${index}].duration_seconds is invalid.`); })(),
      differences,
    };
  });
  const actualCounts = new Map<string, number>();
  for (const result of results) actualCounts.set(result.status, (actualCounts.get(result.status) ?? 0) + 1);
  if (summaryKeys.some((key) => Number(summary[key]) !== (key === "selected" ? results.length : (actualCounts.get(key) ?? 0)))) {
    throw new TestingWorkbenchError("runner result summary disagrees with the results array.");
  }
  const containsUnexecuted = results.some((item) => item.status === "cancelled" || item.status === "not_executed");
  if ((object.status === "cancelled") !== containsUnexecuted) {
    throw new TestingWorkbenchError("runner top-level status disagrees with case execution states.");
  }
  return {
    schema: "lwt.test-results",
    schema_version: 1,
    status: object.status,
    summary: summary as Record<string, number>,
    results,
  };
}

function parseInventoryCaseFromResult(item: Record<string, unknown>, index: number): InventoryCase {
  const expected = requireObject(item.expected, `results[${index}].expected`);
  const override = item.cli_args_override === null
    ? null : requireStringArray(item.cli_args_override, `results[${index}].cli_args_override`);
  const debug = requireObject(item.debug, `results[${index}].debug`);
  const id = requireString(item.id, `results[${index}].id`, true);
  const category = requireString(item.category, `results[${index}].category`, true);
  const source = requireString(item.source, `results[${index}].source`, true);
  validateSource(source);
  const expectedExitCode = expected.exit_code;
  if (!Number.isSafeInteger(expectedExitCode) || Number(expectedExitCode) < 0 || Number(expectedExitCode) > 255) {
    throw new TestingWorkbenchError(`results[${index}].expected.exit_code is invalid.`);
  }
  const stdinBase64 = requireBase64(item.stdin_base64, `results[${index}].stdin_base64`);
  const timeout = item.timeout_seconds;
  if (typeof timeout !== "number" || !Number.isFinite(timeout) || timeout <= 0 || timeout > 30) {
    throw new TestingWorkbenchError(`results[${index}].timeout_seconds is invalid.`);
  }
  const debugAvailable = debug.available === true;
  if (typeof debug.available !== "boolean" || (debug.reason !== null && typeof debug.reason !== "string")) {
    throw new TestingWorkbenchError(`results[${index}].debug is invalid.`);
  }
  const expectedDebugAvailable = override === null
    && expectedExitCode === 0
    && isStrictUtf8(Buffer.from(stdinBase64, "base64"));
  if (debugAvailable !== expectedDebugAvailable) {
    throw new TestingWorkbenchError(`results[${index}].debug.available disagrees with result metadata.`);
  }
  const debugReason = override !== null
    ? "case uses cli_args_override rather than a standard source entry"
    : expectedExitCode !== 0
      ? "case expects a non-zero exit code"
      : !isStrictUtf8(Buffer.from(stdinBase64, "base64"))
        ? "case stdin is not strict UTF-8"
        : null;
  if (debug.reason !== debugReason) {
    throw new TestingWorkbenchError(`results[${index}].debug.reason disagrees with result metadata.`);
  }
  return {
    id,
    category,
    source,
    spec_refs: requireStringArray(item.spec_refs, `results[${index}].spec_refs`),
    tags: requireStringArray(item.tags, `results[${index}].tags`),
    args: requireStringArray(item.args, `results[${index}].args`),
    stdin_base64: stdinBase64,
    expected: {
      exit_code: Number(expectedExitCode),
      stdout_base64: requireBase64(expected.stdout_base64, `results[${index}].expected.stdout_base64`),
      stderr_base64: requireBase64(expected.stderr_base64, `results[${index}].expected.stderr_base64`),
    },
    timeout_seconds: timeout,
    cli_args_override: override,
    debug: { available: debug.available === true, reason: debug.reason === null ? null : String(debug.reason) },
  };
}

export function selectCaseIds(
  cases: ReadonlyMap<string, InventoryCase>,
  categoryCaseIds: ReadonlyMap<string, readonly string[]>,
  include: readonly string[] | undefined,
  exclude: readonly string[] | undefined,
): string[] {
  const expand = (itemId: string): string[] => {
    if (cases.has(itemId)) return [itemId];
    const categoryIds = categoryCaseIds.get(itemId);
    if (categoryIds) return [...categoryIds];
    throw new TestingWorkbenchError(`requested test is no longer present in the current inventory: ${itemId}`);
  };
  const selected = new Set<string>();
  const excluded = new Set<string>();
  if (include === undefined) {
    for (const id of cases.keys()) selected.add(id);
  } else {
    for (const id of include) for (const caseId of expand(id)) selected.add(caseId);
  }
  for (const id of exclude ?? []) for (const caseId of expand(id)) excluded.add(caseId);
  for (const id of excluded) selected.delete(id);
  const ordered = [...cases.keys()].filter((id) => selected.has(id));
  if (ordered.length === 0) throw new TestingWorkbenchError("the Test Explorer selection contains no LWT cases after exclusions.");
  return ordered;
}

interface CommandOutput { stdout: Buffer; stderr: Buffer; code: number | null; signal: NodeJS.Signals | null; }

function childSignalTree(child: ChildProcess): void {
  if (!child.pid || child.exitCode !== null || child.killed) return;
  if (process.platform === "win32") {
    let killer: ChildProcess;
    try {
      killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        shell: false, windowsHide: true, stdio: "ignore",
      });
      killer.once("error", () => child.kill());
    } catch {
      child.kill();
    }
    const fallback = setTimeout(() => child.kill(), 3000);
    fallback.unref();
  } else {
    try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    const fallback = setTimeout(() => {
      if (child.exitCode === null) {
        try { process.kill(-child.pid!, "SIGKILL"); } catch { child.kill("SIGKILL"); }
      }
    }, 500);
    fallback.unref();
  }
}

function runPython(
  executable: string,
  args: readonly string[],
  cwd: string,
  token: vscode.CancellationToken,
  activeProcesses: Set<ChildProcess>,
  onSpawn?: (child: ChildProcess) => void,
): Promise<CommandOutput> {
  return new Promise((resolve, reject) => {
    if (token.isCancellationRequested) {
      reject(new TestingWorkbenchError("operation cancelled"));
      return;
    }
    let child: ChildProcess;
    try {
      child = spawn(executable, [...args], {
        cwd,
        shell: false,
        windowsHide: true,
        detached: process.platform !== "win32",
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (error) {
      reject(new TestingWorkbenchError(`cannot start configured Python interpreter: ${errorMessage(error)}`));
      return;
    }
    activeProcesses.add(child);
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let settled = false;
    const cancellation = token.onCancellationRequested(() => childSignalTree(child));
    const fail = (error: unknown): void => {
      if (settled) return;
      settled = true;
      activeProcesses.delete(child);
      cancellation.dispose();
      reject(new TestingWorkbenchError(`cannot start configured Python interpreter: ${errorMessage(error)}`));
    };
    child.stdout?.on("data", (chunk: Buffer | string) => stdout.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    child.stderr?.on("data", (chunk: Buffer | string) => stderr.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    child.once("error", fail);
    child.once("close", (code, signal) => {
      if (settled) return;
      settled = true;
      activeProcesses.delete(child);
      cancellation.dispose();
      resolve({ stdout: Buffer.concat(stdout), stderr: Buffer.concat(stderr), code, signal });
    });
    onSpawn?.(child);
  });
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function decodeText(bytes: Buffer): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return `<non-UTF-8 bytes; Base64=${bytes.toString("base64")}>`;
  }
}

function sanitizeWorkspacePath(message: string, root: string): string {
  if (!root) return message;
  return message.split(root).join("<workspace>").split(root.replaceAll("\\", "/")).join("<workspace>");
}

export interface WorkbenchOutcome {
  readonly id: string;
  readonly status: string;
  readonly failureKind?: string;
  readonly message?: string;
}

export interface WorkbenchApi {
  readonly controller: vscode.TestController;
  refresh(): Promise<void>;
  runIds(ids: readonly string[], options?: {
    readonly exclude?: readonly string[];
    readonly token?: vscode.CancellationToken;
    readonly onRunnerStarted?: () => void;
  }): Promise<readonly WorkbenchOutcome[]>;
  debugCase(id: string, token?: vscode.CancellationToken): Promise<WorkbenchOutcome>;
  getCaseItem(id: string): vscode.TestItem | undefined;
  snapshot(): { readonly cases: number; readonly categories: number };
  diagnostic(): string | undefined;
  stop(): Promise<void>;
}

interface DebugTemp {
  readonly directory: string;
  readonly cancellation: vscode.Disposable;
  readonly terminated: Promise<void>;
  readonly finish: () => void;
}

export function createTestingWorkbench(
  api: typeof import("vscode"),
  context: vscode.ExtensionContext,
  workspaceFolders: () => readonly vscode.WorkspaceFolder[],
  pythonPath: () => string,
  output: vscode.OutputChannel,
): WorkbenchApi {
  const controller = api.tests.createTestController("lwt.blackbox", "LWT Black-box Tests");
  context.subscriptions.push(controller);
  const debugTag = new api.TestTag("lwt-debuggable");
  const casesById = new Map<string, InventoryCase>();
  const testItemsByCaseId = new Map<string, vscode.TestItem>();
  const itemIdToCaseId = new Map<string, string>();
  const categoryCaseIds = new Map<string, readonly string[]>();
  const categoryItems = new Map<string, vscode.TestItem>();
  const activeProcesses = new Set<ChildProcess>();
  const activeRunTokens = new Set<vscode.CancellationTokenSource>();
  const debugTemps = new Map<string, DebugTemp>();
  const watcherDisposables: vscode.Disposable[] = [];
  let inventory: TestInventory | undefined;
  let currentRoot: vscode.WorkspaceFolder | undefined;
  let discoveryGeneration = 0;
  let refreshPromise: Promise<void> | undefined;
  let discoveryCancellation: vscode.CancellationTokenSource | undefined;
  let refreshTimer: NodeJS.Timeout | undefined;
  let discoveryError: string | undefined;
  let stopped = false;

  const testRunProfile = controller.createRunProfile(
    "Run LWT Black-box Tests",
    api.TestRunProfileKind.Run,
    async (request, token) => { await executeRequest(request, token, false); },
    true,
  );
  const debugRunProfile = controller.createRunProfile(
    "Debug Applicable LWT Case",
    api.TestRunProfileKind.Debug,
    async (request, token) => { await executeRequest(request, token, true); },
    false,
    debugTag,
  );
  context.subscriptions.push(testRunProfile, debugRunProfile);

  controller.resolveHandler = async () => { await refresh(); };
  const terminateSubscription = api.debug.onDidTerminateDebugSession((session) => cleanupDebug(session.name));
  context.subscriptions.push(terminateSubscription);

  function clearWatchers(): void {
    while (watcherDisposables.length) watcherDisposables.pop()?.dispose();
  }

  function currentWorkspace(): { folder?: vscode.WorkspaceFolder; error?: string } {
    const folders = workspaceFolders();
    if (folders.length !== 1) {
      return { error: folders.length === 0
        ? "Open one LWT repository folder to discover black-box tests."
        : "LWT Test Explorer requires a single-root workspace; close extra workspace folders." };
    }
    return { folder: folders[0] };
  }

  function publishError(message: string): void {
    discoveryError = message;
    inventory = undefined;
    casesById.clear();
    testItemsByCaseId.clear();
    itemIdToCaseId.clear();
    categoryCaseIds.clear();
    categoryItems.clear();
    const item = controller.createTestItem("workspace-error", "LWT test discovery unavailable");
    item.error = message;
    controller.items.replace([item]);
    output.appendLine(`Test Explorer: ${message}`);
  }

  function installWatchers(folder: vscode.WorkspaceFolder): void {
    if (currentRoot?.uri.toString() === folder.uri.toString() && watcherDisposables.length) return;
    clearWatchers();
    currentRoot = folder;
    for (const extension of ["json", "lwt"]) {
      const watcher = api.workspace.createFileSystemWatcher(new api.RelativePattern(folder, `tests/cases/**/*.${extension}`));
      const changed = (uri: vscode.Uri): void => {
        if (uri.fsPath.split(path.sep).includes("fixtures")) return;
        controller.invalidateTestResults();
        if (refreshTimer) clearTimeout(refreshTimer);
        refreshTimer = setTimeout(() => { void refresh(); }, 120);
      };
      watcherDisposables.push(watcher, watcher.onDidCreate(changed), watcher.onDidChange(changed), watcher.onDidDelete(changed));
    }
  }

  function refresh(): Promise<void> {
    if (stopped) return Promise.resolve();
    discoveryGeneration += 1;
    discoveryCancellation?.cancel();
    if (refreshTimer) {
      clearTimeout(refreshTimer);
      refreshTimer = undefined;
    }
    if (!refreshPromise) {
      refreshPromise = (async () => {
        let processedGeneration = 0;
        while (!stopped && processedGeneration !== discoveryGeneration) {
          processedGeneration = discoveryGeneration;
          await refreshOnce(processedGeneration);
        }
      })().finally(() => { refreshPromise = undefined; });
    }
    return refreshPromise;
  }

  async function refreshOnce(generation: number): Promise<void> {
    if (stopped) return;
    discoveryCancellation?.cancel();
    discoveryCancellation?.dispose();
    const cancellation = new api.CancellationTokenSource();
    discoveryCancellation = cancellation;
    const current = currentWorkspace();
    if (!current.folder) {
      clearWatchers();
      currentRoot = undefined;
      publishError(current.error ?? "No workspace is open.");
      if (discoveryCancellation === cancellation) discoveryCancellation = undefined;
      cancellation.dispose();
      return;
    }
    const root = current.folder.uri.fsPath;
    if (!isLwtRepository(root)) {
      clearWatchers();
      currentRoot = undefined;
      publishError("This workspace does not contain tools/run_tests.py, lwt/__main__.py and tests/cases; open the LWT repository root.");
      if (discoveryCancellation === cancellation) discoveryCancellation = undefined;
      cancellation.dispose();
      return;
    }
    installWatchers(current.folder);
    try {
      const command = await runPython(
        pythonPath(),
        [path.join("tools", "run_tests.py"), "--list-json"],
        root,
        cancellation.token,
        activeProcesses,
      );
      if (generation !== discoveryGeneration || stopped) return;
      if (command.code !== 0) {
        const details = sanitizeWorkspacePath(decodeText(command.stderr).trim(), root);
        throw new TestingWorkbenchError(details || `runner exited with code ${String(command.code)}.`);
      }
      let parsed: unknown;
      try { parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(command.stdout)); }
      catch (error) { throw new TestingWorkbenchError(`runner returned invalid inventory JSON: ${errorMessage(error)}`); }
      const next = parseInventory(parsed);
      for (const testCase of next.cases) {
        const sourcePath = path.resolve(root, ...testCase.source.split("/"));
        const relative = path.relative(root, sourcePath);
        if (relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative) || !fs.existsSync(sourcePath)) {
          throw new TestingWorkbenchError(`case source is missing or escapes the workspace: ${testCase.source}`);
        }
      }
      if (generation !== discoveryGeneration || stopped) return;
      publishInventory(next, current.folder);
    } catch (error) {
      if (generation !== discoveryGeneration || stopped || cancellation.token.isCancellationRequested) return;
      publishError(sanitizeWorkspacePath(errorMessage(error), root));
    } finally {
      if (discoveryCancellation === cancellation) {
        discoveryCancellation = undefined;
        cancellation.dispose();
      }
    }
  }

  function publishInventory(next: TestInventory, folder: vscode.WorkspaceFolder): void {
    discoveryError = undefined;
    inventory = next;
    casesById.clear();
    testItemsByCaseId.clear();
    itemIdToCaseId.clear();
    categoryCaseIds.clear();
    categoryItems.clear();
    const roots: vscode.TestItem[] = [];
    for (const category of next.categories) {
      const categoryItem = controller.createTestItem(`category:${category.name}`, category.name);
      categoryItems.set(categoryItem.id, categoryItem);
      categoryCaseIds.set(categoryItem.id, category.case_ids.map((id) => `case:${id}`));
      for (const id of category.case_ids) {
        const testCase = next.cases.find((item) => item.id === id);
        if (!testCase) throw new TestingWorkbenchError(`inventory category references missing case ${id}.`);
        const uri = api.Uri.file(path.resolve(folder.uri.fsPath, ...testCase.source.split("/")));
        const item = controller.createTestItem(`case:${testCase.id}`, testCase.id, uri);
        item.description = `spec ${testCase.spec_refs.join(", ")}${testCase.tags.length ? ` · ${testCase.tags.join(", ")}` : ""}${testCase.debug.available ? "" : ` · Debug unavailable: ${testCase.debug.reason}`}`;
        item.tags = [...testCase.tags.map((tag) => new api.TestTag(tag)), ...(testCase.debug.available ? [debugTag] : [])];
        categoryItem.children.add(item);
        casesById.set(testCase.id, testCase);
        testItemsByCaseId.set(testCase.id, item);
        itemIdToCaseId.set(item.id, testCase.id);
      }
      roots.push(categoryItem);
    }
    controller.items.replace(roots);
    output.appendLine(`Test Explorer discovered ${next.case_count} cases in ${next.categories.length} categories.`);
  }

  function caseIdsForRequest(request: vscode.TestRunRequest): string[] {
    const selectedItemIds = selectCaseIds(
      new Map([...itemIdToCaseId.keys()].map((itemId) => [itemId, casesById.get(itemIdToCaseId.get(itemId)!)!])),
      new Map([...categoryCaseIds.entries()].map(([categoryId, ids]) => [categoryId, ids])),
      request.include?.map((item) => item.id),
      request.exclude?.map((item) => item.id),
    );
    return selectedItemIds.map((itemId) => itemIdToCaseId.get(itemId)!);
  }

  async function executeRequest(
    request: vscode.TestRunRequest,
    token: vscode.CancellationToken,
    debug: boolean,
    onRunnerStarted?: () => void,
  ): Promise<readonly WorkbenchOutcome[]> {
    const run = controller.createTestRun(request);
    const effectiveCancellation = new api.CancellationTokenSource();
    const forwardCancellation = token.onCancellationRequested(() => effectiveCancellation.cancel());
    activeRunTokens.add(effectiveCancellation);
    const runToken = effectiveCancellation.token;
    const outcomes: WorkbenchOutcome[] = [];
    let selectedCaseItems: vscode.TestItem[] = [];
    try {
      if (!inventory) await refresh();
      if (!inventory) throw new TestingWorkbenchError("Test inventory is unavailable. Read the discovery error shown in Test Explorer.");
      const rootAtStart = currentRoot?.uri.fsPath;
      if (!rootAtStart) throw new TestingWorkbenchError("LWT workspace is no longer available.");
      const selectedIds = caseIdsForRequest(request);
      if (debug && selectedIds.length !== 1) throw new TestingWorkbenchError("Debug profile accepts exactly one selected case.");
      const selected = selectedIds.map((id) => casesById.get(id)!).filter(Boolean);
      selectedCaseItems = selected.map((testCase) => testItemsByCaseId.get(testCase.id)!).filter(Boolean);
      if (debug) {
        const testCase = selected[0];
        if (!testCase.debug.available) throw new TestingWorkbenchError(testCase.debug.reason ?? "This case cannot be debugged faithfully.");
        const outcome = await startDebugCase(testCase, run, runToken);
        outcomes.push(outcome);
        return outcomes;
      }

      for (const testCase of selected) {
        const item = testItemsByCaseId.get(testCase.id)!;
        run.enqueued(item);
        if (!runToken.isCancellationRequested) run.started(item);
      }
      const queued = selected.filter((item) => !outcomes.some((outcome) => outcome.id === item.id));
      if (queued.length === 0) return outcomes;
      if (runToken.isCancellationRequested) {
        for (const testCase of queued) {
          run.skipped(testItemsByCaseId.get(testCase.id)!);
          outcomes.push({ id: testCase.id, status: "not_executed" });
        }
        return outcomes;
      }
      let command: CommandOutput;
      try {
        const args = [path.join("tools", "run_tests.py"), "--format", "json"];
        for (const testCase of queued) args.push("--case", testCase.id);
        command = await runPython(pythonPath(), args, rootAtStart, runToken, activeProcesses, onRunnerStarted);
      } catch (error) {
        if (runToken.isCancellationRequested) {
          for (const testCase of queued) {
            run.skipped(testItemsByCaseId.get(testCase.id)!);
            outcomes.push({ id: testCase.id, status: "cancelled" });
          }
          return outcomes;
        }
        const message = sanitizeWorkspacePath(errorMessage(error), rootAtStart);
        for (const testCase of queued) {
          const item = testItemsByCaseId.get(testCase.id)!;
          run.errored(item, new api.TestMessage(message));
          outcomes.push({ id: testCase.id, status: "start_failed", message });
        }
        return outcomes;
      }
      if (runToken.isCancellationRequested) {
        for (const testCase of queued) {
          run.skipped(testItemsByCaseId.get(testCase.id)!);
          outcomes.push({ id: testCase.id, status: "cancelled" });
        }
        return outcomes;
      }
      let payload: RunPayload;
      try {
        const raw = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(command.stdout)) as unknown;
        payload = parseRunPayload(raw);
      } catch (error) {
        const detail = sanitizeWorkspacePath(decodeText(command.stderr).trim(), rootAtStart);
        const message = detail || `runner returned invalid JSON: ${errorMessage(error)}`;
        for (const testCase of queued) {
          const item = testItemsByCaseId.get(testCase.id)!;
          run.errored(item, new api.TestMessage(message));
          outcomes.push({ id: testCase.id, status: "runner_error", message });
        }
        return outcomes;
      }
      const expectedRunnerExitCode = payload.status === "cancelled"
        ? 130
        : (payload.summary.failed > 0 || payload.summary.timeout > 0 || payload.summary.start_failed > 0 ? 1 : 0);
      if (command.code !== expectedRunnerExitCode) {
        throw new TestingWorkbenchError(`runner exit code ${String(command.code)} disagrees with result status (expected ${expectedRunnerExitCode}).`);
      }
      const resultsById = new Map(payload.results.map((result) => [result.id, result]));
      if (resultsById.size !== queued.length || queued.some((item) => !resultsById.has(item.id))) {
        throw new TestingWorkbenchError("runner result IDs do not match the selected Test Explorer cases.");
      }
      for (const testCase of queued) {
        const result = resultsById.get(testCase.id)!;
        if (result.source !== testCase.source
            || result.category !== testCase.category
            || JSON.stringify(result.spec_refs) !== JSON.stringify(testCase.spec_refs)
            || JSON.stringify(result.tags) !== JSON.stringify(testCase.tags)
            || result.expected.exit_code !== testCase.expected.exit_code
            || result.expected.stdout_base64 !== testCase.expected.stdout_base64
            || result.expected.stderr_base64 !== testCase.expected.stderr_base64
            || result.stdin_base64 !== testCase.stdin_base64
            || JSON.stringify(result.args) !== JSON.stringify(testCase.args)
            || result.timeout_seconds !== testCase.timeout_seconds
            || JSON.stringify(result.cli_args_override) !== JSON.stringify(testCase.cli_args_override)
            || result.debug.available !== testCase.debug.available
            || result.debug.reason !== testCase.debug.reason) {
          throw new TestingWorkbenchError(`inventory for ${testCase.id} changed while the run was starting; refresh and retry.`);
        }
        const item = testItemsByCaseId.get(testCase.id)!;
        const elapsed = Math.round(result.duration_seconds * 1000);
        const outcome: WorkbenchOutcome = { id: result.id, status: result.status, failureKind: result.failure_kind ?? undefined };
        outcomes.push(outcome);
        if (result.status === "passed") {
          run.passed(item, elapsed);
        } else if (result.status === "failed" && result.failure_kind === "runtime_error") {
          run.errored(item, failureMessage(api, result), elapsed);
        } else if (result.status === "failed") {
          run.failed(item, failureMessage(api, result), elapsed);
        } else if (result.status === "timeout" || result.status === "start_failed") {
          run.errored(item, failureMessage(api, result), elapsed);
        } else {
          run.skipped(item);
        }
        run.appendOutput(formatCaseOutput(result), undefined, item);
      }
      return outcomes;
    } catch (error) {
      const message = sanitizeWorkspacePath(errorMessage(error), currentRoot?.uri.fsPath ?? "");
      output.appendLine(`Test Explorer request failed: ${message}`);
      void api.window.showErrorMessage(message);
      for (const item of selectedCaseItems) {
        const caseId = itemIdToCaseId.get(item.id);
        if (!caseId || outcomes.some((outcome) => outcome.id === caseId)) continue;
        run.errored(item, new api.TestMessage(message));
        outcomes.push({ id: caseId, status: "error", message });
      }
      if (outcomes.length === 0) outcomes.push({ id: request.include?.[0]?.id ?? "selection", status: "error", message });
      return outcomes;
    } finally {
      run.end();
      forwardCancellation.dispose();
      activeRunTokens.delete(effectiveCancellation);
      effectiveCancellation.dispose();
    }
  }

  function failureMessage(apiValue: typeof import("vscode"), result: RunCaseResult): vscode.TestMessage {
    const expectedOut = decodeText(Buffer.from(result.expected.stdout_base64, "base64"));
    const actualOut = decodeText(Buffer.from(result.actual.stdout_base64, "base64"));
    const expectedErr = decodeText(Buffer.from(result.expected.stderr_base64, "base64"));
    const actualErr = decodeText(Buffer.from(result.actual.stderr_base64, "base64"));
    const summary = `status=${result.status}; expected exit=${result.expected.exit_code}; actual exit=${String(result.actual.exit_code)}\n${result.differences.join("\n")}`;
    const message = apiValue.TestMessage.diff(summary, `stdout:\n${expectedOut}\nstderr:\n${expectedErr}`, `stdout:\n${actualOut}\nstderr:\n${actualErr}`);
    return message;
  }

  function formatCaseOutput(result: RunCaseResult): string {
    const stdout = decodeText(Buffer.from(result.actual.stdout_base64, "base64"));
    const stderr = decodeText(Buffer.from(result.actual.stderr_base64, "base64"));
    return `Case ${result.id}: ${result.status}; exit=${String(result.actual.exit_code)}; duration=${result.duration_seconds.toFixed(3)}s\r\nstdout:\r\n${stdout}\r\nstderr:\r\n${stderr}\r\n`;
  }

  async function startDebugCase(
    testCase: InventoryCase,
    run: vscode.TestRun,
    token: vscode.CancellationToken,
  ): Promise<WorkbenchOutcome> {
    const item = testItemsByCaseId.get(testCase.id)!;
    run.enqueued(item);
    run.started(item);
    if (token.isCancellationRequested) {
      run.skipped(item);
      return { id: testCase.id, status: "cancelled" };
    }
    let stdin: Buffer;
    try {
      stdin = Buffer.from(testCase.stdin_base64, "base64");
      new TextDecoder("utf-8", { fatal: true }).decode(stdin);
    } catch {
      const message = "Debug requires stdin bytes that decode as strict UTF-8.";
      run.errored(item, new api.TestMessage(message));
      return { id: testCase.id, status: "unsupported", message };
    }
    const folder = currentRoot;
    if (!folder) {
      const message = "LWT workspace is no longer available.";
      run.errored(item, new api.TestMessage(message));
      return { id: testCase.id, status: "error", message };
    }
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), "lwt-test-debug-"));
    const stdinFile = path.join(directory, "stdin.txt");
    const sessionName = `LWT Test Debug ${testCase.id} ${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const cleanup = (): void => cleanupDebug(sessionName);
    let finishDebug!: () => void;
    const terminated = new Promise<void>((resolve) => { finishDebug = resolve; });
    const cancellation = token.onCancellationRequested(() => {
      const active = api.debug.activeDebugSession;
      if (active?.name === sessionName) void api.debug.stopDebugging(active);
      else cleanup();
    });
    debugTemps.set(sessionName, { directory, cancellation, terminated, finish: finishDebug });
    try {
      fs.writeFileSync(stdinFile, stdin);
      if (token.isCancellationRequested) {
        cleanup();
        run.skipped(item);
        return { id: testCase.id, status: "cancelled" };
      }
      const started = await api.debug.startDebugging(folder, {
        type: "lwt",
        request: "launch",
        name: sessionName,
        program: path.resolve(folder.uri.fsPath, ...testCase.source.split("/")),
        python: pythonPath(),
        cwd: folder.uri.fsPath,
        args: [...testCase.args],
        stdinFile,
      });
      if (!started) {
        cleanup();
        const message = "VS Code did not start the native LWT DAP session.";
        run.errored(item, new api.TestMessage(message));
        return { id: testCase.id, status: "start_failed", message };
      }
      if (token.isCancellationRequested) {
        const active = api.debug.activeDebugSession;
        if (active?.name === sessionName) await api.debug.stopDebugging(active);
      }
      await terminated;
      run.appendOutput(`Debug session ended for ${testCase.id}; the black-box oracle was not run, so this is not a passing test.\r\n`, undefined, item);
      run.skipped(item);
      return { id: testCase.id, status: token.isCancellationRequested ? "cancelled_unverified" : "debug_completed_unverified" };
    } catch (error) {
      cleanup();
      const message = errorMessage(error);
      run.errored(item, new api.TestMessage(message));
      return { id: testCase.id, status: "start_failed", message };
    }
  }

  function cleanupDebug(sessionName: string): void {
    const temp = debugTemps.get(sessionName);
    if (!temp) return;
    debugTemps.delete(sessionName);
    temp.cancellation.dispose();
    fs.rmSync(temp.directory, { recursive: true, force: true });
    temp.finish();
  }

  async function runIds(ids: readonly string[], options: {
    readonly exclude?: readonly string[];
    readonly token?: vscode.CancellationToken;
    readonly onRunnerStarted?: () => void;
  } = {}): Promise<readonly WorkbenchOutcome[]> {
    if (!inventory) await refresh();
    const items = ids.map((id) => testItemsByCaseId.get(id) ?? categoryItems.get(id) ?? categoryItems.get(`category:${id}`) ?? testItemsByCaseId.get(id.replace(/^case:/, "")));
    if (items.some((item) => !item)) throw new TestingWorkbenchError("one or more requested Test Explorer items are unknown.");
    const tokenSource = options.token ? undefined : new api.CancellationTokenSource();
    const token = options.token ?? tokenSource!.token;
    try {
      const request = new api.TestRunRequest(items as vscode.TestItem[], (options.exclude ?? []).map((id) => testItemsByCaseId.get(id) ?? categoryItems.get(id) ?? categoryItems.get(`category:${id}`)).filter((item): item is vscode.TestItem => Boolean(item)), testRunProfile);
      return await executeRequest(request, token, false, options.onRunnerStarted);
    } finally {
      tokenSource?.dispose();
    }
  }

  async function debugCase(id: string, token?: vscode.CancellationToken): Promise<WorkbenchOutcome> {
    if (!inventory) await refresh();
    const testCase = casesById.get(id);
    if (!testCase) throw new TestingWorkbenchError(`unknown LWT case ID: ${id}`);
    if (!testCase.debug.available) {
      const message = testCase.debug.reason ?? "This case cannot be debugged faithfully.";
      const item = testItemsByCaseId.get(id)!;
      const request = new api.TestRunRequest([item], [], debugRunProfile);
      const run = controller.createTestRun(request);
      run.enqueued(item);
      run.started(item);
      run.errored(item, new api.TestMessage(message));
      run.end();
      return { id, status: "unsupported", message };
    }
    const tokenSource = token ? undefined : new api.CancellationTokenSource();
    const actualToken = token ?? tokenSource!.token;
    try {
      const item = testItemsByCaseId.get(id)!;
      const request = new api.TestRunRequest([item], [], debugRunProfile);
      const run = controller.createTestRun(request);
      try { return await startDebugCase(testCase, run, actualToken); }
      finally { run.end(); }
    } finally {
      tokenSource?.dispose();
    }
  }

  async function stop(): Promise<void> {
    stopped = true;
    discoveryGeneration += 1;
    discoveryCancellation?.cancel();
    discoveryCancellation?.dispose();
    for (const cancellation of activeRunTokens) cancellation.cancel();
    if (refreshTimer) clearTimeout(refreshTimer);
    clearWatchers();
    await Promise.all([...activeProcesses].map((child) => new Promise<void>((resolve) => {
      if (child.exitCode !== null || child.pid === undefined) { resolve(); return; }
      child.once("close", () => resolve());
      childSignalTree(child);
      const timeout = setTimeout(() => { child.kill(); resolve(); }, 3500);
      timeout.unref();
    })));
    for (const session of api.debug.activeDebugSession ? [api.debug.activeDebugSession] : []) {
      if (session.name.startsWith("LWT Test Debug ")) await Promise.resolve(api.debug.stopDebugging(session)).catch(() => false);
    }
    for (const name of [...debugTemps.keys()]) cleanupDebug(name);
  }

  context.subscriptions.push({ dispose: () => { void stop(); } });
  void refresh();
  return {
    controller,
    refresh,
    runIds,
    debugCase,
    getCaseItem: (id) => testItemsByCaseId.get(id),
    snapshot: () => ({ cases: inventory?.case_count ?? 0, categories: inventory?.categories.length ?? 0 }),
    diagnostic: () => discoveryError,
    stop,
  };
}
