import * as fs from "node:fs";
import * as path from "node:path";

export type WorkflowMode = "run" | "check" | "debug";

export interface WorkflowSettings {
  pythonPath?: unknown;
  workingDirectory?: unknown;
  programArgs?: unknown;
  programStdin?: unknown;
}

export interface LaunchSpec {
  readonly mode: WorkflowMode;
  readonly executable: string;
  readonly args: readonly string[];
  readonly cwd: string;
  readonly sourcePath: string;
}

export interface DapAdapterSpec {
  readonly executable: string;
  readonly args: readonly string[];
  readonly cwd: string;
}

export interface DapLaunchConfiguration {
  readonly type: "lwt";
  readonly request: "launch";
  readonly name: string;
  readonly program: string;
  readonly python: string;
  readonly cwd: string;
  readonly args: readonly string[];
  readonly stdinFile: string;
}

export class WorkflowConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkflowConfigurationError";
  }
}

function nonEmptyString(value: unknown, fallback: string, name: string): string {
  if (value === undefined || value === "") return fallback;
  if (typeof value !== "string") {
    throw new WorkflowConfigurationError(`${name} must be a string.`);
  }
  return value;
}

function configuredProgramArgs(value: unknown): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new WorkflowConfigurationError("lwt.programArgs must be an array of strings.");
  }
  return [...value];
}

function resolveDirectory(workspaceRoot: string, configured: string): string {
  const candidate = path.resolve(workspaceRoot, configured || ".");
  let stat: fs.Stats;
  try {
    stat = fs.statSync(candidate);
  } catch {
    throw new WorkflowConfigurationError(`LWT working directory does not exist: ${candidate}`);
  }
  if (!stat.isDirectory()) {
    throw new WorkflowConfigurationError(`LWT working directory is not a directory: ${candidate}`);
  }
  return candidate;
}

export function buildDapAdapterSpec(
  pythonPath: string,
  workspaceRoot: string,
  settings: WorkflowSettings = {},
): DapAdapterSpec {
  const executable = nonEmptyString(settings.pythonPath, pythonPath, "lwt.pythonPath");
  return {
    executable,
    args: ["-m", "lwt.dap_server"],
    cwd: resolveDirectory(workspaceRoot, ""),
  };
}

export function buildDapLaunchConfiguration(
  programPath: string,
  workspaceRoot: string,
  settings: WorkflowSettings = {},
): DapLaunchConfiguration {
  if (!programPath) {
    throw new WorkflowConfigurationError("The LWT program path must not be empty.");
  }
  const python = nonEmptyString(settings.pythonPath, "python", "lwt.pythonPath");
  const workingDirectory = nonEmptyString(settings.workingDirectory, "", "lwt.workingDirectory");
  const cwd = resolveDirectory(workspaceRoot, workingDirectory);
  const args = configuredProgramArgs(settings.programArgs);
  const stdinFile = nonEmptyString(settings.programStdin, "", "lwt.programStdin");
  return {
    type: "lwt",
    request: "launch",
    name: "LWT: Debug Current File",
    program: path.resolve(workspaceRoot, programPath),
    python,
    cwd,
    args,
    stdinFile: stdinFile ? path.resolve(cwd, stdinFile) : "",
  };
}

export function buildLaunchSpec(
  mode: WorkflowMode,
  pythonPath: string,
  workspaceRoot: string,
  sourcePath: string,
  settings: WorkflowSettings = {},
): LaunchSpec {
  if (!path.isAbsolute(sourcePath)) {
    throw new WorkflowConfigurationError("The current LWT file must have a filesystem path.");
  }
  const executable = nonEmptyString(settings.pythonPath, pythonPath, "lwt.pythonPath");
  const workingDirectory = nonEmptyString(settings.workingDirectory, "", "lwt.workingDirectory");
  const cwd = resolveDirectory(workspaceRoot, workingDirectory);
  let args: string[];

  if (mode === "run") {
    const programArgs = configuredProgramArgs(settings.programArgs);
    args = ["-m", "lwt", sourcePath];
    if (programArgs.length > 0) args.push("--", ...programArgs);
  } else if (mode === "check") {
    args = ["-m", "lwt", "--check", sourcePath];
  } else {
    args = ["-m", "lwt.debugger"];
    const programStdin = nonEmptyString(settings.programStdin, "", "lwt.programStdin");
    if (programStdin) {
      args.push("--program-stdin", path.resolve(cwd, programStdin));
    }
    args.push(sourcePath);
    const programArgs = configuredProgramArgs(settings.programArgs);
    if (programArgs.length > 0) args.push("--", ...programArgs);
  }

  return { mode, executable, args, cwd, sourcePath };
}
