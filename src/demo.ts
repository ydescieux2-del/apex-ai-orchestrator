import type { TextBlock } from "./types";
import { computeVerticalLayout, computeHorizontalLayout } from "./layoutEngine";
import { generateEmailLayout } from "./templateEngine";

// --- Vertical Layout ---
const verticalBlocks: TextBlock[] = [
  { text: "Magnus Premium", maxWidth: 300, fontSize: 32 },
  { text: "The best part of waking up is Magnus in your blunt", maxWidth: 300, fontSize: 18 },
  { text: "Shop Now", maxWidth: 300, fontSize: 20 },
];

console.log("=== Vertical Layout ===");
console.log(JSON.stringify(computeVerticalLayout(verticalBlocks), null, 2));

// --- Horizontal Layout ---
const horizontalBlocks: TextBlock[] = [
  { text: "Column A", maxWidth: 150, fontSize: 16 },
  { text: "Column B", maxWidth: 150, fontSize: 16 },
  { text: "Column C", maxWidth: 150, fontSize: 16 },
];

console.log("\n=== Horizontal Layout ===");
console.log(JSON.stringify(computeHorizontalLayout(horizontalBlocks, 20), null, 2));

// --- Email Template ---
const emailLayout = generateEmailLayout({
  companyName: "DataTech Disposition",
  headline: "Certified IT Asset Disposition You Can Trust",
  body: "We provide secure, compliant electronics recycling with full chain-of-custody documentation. R2 and e-Stewards certified.",
  cta: "Schedule a Free Pickup",
  maxWidth: 600,
});

console.log("\n=== Email Template Layout ===");
console.log(JSON.stringify(emailLayout, null, 2));
