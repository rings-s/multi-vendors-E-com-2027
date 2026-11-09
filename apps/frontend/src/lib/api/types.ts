/**
 * Friendly aliases for the generated OpenAPI schema (`schema.d.ts`).
 *
 * `schema.d.ts` is generated from the FastAPI app (`pnpm api:types`) and is the
 * single source of truth for request and response shapes. Never hand-write an
 * API type here; alias the generated one instead.
 */
import type { components } from './schema';

type S = components['schemas'];

export type UserPublic = S['UserPublic'];
export type TokenResponse = S['TokenResponse'];
export type SessionOut = S['SessionOut'];
export type CustomerMe = S['CustomerMe'];
export type Address = S['AddressOut'];
export type AddressCreate = S['AddressCreate'];

export type Store = S['StoreOut'];
export type StoreSummary = S['StoreSummary'];
export type StoreUpdate = S['StoreUpdate'];
export type Category = S['CategoryOut'];
export type Product = S['ProductOut'];
export type ProductIn = S['ProductIn'];
export type ProductUpdate = S['ProductUpdate'];
export type Variant = S['VariantOut'];
export type VariantIn = S['VariantIn'];
export type Service = S['ServiceOut'];
export type ServiceIn = S['ServiceIn'];
export type Review = S['ReviewOut'];
export type Image = S['ImageOut'];
export type ImageIn = S['ImageIn'];
export type Homepage = S['HomepageOut'];
export type HomepageSettings = S['HomepageSettings'];

export type Quote = S['QuoteOut'];
export type QuoteGroup = S['QuoteGroupOut'];
export type QuoteLine = S['QuoteLineOut'];
export type CheckoutRequest = S['CheckoutRequest'];
export type DeliveryChoices = S['DeliveryChoices'];
export type DeliverySelection = S['DeliverySelectionIn'];
export type DeliveryOption = S['DeliveryOptionOut'];
export type PickupPoint = S['PickupPointOut'];
export type Delivery = S['DeliveryOut'];
export type DeliveryEvent = S['DeliveryEventOut'];
export type DeliveryStatusUpdate = S['DeliveryStatusUpdate'];
export type DeliveryZone = S['ZoneOut'];
export type DeliveryZoneIn = S['ZoneIn'];
export type DeliverySettings = S['DeliverySettingsOut'];
export type DeliveryListItem = S['DeliveryListItem'];
export type PublicDelivery = S['PublicDeliveryOut'];

export type Order = S['OrderOut'];
export type OrderListItem = S['OrderListItem'];
export type MerchantOrderCustomerView = S['MerchantOrderCustomerView'];
export type MerchantOrderMerchantView = S['MerchantOrderMerchantView'];
export type OrderItem = S['OrderItemOut'];
export type StatusHistory = S['StatusHistoryOut'];
export type Payment = S['PaymentOut'];
export type PaymentSummary = S['PaymentSummary'];
export type PaymentAdmin = S['PaymentAdminOut'];
export type Refund = S['RefundOut'];
export type Chargeback = S['ChargebackOut'];

export type Merchant = S['MerchantOut'];
export type MerchantListItem = S['MerchantListItem'];
export type MerchantDetail = S['MerchantDetail'];
export type MerchantRegisterRequest = S['MerchantRegisterRequest'];
export type OnboardingUpdate = S['OnboardingUpdate'];
export type VerificationEvent = S['VerificationEventOut'];
export type PaymentAccount = S['PaymentAccountOut'];
export type PaymentOnboardingRequest = S['PaymentOnboardingRequest'];
export type BusinessType = S['BusinessType'];
export type Location = S['LocationOut'];
export type LocationIn = S['LocationIn'];
export type Inventory = S['InventoryOut'];

export type FinancialSummary = S['FinancialSummary'];
export type Dashboard = S['DashboardOut'];
export type DailyPoint = S['DailyPoint'];
export type RecentTransaction = S['RecentTransaction'];
export type CommissionTransaction = S['CommissionTransactionOut'];
export type CommissionRule = S['CommissionRuleOut'];
export type CommissionRuleAdmin = S['CommissionRuleAdminOut'];
export type CommissionRuleIn = S['CommissionRuleIn'];
export type Settlement = S['SettlementOut'];
export type AdminSettlement = S['AdminSettlementOut'];
export type MerchantCustomer = S['MerchantCustomerOut'];

export type AdminOverview = S['AdminOverview'];
export type Analytics = S['Analytics'];
export type AnalyticsKpis = S['AnalyticsKpis'];
export type TrendPoint = S['TrendPoint'];
export type WeekdayPoint = S['WeekdayPoint'];
export type BreakdownSlice = S['BreakdownSlice'];
export type RankedItem = S['RankedItem'];
export type Delta = S['Delta'];
export type RateDelta = S['RateDelta'];
export type AuditLog = S['AuditLogOut'];
export type WebhookEvent = S['WebhookEventOut'];
export type Reconciliation = S['ReconciliationOut'];
export type ProviderStatus = S['ProviderStatusOut'];
export type Notification = S['NotificationOut'];
export type NotificationPage = S['NotificationPage'];
export type AdminTicket = S['app__modules__admin__router__TicketOut'];
export type Ticket = S['app__modules__notifications__router__TicketOut'];

export type MerchantStatus = S['MerchantStatus'];
export type MerchantOrderStatus = S['MerchantOrderStatus'];
export type PaymentStatus = S['PaymentStatus'];
export type RefundStatus = S['RefundStatus'];
export type SettlementStatus = S['SettlementStatus'];
export type CatalogStatus = S['CatalogStatus'];
export type RoleName = S['RoleName'];

/** Every paginated endpoint returns this envelope (`app/core/pagination.py`). */
export interface Paged<T> {
	items: T[];
	total: number;
	page: number;
	page_size: number;
}

export type DataModelSummary = S['ModelSummary'];
export type DataModelSchema = S['ModelSchema'];
export type DataField = S['FieldOut'];
export type DataRow = S['RowOut'];
export type DataRowPage = S['RowPage'];
export type DataRowDetail = S['RowDetail'];
export type DataDeletePreview = S['DeletePreview'];
export type DataLookupItem = S['LookupItem'];
export type DataInline = S['InlineOut'];
