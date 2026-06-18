const { spawnSync } = require("node:child_process");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const extraArgs = process.argv.slice(2);

const candidates = [
  process.env.PYTHON ? { command: process.env.PYTHON, args: [] } : null,
  { command: path.join(repoRoot, ".tools", "Python312-embed", "python.exe"), args: [] },
  { command: path.join(repoRoot, ".tools", "Python312", "python.exe"), args: [] },
  { command: "python", args: [] },
  { command: "python3", args: [] },
  { command: "py", args: ["-3.12"] },
].filter(Boolean);

function canRun(candidate) {
  const result = spawnSync(candidate.command, [...candidate.args, "--version"], {
    cwd: repoRoot,
    encoding: "utf8",
  });

  return !result.error && result.status === 0;
}

const python = candidates.find(canRun);

if (!python) {
  console.error("Unable to find Python. Install Python 3.12+ or run the local test bootstrap first.");
  process.exit(1);
}

const result = spawnSync(python.command, [
  ...python.args,
  path.join(repoRoot, "scripts", "run_pytest.py"),
  ...extraArgs,
], {
  cwd: repoRoot,
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

if (result.signal) {
  console.error(`pytest terminated by signal ${result.signal}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
