<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { useSidebar } from '#lib/components/ui/sidebar/index.js';

	/** Closes the mobile sidebar sheet after each navigation. Render inside `Sidebar.Provider`. */
	const sidebar = useSidebar();
	afterNavigate(() => sidebar.setOpenMobile(false));
</script>
