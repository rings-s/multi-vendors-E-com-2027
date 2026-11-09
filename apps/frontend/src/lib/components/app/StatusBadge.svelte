<script lang="ts" module>
	import type { BadgeVariant } from '#lib/components/ui/badge/index.js';

	type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand';

	const TONES: Record<string, Tone> = {
		APPROVED: 'success',
		ACTIVE: 'success',
		PAID: 'success',
		COMPLETED: 'success',
		DELIVERED: 'success',
		SUCCEEDED: 'success',
		PROCESSED: 'success',
		WON: 'success',
		RESOLVED: 'success',
		PUBLISHED: 'success',
		AVAILABLE: 'success',
		ENABLED: 'success',
		SATISFIED: 'success',
		ACCEPTED: 'brand',
		CONFIRMED: 'brand',
		PREPARING: 'info',
		READY_FOR_PICKUP: 'info',
		OUT_FOR_DELIVERY: 'info',
		PROCESSING: 'info',
		SHIPPED: 'info',
		UNDER_REVIEW: 'info',
		SUBMITTED: 'info',
		IN_PROGRESS: 'info',
		RUNNING: 'info',
		AUTHORIZED: 'info',
		OPEN: 'info',
		PENDING: 'warning',
		PENDING_PAYMENT: 'warning',
		PARTIALLY_PAID: 'warning',
		REQUESTED: 'warning',
		ADDITIONAL_INFO_REQUIRED: 'warning',
		ACTION_REQUIRED: 'warning',
		SEMI_ACTIVE: 'warning',
		ON_HOLD: 'warning',
		PARTIALLY_REFUNDED: 'warning',
		REQUIRED: 'warning',
		DRAFT: 'neutral',
		CREATED: 'neutral',
		NOT_STARTED: 'neutral',
		NONE: 'neutral',
		ARCHIVED: 'neutral',
		INACTIVE: 'neutral',
		CLOSED: 'neutral',
		HIDDEN: 'neutral',
		UNAVAILABLE: 'neutral',
		RECEIVED: 'neutral',
		IGNORED: 'neutral',
		REFUNDED: 'neutral',
		REJECTED: 'danger',
		FAILED: 'danger',
		CANCELLED: 'danger',
		SUSPENDED: 'danger',
		BLOCKED: 'danger',
		DISABLED: 'danger',
		DISPUTED: 'danger',
		LOST: 'danger'
	};

	const VARIANTS: Record<Tone, BadgeVariant> = {
		neutral: 'secondary',
		success: 'success',
		warning: 'warning',
		danger: 'destructive',
		info: 'info',
		brand: 'brand'
	};
</script>

<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { statusLabel } from '#lib/i18n/state.svelte.js';

	interface Props {
		status: string | null | undefined;
		label?: string;
		class?: string;
	}

	let { status, label, class: className }: Props = $props();
	const tone = $derived(TONES[(status ?? '').toUpperCase()] ?? 'neutral');
</script>

<Badge data-status={status} variant={VARIANTS[tone]} class={className}>
	<span class="size-1.5 rounded-full bg-current opacity-80" aria-hidden="true"></span>
	{label ?? statusLabel(status?.toUpperCase())}
</Badge>
