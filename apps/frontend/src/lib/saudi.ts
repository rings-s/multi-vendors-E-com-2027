/**
 * Saudi administrative regions. The keys mirror `SAUDI_REGIONS` in
 * `apps/backend/app/core/validators.py`; the backend rejects any other value.
 * `iso` is the ISO 3166-2:SA code, used to map reverse-geocoded locations onto a region.
 */
export const REGIONS = [
	{ key: 'riyadh', iso: 'SA-01', en: 'Riyadh', ar: 'الرياض' },
	{ key: 'makkah', iso: 'SA-02', en: 'Makkah', ar: 'مكة المكرمة' },
	{ key: 'madinah', iso: 'SA-03', en: 'Madinah', ar: 'المدينة المنورة' },
	{ key: 'qassim', iso: 'SA-05', en: 'Al-Qassim', ar: 'القصيم' },
	{ key: 'eastern_province', iso: 'SA-04', en: 'Eastern Province', ar: 'المنطقة الشرقية' },
	{ key: 'asir', iso: 'SA-14', en: 'Asir', ar: 'عسير' },
	{ key: 'tabuk', iso: 'SA-07', en: 'Tabuk', ar: 'تبوك' },
	{ key: 'hail', iso: 'SA-06', en: 'Hail', ar: 'حائل' },
	{ key: 'northern_borders', iso: 'SA-08', en: 'Northern Borders', ar: 'الحدود الشمالية' },
	{ key: 'jazan', iso: 'SA-09', en: 'Jazan', ar: 'جازان' },
	{ key: 'najran', iso: 'SA-10', en: 'Najran', ar: 'نجران' },
	{ key: 'al_bahah', iso: 'SA-11', en: 'Al-Bahah', ar: 'الباحة' },
	{ key: 'al_jawf', iso: 'SA-12', en: 'Al-Jawf', ar: 'الجوف' }
] as const;

export type RegionKey = (typeof REGIONS)[number]['key'];

export function regionName(key: string | null | undefined, locale: 'ar' | 'en'): string {
	const r = REGIONS.find((x) => x.key === key);
	return r ? r[locale] : (key ?? '');
}

/** Major cities, offered as suggestions; the backend accepts any city name. */
export const CITIES: Record<string, { en: string; ar: string }[]> = {
	riyadh: [
		{ en: 'Riyadh', ar: 'الرياض' },
		{ en: 'Al Kharj', ar: 'الخرج' },
		{ en: 'Ad Diriyah', ar: 'الدرعية' }
	],
	makkah: [
		{ en: 'Jeddah', ar: 'جدة' },
		{ en: 'Makkah', ar: 'مكة المكرمة' },
		{ en: 'Taif', ar: 'الطائف' }
	],
	madinah: [
		{ en: 'Madinah', ar: 'المدينة المنورة' },
		{ en: 'Yanbu', ar: 'ينبع' }
	],
	eastern_province: [
		{ en: 'Dammam', ar: 'الدمام' },
		{ en: 'Khobar', ar: 'الخبر' },
		{ en: 'Dhahran', ar: 'الظهران' },
		{ en: 'Al Ahsa', ar: 'الأحساء' },
		{ en: 'Jubail', ar: 'الجبيل' }
	],
	qassim: [
		{ en: 'Buraydah', ar: 'بريدة' },
		{ en: 'Unaizah', ar: 'عنيزة' }
	],
	asir: [
		{ en: 'Abha', ar: 'أبها' },
		{ en: 'Khamis Mushait', ar: 'خميس مشيط' }
	],
	tabuk: [{ en: 'Tabuk', ar: 'تبوك' }],
	hail: [{ en: 'Hail', ar: 'حائل' }],
	northern_borders: [{ en: 'Arar', ar: 'عرعر' }],
	jazan: [{ en: 'Jazan', ar: 'جازان' }],
	najran: [{ en: 'Najran', ar: 'نجران' }],
	al_bahah: [{ en: 'Al Bahah', ar: 'الباحة' }],
	al_jawf: [{ en: 'Sakaka', ar: 'سكاكا' }]
};
