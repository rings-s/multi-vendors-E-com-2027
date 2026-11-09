<script lang="ts">
	import { navigating } from '$app/state';
	import { m } from '#lib/i18n/state.svelte.js';

	// Only show for navigations that take noticeably long, to avoid flicker.
	let visible = $state(false);
	$effect(() => {
		if (!navigating.to) {
			visible = false;
			return;
		}
		const t = setTimeout(() => (visible = true), 150);
		return () => clearTimeout(t);
	});
</script>

{#if visible}
	<div
		class="fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden"
		role="progressbar"
		aria-label={m().common.loading}
	>
		<div class="nav-bar h-full w-1/3 bg-primary"></div>
	</div>
{/if}

<style>
	.nav-bar {
		animation: slide 1.1s ease-in-out infinite;
	}
	@keyframes slide {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(300%);
		}
	}
	:global([dir='rtl']) .nav-bar {
		animation-direction: reverse;
	}
</style>
