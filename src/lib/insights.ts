import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { remark } from "remark";
import remarkGfm from "remark-gfm";
import remarkHtml from "remark-html";
import { readingTimeFromText } from "./utils";
import type { Insight, InsightMeta } from "@/types";

const CONTENT_DIR = path.join(process.cwd(), "content", "insights");

function slugFromFile(fileName: string) {
  return fileName.replace(/\.md$/, "");
}

function extractHeadings(markdown: string) {
  const lines = markdown.split("\n");
  const headings: { id: string; text: string; depth: number }[] = [];
  for (const line of lines) {
    const match = /^(#{2,3})\s+(.*)$/.exec(line.trim());
    if (match) {
      const depth = match[1].length;
      const text = match[2].trim();
      const id = text
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .trim()
        .replace(/\s+/g, "-");
      headings.push({ id, text, depth });
    }
  }
  return headings;
}

function injectHeadingIds(html: string, headings: { id: string; text: string; depth: number }[]) {
  let index = 0;
  return html.replace(/<h([23])>/g, (match, level) => {
    const heading = headings[index];
    index += 1;
    if (!heading) return match;
    return `<h${level} id="${heading.id}">`;
  });
}

export function getAllInsightsMeta(): InsightMeta[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  const files = fs.readdirSync(CONTENT_DIR).filter((file) => file.endsWith(".md"));

  const items = files.map((file) => {
    const raw = fs.readFileSync(path.join(CONTENT_DIR, file), "utf-8");
    const { data, content } = matter(raw);
    return {
      slug: slugFromFile(file),
      title: data.title as string,
      description: data.description as string,
      category: data.category as string,
      author: data.author as string,
      publishedAt: data.publishedAt as string,
      modifiedAt: (data.modifiedAt as string) ?? (data.publishedAt as string),
      readingTime: readingTimeFromText(content),
    } satisfies InsightMeta;
  });

  return items.sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );
}

export async function getInsightBySlug(slug: string): Promise<Insight | null> {
  const filePath = path.join(CONTENT_DIR, `${slug}.md`);
  if (!fs.existsSync(filePath)) return null;

  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);

  const processed = await remark().use(remarkGfm).use(remarkHtml).process(content);
  const headings = extractHeadings(content);
  const contentHtml = injectHeadingIds(processed.toString(), headings);

  return {
    slug,
    title: data.title as string,
    description: data.description as string,
    category: data.category as string,
    author: data.author as string,
    publishedAt: data.publishedAt as string,
    modifiedAt: (data.modifiedAt as string) ?? (data.publishedAt as string),
    readingTime: readingTimeFromText(content),
    contentHtml,
    headings,
  };
}

export function getRelatedInsights(slug: string, category: string, limit = 3): InsightMeta[] {
  return getAllInsightsMeta()
    .filter((item) => item.slug !== slug && item.category === category)
    .slice(0, limit);
}
