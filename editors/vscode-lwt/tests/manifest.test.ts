import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test } from "node:test";

const extensionRoot = path.resolve(__dirname, "..", "..");
const repositoryRoot = path.resolve(extensionRoot, "..", "..");
const readJson = <T>(relativePath: string): T => JSON.parse(fs.readFileSync(path.join(extensionRoot, relativePath), "utf8")) as T;

interface PackageManifest {
  main: string;
  engines: { vscode: string };
  activationEvents: string[];
  contributes: {
    languages: Array<{ id: string; extensions: string[]; configuration: string }>;
    grammars: Array<{ language: string; scopeName: string; path: string }>;
    snippets: Array<{ language: string; path: string }>;
    commands: Array<{ command: string; title: string }>;
    configuration: { properties: Record<string, { type: string; default: unknown }> };
  };
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
}

test("manifest, language id, commands, configuration and launcher are consistent", () => {
  const manifest = readJson<PackageManifest>("package.json");
  const lock = readJson<{ packages: Record<string, { dependencies?: Record<string, string>; devDependencies?: Record<string, string> }> }>("package-lock.json");
  assert.equal(manifest.engines.vscode, "^1.144.0");
  assert.equal(manifest.main, "./out/src/extension.js");
  assert.equal(manifest.contributes.languages.length, 1);
  assert.equal(manifest.contributes.languages[0].id, "lwt");
  assert.deepEqual(manifest.contributes.languages[0].extensions, [".lwt"]);
  assert.equal(manifest.contributes.grammars[0].language, "lwt");
  assert.equal(manifest.contributes.snippets[0].language, "lwt");
  assert.deepEqual(manifest.contributes.commands.map((item) => item.command), [
    "lwt.runCurrentFile", "lwt.checkCurrentFile", "lwt.debugCurrentFile",
  ]);
  for (const command of manifest.contributes.commands) {
    assert.ok(manifest.activationEvents.includes(`onCommand:${command.command}`));
  }
  for (const name of ["lwt.pythonPath", "lwt.workingDirectory", "lwt.programArgs", "lwt.programStdin"]) {
    assert.ok(name in manifest.contributes.configuration.properties, `missing ${name}`);
  }
  assert.deepEqual(lock.packages[""].dependencies, manifest.dependencies);
  assert.deepEqual(lock.packages[""].devDependencies, manifest.devDependencies);
  const source = fs.readFileSync(path.join(extensionRoot, "src", "extension.ts"), "utf8");
  assert.match(source, /\["-m", "lwt\.lsp_server"\]/);
  assert.match(source, /new vscode\.ProcessExecution\(spec\.executable, \[\.\.\.spec\.args\], \{ cwd: spec\.cwd \}\)/);
  assert.doesNotMatch(source, /shell\s*:\s*true|child_process|spawn\s*\(/);
});

test("grammar/configuration/snippets parse and grammar keywords track the real lexer", () => {
  const grammar = readJson<{ scopeName: string; patterns: Array<{ name: string; match: string }> }>("syntaxes/lwt.tmLanguage.json");
  const config = readJson<{ comments: { lineComment: string }; brackets: string[][]; autoClosingPairs: Array<{ open: string; close: string }> }>("language-configuration.json");
  const snippets = readJson<Record<string, { prefix: string; body: string[] }>>("snippets/lwt.json");
  assert.equal(grammar.scopeName, "source.lwt");
  assert.equal(config.comments.lineComment, "#");
  assert.deepEqual(config.brackets, [["{", "}"], ["[", "]"], ["(", ")"]]);
  assert.ok(config.autoClosingPairs.some(({ open, close }) => open === "\"" && close === "\""));
  assert.ok(Object.values(snippets).length >= 5);

  const lexerSource = fs.readFileSync(path.join(repositoryRoot, "lwt", "lexer.py"), "utf8");
  const keywordBlock = lexerSource.match(/_KEYWORDS:\s*dict\[str, TokenKind\]\s*=\s*\{([\s\S]*?)\n\}/);
  assert.ok(keywordBlock, "could not locate the lexer keyword table");
  const lexerKeywords = [...keywordBlock[1].matchAll(/^\s*"([A-Za-z_]+)": TokenKind\./gm)].map((match) => match[1]);
  const keywordPattern = grammar.patterns.find((pattern) => pattern.name === "keyword.control.lwt");
  assert.ok(keywordPattern);
  const keywordMatch = keywordPattern.match.match(/\\b\(\?:([^)]+)\)\\b/);
  assert.ok(keywordMatch, "could not read the grammar keyword pattern");
  const grammarKeywords = keywordMatch[1].split("|").sort();
  assert.deepEqual(grammarKeywords, lexerKeywords.filter((word) => !["true", "false", "null"].includes(word)).sort());

  const stringRule = grammar.patterns.find((pattern) => pattern.name === "string.quoted.double.lwt");
  const commentRule = grammar.patterns.find((pattern) => pattern.name === "comment.line.number-sign.lwt");
  const integerRule = grammar.patterns.find((pattern) => pattern.name === "constant.numeric.integer.lwt");
  assert.ok(stringRule && commentRule && integerRule);
  assert.ok(new RegExp(stringRule.match).test('"escaped\\n text"'));
  assert.ok(new RegExp(commentRule.match).test("# comment"));
  assert.ok(new RegExp(integerRule.match).test("2048"));
});

test("snippet templates expand to syntax accepted by the public non-executing checker", () => {
  const snippets = readJson<Record<string, { body: string[] }>>("snippets/lwt.json");
  const expanded = Object.values(snippets).map((snippet) => snippet.body.map((line) => line
    .replaceAll("${1:name}", "demo")
    .replaceAll("${1:Name}", "Item")
    .replaceAll("${1:condition}", "true")
    .replaceAll("${1:item}", "item")
    .replaceAll("${2:parameters}", "")
    .replaceAll("${2:field}", "value")
    .replaceAll("${2:items}", "[1]")
    .replaceAll("${3:body}", "emit 1;")
    .replaceAll("${3:value}", "1")));
  const source = expanded.flat().map((line) => line.replace(/^\s*\$\{\d+:body\}\s*$/, "emit 1;")).join("\n");
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "lwt vscode snippets "));
  try {
    const file = path.join(directory, "snippets.lwt");
    fs.writeFileSync(file, source, "utf8");
    const result = spawnSync(process.env.LWT_TEST_PYTHON || "python", ["-m", "lwt", "--check", file], {
      cwd: repositoryRoot,
      encoding: "utf8",
      timeout: 15000,
      shell: false,
      windowsHide: true,
    });
    assert.equal(result.status, 0, `${result.stderr}\n${result.stdout}\n${source}`);
    assert.match(result.stdout, /Check passed:/);
    assert.doesNotMatch(result.stdout, /emit 1/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
