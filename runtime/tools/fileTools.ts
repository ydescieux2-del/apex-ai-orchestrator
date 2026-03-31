import * as fs from "fs";
import * as path from "path";
import { registerTool } from "./toolRegistry";

export function registerFileTools(): void {
  registerTool(
    "read_file",
    "Read the contents of a file at the given path",
    async (args) => {
      const filePath = args.path as string;
      if (!filePath) throw new Error("Missing required argument: path");

      const resolved = path.resolve(filePath);
      if (!fs.existsSync(resolved)) {
        throw new Error(`File not found: ${resolved}`);
      }

      const content = fs.readFileSync(resolved, "utf-8");
      return content;
    },
    { requiresWrite: false }
  );

  registerTool(
    "write_file",
    "Write content to a file at the given path",
    async (args) => {
      const filePath = args.path as string;
      const content = args.content as string;
      if (!filePath) throw new Error("Missing required argument: path");
      if (content === undefined) throw new Error("Missing required argument: content");

      const resolved = path.resolve(filePath);
      const dir = path.dirname(resolved);

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      fs.writeFileSync(resolved, content, "utf-8");
      return `File written successfully: ${resolved} (${Buffer.byteLength(content, "utf-8")} bytes)`;
    },
    { requiresWrite: true }
  );
}
