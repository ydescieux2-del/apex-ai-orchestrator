import { createCanvas, type SKRSContext2D } from "@napi-rs/canvas";
import type { TextBlock, MeasuredText } from "./types";

function createMeasureContext(fontSize: number, fontFamily: string): SKRSContext2D {
  const canvas = createCanvas(1, 1);
  const ctx = canvas.getContext("2d");
  ctx.font = `${fontSize}px ${fontFamily}`;
  return ctx;
}

function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function wrapText(
  ctx: SKRSContext2D,
  text: string,
  maxWidth: number
): string[] {
  const normalized = normalizeWhitespace(text);

  if (normalized === "") {
    return [];
  }

  const words = normalized.split(" ");
  const lines: string[] = [];
  let currentLine = "";

  for (const word of words) {
    const wordWidth = ctx.measureText(word).width;

    // Single word longer than maxWidth — force it onto its own line
    if (wordWidth > maxWidth && currentLine === "") {
      lines.push(word);
      continue;
    }

    const testLine = currentLine === "" ? word : `${currentLine} ${word}`;
    const testWidth = ctx.measureText(testLine).width;

    if (testWidth > maxWidth && currentLine !== "") {
      lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = testLine;
    }
  }

  if (currentLine !== "") {
    lines.push(currentLine);
  }

  return lines;
}

export function measureTextBlock(block: TextBlock): MeasuredText {
  const fontFamily = block.fontFamily ?? "Arial";
  const lineHeight = block.lineHeight ?? block.fontSize * 1.2;
  const ctx = createMeasureContext(block.fontSize, fontFamily);

  const lines = wrapText(ctx, block.text, block.maxWidth);

  if (lines.length === 0) {
    return { width: 0, height: 0, lines: [] };
  }

  let maxWidth = 0;
  for (const line of lines) {
    const measured = ctx.measureText(line).width;
    if (measured > maxWidth) {
      maxWidth = measured;
    }
  }

  const height = lines.length * lineHeight;

  return {
    width: Math.ceil(maxWidth * 100) / 100,
    height: Math.ceil(height * 100) / 100,
    lines,
  };
}
