import { registerTool } from "./toolRegistry";

export function registerWebTools(): void {
  registerTool(
    "fetch_url",
    "Fetch the content of a URL via HTTP GET",
    async (args) => {
      const url = args.url as string;
      if (!url) throw new Error("Missing required argument: url");

      // Validate URL format
      try {
        new URL(url);
      } catch {
        throw new Error(`Invalid URL: ${url}`);
      }

      // Use dynamic import for node-fetch (CommonJS compatibility)
      const fetch = (await import("node-fetch")).default;

      const response = await fetch(url, {
        headers: {
          "User-Agent": "ApexAI-Runtime/1.0",
        },
        timeout: 10000,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const json = await response.json();
        return JSON.stringify(json, null, 2);
      }

      const text = await response.text();
      // Truncate very large responses
      if (text.length > 50000) {
        return text.substring(0, 50000) + "\n\n[Truncated — response exceeded 50KB]";
      }
      return text;
    },
    { requiresWrite: false }
  );
}
