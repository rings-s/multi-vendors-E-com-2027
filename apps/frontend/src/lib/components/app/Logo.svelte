<script lang="ts">
	import { cn } from '#lib/utils.js';

	interface Props {
		class?: string;
		/** Accessible name. Leave unset when the logo sits next to visible brand text. */
		label?: string;
	}

	let { class: className, label }: Props = $props();
</script>

<!-- Brand mark (source: docs/logo/logo.svg, corners rounded to 25%). A rounded tile with the mark knocked out,
     drawn in currentColor so it follows the text colour in both themes. -->
<svg
	viewBox="0 0 400 400"
	xmlns="http://www.w3.org/2000/svg"
	class={cn('size-7 shrink-0', className)}
	fill="currentColor"
	role={label ? 'img' : undefined}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
	focusable="false"
>
	<path
		transform="translate(0 400) scale(.1 -.1)"
		d="M0 2000 L0 1000 C0 448 448 0 1000 0 L3000 0 C3552 0 4000 448 4000 1000 L4000 3000 C4000 3552 3552 4000 3000 4000 L1000 4000 C448 4000 0 3552 0 3000 Z M2665 2400 l400 -400 -385 -385 c-212 -212 -389 -385 -395 -385 -5 0 -189 179 -407 398 l-397 398 104 104 105 105 312 -313 312 -312 178 177 c98 98 178 181 178 184 0 4 -129 137 -288 295 -158 159 -296 299 -306 312 l-20 23 99 99 c55 55 102 100 105 100 3 0 185 -180 405 -400z m-543 -28 l397 -398 -104 -104 -105 -105 -312 313 -312 312 -178 -177 c-98 -98 -178 -181 -178 -184 0 -3 137 -145 305 -314 168 -170 305 -311 305 -314 0 -4 -45 -51 -100 -106 l-100 -100 -403 403 -402 402 385 385 c212 212 389 385 395 385 5 0 189 -179 407 -398z"
	/>
</svg>
