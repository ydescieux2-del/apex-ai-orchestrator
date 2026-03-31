import * as fs from "fs";
import * as path from "path";
import { TaskStep } from "../core/stateManager";
import { logDecision, log, LogLevel } from "../logs/logger";
import { saveMemory } from "../memory/memoryManager";

const PROMPT_PATH = path.resolve(__dirname, "../prompts/reflection.md");
const MAX_RETRIES = 3;

export type DebugAction = "RETRY" | "ADJUST" | "ABORT";

export interface DebugResult {
  action: DebugAction;
  reason: string;
  adjustedStep?: Partial<TaskStep>;
}

export function loadDebuggerPrompt(): string {
  return fs.readFileSync(PROMPT_PATH, "utf-8");
}

function classifyError(error: string): "transient" | "fixable" | "fatal" {
  const lower = error.toLowerCase();

  // Transient errors — worth retrying
  if (
    lower.includes("timeout") ||
    lower.includes("econnreset") ||
    lower.includes("econnrefused") ||
    lower.includes("temporary") ||
    lower.includes("rate limit") ||
    lower.includes("429") ||
    lower.includes("503")
  ) {
    return "transient";
  }

  // Fatal errors — cannot recover
  if (
    lower.includes("not allowed") ||
    lower.includes("not permitted") ||
    lower.includes("permission denied") ||
    lower.includes("blocked") ||
    lower.includes("disabled via feature flag") ||
    lower.includes("switch to")
  ) {
    return "fatal";
  }

  // Fixable errors — might work with adjusted parameters
  if (
    lower.includes("not found") ||
    lower.includes("invalid") ||
    lower.includes("missing") ||
    lower.includes("no such file")
  ) {
    return "fixable";
  }

  // Default to fixable for unknown errors
  return "fixable";
}

export function diagnose(step: TaskStep): DebugResult {
  const error = step.error || "Unknown error";
  logDecision("Debugger", `Diagnosing failure for step: ${step.description}`, error);

  const errorType = classifyError(error);
  log(LogLevel.INFO, "DEBUGGER", `Error classified as: ${errorType}`);

  // Check retry budget
  if (step.retries >= MAX_RETRIES) {
    logDecision("Debugger", "Max retries exceeded — aborting", `${step.retries}/${MAX_RETRIES} retries used`);
    return {
      action: "ABORT",
      reason: `Step failed after ${MAX_RETRIES} retries. Last error: ${error}`,
    };
  }

  switch (errorType) {
    case "transient":
      logDecision("Debugger", "Transient error detected — retrying");
      return {
        action: "RETRY",
        reason: `Transient error detected: ${error}. Retrying (attempt ${step.retries + 1}/${MAX_RETRIES}).`,
      };

    case "fixable":
      logDecision("Debugger", "Fixable error detected — adjusting step");
      saveMemory(`debug:${step.id}`, { error, attempt: step.retries + 1 });
      return {
        action: "ADJUST",
        reason: `Error may be fixable: ${error}. Adjusting parameters.`,
        adjustedStep: {
          description: `[Retry ${step.retries + 1}] ${step.description}`,
          status: "pending",
          error: undefined,
        },
      };

    case "fatal":
      logDecision("Debugger", "Fatal error — aborting step");
      return {
        action: "ABORT",
        reason: `Fatal error — cannot recover: ${error}`,
      };

    default:
      return {
        action: "ABORT",
        reason: `Unclassified error: ${error}`,
      };
  }
}
