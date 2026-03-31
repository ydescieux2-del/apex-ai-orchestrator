import * as fs from "fs";
import * as path from "path";
import {
  createInitialState,
  setState,
  getState,
  updateStatus,
  setPlan,
  getCurrentStep,
  advanceStep,
  markStepCompleted,
  markStepFailed,
  isAllStepsCompleted,
  finalizeState,
  ExecutionState,
} from "./stateManager";
import { getExecutionMode, ExecutionMode, setExecutionMode } from "./executionMode";
import { loadFeatureFlags } from "./featureFlags";
import { createPlan } from "../agents/planner";
import { executeStep } from "../agents/executor";
import { diagnose } from "../agents/debugger";
import { log, LogLevel, logDecision } from "../logs/logger";
import { initMemory, saveMemory, summarizeSession } from "../memory/memoryManager";

const SYSTEM_PROMPT_PATH = path.resolve(__dirname, "../prompts/system.md");

export interface OrchestratorResult {
  success: boolean;
  sessionId: string;
  results: string[];
  errors: string[];
  durationMs: number;
  memorySummary: string;
}

function loadSystemPrompt(): string {
  return fs.readFileSync(SYSTEM_PROMPT_PATH, "utf-8");
}

export async function runOrchestrator(userInput: string): Promise<OrchestratorResult> {
  // Initialize
  const systemPrompt = loadSystemPrompt();
  loadFeatureFlags();
  initMemory();

  log(LogLevel.INFO, "ORCHESTRATOR", `System prompt loaded (${systemPrompt.length} chars)`);
  log(LogLevel.INFO, "ORCHESTRATOR", `Starting new session for input: "${userInput}"`);
  log(LogLevel.INFO, "ORCHESTRATOR", `Execution mode: ${getExecutionMode()}`);

  const state = createInitialState(userInput);
  setState(state);

  const results: string[] = [];
  const errors: string[] = [];

  // Phase 1: Planning
  updateStatus("planning");
  logDecision("Orchestrator", "Entering planning phase");

  let plan;
  try {
    plan = createPlan(userInput);
    setPlan(plan);
    saveMemory("currentPlan", plan.map((s) => s.description));
    log(LogLevel.INFO, "ORCHESTRATOR", `Plan created with ${plan.length} steps`);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log(LogLevel.ERROR, "ORCHESTRATOR", `Planning failed: ${msg}`);
    updateStatus("failed");
    return {
      success: false,
      sessionId: state.sessionId,
      results: [],
      errors: [`Planning failed: ${msg}`],
      durationMs: Date.now() - state.startTime,
      memorySummary: summarizeSession(),
    };
  }

  // Check for pre-failed steps (e.g., blocked by execution mode)
  const preFailed = plan.filter((s) => s.status === "failed");
  if (preFailed.length > 0) {
    preFailed.forEach((s) => {
      errors.push(s.error || s.description);
      log(LogLevel.WARN, "ORCHESTRATOR", `Pre-blocked step: ${s.description}`);
    });

    if (preFailed.length === plan.length) {
      finalizeState();
      return {
        success: false,
        sessionId: state.sessionId,
        results: [],
        errors,
        durationMs: Date.now() - state.startTime,
        memorySummary: summarizeSession(),
      };
    }
  }

  // Phase 2: Execution
  updateStatus("executing");
  logDecision("Orchestrator", "Entering execution phase");

  for (let i = 0; i < plan.length; i++) {
    const step = plan[i];

    // Skip pre-failed steps
    if (step.status === "failed") {
      continue;
    }

    log(LogLevel.INFO, "ORCHESTRATOR", `Executing step ${i + 1}/${plan.length}: ${step.description}`);

    try {
      const result = await executeStep(step);
      markStepCompleted(result);
      results.push(result);
      log(LogLevel.INFO, "ORCHESTRATOR", `Step ${i + 1} completed successfully`);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      markStepFailed(errorMsg);

      // Phase 3: Debugging
      updateStatus("debugging");
      logDecision("Orchestrator", "Entering debugging phase", errorMsg);

      const debugResult = diagnose(step);

      switch (debugResult.action) {
        case "RETRY":
          log(LogLevel.INFO, "ORCHESTRATOR", `Retrying step ${i + 1}: ${debugResult.reason}`);
          step.status = "pending";
          step.error = undefined;
          i--; // Retry same index
          updateStatus("executing");
          break;

        case "ADJUST":
          log(LogLevel.INFO, "ORCHESTRATOR", `Adjusting step ${i + 1}: ${debugResult.reason}`);
          if (debugResult.adjustedStep) {
            Object.assign(step, debugResult.adjustedStep);
          }
          i--; // Retry with adjusted step
          updateStatus("executing");
          break;

        case "ABORT":
          log(LogLevel.ERROR, "ORCHESTRATOR", `Aborting: ${debugResult.reason}`);
          errors.push(debugResult.reason);
          break;
      }
    }
  }

  // Finalize
  finalizeState();
  const finalState = getState();

  const memorySummary = summarizeSession();
  saveMemory("lastSessionResult", { success: isAllStepsCompleted(), results, errors }, true);

  log(LogLevel.INFO, "ORCHESTRATOR", `Session ${finalState.sessionId} completed. Status: ${finalState.status}`);

  return {
    success: isAllStepsCompleted(),
    sessionId: finalState.sessionId,
    results,
    errors,
    durationMs: Date.now() - finalState.startTime,
    memorySummary,
  };
}

export { setExecutionMode, ExecutionMode };
