<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import { getNoteById } from '$lib/apis/notes';
	import NotePrintPreview from '$lib/components/notes/NotePrintPreview.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	let loading = true;
	let note = null;

	onMount(async () => {
		const res = await getNoteById(localStorage.token, $page.params.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!res) {
			goto('/notes');
			return;
		}

		note = res;
		loading = false;
	});
</script>

{#if loading}
	<div class="w-full h-full flex items-center justify-center">
		<Spinner />
	</div>
{:else}
	<NotePrintPreview {note} />
{/if}
