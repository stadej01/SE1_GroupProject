/** Convert inclusive, one-based source lines into textarea UTF-16 offsets. */
export function sourceRange(source: string, startLine: number, endLine = startLine) {
  const lines = source.split("\n");
  const first = Math.max(0, Math.min(lines.length - 1, startLine - 1));
  const last = Math.max(first, Math.min(lines.length - 1, endLine - 1));
  let start = 0;
  for (let i = 0; i < first; i++) start += lines[i].length + 1;
  const end = start + lines.slice(first, last + 1).join("\n").length;
  return { start, end };
}
