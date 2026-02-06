import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { marked } from 'marked';

const SLOS = {
  typingLatencyMsP95: 24,
  initialLoadMsP95: 1200,
  mdToHtmlMsP95: 160,
  htmlToMdApproxMsP95: 120
};

const fixtureDir = path.resolve('benchmarks/fixtures');
const fixtures = fs.readdirSync(fixtureDir).filter((name) => name.endsWith('.md'));

const percentile = (arr, p) => {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[idx];
};

const htmlToMdApprox = (html) => html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

const report = [];
for (const fixture of fixtures) {
  const md = fs.readFileSync(path.join(fixtureDir, fixture), 'utf8');
  const mdToHtmlRuns = [];
  const htmlToMdRuns = [];

  for (let i = 0; i < 20; i += 1) {
    const start1 = performance.now();
    const html = marked.parse(md, { breaks: false });
    mdToHtmlRuns.push(performance.now() - start1);

    const start2 = performance.now();
    htmlToMdApprox(html);
    htmlToMdRuns.push(performance.now() - start2);
  }

  report.push({
    fixture,
    sizeChars: md.length,
    mdToHtmlP95: percentile(mdToHtmlRuns, 95),
    htmlToMdApproxP95: percentile(htmlToMdRuns, 95)
  });
}

console.table(report);

let failed = false;
for (const row of report) {
  if (row.mdToHtmlP95 > SLOS.mdToHtmlMsP95 || row.htmlToMdApproxP95 > SLOS.htmlToMdApproxMsP95) {
    failed = true;
  }
}

if (failed) {
  console.error('Benchmark SLO regression detected.', SLOS);
  process.exit(1);
}

console.log('Benchmark SLOs satisfied.', SLOS);
