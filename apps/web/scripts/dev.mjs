import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const webDir = fileURLToPath(new URL("../", import.meta.url));
const apiDir = fileURLToPath(new URL("../../api/", import.meta.url));
const python = fileURLToPath(new URL(process.platform === "win32"
  ? "../../api/.venv/Scripts/python.exe"
  : "../../api/.venv/bin/python", import.meta.url));

const host = "127.0.0.1";
const webPort = process.env.AGENT_DEV_WEB_PORT ?? "3000";
const apiPort = process.env.AGENT_DEV_API_PORT ?? "8000";
const webOrigin = `http://${host}:${webPort}`;
const apiOrigin = `http://${host}:${apiPort}`;
const stopOnEof = process.env.AGENT_DEV_STOP_ON_EOF === "1";

const commands = [
  {
    name: "API",
    executable: python,
    args: ["-m", "uvicorn", "app.main:app", "--app-dir", "src", "--host", host, "--port", apiPort, "--no-access-log"],
    cwd: apiDir,
    env: { ...process.env, AGENT_WEB_ORIGIN: webOrigin, AGENT_CALLBACK: `${apiOrigin}/auth/callback` },
  },
  {
    name: "Web",
    executable: process.execPath,
    args: [require.resolve("next/dist/bin/next"), "dev", "--hostname", host, "--port", webPort],
    cwd: webDir,
    env: { ...process.env, API_URL: apiOrigin },
  },
];

const children = commands.map(({ name, executable, args, cwd, env }) => {
  const child = spawn(executable, args, { cwd, env, stdio: stopOnEof ? ["ignore", "inherit", "inherit"] : "inherit" });
  child.once("error", (error) => {
    console.error(`${name}: ${error.message}`);
    if (name === "API" && error.code === "ENOENT") {
      console.error("Crea el entorno de Python en apps/api/.venv e instala la API según el README.");
    }
    stop(1);
  });
  child.once("exit", (code) => stop(code ?? 1));
  return child;
});

function stop(exitCode) {
  if (process.exitCode !== undefined) return;
  process.exitCode = exitCode;
  if (stopOnEof) process.stdin.pause();
  for (const child of children) child.kill();
}

process.once("SIGINT", () => stop(0));
process.once("SIGTERM", () => stop(0));

if (stopOnEof) {
  process.stdin.once("end", () => stop(0));
  process.stdin.resume();
}
