import * as assert from "assert";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

const extensionId = "05t1925.lwt-language-tools";
const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
const python = process.env.LWT_TEST_PYTHON ?? "python";

function waitForDiagnostics(uri: vscode.Uri, predicate: (items: readonly vscode.Diagnostic[]) => boolean, checkCurrent = true): Promise<readonly vscode.Diagnostic[]> {
  const current = vscode.languages.getDiagnostics(uri);
  if (checkCurrent && predicate(current)) return Promise.resolve(current);
  return new Promise((resolve, reject) => {
    let subscription: vscode.Disposable;
    const timeout = setTimeout(() => {
      subscription.dispose();
      reject(new Error(`Timed out waiting for diagnostics on ${uri.fsPath}`));
    }, 15000);
    subscription = vscode.languages.onDidChangeDiagnostics((event) => {
      if (!event.uris.some((candidate) => candidate.toString() === uri.toString())) return;
      const items = vscode.languages.getDiagnostics(uri);
      if (predicate(items)) {
        clearTimeout(timeout);
        subscription.dispose();
        resolve(items);
      }
    });
  });
}

function waitForTaskEnd(mode: string): Promise<number | undefined> {
  return new Promise((resolve, reject) => {
    let subscription: vscode.Disposable;
    const timeout = setTimeout(() => {
      subscription.dispose();
      reject(new Error(`Timed out waiting for ${mode} task to finish`));
    }, 15000);
    subscription = vscode.tasks.onDidEndTaskProcess((event) => {
      if (event.execution.task.definition.type !== "lwt" || event.execution.task.definition.mode !== mode) return;
      clearTimeout(timeout);
      subscription.dispose();
      resolve(event.exitCode);
    });
  });
}

