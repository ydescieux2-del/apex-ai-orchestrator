import type { TextBlock } from "./types";
import { computeVerticalLayout } from "./layoutEngine";

const blocks: TextBlock[] = [
  { text: "Magnus Premium", maxWidth: 300, fontSize: 32 },
  { text: "The best part of waking up is Magnus in your blunt", maxWidth: 300, fontSize: 18 },
  { text: "Shop Now", maxWidth: 300, fontSize: 20 },
];

const layout = computeVerticalLayout(blocks);

console.log(JSON.stringify(layout, null, 2));
