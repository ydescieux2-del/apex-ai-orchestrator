import { logToolCall, log, LogLevel } from "../logs/logger";
import { getExecutionMode, canPerformWrite, canExecuteShell, requiresConfirmation } from "../core/executionMode";
import { isEnabled } from "../core/featureFlags";

export type ToolHandler = (args: Record<string, unknown>) => Promise<string>;

export interface ToolDefinition {
  name: string;
  description: string;
  requiresWrite: boolean;
  requiresShell: boolean;
  handler: ToolHandler;
}

const registry: Map<string, ToolDefinition> = new Map();

export function registerTool(
  name: string,
  description: string,
  handler: ToolHandler,
  options: { requiresWrite?: boolean; requiresShell?: boolean } = {}
): void {
  registry.set(name, {
    name,
    description,
    requiresWrite: options.requiresWrite ?? false,
    requiresShell: options.requiresShell ?? false,
    handler,
  });
  log(LogLevel.DEBUG, "TOOLS", `Registered tool: ${name}`);
}

export async function executeTool(name: string, args: Record<string, unknown>): Promise<string> {
  if (!isEnabled("enableTools")) {
    throw new Error("Tool execution is disabled via feature flags");
  }

  const tool = registry.get(name);
  if (!tool) {
    throw new Error(`Tool not found: ${name}`);
  }

  // Enforce execution mode permissions
  if (tool.requiresWrite && !canPerformWrite()) {
    throw new Error(
      `Tool "${name}" requires write permission, but current mode is ${getExecutionMode()}. Switch to ASSISTED or AUTONOMOUS mode.`
    );
  }

  if (tool.requiresShell) {
    if (!canExecuteShell()) {
      throw new Error(
        `Tool "${name}" requires shell execution, but current mode is ${getExecutionMode()}. Switch to ASSISTED or AUTONOMOUS mode.`
      );
    }
    if (!isEnabled("allowShell")) {
      throw new Error(`Tool "${name}" requires shell execution, but allowShell feature flag is disabled.`);
    }
  }

  // Check confirmation requirement
  if (requiresConfirmation() && (tool.requiresWrite || tool.requiresShell)) {
    log(LogLevel.WARN, "TOOLS", `ASSISTED mode: Tool "${name}" requires confirmation. Proceeding with logged confirmation.`, { args });
  }

  const startTime = Date.now();
  try {
    const result = await tool.handler(args);
    const duration = Date.now() - startTime;
    logToolCall(name, args, result, duration);
    return result;
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMsg = error instanceof Error ? error.message : String(error);
    logToolCall(name, args, { error: errorMsg }, duration);
    throw error;
  }
}

export function listTools(): ToolDefinition[] {
  return Array.from(registry.values());
}

export function getTool(name: string): ToolDefinition | undefined {
  return registry.get(name);
}
