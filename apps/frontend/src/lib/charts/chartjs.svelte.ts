/**
 * Chart.js setup shared by every chart in the app.
 *
 * - Registers only the controllers we draw (bar + line), so the bundle stays small.
 * - Colors are never hard-coded: `readTheme()` resolves the design tokens from
 *   `layout.css` (`--chart-*`, ink, border, popover) on the chart's own element, so
 *   light and dark mode each use their own validated steps.
 * - `themeVersion()` changes when `<html data-theme>` or the OS color scheme changes,
 *   so charts re-render with the new token values (canvas cannot read CSS variables).
 */
import {
	BarController,
	BarElement,
	CategoryScale,
	Chart,
	LinearScale,
	LineController,
	LineElement,
	PointElement,
	Tooltip,
	type ChartOptions,
	type Plugin,
	type TooltipOptions
} from 'chart.js';
import { intlTag, type Locale } from '#lib/i18n/index.js';

Chart.register(
	BarController,
	BarElement,
	CategoryScale,
	LinearScale,
	LineController,
	LineElement,
	PointElement,
	Tooltip
);

export interface ChartTheme {
	/** Categorical slots in their validated order: --chart-1, 4, 5, 6. */
	categorical: string[];
	brand: string;
	recessive: string;
	ink: string;
	ink3: string;
	grid: string;
	surface: string;
	popover: string;
	popoverInk: string;
	font: string;
	reducedMotion: boolean;
}

let tick = $state(0);
let watching = false;

/** Read it inside an effect to re-run the effect when the theme changes. */
export function themeVersion(): number {
	if (!watching && typeof window !== 'undefined') {
		watching = true;
		const bump = () => (tick += 1);
		new MutationObserver(bump).observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['data-theme', 'class', 'dir', 'lang']
		});
		window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', bump);
	}
	return tick;
}

export function readTheme(el: Element): ChartTheme {
	const style = getComputedStyle(el);
	const v = (name: string) => style.getPropertyValue(name).trim();
	const font = getComputedStyle(document.body).fontFamily;
	Chart.defaults.font.family = font;
	return {
		categorical: [v('--chart-1'), v('--chart-4'), v('--chart-5'), v('--chart-6')],
		brand: v('--chart-1'),
		recessive: v('--chart-3'),
		ink: v('--foreground'),
		ink3: v('--ink-3'),
		grid: v('--border'),
		surface: v('--card'),
		popover: v('--popover') || v('--card'),
		popoverInk: v('--popover-foreground') || v('--foreground'),
		font,
		reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
	};
}

/** Short axis labels: 12.5K, 1.2M (in riyals when given halalas). */
export function compact(value: number, locale: Locale): string {
	return new Intl.NumberFormat(intlTag(locale), {
		notation: 'compact',
		maximumFractionDigits: 1
	}).format(value);
}

export function tooltip(theme: ChartTheme, rtl: boolean): Partial<TooltipOptions> {
	return {
		backgroundColor: theme.popover,
		titleColor: theme.popoverInk,
		bodyColor: theme.popoverInk,
		borderColor: theme.grid,
		borderWidth: 1,
		cornerRadius: 8,
		padding: 10,
		boxPadding: 6,
		usePointStyle: true,
		titleFont: { family: theme.font, weight: 500 },
		bodyFont: { family: theme.font },
		rtl,
		textDirection: rtl ? 'rtl' : 'ltr'
	};
}

/** Defaults every chart shares: responsive, hairline recessive axes, no canvas legend. */
export function baseOptions(
	theme: ChartTheme,
	locale: Locale,
	rtl: boolean
): ChartOptions<'bar' | 'line'> {
	return {
		responsive: true,
		maintainAspectRatio: false,
		locale: intlTag(locale),
		animation: theme.reducedMotion ? false : { duration: 250 },
		plugins: { legend: { display: false }, tooltip: tooltip(theme, rtl) }
	};
}

/** Hairline grid in the border token, muted ticks, no axis rule. */
export function axis(theme: ChartTheme, grid: boolean) {
	return {
		border: { display: false },
		grid: { display: grid, color: theme.grid, lineWidth: 1, drawTicks: false },
		ticks: { color: theme.ink3, padding: 8, font: { family: theme.font, size: 11 } }
	};
}

const LABEL_FONT = (family: string) => `500 12px ${family}`;

/** Room to reserve past the bar ends so the widest `barEndLabels` text is never clipped. */
export function barEndLabelRoom(labels: string[], family: string): number {
	const ctx = document.createElement('canvas').getContext('2d');
	if (!ctx) return 96;
	ctx.font = LABEL_FONT(family);
	return Math.ceil(Math.max(0, ...labels.map((l) => ctx.measureText(l).width))) + 16;
}

/**
 * Writes each bar's value just past its end (horizontal bars only), in muted ink —
 * text never wears the series color. Reserve `barEndLabelRoom()` with `layout.padding` on that side.
 */
export function barEndLabels(
	format: (value: number) => string,
	color: string,
	rtl: boolean
): Plugin<'bar'> {
	return {
		id: 'barEndLabels',
		afterDatasetsDraw(chart) {
			const { ctx } = chart;
			const meta = chart.getDatasetMeta(0);
			const values = chart.data.datasets[0]?.data ?? [];
			ctx.save();
			ctx.fillStyle = color;
			ctx.font = LABEL_FONT(String(Chart.defaults.font.family));
			ctx.textBaseline = 'middle';
			ctx.textAlign = rtl ? 'right' : 'left';
			meta.data.forEach((bar, i) => {
				const value = Number(values[i] ?? 0);
				const { x, y } = bar.getProps(['x', 'y'], true) as { x: number; y: number };
				ctx.fillText(format(value), rtl ? x - 8 : x + 8, y);
			});
			ctx.restore();
		}
	};
}
