import { execSync } from "child_process";
import { registerTool } from "./toolRegistry";

const BLOCKED_COMMANDS = [
  "rm -rf /",
  "rm -rf /*",
  "mkfs",
  ":(){:|:&};:",
  "dd if=/dev/zero",
  "chmod -R 777 /",
  "shutdown",
  "reboot",
  "halt",
  "init 0",
  "init 6",
];

function isSafeCommand(command: string): boolean {
  const normalized = command.trim().toLowerCase();
  return !BLOCKED_COMMANDS.some((blocked) => normalized.includes(blocked));
}

export function registerShellTools(): void {
  registerTool(
    "run_shell_command",
    "Execute a shell command and return its output",
    async (args) => {
      const command = args.command as string;
      if (!command) throw new Error("Missing required argument: command");

      if (!isSafeCommand(command)) {
        throw new Error(`Blocked dangerous command: ${command}`);
      }

      const timeout = (args.timeout as number) || 30000;

      try {
        const output = execSync(command, {
          encoding: "utf-8",
          timeout,
          maxBuffer: 1024 * 1024, // 1MB
          stdio: ["pipe", "pipe", "pipe"],
        });
        return output || "(command completed with no output)";
      } catch (error: unknown) {
        const execError = error as { stderr?: string; status?: number; message?: string };
        const stderr = execError.stderr || "";
        const exitCode = execError.status ?? 1;
        throw new Error(`Command failed (exit ${exitCode}): ${stderr || execError.message}`);
      }
    },
    { requiresShell: true, requiresWrite: true }
  );
}
