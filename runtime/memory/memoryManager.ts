import * as fs from "fs";
import * as path from "path";
import { log, LogLevel } from "../logs/logger";
import { isEnabled } from "../core/featureFlags";

const SHORT_TERM_PATH = path.resolve(__dirname, "shortTerm.json");
const LONG_TERM_PATH = path.resolve(__dirname, "longTerm.json");

interface MemoryStore {
  [key: string]: unknown;
}

let shortTermMemory: MemoryStore = {};
let longTermMemory: MemoryStore = {};

function loadStore(filePath: string): MemoryStore {
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function persistStore(filePath: string, store: MemoryStore): void {
  fs.writeFileSync(filePath, JSON.stringify(store, null, 2), "utf-8");
}

export function initMemory(): void {
  shortTermMemory = {};
  longTermMemory = loadStore(LONG_TERM_PATH);
  persistStore(SHORT_TERM_PATH, shortTermMemory);
  log(LogLevel.INFO, "MEMORY", "Memory system initialized");
}

export function saveMemory(key: string, value: unknown, persistent: boolean = false): void {
  if (!isEnabled("useMemory")) {
    log(LogLevel.WARN, "MEMORY", "Memory system disabled via feature flags");
    return;
  }

  if (persistent) {
    longTermMemory[key] = value;
    persistStore(LONG_TERM_PATH, longTermMemory);
    log(LogLevel.DEBUG, "MEMORY", `Saved to long-term: ${key}`);
  } else {
    shortTermMemory[key] = value;
    persistStore(SHORT_TERM_PATH, shortTermMemory);
    log(LogLevel.DEBUG, "MEMORY", `Saved to short-term: ${key}`);
  }
}

export function retrieveMemory(key: string): unknown | undefined {
  if (!isEnabled("useMemory")) {
    return undefined;
  }

  // Check short-term first, then long-term
  if (key in shortTermMemory) {
    return shortTermMemory[key];
  }
  if (key in longTermMemory) {
    return longTermMemory[key];
  }
  return undefined;
}

export function getAllShortTermMemory(): MemoryStore {
  return { ...shortTermMemory };
}

export function getAllLongTermMemory(): MemoryStore {
  return { ...longTermMemory };
}

export function summarizeSession(): string {
  const shortTermKeys = Object.keys(shortTermMemory);
  const longTermKeys = Object.keys(longTermMemory);

  const summary = [
    `Session Memory Summary:`,
    `  Short-term entries: ${shortTermKeys.length}`,
    shortTermKeys.length > 0 ? `    Keys: ${shortTermKeys.join(", ")}` : "",
    `  Long-term entries: ${longTermKeys.length}`,
    longTermKeys.length > 0 ? `    Keys: ${longTermKeys.join(", ")}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  log(LogLevel.INFO, "MEMORY", "Session summarized");
  return summary;
}

export function clearShortTermMemory(): void {
  shortTermMemory = {};
  persistStore(SHORT_TERM_PATH, shortTermMemory);
}
