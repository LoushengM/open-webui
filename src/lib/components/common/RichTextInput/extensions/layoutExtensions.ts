import { Node, Mark } from '@tiptap/core';
import { TableKit } from '@tiptap/extension-table';
import { ListKit } from '@tiptap/extension-list';

export const PageBreak = Node.create({
	name: 'pageBreak',
	group: 'block',
	atom: true,
	selectable: true,
	parseHTML() {
		return [{ tag: 'hr[data-page-break="true"]' }];
	},
	renderHTML() {
		return ['hr', { 'data-page-break': 'true', class: 'page-break' }];
	},
	addCommands() {
		return {
			insertPageBreak:
				() =>
				({ chain }) =>
					chain().insertContent({ type: this.name }).run()
		};
	}
});

export const StylePreset = Mark.create({
	name: 'stylePreset',
	inclusive: false,
	addAttributes() {
		return {
			preset: { default: 'body-1' }
		};
	},
	parseHTML() {
		return [{ tag: 'span[data-style-preset]' }];
	},
	renderHTML({ HTMLAttributes }) {
		const preset = HTMLAttributes.preset || 'body-1';
		return [
			'span',
			{
				...HTMLAttributes,
				'data-style-preset': preset,
				class: `style-preset-${preset}`
			},
			0
		];
	},
	addCommands() {
		return {
			setStylePreset:
				(preset: string) =>
				({ chain }) =>
					chain().setMark(this.name, { preset }).run(),
			unsetStylePreset:
				() =>
				({ chain }) =>
					chain().unsetMark(this.name).run()
		};
	}
});

export const getLayoutExtensions = () => [
	TableKit.configure({
		table: { resizable: true }
	}),
	ListKit.configure({
		taskItem: {
			nested: true
		}
	}),
	PageBreak,
	StylePreset
];
