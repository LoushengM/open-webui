import StarterKit from '@tiptap/starter-kit';
import Typography from '@tiptap/extension-typography';
import Highlight from '@tiptap/extension-highlight';
import Underline from '@tiptap/extension-underline';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';

export const getCoreFormattingExtensions = ({
	link,
	lowlight
}: {
	link: boolean;
	lowlight: any;
}) => [
	StarterKit.configure({
		link
	}),
	CodeBlockLowlight.configure({
		lowlight
	}),
	Typography,
	Highlight,
	Underline
];
