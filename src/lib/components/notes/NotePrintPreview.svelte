<script lang="ts">
	import RichTextInput from '$lib/components/common/RichTextInput.svelte';
	import { DEFAULT_PAGE_LAYOUT_CONFIG, type PageLayoutConfig } from './pageLayout';

	export let note;
	export let layoutConfig: Partial<PageLayoutConfig> = DEFAULT_PAGE_LAYOUT_CONFIG;

	$: noteHtml = note?.data?.content?.html ?? '';
	$: noteTitle = note?.title ?? 'Untitled';
</script>

<div class="w-full h-full overflow-auto p-4 bg-gray-100 dark:bg-gray-900">
	<RichTextInput
		renderMode="page-layout"
		raw={true}
		richText={false}
		editable={false}
		showFormattingToolbar={false}
		value={noteHtml}
		html={noteHtml}
		pageLayoutTitle={noteTitle}
		pageLayoutConfig={layoutConfig}
		className="max-w-4xl mx-auto"
	/>
</div>
