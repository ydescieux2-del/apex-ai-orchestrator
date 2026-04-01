import type { TextBlock, LayoutItem } from "./types";
import { computeVerticalLayout } from "./layoutEngine";

export type EmailTemplateConfig = {
  companyName: string;
  headline: string;
  body: string;
  cta: string;
  maxWidth?: number;
};

export type EmailLayout = {
  items: LayoutItem[];
  totalWidth: number;
  totalHeight: number;
  config: EmailTemplateConfig;
};

export function generateEmailLayout(config: EmailTemplateConfig): EmailLayout {
  const maxWidth = config.maxWidth ?? 600;

  const blocks: TextBlock[] = [
    { text: config.companyName, maxWidth, fontSize: 14, fontFamily: "Arial" },
    { text: config.headline, maxWidth, fontSize: 28, fontFamily: "Arial" },
    { text: config.body, maxWidth, fontSize: 16, fontFamily: "Arial" },
    { text: config.cta, maxWidth, fontSize: 18, fontFamily: "Arial" },
  ];

  const items = computeVerticalLayout(blocks, 16);

  let totalWidth = 0;
  let totalHeight = 0;
  for (const item of items) {
    totalWidth = Math.max(totalWidth, item.x + item.width);
    totalHeight = Math.max(totalHeight, item.y + item.height);
  }

  return { items, totalWidth, totalHeight, config };
}
