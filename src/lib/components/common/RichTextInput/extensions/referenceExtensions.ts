import { Mark, Node } from '@tiptap/core';

const createNoteMark = (name: string, attributeName: string) =>
	Mark.create({
		name,
		inclusive: false,
		addAttributes() {
			return {
				id: { default: null }
			};
		},
		parseHTML() {
			return [{ tag: `span[data-${attributeName}]` }];
		},
		renderHTML({ HTMLAttributes }) {
			return ['span', { ...HTMLAttributes, [`data-${attributeName}`]: HTMLAttributes.id || '' }, 0];
		},
		addCommands() {
			return {
				[`set${name.charAt(0).toUpperCase()}${name.slice(1)}`]:
					(id: string) =>
					({ chain }) =>
						chain().setMark(this.name, { id }).run(),
				[`unset${name.charAt(0).toUpperCase()}${name.slice(1)}`]:
					() =>
					({ chain }) =>
						chain().unsetMark(this.name).run()
			};
		}
	});

export const Footnote = createNoteMark('footnote', 'footnote');
export const Endnote = createNoteMark('endnote', 'endnote');

export const CitationBlock = Node.create({
	name: 'citationBlock',
	group: 'block',
	content: 'inline*',
	defining: true,
	addAttributes() {
		return {
			referenceId: { default: null }
		};
	},
	parseHTML() {
		return [{ tag: 'blockquote[data-citation-block="true"]' }];
	},
	renderHTML({ HTMLAttributes }) {
		return ['blockquote', { ...HTMLAttributes, 'data-citation-block': 'true' }, 0];
	},
	addCommands() {
		return {
			insertCitationBlock:
				(referenceId?: string) =>
				({ chain }) =>
					chain()
						.insertContent({
							type: this.name,
							attrs: { referenceId: referenceId || null },
							content: [{ type: 'text', text: 'Citation' }]
						})
						.run()
		};
	}
});

export const ReferenceBlock = Node.create({
	name: 'referenceBlock',
	group: 'block',
	content: 'inline*',
	defining: true,
	addAttributes() {
		return {
			referenceId: { default: null },
			kind: { default: 'reference' }
		};
	},
	parseHTML() {
		return [{ tag: 'div[data-reference-block="true"]' }];
	},
	renderHTML({ HTMLAttributes }) {
		return ['div', { ...HTMLAttributes, 'data-reference-block': 'true' }, 0];
	},
	addCommands() {
		return {
			insertReferenceBlock:
				(referenceId?: string) =>
				({ chain }) =>
					chain()
						.insertContent({
							type: this.name,
							attrs: { referenceId: referenceId || null },
							content: [{ type: 'text', text: 'Reference' }]
						})
						.run()
		};
	}
});

export const getReferenceExtensions = () => [Footnote, Endnote, CitationBlock, ReferenceBlock];
