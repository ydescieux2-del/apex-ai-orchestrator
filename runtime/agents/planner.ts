import * as fs from "fs";
import * as path from "path";
import { TaskStep } from "../core/stateManager";
import { getExecutionMode, canPerformWrite, canExecuteShell } from "../core/executionMode";
import { isEnabled } from "../core/featureFlags";
import { logDecision, log, LogLevel } from "../logs/logger";
import { retrieveMemory, saveMemory } from "../memory/memoryManager";
import { listTools } from "../tools/toolRegistry";

const PROMPT_PATH = path.resolve(__dirname, "../prompts/planner.md");

export function loadPlannerPrompt(): string {
  return fs.readFileSync(PROMPT_PATH, "utf-8");
}

interface ParsedTask {
  action: string;
  target?: string;
  content?: string;
}

function parseUserInput(input: string): ParsedTask {
  const lower = input.toLowerCase().trim();

  if (lower.startsWith("read ") || lower.startsWith("show ") || lower.startsWith("cat ")) {
    const target = input.replace(/^(read|show|cat)\s+/i, "").trim();
    return { action: "read", target };
  }

  if (lower.startsWith("write ") || lower.startsWith("create ")) {
    const parts = input.replace(/^(write|create)\s+/i, "").trim();
    const match = parts.match(/^(.+?)\s+with\s+content\s*[:\s]*(.+)$/is);
    if (match) {
      return { action: "write", target: match[1].trim(), content: match[2].trim() };
    }
    return { action: "write", target: parts };
  }

  if (lower.startsWith("fetch ") || lower.startsWith("get ") || lower.startsWith("curl ")) {
    const target = input.replace(/^(fetch|get|curl)\s+/i, "").trim();
    return { action: "fetch", target };
  }

  if (lower.startsWith("run ") || lower.startsWith("exec ") || lower.startsWith("shell ") || lower.startsWith("$")) {
    const command = input.replace(/^(run|exec|shell|\$)\s*/i, "").trim();
    return { action: "shell", target: command };
  }

  if (lower.startsWith("list tools") || lower === "tools") {
    return { action: "list_tools" };
  }

  if (lower.startsWith("memory") || lower.startsWith("remember")) {
    return { action: "memory", target: input };
  }

  // Default: treat as a multi-step task description
  return { action: "complex", target: input };
}

function generateId(): string {
  return `step_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
}

export function createPlan(userInput: string): TaskStep[] {
  const prompt = loadPlannerPrompt();
  logDecision("Planner", `Creating plan for: "${userInput}"`, `Using prompt: ${prompt.substring(0, 80)}...`);

  const mode = getExecutionMode();
  const tools = listTools();
  const availableToolNames = tools.map((t) => t.name);

  log(LogLevel.INFO, "PLANNER", `Mode: ${mode}, Available tools: ${availableToolNames.join(", ")}`);

  // Check for previous context in memory
  const previousResult = retrieveMemory("lastResult");
  if (previousResult) {
    log(LogLevel.DEBUG, "PLANNER", "Found previous result in memory for context");
  }

  const parsed = parseUserInput(userInput);
  const steps: TaskStep[] = [];

  switch (parsed.action) {
    case "read":
      steps.push({
        id: generateId(),
        description: `Read file: ${parsed.target}`,
        status: "pending",
        retries: 0,
      });
      // Store metadata for executor
      saveMemory(`plan:${steps[0].id}`, { tool: "read_file", args: { path: parsed.target } });
      break;

    case "write":
      if (!canPerformWrite()) {
        steps.push({
          id: generateId(),
          description: `[BLOCKED] Cannot write in ${mode} mode. Switch to ASSISTED or AUTONOMOUS mode first.`,
          status: "failed",
          error: `Write operations not allowed in ${mode} mode`,
          retries: 0,
        });
      } else {
        steps.push({
          id: generateId(),
          description: `Write file: ${parsed.target}`,
          status: "pending",
          retries: 0,
        });
        saveMemory(`plan:${steps[0].id}`, {
          tool: "write_file",
          args: { path: parsed.target, content: parsed.content || "" },
        });
      }
      break;

    case "fetch":
      steps.push({
        id: generateId(),
        description: `Fetch URL: ${parsed.target}`,
        status: "pending",
        retries: 0,
      });
      saveMemory(`plan:${steps[0].id}`, { tool: "fetch_url", args: { url: parsed.target } });
      break;

    case "shell":
      if (!canExecuteShell() || !isEnabled("allowShell")) {
        steps.push({
          id: generateId(),
          description: `[BLOCKED] Cannot execute shell commands. Mode: ${mode}, allowShell: ${isEnabled("allowShell")}`,
          status: "failed",
          error: "Shell execution not permitted",
          retries: 0,
        });
      } else {
        steps.push({
          id: generateId(),
          description: `Run command: ${parsed.target}`,
          status: "pending",
          retries: 0,
        });
        saveMemory(`plan:${steps[0].id}`, { tool: "run_shell_command", args: { command: parsed.target } });
      }
      break;

    case "list_tools":
      steps.push({
        id: generateId(),
        description: "List all registered tools",
        status: "pending",
        retries: 0,
      });
      saveMemory(`plan:${steps[0].id}`, { tool: "none", args: {} });
      break;

    case "memory":
      steps.push({
        id: generateId(),
        description: "Retrieve memory summary",
        status: "pending",
        retries: 0,
      });
      saveMemory(`plan:${steps[0].id}`, { tool: "none", args: { action: "summarize" } });
      break;

    case "complex":
    default:
      // Break complex input into read → process → report steps
      steps.push(
        {
          id: generateId(),
          description: `Analyze task: "${parsed.target}"`,
          status: "pending",
          retries: 0,
        },
        {
          id: generateId(),
          description: `Execute primary action for: "${parsed.target}"`,
          status: "pending",
          retries: 0,
        },
        {
          id: generateId(),
          description: "Compile and return result",
          status: "pending",
          retries: 0,
        }
      );

      // Store plan metadata
      steps.forEach((step) => {
        saveMemory(`plan:${step.id}`, { tool: "none", args: { task: parsed.target } });
      });
      break;
  }

  logDecision("Planner", `Plan created with ${steps.length} step(s)`, steps.map((s) => s.description).join(" → "));
  return steps;
}
