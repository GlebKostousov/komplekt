export type Page = 'requests' | 'price' | 'quote' | 'history';
export type ImportKind = 'request' | 'price';
export type Money = string;
export interface Issue {
  row: number | null;
  field: string | null;
  value: string | null;
  message: string;
}
export interface ApiProblem {
  code: string;
  message: string;
  issues: Issue[];
}
export interface Product {
  id: string;
  sku: string;
  name: string;
  unit: 'шт' | 'упак';
  pack_size: number;
  price: Money | null;
  price_basis: 'net' | 'gross';
  vat_rate: string;
  source: string;
  updated_at: string;
}
export interface RequestRow {
  request_id: string;
  line: number;
  sku: string;
  name: string;
  quantity: number;
  unit: 'шт';
}
export interface Buyer {
  company_name: string;
  inn: string;
  kpp: string;
  ogrn: string;
  address: string;
  contact_name: string;
  email: string;
  phone: string;
  bank_name: string;
  bik: string;
  account: string;
  correspondent_account: string;
}
export interface Seller {
  company_name: string;
  inn: string;
  kpp: string;
  ogrn: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  bank_name: string;
  bik: string;
  account: string;
  correspondent_account: string;
  manager: string;
  manager_title: string;
}
export interface RequestRecord {
  request_id: string;
  filename: string;
  sha256: string;
  uploaded_at: string;
  rows: RequestRow[];
  buyer: Buyer;
  buyer_draft: Buyer;
  selected_lines: number[];
  choices: Record<string, string>;
  discount_percent: Money;
  discount_draft: string;
}
export interface QuoteSummary {
  id: string;
  number: string;
  created_at: string;
  request_id: string;
  buyer_name: string;
  subtotal_with_vat: Money;
  vat_amount: Money;
  is_complete: boolean;
  selected_count: number;
  unresolved_count: number;
  filename: string;
}
export interface State {
  revision: number;
  catalog: {
    generation: string;
    filename: string;
    uploaded_at: string;
    sha256: string;
    products: Product[];
  } | null;
  requests: RequestRecord[];
  quotes: QuoteSummary[];
  seller: Seller;
  assumptions: string[];
}
export interface ImportPreview {
  token: string;
  revision: number;
  kind: ImportKind;
  filename: string;
  row_count: number;
  request_id: string | null;
  rows: Record<string, string | number | null>[];
  warnings: Issue[];
  changes: { added: number; changed: number; removed: number; replaces_request: boolean };
  expires_at: string;
}
export type LineStatus =
  'confirmed' | 'needs_clarification' | 'missing_price' | 'not_found' | 'quantity_mismatch';
export interface QuoteLine {
  request: RequestRow;
  status: LineStatus;
  selected: Product | null;
  sale_quantity: number | null;
  discounted_price: Money | null;
  unit_price_with_vat: Money | null;
  total_with_vat: Money | null;
  vat_amount: Money | null;
  candidates: Product[];
  note: string;
  manually_selected: boolean;
}
export interface Draft {
  request_id: string;
  lines: QuoteLine[];
  discount_percent: Money;
  vat_rate: string;
  currency: 'RUB';
  confirmed_count: number;
  unresolved_count: number;
  selected_count: number;
  excluded_count: number;
  calculation_complete: boolean;
  is_complete: boolean;
  missing_buyer_fields: string[];
  subtotal_with_vat: Money;
  vat_amount: Money;
  buyer: Buyer;
  request_source: { name: string; sha256: string };
  price_source: { name: string; sha256: string } | null;
}
export interface SavedQuote {
  id: string;
  number: string;
  created_at: string;
  seller: Seller;
  quote: Draft;
}
export type StateHandler = (value: State) => void;
export type Navigate = (page: Page, requestId?: string) => void;
