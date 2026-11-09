/**
 * Customer payment flow. One provider payment exists per merchant order (split
 * payments, `docs/architecture/payment-architecture.md`). The frontend never decides
 * whether a payment succeeded: after the provider redirects back, the result page
 * asks the backend to sync with the provider (`POST /payments/{id}/sync`).
 */
import { goto } from '$app/navigation';
import { api, call, paymentRedirectUrl } from '#lib/api/client.js';
import type { MerchantOrderCustomerView, Payment, PaymentSummary } from '#lib/api/types.js';

export class ProviderFormRequired extends Error {}

const RETRYABLE = new Set(['FAILED', 'CANCELLED']);

export function needsPayment(mo: MerchantOrderCustomerView): boolean {
	return mo.status === 'PENDING_PAYMENT';
}

export function reservationExpired(mo: MerchantOrderCustomerView, now = Date.now()): boolean {
	return !!mo.reservation_expires_at && new Date(mo.reservation_expires_at).getTime() < now;
}

/** Start (or resume, or retry) the payment for one store's order and redirect the payer. */
export async function payMerchantOrder(
	mo: MerchantOrderCustomerView,
	mock: boolean
): Promise<void> {
	let payment: PaymentSummary | Payment | null = mo.payment;
	if (!payment || RETRYABLE.has(payment.status)) {
		payment = await call(
			api.POST('/api/v1/payments/merchant-orders/{mo_id}/retry', {
				params: { path: { mo_id: mo.id } }
			})
		);
	}
	if (payment.status === 'PENDING' && payment.transaction_url) {
		location.assign(paymentRedirectUrl(payment.transaction_url));
		return;
	}
	if (payment.status === 'CREATED') {
		// Real providers need card data tokenised by their own hosted form; the mock
		// provider offers a hosted test page instead.
		if (!mock) throw new ProviderFormRequired();
		payment = await call(
			api.POST('/api/v1/payments/{payment_id}/pay', {
				params: { path: { payment_id: payment.id } },
				body: { source: { type: 'mock', outcome: 'redirect' } }
			})
		);
	}
	if (payment.transaction_url) {
		location.assign(paymentRedirectUrl(payment.transaction_url));
	} else {
		await goto(`/checkout/result?payment_id=${payment.id}`);
	}
}
