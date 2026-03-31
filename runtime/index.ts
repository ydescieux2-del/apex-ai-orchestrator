import * as readline from "readline";
import { runOrchestrator, setExecutionMode, ExecutionMode } from "./core/orchestrator";
import { loadFeatureFlags, setFeatureFlag } from "./core/featureFlags";
import { getExecutionMode } from "./core/executionMode";
import { registerFileTools } from "./tools/fileTools";
import { registerWebTools } from "./tools/webTools";
import { registerShellTools } from "./tools/shellTools";
import { listTools } from "./tools/toolRegistry";
import { clearSessionLogs } from "./logs/logger";

// ──────────────────────────────────────────────
// Bootstrap
// ──────────────────────────────────────────────

function bootstrap(): void {
  loadFeatureFlags();
  registerFileTools();
  registerWebTools();
  registerShellTools();

  console.log("╔══════════════════════════════════════════════╗");
  console.log("║          APEX AI RUNTIME v1.0.0              ║");
  console.log("║    Modular Agent Orchestration System        ║");
  console.log("╚══════════════════════════════════════════════╝");
  console.log();
  console.log(`Mode: ${getExecutionMode()}`);
  console.log(`Tools: ${listTools().map((t) => t.name).join(", ")}`);
  console.log();
  console.log("Commands:");
  console.log("  :mode <SAFE|ASSISTED|AUTONOMOUS>  — Switch execution mode");
  console.log("  :flag <name> <true|false>          — Toggle feature flag");
  console.log("  :tools                             — List registered tools");
  console.log("  :clear                             — Clear session logs");
  console.log("  :exit                              — Quit");
  console.log();
}

// ──────────────────────────────────────────────
// REPL
// ──────────────────────────────────────────────

function startREPL(): void {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: `[${getExecutionMode()}] > `,
  });

  rl.prompt();

  rl.on("line", async (line: string) => {
    const input = line.trim();

    if (!input) {
      rl.prompt();
      return;
    }

    // Handle meta-commands
    if (input.startsWith(":")) {
      handleMetaCommand(input);
      rl.setPrompt(`[${getExecutionMode()}] > `);
      rl.prompt();
      return;
    }

    // Run the orchestrator
    try {
      console.log("\n─── Orchestrator Running ───\n");
      const result = await runOrchestrator(input);
      console.log("\n─── Result ───\n");

      if (result.success) {
        console.log("Status: SUCCESS");
      } else {
        console.log("Status: FAILED");
      }

      console.log(`Session: ${result.sessionId}`);
      console.log(`Duration: ${result.durationMs}ms`);

      if (result.results.length > 0) {
        console.log("\nOutputs:");
        result.results.forEach((r, i) => {
          console.log(`  [${i + 1}] ${r.substring(0, 500)}${r.length > 500 ? "..." : ""}`);
        });
      }

      if (result.errors.length > 0) {
        console.log("\nErrors:");
        result.errors.forEach((e) => console.log(`  ✗ ${e}`));
      }

      console.log(`\nMemory:\n${result.memorySummary}`);
    } catch (error) {
      console.error("Fatal error:", error instanceof Error ? error.message : error);
    }

    console.log();
    rl.setPrompt(`[${getExecutionMode()}] > `);
    rl.prompt();
  });

  rl.on("close", () => {
    console.log("\nGoodbye.");
    process.exit(0);
  });
}

function handleMetaCommand(input: string): void {
  const parts = input.split(/\s+/);
  const cmd = parts[0];

  switch (cmd) {
    case ":mode": {
      const mode = parts[1]?.toUpperCase();
      if (mode && mode in ExecutionMode) {
        setExecutionMode(mode as ExecutionMode);
        console.log(`Execution mode set to: ${mode}`);
      } else {
        console.log(`Usage: :mode <SAFE|ASSISTED|AUTONOMOUS>`);
        console.log(`Current mode: ${getExecutionMode()}`);
      }
      break;
    }

    case ":flag": {
      const flagName = parts[1];
      const flagValue = parts[2];
      if (flagName && flagValue !== undefined) {
        const value = flagValue === "true";
        setFeatureFlag(flagName as any, value);
        console.log(`Feature flag "${flagName}" set to: ${value}`);
      } else {
        const flags = loadFeatureFlags();
        console.log("Feature flags:", JSON.stringify(flags, null, 2));
      }
      break;
    }

    case ":tools": {
      const tools = listTools();
      console.log("Registered tools:");
      tools.forEach((t) => {
        console.log(`  ${t.name} — ${t.description} (write: ${t.requiresWrite}, shell: ${t.requiresShell})`);
      });
      break;
    }

    case ":clear":
      clearSessionLogs();
      console.log("Session logs cleared.");
      break;

    case ":exit":
    case ":quit":
      console.log("Goodbye.");
      process.exit(0);

    default:
      console.log(`Unknown command: ${cmd}`);
  }
}

// ──────────────────────────────────────────────
// Non-interactive mode (for piped input / single command)
// ──────────────────────────────────────────────

async function runSingleCommand(input: string): Promise<void> {
  bootstrap();
  const result = await runOrchestrator(input);
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.success ? 0 : 1);
}

// ──────────────────────────────────────────────
// Entry point
// ──────────────────────────────────────────────

const args = process.argv.slice(2);

if (args.length > 0 && args[0] === "--run") {
  const input = args.slice(1).join(" ");
  runSingleCommand(input);
} else {
  bootstrap();
  startREPL();
}
