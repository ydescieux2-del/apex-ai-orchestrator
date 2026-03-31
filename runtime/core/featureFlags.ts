import * as fs from "fs";
import * as path from "path";

export interface FeatureFlags {
  enableTools: boolean;
  allowShell: boolean;
  useMemory: boolean;
  autoExecute: boolean;
}

const CONFIG_PATH = path.resolve(__dirname, "../config/config.json");

let flags: FeatureFlags = {
  enableTools: true,
  allowShell: false,
  useMemory: true,
  autoExecute: false,
};

export function loadFeatureFlags(): FeatureFlags {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
    const config = JSON.parse(raw);
    if (config.featureFlags) {
      flags = { ...flags, ...config.featureFlags };
    }
  } catch {
    // Use defaults if config not found
  }
  return flags;
}

export function getFeatureFlags(): FeatureFlags {
  return { ...flags };
}

export function setFeatureFlag<K extends keyof FeatureFlags>(key: K, value: FeatureFlags[K]): void {
  flags[key] = value;
  persistFlags();
}

export function isEnabled(key: keyof FeatureFlags): boolean {
  return flags[key];
}

function persistFlags(): void {
  try {
    let config: Record<string, unknown> = {};
    try {
      const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
      config = JSON.parse(raw);
    } catch {
      // Start fresh
    }
    config.featureFlags = flags;
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), "utf-8");
  } catch {
    // Silent fail on write
  }
}
