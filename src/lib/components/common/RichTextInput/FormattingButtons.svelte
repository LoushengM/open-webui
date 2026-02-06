<script>
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	export let editor = null;
	let activeTab = 'home';

	import Bold from '$lib/components/icons/Bold.svelte';
	import CodeBracket from '$lib/components/icons/CodeBracket.svelte';
	import H1 from '$lib/components/icons/H1.svelte';
	import H2 from '$lib/components/icons/H2.svelte';
	import H3 from '$lib/components/icons/H3.svelte';
	import Italic from '$lib/components/icons/Italic.svelte';
	import ListBullet from '$lib/components/icons/ListBullet.svelte';
	import NumberedList from '$lib/components/icons/NumberedList.svelte';
	import Strikethrough from '$lib/components/icons/Strikethrough.svelte';
	import Underline from '$lib/components/icons/Underline.svelte';

	import Tooltip from '../Tooltip.svelte';
	import CheckBox from '$lib/components/icons/CheckBox.svelte';
	import ArrowLeftTag from '$lib/components/icons/ArrowLeftTag.svelte';
	import ArrowRightTag from '$lib/components/icons/ArrowRightTag.svelte';

	const tabs = [
		{ key: 'home', label: 'Home' },
		{ key: 'insert', label: 'Insert' },
		{ key: 'layout', label: 'Layout' },
		{ key: 'review', label: 'Review' }
	];

	const applyStylePreset = (preset) => {
		if (!editor?.commands?.setStylePreset) return;
		editor.chain().focus().setStylePreset(preset).run();
	};

	const runIfAvailable = (commandName, ...args) => {
		if (!editor?.commands?.[commandName]) return;
		editor.chain().focus()[commandName](...args).run();
	};
</script>

<div
	class="rounded-xl shadow-lg bg-white text-gray-800 dark:text-white dark:bg-gray-850 min-w-fit border border-gray-100 dark:border-gray-800"
>
	<div class="flex gap-1 p-1 border-b border-gray-100 dark:border-gray-800">
		{#each tabs as tab}
			<button
				type="button"
				on:click={() => (activeTab = tab.key)}
				class="px-2.5 py-1 text-xs rounded-md transition-all {activeTab === tab.key
					? 'bg-gray-100 dark:bg-gray-700 font-medium'
					: 'hover:bg-gray-50 dark:hover:bg-gray-800'}"
			>
				{$i18n.t(tab.label)}
			</button>
		{/each}
	</div>

	<div class="flex flex-wrap gap-0.5 p-1">
		{#if activeTab === 'home'}
			<Tooltip placement="top" content={$i18n.t('H1')}>
				<button
					on:click={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
					class="{editor?.isActive('heading', { level: 1 }) ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all"
					type="button"
				>
					<H1 />
				</button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('H2')}>
				<button on:click={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} class="{editor?.isActive('heading', { level: 2 }) ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><H2 /></button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('H3')}>
				<button on:click={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()} class="{editor?.isActive('heading', { level: 3 }) ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><H3 /></button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('Body')}>
				<button on:click={() => applyStylePreset('body-1')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">B1</button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('Bold')}><button on:click={() => editor?.chain().focus().toggleBold().run()} class="{editor?.isActive('bold') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><Bold /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Italic')}><button on:click={() => editor?.chain().focus().toggleItalic().run()} class="{editor?.isActive('italic') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><Italic /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Underline')}><button on:click={() => editor?.chain().focus().toggleUnderline().run()} class="{editor?.isActive('underline') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><Underline /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Strikethrough')}><button on:click={() => editor?.chain().focus().toggleStrike().run()} class="{editor?.isActive('strike') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><Strikethrough /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Code Block')}><button on:click={() => editor?.chain().focus().toggleCodeBlock().run()} class="{editor?.isActive('codeBlock') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><CodeBracket /></button></Tooltip>
		{/if}

		{#if activeTab === 'insert'}
			<Tooltip placement="top" content={$i18n.t('Citation Block')}>
				<button on:click={() => runIfAvailable('insertCitationBlock')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">Cite</button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('Reference Block')}>
				<button on:click={() => runIfAvailable('insertReferenceBlock')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">Ref</button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('Footnote')}>
				<button on:click={() => runIfAvailable('setFootnote', 'fn-1')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">Fn</button>
			</Tooltip>
			<Tooltip placement="top" content={$i18n.t('Endnote')}>
				<button on:click={() => runIfAvailable('setEndnote', 'en-1')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">En</button>
			</Tooltip>
		{/if}

		{#if activeTab === 'layout'}
			{#if editor?.isActive('bulletList') || editor?.isActive('orderedList') || editor?.isActive('taskList')}
				<Tooltip placement="top" content={$i18n.t('Lift List')}><button on:click={() => editor?.commands.liftListItem(editor?.isActive('taskList') ? 'taskItem' : 'listItem')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><ArrowLeftTag /></button></Tooltip>
				<Tooltip placement="top" content={$i18n.t('Sink List')}><button on:click={() => editor?.commands.sinkListItem(editor?.isActive('taskList') ? 'taskItem' : 'listItem')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><ArrowRightTag /></button></Tooltip>
			{/if}
			<Tooltip placement="top" content={$i18n.t('Bullet List')}><button on:click={() => editor?.chain().focus().toggleBulletList().run()} class="{editor?.isActive('bulletList') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><ListBullet /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Ordered List')}><button on:click={() => editor?.chain().focus().toggleOrderedList().run()} class="{editor?.isActive('orderedList') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><NumberedList /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Task List')}><button on:click={() => editor?.chain().focus().toggleTaskList().run()} class="{editor?.isActive('taskList') ? 'bg-gray-50 dark:bg-gray-700' : ''} hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 transition-all" type="button"><CheckBox /></button></Tooltip>
			<Tooltip placement="top" content={$i18n.t('Page Break')}>
				<button on:click={() => runIfAvailable('insertPageBreak')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">PB</button>
			</Tooltip>
		{/if}

		{#if activeTab === 'review'}
			<Tooltip placement="top" content={$i18n.t('Comment Anchor')}>
				<button on:click={() => runIfAvailable('setCommentAnchor', 'comment-1')} class="hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg p-1.5 text-xs transition-all" type="button">Cm</button>
			</Tooltip>
		{/if}
	</div>
</div>
