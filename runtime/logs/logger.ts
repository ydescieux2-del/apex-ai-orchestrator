import * as fs from "fs";
import * as path from "path";

export enum LogLevel {
  DEBUG = "DEBUG",
  INFO = "INFO",
  WARN = "WARN",
  ERROR = "ERROR",
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  category: string;
  message: string;
  data?: unknown;
  durationMs?: number;
}

const LOG_FILE = path.resolve(__dirname, "sessionLogs.json");

let sessionLogs: LogEntry[] = [];

function loadLogs(): void {
  try {
    const raw = fs.readFileSync(LOG_FILE, "utf-8");
    sessionLogs = JSON.parse(raw);
  } catch {
    sessionLogs = [];
  }
}

function persistLogs(): void {
  fs.writeFileSync(LOG_FILE, JSON.stringify(sessionLogs, null, 2), "utf-8");
}

export function log(level: LogLevel, category: string, message: string, data?: unknown): void {
  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    category,
    message,
    data,
  };
  sessionLogs.push(entry);
  persistLogs();

  const prefix = `[${entry.timestamp}] [${level}] [${category}]`;
  if (level === LogLevel.ERROR) {
    console.error(`${prefix} ${message}`, data ?? "");
  } else if (level === LogLevel.WARN) {
    console.warn(`${prefix} ${message}`, data ?? "");
  } else {
    console.log(`${prefix} ${message}`, data !== undefined ? data : "");
  }
}

export function logToolCall(toolName: string, args: unknown, result: unknown, durationMs: number): void {
  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level: LogLevel.INFO,
    category: "TOOL",
    message: `Executed tool: ${toolName}`,
    data: { args, result: typeof result === "string" ? result.substring(0, 500) : result },
    durationMs,
  };
  sessionLogs.push(entry);
  persistLogs();
  console.log(`[TOOL] ${toolName} completed in ${durationMs}ms`);
}

export function logDecision(agent: string, decision: string, reasoning?: string): void {
  log(LogLevel.INFO, `DECISION:${agent}`, decision, reasoning ? { reasoning } : undefined);
}

export function getSessionLogs(): LogEntry[] {
  return [...sessionLogs];
}

export function clearSessionLogs(): void {
  sessionLogs = [];
  persistLogs();
}

// Load existing logs on import
loadLogs();