suite("LWT VS Code extension host", () => {
  test("activates and registers the language and commands", async () => {
    assert.ok(workspaceRoot?.includes(" ") && workspaceRoot.includes("λ"), "host workspace should contain spaces and Unicode");
    assert.ok(vscode.workspace.getConfiguration("lwt").get("pythonPath"));
    const extension = vscode.extensions.getExtension(extensionId);
    assert.ok(extension, `extension ${extensionId} was not found`);
    await extension.activate();
    const commands = await vscode.commands.getCommands(true);
    for (const command of ["lwt.runCurrentFile", "lwt.checkCurrentFile", "lwt.debugCurrentFile"]) {
      assert.ok(commands.includes(command), `missing command ${command}`);
    }
    assert.ok((await vscode.languages.getLanguages()).includes("lwt"));
  });

  test("real LSP subprocess publishes and clears diagnostics, hover and definition", async () => {
    assert.ok(workspaceRoot);
    const file = path.join(workspaceRoot, "lab source λ.lwt");
    fs.writeFileSync(file, "let answer = 42;\nemit answer;\n", "utf8");
    const uri = vscode.Uri.file(file);
    const diagnosticsPublished = waitForDiagnostics(uri, (items) => items.length === 0, false);
    const document = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(document);
    assert.deepEqual(await diagnosticsPublished, []);

    const definition = await vscode.commands.executeCommand<vscode.Location[] | vscode.LocationLink[]>(
      "vscode.executeDefinitionProvider", uri, new vscode.Position(1, 7),
    );
    assert.ok(definition?.length, "definition provider returned no location");
    const hover = await vscode.commands.executeCommand<vscode.Hover[]>(
      "vscode.executeHoverProvider", uri, new vscode.Position(1, 7),
    );
    assert.ok(hover?.length, "hover provider returned no result");

    const invalid = new vscode.WorkspaceEdit();
    invalid.replace(uri, new vscode.Range(new vscode.Position(1, 0), new vscode.Position(1, document.lineAt(1).text.length)), "emit ;");
    assert.ok(await vscode.workspace.applyEdit(invalid));
    const errors = await waitForDiagnostics(uri, (items) => items.length > 0);
    assert.ok(errors.some((item) => item.code === "PAR001"));

    const repaired = new vscode.WorkspaceEdit();
    repaired.replace(uri, new vscode.Range(new vscode.Position(1, 0), new vscode.Position(1, "emit ;".length)), "emit answer;");
    assert.ok(await vscode.workspace.applyEdit(repaired));
    assert.deepEqual(await waitForDiagnostics(uri, (items) => items.length === 0), []);
    await vscode.commands.executeCommand("workbench.action.closeActiveEditor");
  });

  test("configured Python path starts LSP and Run/Check commands create real process tasks", async () => {
    assert.ok(workspaceRoot);
    const file = path.join(workspaceRoot, "task program λ.lwt");
    fs.writeFileSync(file, "emit args();\n", "utf8");
    await vscode.workspace.getConfiguration("lwt").update("pythonPath", python, vscode.ConfigurationTarget.Workspace);
    await vscode.workspace.getConfiguration("lwt").update("workingDirectory", ".", vscode.ConfigurationTarget.Workspace);
    await vscode.workspace.getConfiguration("lwt").update("programArgs", ["two words", "--flag", "雪"], vscode.ConfigurationTarget.Workspace);
    const diagnosticsPublished = waitForDiagnostics(vscode.Uri.file(file), (items) => items.length === 0, false);
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    await vscode.window.showTextDocument(document);
    assert.deepEqual(await diagnosticsPublished, []);
    await vscode.workspace.getConfiguration("lwt").update("programStdin", "program input λ.txt", vscode.ConfigurationTarget.Workspace);
    fs.writeFileSync(path.join(workspaceRoot, "program input λ.txt"), "input for debug\n", "utf8");

    const runEnd = waitForTaskEnd("run");
    const runExecution = await vscode.commands.executeCommand<vscode.TaskExecution>("lwt.runCurrentFile");
    assert.ok(runExecution);
    const runProcess = runExecution.task.execution as vscode.ProcessExecution;
    assert.equal(runProcess.process, python);
    assert.deepEqual(runProcess.args, ["-m", "lwt", file, "--", "two words", "--flag", "雪"]);
    assert.equal(runProcess.options?.cwd, workspaceRoot);
    assert.equal(await runEnd, 0);

    const checkEnd = waitForTaskEnd("check");
    const checkExecution = await vscode.commands.executeCommand<vscode.TaskExecution>("lwt.checkCurrentFile");
    assert.ok(checkExecution);
    const checkProcess = checkExecution.task.execution as vscode.ProcessExecution;
    assert.equal(checkProcess.process, python);
    assert.deepEqual(checkProcess.args, ["-m", "lwt", "--check", file]);
    assert.equal(checkProcess.options?.cwd, workspaceRoot);
    assert.equal(await checkEnd, 0);

    const extension = vscode.extensions.getExtension(extensionId);
    assert.ok(extension);
    const api = extension.exports as { createTask: (mode: "run" | "check" | "debug", document: vscode.TextDocument) => vscode.Task };
    const run = api.createTask("run", document);
    const factoryRunProcess = run.execution as vscode.ProcessExecution;
    assert.equal(factoryRunProcess.process, python);
    assert.deepEqual(factoryRunProcess.args, ["-m", "lwt", file, "--", "two words", "--flag", "雪"]);
    assert.equal(factoryRunProcess.options?.cwd, workspaceRoot);

    const check = api.createTask("check", document);
    const factoryCheckProcess = check.execution as vscode.ProcessExecution;
    assert.equal(factoryCheckProcess.process, python);
    assert.deepEqual(factoryCheckProcess.args, ["-m", "lwt", "--check", file]);
    assert.equal(factoryCheckProcess.options?.cwd, workspaceRoot);

    const debug = api.createTask("debug", document);
    const factoryDebugProcess = debug.execution as vscode.ProcessExecution;
    assert.equal(factoryDebugProcess.process, python);
    assert.deepEqual(factoryDebugProcess.args, [
      "-m", "lwt.debugger", "--program-stdin", path.join(workspaceRoot, "program input λ.txt"),
      file, "--", "two words", "--flag", "雪",
    ]);
    assert.equal(factoryDebugProcess.options?.cwd, workspaceRoot);
  });
});
