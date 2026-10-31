import * as vscode from "vscode";
import {
  CloseAction,
  ErrorAction,
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
} from "vscode-languageclient/node";
import { buildLaunchSpec, WorkflowMode, WorkflowConfigurationError } from "./workflow";

const LANGUAGE_ID = "lwt";
const TASK_TYPE = "lwt";
let activeClient: LanguageClient | undefined;
let restartQueue = Promise.resolve();
let disposed = false;
const activeTasks = new Map<string, Promise<vscode.TaskExecution>>();

export interface ExtensionTestApi {
  createTask(mode: WorkflowMode, document: vscode.TextDocument): vscode.Task;
}

export function activate(context: vscode.ExtensionContext): ExtensionTestApi {
  disposed = false;
  const output = vscode.window.createOutputChannel("LWT", { log: true });
  context.subscriptions.push(output);
  context.subscriptions.push(
    vscode.tasks.registerTaskProvider(TASK_TYPE, {
      provideTasks: () => [],
      resolveTask: (task) => task,
    }),
  );

  const restartLanguageClient = (): Promise<void> => {
    restartQueue = restartQueue.then(async () => {
      if (disposed) return;
      if (activeClient) {
        const previous = activeClient;
        activeClient = undefined;
        await previous.stop().catch((error: unknown) => {
          output.appendLine(`Language server stop failed: ${errorMessage(error)}`);
        });
      }

      const folders = vscode.workspace.workspaceFolders ?? [];
      if (folders.length !== 1) {
        const message = folders.length === 0
          ? "Open one LWT project folder to start the language server."
          : "LWT currently supports one workspace folder. Close extra folders to start the language server.";
        output.appendLine(message);
        if (folders.length > 1) void vscode.window.showWarningMessage(message);
        return;
      }

      const workspaceRoot = folders[0].uri.fsPath;
      const pythonPath = vscode.workspace.getConfiguration("lwt").get<string>("pythonPath", "python");
      const serverOptions: ServerOptions = {
        command: pythonPath,
        args: ["-m", "lwt.lsp_server"],
        options: { cwd: workspaceRoot },
      };
      const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: LANGUAGE_ID }],
        workspaceFolder: folders[0],
        outputChannel: output,
        errorHandler: {
          error: (error) => {
            output.appendLine(`Language server error: ${error.message}`);
            return { action: ErrorAction.Continue };
          },
          closed: () => {
            output.appendLine("Language server stopped. Automatic restart is disabled; run Developer: Reload Window after fixing the Python or workspace setup.");
            return { action: CloseAction.DoNotRestart };
          },
        },
      };
      const next = new LanguageClient("lwt", "LWT Language Server", serverOptions, clientOptions);
      activeClient = next;
      try {
        await next.start();
        output.appendLine(`Language server started with ${pythonPath} in ${workspaceRoot}`);
      } catch (error) {
        if (activeClient === next) activeClient = undefined;
        output.appendLine(`Could not start LWT language server: ${errorMessage(error)}`);
        const action = await vscode.window.showErrorMessage(
          `Could not start the LWT language server. Check lwt.pythonPath and open the LWT repository root. Details are in the LWT output channel.`,
          "Open LWT Output",
        );
        if (action) output.show(true);
      }
    }).catch((error: unknown) => {
      output.appendLine(`Language server lifecycle failed: ${errorMessage(error)}`);
    });
    return restartQueue;
  };

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("lwt.pythonPath")) void restartLanguageClient();
    }),
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => void restartLanguageClient()),
  );

  for (const [command, mode] of [
    ["lwt.runCurrentFile", "run"],
    ["lwt.checkCurrentFile", "check"],
    ["lwt.debugCurrentFile", "debug"],
  ] as const) {
    context.subscriptions.push(vscode.commands.registerCommand(command, () => runWorkflow(mode, output)));
  }

  context.subscriptions.push(
    vscode.tasks.onDidEndTaskProcess((event) => {
      if (event.execution.task.definition.type !== TASK_TYPE) return;
      const mode = String(event.execution.task.definition.mode ?? "task");
      const runId = String(event.execution.task.definition.runId ?? "");
      activeTasks.delete(runId);
      output.appendLine(`${mode} task finished with exit code ${String(event.exitCode)}.`);
    }),
  );

  void restartLanguageClient();

  async function runWorkflow(mode: WorkflowMode, channel: vscode.OutputChannel): Promise<vscode.TaskExecution | undefined> {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== LANGUAGE_ID || editor.document.isUntitled) {
      void vscode.window.showErrorMessage("Open a saved .lwt file before running an LWT command.");
      return undefined;
    }
    if (!(await editor.document.save())) {
      void vscode.window.showErrorMessage("Save the current LWT file before starting the task.");
      return undefined;
    }

    let task: vscode.Task;
    try {
      task = createWorkflowTask(mode, editor.document, channel);
    } catch (error) {
      const message = error instanceof WorkflowConfigurationError ? error.message : errorMessage(error);
      channel.appendLine(message);
      void vscode.window.showErrorMessage(message);
      return undefined;
    }

    const runId = String(task.definition.runId);
    const taskPromise = Promise.resolve(vscode.tasks.executeTask(task));
    activeTasks.set(runId, taskPromise);
    try {
      return await taskPromise;
    } catch (error) {
      activeTasks.delete(runId);
      const message = `Could not start LWT ${mode} task: ${errorMessage(error)}`;
      channel.appendLine(message);
      void vscode.window.showErrorMessage(message);
      return undefined;
    }
  }

  return { createTask: (mode, document) => createWorkflowTask(mode, document, output) };
}

function createWorkflowTask(mode: WorkflowMode, document: vscode.TextDocument, channel: vscode.OutputChannel): vscode.Task {
  if (document.languageId !== LANGUAGE_ID || document.isUntitled) {
    throw new WorkflowConfigurationError("Open a saved .lwt file before running an LWT command.");
  }
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (folders.length !== 1) {
    throw new WorkflowConfigurationError("LWT tasks require exactly one open workspace folder.");
  }
  const config = vscode.workspace.getConfiguration("lwt");
  const spec = buildLaunchSpec(
    mode,
    config.get<string>("pythonPath", "python"),
    folders[0].uri.fsPath,
    document.uri.fsPath,
    {
      pythonPath: config.get("pythonPath"),
      workingDirectory: config.get("workingDirectory"),
      programArgs: config.get("programArgs"),
      programStdin: config.get("programStdin"),
    },
  );
  const runId = `${mode}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const execution = new vscode.ProcessExecution(spec.executable, [...spec.args], { cwd: spec.cwd });
  const task = new vscode.Task(
    { type: TASK_TYPE, mode, runId },
    folders[0],
    `LWT: ${mode} ${vscode.workspace.asRelativePath(document.uri)}`,
    "LWT",
    execution,
    [],
  );
  task.presentationOptions = {
    reveal: vscode.TaskRevealKind.Always,
    panel: vscode.TaskPanelKind.Dedicated,
    clear: false,
    showReuseMessage: true,
    focus: mode !== "check",
    echo: true,
  };
  channel.appendLine(`${mode} argv: ${JSON.stringify([spec.executable, ...spec.args])}`);
  channel.appendLine(`${mode} cwd: ${spec.cwd}`);
  return task;
}

export async function deactivate(): Promise<void> {
  disposed = true;
  await restartQueue;
  await Promise.all([...activeTasks.values()].map(async (taskPromise) => {
    try {
      (await taskPromise).terminate();
    } catch {
      // VS Code may already have ended a task while deactivation is running.
    }
  }));
  activeTasks.clear();
  await activeClient?.stop();
  activeClient = undefined;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
