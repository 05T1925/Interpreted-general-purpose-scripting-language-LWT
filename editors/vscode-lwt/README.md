# LWT Language Tools for VS Code

Local VSIX extension sources for `.lwt` syntax highlighting, the existing LWT Language Server, Run/Check tasks, terminal CLI debugging, a native DAP adapter for F5/Run and Debug, and the LWT black-box Test Explorer.

## Build and test

From this directory:

```powershell
npm ci
npm test
npm run package
```

If VS Code is installed outside a standard path, set `VSCODE_EXECUTABLE_PATH` to its `Code.exe` before `npm test`. Extension Host tests use an isolated profile and temporary workspace. They do not use the user's VS Code profile.

The package command creates `lwt-language-tools-0.1.0.vsix` in this directory. Install it locally with:

```powershell
code --install-extension .\lwt-language-tools-0.1.0.vsix
```

No Marketplace publishing is configured. Remove the generated VSIX after local validation; it is a build artifact, not source.

The repository's [extension guide](../../docs/vscode-extension.md) describes installation, settings, and workflow boundaries. The [DAP guide](../../docs/dap.md) covers launch configuration, source breakpoints, stepping, variables, stdin, and adapter limits.

## Black-box Test Explorer (S33)

Open the LWT repository root as a **single-folder workspace**. The extension discovers tests by running `python tools/run_tests.py --list-json`; the existing `.lwt` programs and paired JSON metadata remain the only test inventory. Use the Testing view to run all discovered tests, a category, or a single case. `LWT: Refresh Black-box Tests` refreshes discovery manually; changes under `tests/cases/` also trigger a debounced refresh.

Test output includes the runner status, exit code, stdout/stderr and expected-versus-actual differences. A selected batch is sent to one runner process, which validates the complete inventory once and uses the existing oracle. The Python runner can also be used without VS Code:

```powershell
python tools/run_tests.py --list-json
python tools/run_tests.py --case args-empty --format json
python tools/run_tests.py --category arrays-records-each --format json
```

The Debug profile is offered only for cases that expect exit code 0, use the standard source entry, and have strict UTF-8 stdin. Select one case at a time. CLI override cases, expected-error cases, and invalid UTF-8 stdin cases cannot be debugged faithfully. A DAP session is marked unverified/skipped in Test Explorer; only a runner oracle comparison can mark a case passed. Python/TypeScript provide this development UI; the LWT language and course application remain unchanged.

The automated Extension Host suite validates discovery, selection, output, cancellation, refresh, source opening, and a DAP breakpoint. It does not substitute for manual mouse/keyboard verification in a user's VS Code installation. Schema, detailed evidence and limitations are in [docs/s33-testing-workbench.md](../../docs/s33-testing-workbench.md).
