export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function readingTimeFromWordCount(wordCount: number): number {
  return Math.max(1, Math.round(wordCount / 200));
}

export function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}
