export interface TaskStep {
  id: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  result?: string;
  error?: string;
  retries: number;
}

export interface ExecutionState {
  sessionId: string;
  userInput: string;
  plan: TaskStep[];
  currentStepIndex: number;
  status: "idle" | "planning" | "executing" | "debugging" | "completed" | "failed";
  startTime: number;
  endTime?: number;
}

let state: ExecutionState = createInitialState("");

function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
}

export function createInitialState(userInput: string): ExecutionState {
  return {
    sessionId: generateSessionId(),
    userInput,
    plan: [],
    currentStepIndex: 0,
    status: "idle",
    startTime: Date.now(),
  };
}

export function getState(): ExecutionState {
  return state;
}

export function setState(newState: ExecutionState): void {
  state = newState;
}

export function updateStatus(status: ExecutionState["status"]): void {
  state.status = status;
}

export function setPlan(steps: TaskStep[]): void {
  state.plan = steps;
  state.currentStepIndex = 0;
}

export function getCurrentStep(): TaskStep | undefined {
  return state.plan[state.currentStepIndex];
}

export function advanceStep(): void {
  if (state.currentStepIndex < state.plan.length - 1) {
    state.currentStepIndex++;
  }
}

export function markStepCompleted(result: string): void {
  const step = getCurrentStep();
  if (step) {
    step.status = "completed";
    step.result = result;
  }
}

export function markStepFailed(error: string): void {
  const step = getCurrentStep();
  if (step) {
    step.status = "failed";
    step.error = error;
    step.retries++;
  }
}

export function isAllStepsCompleted(): boolean {
  return state.plan.every((s) => s.status === "completed");
}

export function finalizeState(): void {
  state.endTime = Date.now();
  state.status = isAllStepsCompleted() ? "completed" : "failed";
}
