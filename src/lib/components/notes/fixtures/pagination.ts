export const COMPLEX_TABLE_FIXTURE = `
<h2>Complex table fixture</h2>
<table>
  <thead>
    <tr><th>Section</th><th>Metric</th><th>Value</th><th>Notes</th></tr>
  </thead>
  <tbody>
    ${Array.from({ length: 28 })
		.map(
			(_, idx) =>
				`<tr><td>Block ${idx + 1}</td><td>Latency</td><td>${12 + idx}ms</td><td>Row ${idx + 1} carries verbose text for pagination resilience checks.</td></tr>`
		)
		.join('')}
  </tbody>
</table>
`;

export const LONG_DOCUMENT_FIXTURE = `
<h1>Long document fixture</h1>
${Array.from({ length: 120 })
	.map(
		(_, idx) =>
			`<p>Paragraph ${idx + 1}. This is intentionally verbose prose with multiple clauses, comma-separated details, and stable token density to emulate export workloads under sustained pagination pressure.</p>`
	)
	.join('')}
`;

export const FOOTNOTE_FIXTURE = `
<h2>Footnotes fixture</h2>
${Array.from({ length: 40 })
	.map(
		(_, idx) =>
			`<p>Observation ${idx + 1} with citation marker <sup>${idx + 1}</sup>.</p>`
	)
	.join('')}
<hr data-page-break="section" />
<section class="footnotes">
${Array.from({ length: 40 })
	.map((_, idx) => `<p><sup>${idx + 1}</sup> Footnote detail ${idx + 1} with cross-reference text.</p>`)
	.join('')}
</section>
`;
