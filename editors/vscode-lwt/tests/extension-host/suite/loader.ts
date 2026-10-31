import * as path from "path";
import Mocha = require("mocha");

export function run(): Promise<void> {
  const mocha = new Mocha({ ui: "tdd", color: true, timeout: 30000 });
  const testsRoot = path.resolve(__dirname);
  mocha.addFile(path.join(testsRoot, "index.js"));
  return new Promise((resolve, reject) => {
    mocha.run((failures: number) => {
      if (failures > 0) reject(new Error(`${failures} extension host test(s) failed.`));
      else resolve();
    });
  });
}
