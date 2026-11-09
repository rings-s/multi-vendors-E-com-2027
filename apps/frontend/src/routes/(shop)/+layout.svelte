<script lang="ts">
	import SiteFooter from '#lib/components/app/SiteFooter.svelte';
	import SiteHeader from '#lib/components/app/SiteHeader.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<SiteHeader />
<main id="main" class="min-h-[60dvh]">
	{@render children()}
</main>
<SiteFooter />
