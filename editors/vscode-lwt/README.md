# LWT Language Tools for VS Code

Local VSIX extension sources for `.lwt` syntax highlighting, the existing LWT Language Server, Run/Check tasks, terminal CLI debugging, and a native DAP adapter for F5/Run and Debug.

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
