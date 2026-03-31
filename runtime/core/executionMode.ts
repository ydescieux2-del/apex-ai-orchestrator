export enum ExecutionMode {
  SAFE = "SAFE",
  ASSISTED = "ASSISTED",
  AUTONOMOUS = "AUTONOMOUS",
}

const MODE_PERMISSIONS: Record<ExecutionMode, { canRead: boolean; canWrite: boolean; canExecuteShell: boolean; requiresConfirmation: boolean }> = {
  [ExecutionMode.SAFE]: {
    canRead: true,
    canWrite: false,
    canExecuteShell: false,
    requiresConfirmation: false,
  },
  [ExecutionMode.ASSISTED]: {
    canRead: true,
    canWrite: true,
    canExecuteShell: true,
    requiresConfirmation: true,
  },
  [ExecutionMode.AUTONOMOUS]: {
    canRead: true,
    canWrite: true,
    canExecuteShell: true,
    requiresConfirmation: false,
  },
};

let currentMode: ExecutionMode = ExecutionMode.SAFE;

export function setExecutionMode(mode: ExecutionMode): void {
  currentMode = mode;
}

export function getExecutionMode(): ExecutionMode {
  return currentMode;
}

export function getPermissions() {
  return MODE_PERMISSIONS[currentMode];
}

export function canPerformWrite(): boolean {
  return MODE_PERMISSIONS[currentMode].canWrite;
}

export function canExecuteShell(): boolean {
  return MODE_PERMISSIONS[currentMode].canExecuteShell;
}

export function requiresConfirmation(): boolean {
  return MODE_PERMISSIONS[currentMode].requiresConfirmation;
}
