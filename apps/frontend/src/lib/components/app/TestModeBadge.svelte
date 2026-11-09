<script lang="ts">
	import FlaskIcon from '@lucide/svelte/icons/flask-conical';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
</script>

<Tooltip.Provider>
	<Tooltip.Root>
		<Tooltip.Trigger data-testid="test-mode">
			{#snippet child({ props })}
				<Badge {...props} variant="warning" tabindex={0}>
					<FlaskIcon data-icon="inline-start" aria-hidden="true" />{m().common.testMode}
				</Badge>
			{/snippet}
		</Tooltip.Trigger>
		<Tooltip.Content>{m().common.testModeNote}</Tooltip.Content>
	</Tooltip.Root>
</Tooltip.Provider>
