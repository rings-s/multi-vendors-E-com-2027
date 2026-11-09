<script lang="ts" module>
	export interface MapPin {
		id: string;
		lat: number;
		lng: number;
		label: string;
	}
	export interface LatLng {
		lat: number;
		lng: number;
	}

	/** OpenStreetMap raster tiles: free, no API key. Swap here to change the basemap everywhere. */
	export const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
	export const TILE_ATTRIBUTION =
		'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
	/** Whole-Kingdom view used when there is nothing to show yet. */
	const SAUDI_CENTER: [number, number] = [23.8859, 45.0792];
	const SAUDI_ZOOM = 5;
	const PIN_ZOOM = 15;
</script>

<script lang="ts">
	import 'leaflet/dist/leaflet.css';
	import type { Map as LeafletMap, Marker } from 'leaflet';
	import CrosshairIcon from '@lucide/svelte/icons/crosshair';
	import LocateFixedIcon from '@lucide/svelte/icons/locate-fixed';
	import XIcon from '@lucide/svelte/icons/x';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { m } from '#lib/i18n/state.svelte.js';
	import { cn } from '#lib/utils.js';

	interface Props {
		/** Accessible name for the map region. */
		label: string;
		/** Display mode: pins to show (the view fits them). */
		pins?: MapPin[];
		/** Called when a displayed pin is activated. */
		onselect?: (id: string) => void;
		/** Picker mode: a single, draggable pin bound to `value`. */
		editable?: boolean;
		value?: LatLng | null;
		class?: string;
	}

	let {
		label,
		pins = [],
		onselect,
		editable = false,
		value = $bindable(null),
		class: className
	}: Props = $props();

	let el: HTMLDivElement;
	let L = $state<typeof import('leaflet') | null>(null);
	let map = $state<LeafletMap | null>(null);
	let pickerMarker: Marker | null = null;
	let pinLayer: import('leaflet').LayerGroup | null = null;
	let locating = $state(false);

	// Six decimals ≈ 11 cm — more precision than a shopfront needs, less noise in the DB.
	const round = (n: number) => Math.round(n * 1e6) / 1e6;
	const set = (lat: number, lng: number) => (value = { lat: round(lat), lng: round(lng) });

	onMount(() => {
		let disposed = false;
		let ro: ResizeObserver | undefined;
		void import('leaflet').then((mod) => {
			if (disposed) return;
			const Leaf = mod.default;
			const instance = Leaf.map(el, {
				zoomControl: false,
				// A display map inside a scrolling page must not hijack the wheel.
				scrollWheelZoom: editable,
				attributionControl: true
			}).setView(SAUDI_CENTER, SAUDI_ZOOM);
			Leaf.control.zoom({ position: 'bottomright' }).addTo(instance);
			Leaf.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(instance);
			if (editable) instance.on('click', (e) => set(e.latlng.lat, e.latlng.lng));
			// Dialogs animate in, and grids reflow: keep tiles in sync with the real size.
			ro = new ResizeObserver(() => instance.invalidateSize());
			ro.observe(el);
			L = Leaf;
			map = instance;
		});
		return () => {
			disposed = true;
			ro?.disconnect();
			map?.remove();
			map = null;
		};
	});

	function pinIcon(Leaf: typeof import('leaflet')) {
		return Leaf.divIcon({
			className: 'map-pin',
			html: '<span></span>',
			iconSize: [30, 38],
			iconAnchor: [15, 36],
			tooltipAnchor: [0, -34]
		});
	}

	// Display mode: (re)draw pins and fit them whenever the list changes.
	$effect(() => {
		if (!L || !map || editable) return;
		const Leaf = L;
		pinLayer?.remove();
		pinLayer = Leaf.layerGroup().addTo(map);
		for (const p of pins) {
			const marker = Leaf.marker([p.lat, p.lng], {
				icon: pinIcon(Leaf),
				title: p.label,
				alt: p.label,
				keyboard: true
			})
				.bindTooltip(p.label, { direction: 'top', className: 'map-tooltip' })
				.addTo(pinLayer);
			if (onselect) marker.on('click', () => onselect(p.id));
		}
		if (pins.length === 1) map.setView([pins[0].lat, pins[0].lng], PIN_ZOOM);
		else if (pins.length > 1)
			map.fitBounds(Leaf.latLngBounds(pins.map((p) => [p.lat, p.lng])), {
				padding: [48, 48],
				maxZoom: PIN_ZOOM
			});
	});

	// Picker mode: keep the single draggable pin in step with `value` (map clicks, drags, buttons).
	$effect(() => {
		if (!L || !map || !editable) return;
		const Leaf = L;
		const v = value;
		if (!v) {
			pickerMarker?.remove();
			pickerMarker = null;
			return;
		}
		if (pickerMarker) {
			pickerMarker.setLatLng([v.lat, v.lng]);
		} else {
			pickerMarker = Leaf.marker([v.lat, v.lng], {
				icon: pinIcon(Leaf),
				draggable: true,
				autoPan: true,
				alt: label
			}).addTo(map);
			pickerMarker.on('dragend', () => {
				const ll = pickerMarker!.getLatLng();
				set(ll.lat, ll.lng);
			});
			map.setView([v.lat, v.lng], Math.max(map.getZoom(), PIN_ZOOM));
		}
	});

	function locate() {
		if (!navigator.geolocation) return toast.error(m().merchant.locationFailed);
		locating = true;
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				locating = false;
				set(pos.coords.latitude, pos.coords.longitude);
				map?.setView([pos.coords.latitude, pos.coords.longitude], PIN_ZOOM);
			},
			() => {
				locating = false;
				toast.error(m().merchant.locationFailed);
			},
			{ enableHighAccuracy: true, timeout: 10_000 }
		);
	}

	function pinCentre() {
		if (!map) return;
		const c = map.getCenter();
		set(c.lat, c.lng);
	}
</script>

<div class={cn('flex flex-col gap-3', className)}>
	<!-- Leaflet lays out its controls in LTR; the page around it still mirrors. -->
	<div
		bind:this={el}
		dir="ltr"
		role="region"
		aria-label={label}
		class={cn(
			'location-map relative isolate z-0 w-full overflow-hidden rounded-2xl bg-surface-2 ring-1 ring-edge',
			editable ? 'h-64 sm:h-72' : 'h-72 sm:h-80'
		)}
	></div>

	{#if editable}
		<p class="text-sm text-ink-2">{m().merchant.mapHint}</p>
		<div class="flex flex-wrap items-center gap-2">
			<Button type="button" variant="outline" size="sm" onclick={locate} disabled={locating}>
				{#if locating}<Spinner data-icon="inline-start" />{:else}<LocateFixedIcon
						data-icon="inline-start"
					/>{/if}
				{m().merchant.useMyLocation}
			</Button>
			<Button type="button" variant="outline" size="sm" onclick={pinCentre} disabled={!map}>
				<CrosshairIcon data-icon="inline-start" />{m().merchant.pinCentre}
			</Button>
			{#if value}
				<Button type="button" variant="ghost" size="sm" onclick={() => (value = null)}>
					<XIcon data-icon="inline-start" />{m().merchant.clearPin}
				</Button>
				<span class="ms-auto type-label text-ink-3 tabular" dir="ltr">
					{value.lat.toFixed(5)}, {value.lng.toFixed(5)}
				</span>
			{/if}
		</div>
	{/if}
</div>
