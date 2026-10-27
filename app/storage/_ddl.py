"""Столбцы и ограничения рабочей базы. Версия схемы — 1."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO metadata (key, value) VALUES ('revision', '0');
CREATE TABLE IF NOT EXISTS catalog (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    generation TEXT NOT NULL CHECK (length(generation) = 32),
    filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 150),
    uploaded_at TEXT NOT NULL CHECK (length(uploaded_at) BETWEEN 20 AND 40),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64)
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY CHECK (length(id) = 32),
    sku TEXT NOT NULL UNIQUE CHECK (length(sku) BETWEEN 1 AND 80),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    unit TEXT NOT NULL CHECK (unit IN ('шт', 'упак')),
    pack_size INTEGER NOT NULL CHECK (pack_size BETWEEN 1 AND 1000000),
    price_kopecks INTEGER CHECK (
        price_kopecks IS NULL
        OR (price_kopecks >= 0 AND price_kopecks <= 99999999999999)
    ),
    price_basis TEXT NOT NULL CHECK (price_basis IN ('net', 'gross')),
    vat_bp INTEGER NOT NULL CHECK (vat_bp = 2000),
    source TEXT NOT NULL CHECK (length(source) BETWEEN 1 AND 500),
    updated_at TEXT NOT NULL CHECK (length(updated_at) BETWEEN 20 AND 40),
    CHECK ((unit = 'шт' AND pack_size = 1) OR unit = 'упак')
);
CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY CHECK (length(request_id) BETWEEN 1 AND 80),
    filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 150),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    uploaded_at TEXT NOT NULL CHECK (length(uploaded_at) BETWEEN 20 AND 40),
    discount_bp INTEGER NOT NULL CHECK (discount_bp BETWEEN 0 AND 10000),
    discount_draft TEXT NOT NULL CHECK (length(discount_draft) <= 16),
    company_name TEXT NOT NULL CHECK (length(company_name) <= 200),
    inn TEXT NOT NULL CHECK (
        inn = '' OR (length(inn) IN (10, 12) AND inn NOT GLOB '*[^0-9]*')
    ),
    kpp TEXT NOT NULL CHECK (
        kpp = '' OR (length(kpp) = 9 AND kpp NOT GLOB '*[^0-9]*')
    ),
    ogrn TEXT NOT NULL CHECK (
        ogrn = '' OR (length(ogrn) IN (13, 15) AND ogrn NOT GLOB '*[^0-9]*')
    ),
    address TEXT NOT NULL CHECK (length(address) <= 350),
    contact_name TEXT NOT NULL CHECK (length(contact_name) <= 200),
    email TEXT NOT NULL CHECK (length(email) <= 254),
    phone TEXT NOT NULL CHECK (length(phone) <= 40),
    bank_name TEXT NOT NULL CHECK (length(bank_name) <= 200),
    bik TEXT NOT NULL CHECK (
        bik = '' OR (length(bik) = 9 AND bik NOT GLOB '*[^0-9]*')
    ),
    account TEXT NOT NULL CHECK (
        account = '' OR (length(account) = 20 AND account NOT GLOB '*[^0-9]*')
    ),
    correspondent_account TEXT NOT NULL CHECK (
        correspondent_account = ''
        OR (
            length(correspondent_account) = 20
            AND correspondent_account NOT GLOB '*[^0-9]*'
        )
    ),
    draft_company_name TEXT NOT NULL CHECK (length(draft_company_name) <= 200),
    draft_inn TEXT NOT NULL CHECK (length(draft_inn) <= 12),
    draft_kpp TEXT NOT NULL CHECK (length(draft_kpp) <= 9),
    draft_ogrn TEXT NOT NULL CHECK (length(draft_ogrn) <= 15),
    draft_address TEXT NOT NULL CHECK (length(draft_address) <= 350),
    draft_contact_name TEXT NOT NULL CHECK (length(draft_contact_name) <= 200),
    draft_email TEXT NOT NULL CHECK (length(draft_email) <= 254),
    draft_phone TEXT NOT NULL CHECK (length(draft_phone) <= 40),
    draft_bank_name TEXT NOT NULL CHECK (length(draft_bank_name) <= 200),
    draft_bik TEXT NOT NULL CHECK (length(draft_bik) <= 9),
    draft_account TEXT NOT NULL CHECK (length(draft_account) <= 20),
    draft_correspondent_account TEXT NOT NULL
        CHECK (length(draft_correspondent_account) <= 20)
);
CREATE TABLE IF NOT EXISTS request_lines (
    request_id TEXT NOT NULL,
    line INTEGER NOT NULL CHECK (line BETWEEN 1 AND 1000000),
    sku TEXT NOT NULL CHECK (length(sku) <= 80),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 1000000),
    unit TEXT NOT NULL CHECK (unit = 'шт'),
    PRIMARY KEY (request_id, line),
    FOREIGN KEY (request_id) REFERENCES requests (request_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS request_selected (
    request_id TEXT NOT NULL,
    line INTEGER NOT NULL,
    PRIMARY KEY (request_id, line),
    FOREIGN KEY (request_id, line)
        REFERENCES request_lines (request_id, line) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS request_choices (
    request_id TEXT NOT NULL,
    line INTEGER NOT NULL,
    product_id TEXT NOT NULL,
    PRIMARY KEY (request_id, line),
    FOREIGN KEY (request_id, line)
        REFERENCES request_lines (request_id, line) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS quotes (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE CHECK (length(id) = 32),
    number TEXT NOT NULL CHECK (length(number) BETWEEN 1 AND 20),
    created_at TEXT NOT NULL CHECK (length(created_at) BETWEEN 20 AND 40),
    idempotency_key TEXT UNIQUE CHECK (
        idempotency_key IS NULL OR length(idempotency_key) = 32
    ),
    filename TEXT NOT NULL CHECK (length(filename) BETWEEN 1 AND 180),
    pdf BLOB NOT NULL,
    request_id TEXT NOT NULL CHECK (length(request_id) BETWEEN 1 AND 80),
    discount_bp INTEGER NOT NULL CHECK (discount_bp BETWEEN 0 AND 10000),
    vat_bp INTEGER NOT NULL CHECK (vat_bp = 2000),
    currency TEXT NOT NULL CHECK (currency = 'RUB'),
    confirmed_count INTEGER NOT NULL CHECK (confirmed_count >= 0),
    unresolved_count INTEGER NOT NULL CHECK (unresolved_count >= 0),
    is_complete INTEGER NOT NULL CHECK (is_complete IN (0, 1)),
    subtotal_kopecks INTEGER NOT NULL CHECK (subtotal_kopecks >= 0),
    vat_kopecks INTEGER NOT NULL CHECK (vat_kopecks >= 0),
    selected_count INTEGER NOT NULL CHECK (selected_count >= 0),
    excluded_count INTEGER NOT NULL CHECK (excluded_count >= 0),
    calculation_complete INTEGER NOT NULL CHECK (calculation_complete IN (0, 1)),
    buyer_name TEXT NOT NULL CHECK (length(buyer_name) <= 200),
    request_filename TEXT CHECK (
        request_filename IS NULL OR length(request_filename) BETWEEN 1 AND 150
    ),
    request_sha256 TEXT CHECK (
        request_sha256 IS NULL OR length(request_sha256) = 64
    ),
    price_filename TEXT CHECK (
        price_filename IS NULL OR length(price_filename) BETWEEN 1 AND 150
    ),
    price_sha256 TEXT CHECK (price_sha256 IS NULL OR length(price_sha256) = 64),
    seller_company_name TEXT NOT NULL CHECK (length(seller_company_name) <= 200),
    seller_inn TEXT NOT NULL CHECK (length(seller_inn) <= 12),
    seller_kpp TEXT NOT NULL CHECK (length(seller_kpp) <= 9),
    seller_ogrn TEXT NOT NULL CHECK (length(seller_ogrn) <= 15),
    seller_address TEXT NOT NULL CHECK (length(seller_address) <= 350),
    seller_phone TEXT NOT NULL CHECK (length(seller_phone) <= 40),
    seller_email TEXT NOT NULL CHECK (length(seller_email) <= 254),
    seller_website TEXT NOT NULL CHECK (length(seller_website) <= 200),
    seller_bank_name TEXT NOT NULL CHECK (length(seller_bank_name) <= 200),
    seller_bik TEXT NOT NULL CHECK (length(seller_bik) <= 9),
    seller_account TEXT NOT NULL CHECK (length(seller_account) <= 20),
    seller_correspondent_account TEXT NOT NULL
        CHECK (length(seller_correspondent_account) <= 20),
    seller_manager TEXT NOT NULL CHECK (length(seller_manager) <= 200),
    seller_manager_title TEXT NOT NULL CHECK (length(seller_manager_title) <= 200),
    buyer_company_name TEXT NOT NULL CHECK (length(buyer_company_name) <= 200),
    buyer_inn TEXT NOT NULL CHECK (length(buyer_inn) <= 12),
    buyer_kpp TEXT NOT NULL CHECK (length(buyer_kpp) <= 9),
    buyer_ogrn TEXT NOT NULL CHECK (length(buyer_ogrn) <= 15),
    buyer_address TEXT NOT NULL CHECK (length(buyer_address) <= 350),
    buyer_contact_name TEXT NOT NULL CHECK (length(buyer_contact_name) <= 200),
    buyer_email TEXT NOT NULL CHECK (length(buyer_email) <= 254),
    buyer_phone TEXT NOT NULL CHECK (length(buyer_phone) <= 40),
    buyer_bank_name TEXT NOT NULL CHECK (length(buyer_bank_name) <= 200),
    buyer_bik TEXT NOT NULL CHECK (length(buyer_bik) <= 9),
    buyer_account TEXT NOT NULL CHECK (length(buyer_account) <= 20),
    buyer_correspondent_account TEXT NOT NULL
        CHECK (length(buyer_correspondent_account) <= 20)
);
CREATE TABLE IF NOT EXISTS quote_lines (
    quote_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    request_id TEXT NOT NULL,
    line INTEGER NOT NULL,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit TEXT NOT NULL CHECK (unit = 'шт'),
    status TEXT NOT NULL CHECK (
        status IN (
            'confirmed', 'needs_clarification', 'missing_price',
            'not_found', 'quantity_mismatch'
        )
    ),
    sale_quantity INTEGER,
    discounted_kopecks INTEGER,
    unit_kopecks INTEGER,
    total_kopecks INTEGER,
    vat_kopecks INTEGER,
    note TEXT NOT NULL CHECK (length(note) <= 500),
    manually_selected INTEGER NOT NULL CHECK (manually_selected IN (0, 1)),
    selected_id TEXT,
    selected_sku TEXT,
    selected_name TEXT,
    selected_unit TEXT,
    selected_pack_size INTEGER,
    selected_price_kopecks INTEGER,
    selected_price_basis TEXT,
    selected_vat_bp INTEGER,
    selected_source TEXT,
    selected_updated_at TEXT,
    PRIMARY KEY (quote_id, position),
    FOREIGN KEY (quote_id) REFERENCES quotes (id)
);
CREATE TABLE IF NOT EXISTS quote_candidates (
    quote_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    candidate_index INTEGER NOT NULL CHECK (candidate_index >= 0),
    id TEXT NOT NULL,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    pack_size INTEGER NOT NULL,
    price_kopecks INTEGER,
    price_basis TEXT NOT NULL,
    vat_bp INTEGER NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (quote_id, position, candidate_index),
    FOREIGN KEY (quote_id, position)
        REFERENCES quote_lines (quote_id, position) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS quote_missing_fields (
    quote_id TEXT NOT NULL,
    field TEXT NOT NULL CHECK (
        field IN ('company_name', 'inn', 'address')
    ),
    PRIMARY KEY (quote_id, field),
    FOREIGN KEY (quote_id) REFERENCES quotes (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pending_imports (
    token TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('price', 'request')),
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    payload BLOB NOT NULL,
    revision INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);
"""
