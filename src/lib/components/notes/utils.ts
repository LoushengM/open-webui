import DOMPurify from 'dompurify';
import { toast } from 'svelte-sonner';

import { createNewNote } from '$lib/apis/notes';
import { buildLayoutPages, mergePageLayoutConfig, type PageLayoutConfig } from './pageLayout';

const renderPageCanvas = async (
	html2canvas,
	{
		title,
		headerHtml,
		bodyHtml,
		footerHtml
	}: {
		title: string;
		headerHtml: string;
		bodyHtml: string;
		footerHtml: string;
	}
) => {
	const host = document.createElement('div');
	host.style.width = '794px';
	host.style.background = 'white';
	host.style.color = 'black';
	host.style.position = 'absolute';
	host.style.left = '-10000px';
	host.style.top = '0';
	host.style.padding = '48px';
	host.style.display = 'flex';
	host.style.flexDirection = 'column';
	host.style.gap = '16px';

	host.innerHTML = `
		<header style="font-size:12px;color:#475569;display:flex;justify-content:space-between">${headerHtml}</header>
		<h1 style="font-size:22px;margin:0;line-height:1.2">${title}</h1>
		<main style="font-size:14px;line-height:1.6">${bodyHtml}</main>
		<footer style="margin-top:16px;font-size:12px;color:#64748b">${footerHtml}</footer>
	`;

	document.body.appendChild(host);
	const canvas = await html2canvas(host, {
		useCORS: true,
		backgroundColor: '#fff',
		scale: 2,
		width: host.clientWidth,
		windowWidth: host.clientWidth
	});
	document.body.removeChild(host);
	return canvas;
};

export const downloadPdf = async (note, config: Partial<PageLayoutConfig> = {}) => {
	const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
		import('jspdf'),
		import('html2canvas-pro')
	]);

	const html = DOMPurify.sanitize(note.data?.content?.html ?? '');
	const pages = buildLayoutPages({
		title: note.title,
		html,
		config: mergePageLayoutConfig(config)
	});

	const pdf = new jsPDF('p', 'mm', 'a4');
	for (let i = 0; i < pages.length; i += 1) {
		if (i > 0) {
			pdf.addPage();
		}

		const canvas = await renderPageCanvas(html2canvas, {
			title: note.title,
			headerHtml: pages[i].headerHtml,
			bodyHtml: pages[i].bodyHtml,
			footerHtml: pages[i].footerHtml
		});

		const pageWidth = pdf.internal.pageSize.getWidth();
		const pageHeight = pdf.internal.pageSize.getHeight();
		const imageHeight = (canvas.height * pageWidth) / canvas.width;
		pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, 0, pageWidth, Math.min(imageHeight, pageHeight));
	}

	pdf.save(`${note.title}.pdf`);
};

export const createNoteHandler = async (title: string, md?: string, html?: string) => {
	//  $i18n.t('New Note'),
	const res = await createNewNote(localStorage.token, {
		// YYYY-MM-DD
		title: title,
		data: {
			content: {
				json: null,
				html: html || md || '',
				md: md || ''
			}
		},
		meta: null,
		access_control: {}
	}).catch((error) => {
		toast.error(`${error}`);
		return null;
	});

	if (res) {
		return res;
	}
};
