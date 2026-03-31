import * as fs from "fs";
import * as path from "path";
import { TaskStep } from "../core/stateManager";
import { executeTool, listTools } from "../tools/toolRegistry";
import { logDecision, log, LogLevel } from "../logs/logger";
import { retrieveMemory, saveMemory, summarizeSession } from "../memory/memoryManager";

const PROMPT_PATH = path.resolve(__dirname, "../prompts/executor.md");

export function loadExecutorPrompt(): string {
  return fs.readFileSync(PROMPT_PATH, "utf-8");
}

export async function executeStep(step: TaskStep): Promise<string> {
  logDecision("Executor", `Executing step: ${step.description}`);
  step.status = "running";

  // Retrieve the plan metadata stored by the planner
  const planData = retrieveMemory(`plan:${step.id}`) as
    | { tool: string; args: Record<string, unknown> }
    | undefined;

  if (!planData) {
    // No tool metadata — this is a logic-only step
    log(LogLevel.INFO, "EXECUTOR", `Logic-only step: ${step.description}`);
    const result = `Completed: ${step.description}`;
    step.status = "completed";
    step.result = result;
    saveMemory("lastResult", result);
    return result;
  }

  const { tool, args } = planData;

  // Handle special non-tool actions
  if (tool === "none") {
    if (args.action === "summarize") {
      const summary = summarizeSession();
      step.status = "completed";
      step.result = summary;
      saveMemory("lastResult", summary);
      return summary;
    }

    // List tools action
    if (step.description.includes("List all registered tools")) {
      const tools = listTools();
      const result = tools
        .map((t) => `- ${t.name}: ${t.description} (write: ${t.requiresWrite}, shell: ${t.requiresShell})`)
        .join("\n");
      step.status = "completed";
      step.result = result;
      saveMemory("lastResult", result);
      return result;
    }

    // Generic logic step
    const result = `Processed: ${step.description}`;
    step.status = "completed";
    step.result = result;
    saveMemory("lastResult", result);
    return result;
  }

  // Execute the tool
  try {
    const result = await executeTool(tool, args);
    step.status = "completed";
    step.result = result;
    saveMemory("lastResult", result);
    logDecision("Executor", `Step completed successfully`, result.substring(0, 200));
    return result;
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    step.status = "failed";
    step.error = errorMsg;
    log(LogLevel.ERROR, "EXECUTOR", `Step failed: ${errorMsg}`);
    throw error;
  }
}
