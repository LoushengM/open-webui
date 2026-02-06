// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { buildLayoutPages } from '../pageLayout';
import {
	COMPLEX_TABLE_FIXTURE,
	FOOTNOTE_FIXTURE,
	LONG_DOCUMENT_FIXTURE
} from '../fixtures/pagination';

describe('layout pagination fixtures', () => {
	it('keeps complex tables paginated into multiple pages', () => {
		const pages = buildLayoutPages({
			title: 'Complex Table',
			html: COMPLEX_TABLE_FIXTURE
		});
		expect(pages.length).toBeGreaterThan(1);
		expect(pages[0].bodyHtml).toContain('<table>');
	});

	it('generates stable running headers and footers for long documents', () => {
		const pages = buildLayoutPages({
			title: 'Long Form',
			html: LONG_DOCUMENT_FIXTURE
		});
		expect(pages.length).toBeGreaterThan(2);
		expect(pages[0].headerHtml).toContain('Long Form');
		expect(pages.at(-1)?.footerHtml).toContain(`${pages.length}`);
	});

	it('respects section breaks for footnote sections', () => {
		const pages = buildLayoutPages({
			title: 'Footnotes',
			html: FOOTNOTE_FIXTURE
		});
		expect(pages.length).toBeGreaterThan(1);
		expect(pages.some((page) => page.bodyHtml.includes('footnotes'))).toBeTruthy();
	});
});
