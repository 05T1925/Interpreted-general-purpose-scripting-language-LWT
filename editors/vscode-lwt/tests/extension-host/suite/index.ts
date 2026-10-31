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

type TrackedMessage = Record<string, unknown>;

function debugMessageWaiter() {
  const messages: TrackedMessage[] = [];
  const waiters: Array<{
    predicate: (message: TrackedMessage) => boolean;
    resolve: (message: TrackedMessage) => void;
    reject: (error: Error) => void;
    timeout: NodeJS.Timeout;
  }> = [];
  const waitFor = (predicate: (message: TrackedMessage) => boolean): Promise<TrackedMessage> => {
    const existing = messages.find(predicate);
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
      const waiter = {
        predicate,
        resolve,
        reject,
        timeout: setTimeout(() => {
          const index = waiters.indexOf(waiter);
          if (index >= 0) waiters.splice(index, 1);
          reject(new Error("Timed out waiting for a native LWT DAP message."));
        }, 15000),
      };
      waiters.push(waiter);
    });
  };
  const record = (message: unknown): void => {
    if (typeof message !== "object" || message === null) return;
    const value = message as TrackedMessage;
    messages.push(value);
    for (let index = waiters.length - 1; index >= 0; index -= 1) {
      const waiter = waiters[index];
      if (waiter.predicate(value)) {
        clearTimeout(waiter.timeout);
        waiters.splice(index, 1);
        waiter.resolve(value);
      }
    }
  };
  return { waitFor, record };
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

  test("native DAP hits a VS Code source breakpoint and serves stack, variables, output and exit", async () => {
    assert.ok(workspaceRoot);
    const file = path.join(workspaceRoot, "native DAP program λ.lwt");
    fs.writeFileSync(
      file,
      "fn increment(value) {\n  let local = value + 1;\n  return local;\n}\nlet global = 41;\nlet result = increment(global);\nemit result;\n",
      "utf8",
    );
    const uri = vscode.Uri.file(file);
    const document = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(document);
    assert.ok(await document.save());
    const breakpoint = new vscode.SourceBreakpoint(
      new vscode.Location(uri, new vscode.Position(1, 0)),
      true,
    );
    vscode.debug.addBreakpoints([breakpoint]);

    const tracked = debugMessageWaiter();
    const trackerFactory = vscode.debug.registerDebugAdapterTrackerFactory("lwt", {
      createDebugAdapterTracker: () => ({
        onWillReceiveMessage: (message) => tracked.record(message),
        onDidSendMessage: (message) => tracked.record(message),
      }),
    });
    let session: vscode.DebugSession | undefined;
    try {
      const stoppedPromise = tracked.waitFor((message) => message.type === "event" && message.event === "stopped");
      const started = await vscode.debug.startDebugging(vscode.workspace.workspaceFolders?.[0], {
        type: "lwt",
        request: "launch",
        name: "S32 native DAP Extension Host",
        program: file,
        python,
        cwd: workspaceRoot,
        args: [],
        stdinFile: "",
      });
      assert.ok(started, "VS Code refused to start the LWT DAP session");
      session = vscode.debug.activeDebugSession;
      assert.ok(session, "the native DAP session did not become active");
      await tracked.waitFor((message) => message.type === "request" && message.command === "configurationDone");

      const setBreakpointResponse = await tracked.waitFor((message) =>
        message.type === "response" && message.command === "setBreakpoints",
      );
      const responseBody = setBreakpointResponse.body as { breakpoints?: Array<{ verified?: boolean }> };
      assert.equal(responseBody.breakpoints?.[0]?.verified, true);
      const stopped = await stoppedPromise;
      const stoppedBody = stopped.body as { threadId?: number; reason?: string };
      assert.equal(stoppedBody.threadId, 1);
      assert.equal(stoppedBody.reason, "breakpoint");

      const threads = await session.customRequest("threads") as { threads: Array<{ id: number }> };
      assert.deepEqual(threads.threads, [{ id: 1, name: "LWT program" }]);
      const stack = await session.customRequest("stackTrace", { threadId: 1 }) as {
        stackFrames: Array<{ id: number; name: string; line: number }>;
      };
      assert.equal(stack.stackFrames[0].name, "increment");
      assert.equal(stack.stackFrames[0].line, 2);
      assert.equal(stack.stackFrames.length, 2);
      const scopes = await session.customRequest("scopes", {
        frameId: stack.stackFrames[0].id,
      }) as { scopes: Array<{ name: string; variablesReference: number }> };
      const locals = scopes.scopes.find((item) => item.name === "Locals");
      assert.ok(locals);
      const variables = await session.customRequest("variables", {
        variablesReference: locals.variablesReference,
      }) as { variables: Array<{ name: string; value: string }> };
      assert.deepEqual(variables.variables.map((item) => item.name), ["value"]);
      assert.equal(variables.variables[0].value, "41");

      const continuedPromise = tracked.waitFor((message) => message.type === "event" && message.event === "continued");
      const stdoutPromise = tracked.waitFor((message) => {
        if (message.type !== "event" || message.event !== "output") return false;
        const body = message.body as { category?: string; output?: string };
        return body.category === "stdout";
      });
      const exitedPromise = tracked.waitFor((message) => message.type === "event" && message.event === "exited");
      const terminatedPromise = tracked.waitFor((message) => message.type === "event" && message.event === "terminated");
      const continued = await session.customRequest("continue", { threadId: 1 }) as {
        allThreadsContinued?: boolean;
      };
      assert.equal(continued.allThreadsContinued, true);
      await continuedPromise;
      const stdout = await stdoutPromise;
      assert.equal((stdout.body as { output: string }).output, "42\n");
      const exited = await exitedPromise;
      assert.equal((exited.body as { exitCode: number }).exitCode, 0);
      await terminatedPromise;
    } catch (error) {
      console.error("native DAP Extension Host test failed:", error);
      throw error;
    } finally {
      if (session && vscode.debug.activeDebugSession?.id === session.id) {
        await Promise.resolve(vscode.debug.stopDebugging(session)).catch(() => false);
      }
      trackerFactory.dispose();
      vscode.debug.removeBreakpoints([breakpoint]);
      await vscode.commands.executeCommand("workbench.action.closeActiveEditor");
    }
  });
});
