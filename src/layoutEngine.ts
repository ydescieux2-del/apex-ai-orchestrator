import type { TextBlock, LayoutItem } from "./types";
import { measureTextBlock } from "./textEngine";

export function computeVerticalLayout(
  blocks: TextBlock[],
  spacing: number = 10
): LayoutItem[] {
  const items: LayoutItem[] = [];
  let runningY = 0;

  for (const block of blocks) {
    const measured = measureTextBlock(block);

    items.push({
      text: block.text,
      x: 0,
      y: runningY,
      width: measured.width,
      height: measured.height,
    });

    runningY += measured.height + spacing;
  }

  return items;
}
