export type TextBlock = {
  text: string;
  maxWidth: number;
  fontSize: number;
  fontFamily?: string;
  lineHeight?: number;
};

export type MeasuredText = {
  width: number;
  height: number;
  lines: string[];
};

export type LayoutItem = {
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
