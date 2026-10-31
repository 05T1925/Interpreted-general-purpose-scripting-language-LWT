import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { spawnSync } from "node:child_process";
import { runTests } from "@vscode/test-electron";

function locateCodeExecutable(): string | undefined {
  const configured = process.env.VSCODE_EXECUTABLE_PATH;
  if (configured && fs.existsSync(configured)) return configured;
  if (configured) throw new Error(`VSCODE_EXECUTABLE_PATH does not exist: ${configured}`);
  if (process.platform === "win32") {
    const commandCandidates = [process.env.VSCODE_COMMAND_PATH].filter((value): value is string => Boolean(value));
    const discovered = spawnSync("where.exe", ["code"], { encoding: "utf8", shell: false, windowsHide: true });
    if (discovered.status === 0) commandCandidates.push(...discovered.stdout.split(/\r?\n/).filter(Boolean));
    for (const commandPath of commandCandidates) {
      const candidate = path.resolve(path.dirname(commandPath), "..", "Code.exe");
      if (fs.existsSync(candidate)) return candidate;
    }
    const roots = [process.env.LOCALAPPDATA, process.env.ProgramFiles, process.env["ProgramFiles(x86)"]]
      .filter((value): value is string => Boolean(value));
    for (const root of roots) {
      const candidate = path.join(root, "Programs", "Microsoft VS Code", "Code.exe");
      if (fs.existsSync(candidate)) return candidate;
      const systemCandidate = path.join(root, "Microsoft VS Code", "Code.exe");
      if (fs.existsSync(systemCandidate)) return systemCandidate;
    }
  }
  return undefined;
}

async function main(): Promise<void> {
  const extensionRoot = path.resolve(__dirname, "..", "..");
  const repositoryRoot = path.resolve(extensionRoot, "..", "..");
  const vscodeExecutablePath = locateCodeExecutable();
  if (!vscodeExecutablePath) {
    console.log("Extension Host tests skipped: VS Code Code.exe is unavailable; set VSCODE_EXECUTABLE_PATH to run them.");
    return;
  }
  const workspaceRoot = fs.mkdtempSync(path.join(os.tmpdir(), "lwt vscode workspace λ "));
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "lwt vscode user data "));
  const extensionsDir = fs.mkdtempSync(path.join(os.tmpdir(), "lwt vscode extensions "));
  fs.writeFileSync(path.join(workspaceRoot, "main.lwt"), "let answer = 42;\nemit answer;\n", "utf8");
  if (!process.env.LWT_TEST_PYTHON) {
    const probe = spawnSync("python", ["-c", "import sys; print(sys.executable)"], {
      encoding: "utf8",
      shell: false,
      windowsHide: true,
    });
    if (probe.status !== 0 || !probe.stdout.trim()) {
      throw new Error("Python is unavailable; set LWT_TEST_PYTHON to the interpreter executable.");
    }
    process.env.LWT_TEST_PYTHON = probe.stdout.trim();
  }
  process.env.PYTHONPATH = [repositoryRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  try {
    await runTests({
      vscodeExecutablePath,
      extensionDevelopmentPath: extensionRoot,
      extensionTestsPath: path.join(extensionRoot, "out", "tests", "extension-host", "suite", "loader.js"),
      launchArgs: [
        workspaceRoot,
        "--disable-extensions",
        "--skip-welcome",
        "--skip-release-notes",
        "--user-data-dir", userDataDir,
        "--extensions-dir", extensionsDir,
      ],
      extensionTestsEnv: {
        LWT_TEST_PYTHON: process.env.LWT_TEST_PYTHON,
        LWT_REPO_ROOT: repositoryRoot,
        PYTHONPATH: process.env.PYTHONPATH,
      },
    });
  } finally {
    fs.rmSync(workspaceRoot, { recursive: true, force: true });
    fs.rmSync(userDataDir, { recursive: true, force: true });
    fs.rmSync(extensionsDir, { recursive: true, force: true });
  }
}

void main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
