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

export function computeHorizontalLayout(
  blocks: TextBlock[],
  spacing: number = 10,
  containerWidth?: number
): LayoutItem[] {
  const items: LayoutItem[] = [];
  let runningX = 0;
  let runningY = 0;
  let rowHeight = 0;

  for (const block of blocks) {
    const measured = measureTextBlock(block);

    // Wrap to next row if we exceed container width
    if (containerWidth && runningX > 0 && runningX + measured.width > containerWidth) {
      runningX = 0;
      runningY += rowHeight + spacing;
      rowHeight = 0;
    }

    items.push({
      text: block.text,
      x: runningX,
      y: runningY,
      width: measured.width,
      height: measured.height,
    });

    runningX += measured.width + spacing;
    rowHeight = Math.max(rowHeight, measured.height);
  }

  return items;
}
