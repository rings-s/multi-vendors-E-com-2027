/** Dashboard analytics periods (days, ending today); the API accepts 7-365. */
export const ANALYTICS_PERIODS = [7, 30, 90, 365];

/** `?days=` when it is one of the offered periods, else 30. */
export function periodParam(url: URL): number {
	const requested = Number(url.searchParams.get('days'));
	return ANALYTICS_PERIODS.includes(requested) ? requested : 30;
}
