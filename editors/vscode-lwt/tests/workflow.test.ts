import assert from "node:assert/strict";
import { spawnSync, SpawnSyncReturns } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test } from "node:test";
import {
  buildDapAdapterSpec,
  buildDapLaunchConfiguration,
  buildLaunchSpec,
} from "../src/workflow";

const repositoryRoot = path.resolve(__dirname, "..", "..", "..", "..");
const python = process.env.LWT_TEST_PYTHON || "python";

function temporaryDirectory(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "lwt vscode λ space "));
}

function runPython(args: string[], options: { cwd: string; input?: string }): SpawnSyncReturns<string> {
  return spawnSync(python, args, {
    cwd: options.cwd,
    input: options.input,
    encoding: "utf8",
    timeout: 15000,
    shell: false,
    windowsHide: true,
  }) as SpawnSyncReturns<string>;
}

test("run launch uses argv and preserves -- arguments in Unicode paths", () => {
  const directory = temporaryDirectory();
  try {
    const source = path.join(directory, "任务 with spaces.lwt");
    fs.writeFileSync(source, "emit args();\n", "utf8");
    const spec = buildLaunchSpec("run", "C:\\Program Files\\Python\\python.exe", repositoryRoot, source, {
      programArgs: ["one value", "--looks-like-an-option", "雪"],
    });
    assert.equal(spec.executable, "C:\\Program Files\\Python\\python.exe");
    assert.deepEqual(spec.args, ["-m", "lwt", source, "--", "one value", "--looks-like-an-option", "雪"]);
    assert.equal(spec.cwd, repositoryRoot);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("check stays non-executing and does not inherit program arguments", () => {
  const directory = temporaryDirectory();
  try {
    const source = path.join(directory, "静态 check.lwt");
    fs.writeFileSync(source, 'emit "must not execute";\n', "utf8");
    const spec = buildLaunchSpec("check", python, repositoryRoot, source, { programArgs: ["unused"] });
    assert.deepEqual(spec.args, ["-m", "lwt", "--check", source]);
    const result = runPython([...spec.args], { cwd: spec.cwd });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /^Check passed: 1 source file\(s\)\.\r?\n$/);
    assert.doesNotMatch(result.stdout, /must not execute/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("ordinary CLI launch reads stdin and forwards Unicode program arguments", () => {
  const directory = temporaryDirectory();
  try {
    const source = path.join(directory, "echo input λ.lwt");
    fs.writeFileSync(source, "let value = input();\nemit value;\nemit args();\n", "utf8");
    const spec = buildLaunchSpec("run", python, repositoryRoot, source, {
      programArgs: ["two words", "参数"],
    });
    const result = runPython([...spec.args], { cwd: spec.cwd, input: "typed line\n" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'typed line\n["two words", "参数"]\n');
    assert.equal(result.stderr, "");
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("debug launch separates program stdin and places program arguments after --", () => {
  const directory = temporaryDirectory();
  try {
    const source = path.join(directory, "debug target.lwt");
    const input = path.join(directory, "程序 input.txt");
    fs.writeFileSync(source, "emit args();\n", "utf8");
    fs.writeFileSync(input, "program data\n", "utf8");
    const spec = buildLaunchSpec("debug", python, repositoryRoot, source, {
      programStdin: input,
      programArgs: ["two words", "--program-stdin", "雪"],
    });
    assert.deepEqual(spec.args, [
      "-m", "lwt.debugger", "--program-stdin", input, source, "--",
      "two words", "--program-stdin", "雪",
    ]);
    assert.equal(spec.cwd, repositoryRoot);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("working directory resolves relative to workspace and missing paths fail clearly", () => {
  const directory = temporaryDirectory();
  try {
    const subdirectory = path.join(directory, "data with spaces");
    fs.mkdirSync(subdirectory);
    const source = path.join(directory, "program.lwt");
    fs.writeFileSync(source, "emit 1;\n", "utf8");
    assert.equal(
      buildLaunchSpec("run", python, directory, source, { workingDirectory: "data with spaces" }).cwd,
      subdirectory,
    );
    assert.throws(
      () => buildLaunchSpec("run", python, directory, source, { workingDirectory: "missing" }),
      /working directory does not exist/,
    );
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("debug CLI runs the checked-in S30 session with separate program stdin and output", () => {
  const result = runPython([
    "-m", "lwt.debugger",
    "--commands", "examples/debugger/session.txt",
    "--program-stdin", "examples/debugger/program-input.txt",
    "examples/debugger/main.lwt",
  ], { cwd: repositoryRoot });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, "demo:5\n");
  assert.match(result.stderr, /Breakpoint/);
  assert.doesNotMatch(result.stdout, /Breakpoint|locals|Paused/);
});

test("native DAP adapter uses an argv list and starts from the workspace root", () => {
  const directory = temporaryDirectory();
  try {
    const spec = buildDapAdapterSpec("C:\\Program Files\\Python\\python.exe", directory);
    assert.equal(spec.executable, "C:\\Program Files\\Python\\python.exe");
    assert.deepEqual(spec.args, ["-m", "lwt.dap_server"]);
    assert.equal(spec.cwd, directory);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("DAP launch configuration resolves Unicode paths, cwd, args and stdin separately", () => {
  const directory = temporaryDirectory();
  try {
    const cwd = path.join(directory, "运行目录 λ");
    fs.mkdirSync(cwd);
    const source = path.join(directory, "程序 with spaces.lwt");
    const stdin = path.join(cwd, "输入 数据.txt");
    fs.writeFileSync(source, "emit args();\n", "utf8");
    fs.writeFileSync(stdin, "line\n", "utf8");
    const config = buildDapLaunchConfiguration(source, directory, {
      pythonPath: "python with spaces",
      workingDirectory: "运行目录 λ",
      programArgs: ["one value", "参数"],
      programStdin: "输入 数据.txt",
    });
    assert.deepEqual(config, {
      type: "lwt",
      request: "launch",
      name: "LWT: Debug Current File",
      program: source,
      python: "python with spaces",
      cwd,
      args: ["one value", "参数"],
      stdinFile: stdin,
    });
    assert.throws(
      () => buildDapLaunchConfiguration(source, directory, { programArgs: "not an array" }),
      /array of strings/,
    );
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
