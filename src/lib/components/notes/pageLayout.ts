export type PaperSize = 'a4' | 'letter' | 'legal';

export type LayoutMarginsMm = {
	top: number;
	right: number;
	bottom: number;
	left: number;
};

export type PageLayoutConfig = {
	paperSize: PaperSize;
	orientation: 'portrait' | 'landscape';
	marginsMm: LayoutMarginsMm;
	headerHeightMm: number;
	footerHeightMm: number;
	sectionBreakSelector: string;
	headerTemplate: string;
	footerTemplate: string;
};

export type LayoutPage = {
	index: number;
	headerHtml: string;
	bodyHtml: string;
	footerHtml: string;
};

const PAPER_SIZES_MM: Record<PaperSize, { width: number; height: number }> = {
	a4: { width: 210, height: 297 },
	letter: { width: 216, height: 279 },
	legal: { width: 216, height: 356 }
};

const MM_TO_PX = 3.7795275591;

export const DEFAULT_PAGE_LAYOUT_CONFIG: PageLayoutConfig = {
	paperSize: 'a4',
	orientation: 'portrait',
	marginsMm: {
		top: 18,
		right: 16,
		bottom: 18,
		left: 16
	},
	headerHeightMm: 14,
	footerHeightMm: 14,
	sectionBreakSelector: '[data-section-break="true"], .section-break, hr[data-page-break="section"]',
	headerTemplate: '<div class="layout-running-header">{title}</div>',
	footerTemplate:
		'<div class="layout-running-footer"><span>{pageNumber}</span><span class="layout-footer-divider">/</span><span>{totalPages}</span></div>'
};

export const resolvePageSizeMm = (config: PageLayoutConfig) => {
	const base = PAPER_SIZES_MM[config.paperSize];
	return config.orientation === 'landscape'
		? { width: base.height, height: base.width }
		: { ...base };
};

const estimateNodeHeightPx = (node: HTMLElement, pageContentWidthPx: number) => {
	const tag = node.tagName.toLowerCase();
	const text = (node.textContent ?? '').trim();
	const textLength = text.length;

	if (tag === 'hr') return 24;
	if (tag === 'table') {
		const rows = node.querySelectorAll('tr').length || 1;
		const columns = node.querySelectorAll('tr:first-child > *').length || 1;
		return 36 + rows * 24 + columns * 6;
	}
	if (tag === 'blockquote') return 44 + Math.ceil(textLength / 90) * 18;
	if (tag === 'pre' || tag === 'code') return 40 + Math.ceil(textLength / 65) * 16;
	if (tag === 'h1') return 52;
	if (tag === 'h2') return 44;
	if (tag === 'h3') return 40;
	if (tag === 'ul' || tag === 'ol') {
		const items = node.querySelectorAll('li').length || 1;
		return 18 + items * 24;
	}
	if (node.getAttribute('data-section-break') === 'true' || node.classList.contains('section-break')) {
		return 0;
	}

	const approxCharsPerLine = Math.max(30, Math.floor(pageContentWidthPx / 8));
	const lines = Math.max(1, Math.ceil(textLength / approxCharsPerLine));
	return 20 + lines * 18;
};

const applyTemplate = (template: string, tokens: Record<string, string | number>) => {
	return Object.entries(tokens).reduce(
		(output, [key, value]) => output.replaceAll(`{${key}}`, `${value}`),
		template
	);
};

export const mergePageLayoutConfig = (overrides: Partial<PageLayoutConfig> = {}): PageLayoutConfig => ({
	...DEFAULT_PAGE_LAYOUT_CONFIG,
	...overrides,
	marginsMm: {
		...DEFAULT_PAGE_LAYOUT_CONFIG.marginsMm,
		...(overrides.marginsMm ?? {})
	}
});

export const buildLayoutPages = ({
	title,
	html,
	config
}: {
	title: string;
	html: string;
	config?: Partial<PageLayoutConfig>;
}): LayoutPage[] => {
	const mergedConfig = mergePageLayoutConfig(config);
	const pageSizeMm = resolvePageSizeMm(mergedConfig);
	const bodyHeightMm =
		pageSizeMm.height -
		mergedConfig.marginsMm.top -
		mergedConfig.marginsMm.bottom -
		mergedConfig.headerHeightMm -
		mergedConfig.footerHeightMm;
	const bodyWidthMm = pageSizeMm.width - mergedConfig.marginsMm.left - mergedConfig.marginsMm.right;

	const pageBodyHeightPx = Math.max(240, bodyHeightMm * MM_TO_PX);
	const pageBodyWidthPx = Math.max(300, bodyWidthMm * MM_TO_PX);

	if (typeof window === 'undefined') {
		return [
			{
				index: 0,
				headerHtml: mergedConfig.headerTemplate,
				bodyHtml: html,
				footerHtml: mergedConfig.footerTemplate
			}
		];
	}

	const parser = new DOMParser();
	const documentNode = parser.parseFromString(`<div>${html}</div>`, 'text/html');
	const nodes = Array.from(documentNode.body.firstElementChild?.children ?? []) as HTMLElement[];
	const pages: { blocks: string[] }[] = [{ blocks: [] }];
	let currentPageHeightPx = 0;

	for (const node of nodes) {
		const isSectionBreak =
			node.matches(mergedConfig.sectionBreakSelector) ||
			node.getAttribute('data-section-break') === 'true' ||
			node.classList.contains('section-break');

		if (isSectionBreak) {
			if (pages[pages.length - 1].blocks.length > 0) {
				pages.push({ blocks: [] });
				currentPageHeightPx = 0;
			}
			continue;
		}

		const nodeHeightPx = estimateNodeHeightPx(node, pageBodyWidthPx);
		if (currentPageHeightPx + nodeHeightPx > pageBodyHeightPx && pages[pages.length - 1].blocks.length > 0) {
			pages.push({ blocks: [] });
			currentPageHeightPx = 0;
		}

		pages[pages.length - 1].blocks.push(node.outerHTML);
		currentPageHeightPx += nodeHeightPx;
	}

	if (pages.length === 0) {
		pages.push({ blocks: [html] });
	}

	return pages.map((page, index) => {
		const tokens = {
			title,
			pageNumber: index + 1,
			totalPages: pages.length
		};
		return {
			index,
			headerHtml: applyTemplate(mergedConfig.headerTemplate, tokens),
			bodyHtml: page.blocks.join(''),
			footerHtml: applyTemplate(mergedConfig.footerTemplate, tokens)
		};
	});
};
