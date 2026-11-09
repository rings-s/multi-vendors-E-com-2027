/**
 * Every backend error has the shape `{"error": {"code", "message", "details"}}`
 * (`apps/backend/app/core/errors.py`). The frontend translates `code`, never `message`.
 */
export interface ApiErrorBody {
	code: string;
	message: string;
	details?: unknown;
}

export interface FieldIssue {
	loc: (string | number)[];
	msg: string;
	type: string;
}

export class ApiError extends Error {
	readonly status: number;
	readonly code: string;
	readonly details: unknown;

	constructor(status: number, body: ApiErrorBody) {
		super(body.message);
		this.name = 'ApiError';
		this.status = status;
		this.code = body.code;
		this.details = body.details ?? null;
	}

	/**
	 * Request validation issues keyed by field path (without the leading `body`),
	 * e.g. `{ "address.city": "Field required" }`.
	 */
	get fieldErrors(): Record<string, string> {
		const out: Record<string, string> = {};
		if (this.code !== 'validation_failed' || !Array.isArray(this.details)) return out;
		for (const issue of this.details as FieldIssue[]) {
			if (!issue || !Array.isArray(issue.loc)) continue;
			const path = issue.loc.filter((p, i) => !(i === 0 && (p === 'body' || p === 'query')));
			const key = path.join('.') || '_';
			out[key] ??= cleanPydanticMessage(issue.msg);
		}
		return out;
	}
}

/** Pydantic prefixes custom validator messages with "Value error, ". */
function cleanPydanticMessage(msg: string): string {
	return msg.replace(/^Value error, /, '');
}

export function toApiError(status: number, payload: unknown): ApiError {
	if (payload && typeof payload === 'object' && 'error' in payload) {
		const body = (payload as { error: ApiErrorBody }).error;
		if (body && typeof body.code === 'string') return new ApiError(status, body);
	}
	return new ApiError(status, {
		code: status >= 500 ? 'internal_error' : `http_${status}`,
		message: 'Unexpected response from the server.'
	});
}

export function isApiError(e: unknown): e is ApiError {
	return e instanceof ApiError;
}
