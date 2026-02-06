import { Mark } from '@tiptap/core';

export const CommentAnchor = Mark.create({
	name: 'commentAnchor',
	inclusive: false,
	addAttributes() {
		return {
			commentId: { default: null }
		};
	},
	parseHTML() {
		return [{ tag: 'span[data-comment-anchor]' }];
	},
	renderHTML({ HTMLAttributes }) {
		return ['span', { ...HTMLAttributes, 'data-comment-anchor': HTMLAttributes.commentId || '' }, 0];
	},
	addCommands() {
		return {
			setCommentAnchor:
				(commentId: string) =>
				({ chain }) =>
					chain().setMark(this.name, { commentId }).run(),
			unsetCommentAnchor:
				() =>
				({ chain }) =>
					chain().unsetMark(this.name).run()
		};
	}
});

export const getReviewExtensions = () => [CommentAnchor];
