/**
 * Sliding selection indicator.
 *
 * Measures the chosen item inside `node` and writes its box to CSS variables; the
 * `[data-indicator]` rules in layout.css draw and animate the marker. The markup
 * decides the look (`data-indicator="pill"` or `"line"`); this only supplies position.
 */
const CHOSEN =
	'[data-state="active"], [data-state="on"], [aria-current="page"], [aria-checked="true"], [data-active="true"]';

export function trackIndicator(node: HTMLElement, selector: string = CHOSEN): () => void {
	let painted = false;
	let frame = 0;

	function measure() {
		const chosen = node.querySelector<HTMLElement>(selector);
		if (!chosen || chosen.offsetParent === null) {
			node.style.setProperty('--ind-o', '0');
			node.dataset.indicatorReady = 'instant';
			painted = false;
			return;
		}
		const box = node.getBoundingClientRect();
		const r = chosen.getBoundingClientRect();
		// First paint, or reappearing: place it without travelling from the corner.
		if (!painted) node.dataset.indicatorReady = 'instant';
		node.style.setProperty('--ind-x', `${r.left - box.left - node.clientLeft + node.scrollLeft}px`);
		node.style.setProperty('--ind-y', `${r.top - box.top - node.clientTop + node.scrollTop}px`);
		node.style.setProperty('--ind-w', `${r.width}px`);
		node.style.setProperty('--ind-h', `${r.height}px`);
		node.style.setProperty('--ind-o', '1');
		if (!painted) {
			painted = true;
			requestAnimationFrame(() => requestAnimationFrame(() => (node.dataset.indicatorReady = '')));
		}
	}

	function schedule() {
		cancelAnimationFrame(frame);
		frame = requestAnimationFrame(measure);
	}

	const mutations = new MutationObserver(schedule);
	mutations.observe(node, {
		subtree: true,
		childList: true,
		characterData: true,
		attributes: true,
		attributeFilter: ['data-state', 'aria-current', 'aria-checked', 'data-active', 'hidden']
	});
	const resize = new ResizeObserver(schedule);
	resize.observe(node);
	for (const child of node.children) resize.observe(child);
	void document.fonts?.ready.then(schedule);
	measure();

	return () => {
		cancelAnimationFrame(frame);
		mutations.disconnect();
		resize.disconnect();
	};
}
