-- Adventskalender 2026 – schema. Run in the Supabase SQL editor.
create extension if not exists pgcrypto;

create table if not exists kids (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  token text not null unique default encode(gen_random_bytes(24), 'hex'),
  pin_hash text not null,
  failed_attempts int not null default 0,
  locked_until timestamptz,
  level text not null default 'easy' check (level in ('easy',
 'hard'))
);

create table if not exists days (
  id serial primary key,
  date date not null unique,
  day_type text not null check (day_type in ('standard','split','coop','finale')),
  chapter_text text not null,
  riddle_easy text,
  riddle_hard text,
  answer text,
  coop_half_a text,
  coop_half_b text,
  secret text not null unique default encode(gen_random_bytes(6), 'hex'),
  base_coins int not null default 10,
  coop_bonus int not null default 0
);

create table if not exists claims (
  id bigserial primary key,
  kid_id uuid not null references kids(id),
  day_id int not null references days(id),
  claimed_at timestamptz not null default now(),
  unique (kid_id, day_id)
);

create table if not exists coop_solves (
  id bigserial primary key,
  kid_id uuid not null references kids(id),
  day_id int not null references days(id),
  solved_at timestamptz not null default now(),
  unique (kid_id, day_id)
);

create table if not exists shop_items (
  id serial primary key,
  name text not null,
  description text,
  price int not null check (price > 0),
  stock int not null check (stock >= 0),   -- pieces for all kids together
  per_kid_limit int not null default 1,    -- max pieces per kid
  kind text not null default 'voucher' check (kind in ('present','voucher')),
  active boolean not null default true,
  image_url text                           -- shop card picture; null shows the kind emoji
);
create unique index if not exists shop_items_name_idx on shop_items(name);   -- seed upserts on name

create table if not exists purchases (
  id uuid primary key default gen_random_uuid(),
  kid_id uuid not null references kids(id),
  item_id int not null references shop_items(id),
  price_paid int not null,
  -- owned: bought. requested: the kid wants to use the voucher now (the kid can undo it).
  -- redeemed: voucher used, or present handed over, confirmed by the admin. cancelled: refunded.
  status text not null default 'owned' check (status in ('owned','requested','redeemed','cancelled')),
  purchased_at timestamptz not null default now(),
  requested_at timestamptz,
  redeemed_at timestamptz
);

-- One row once the admin changes the PIN in the app; until then the app checks ADMIN_PIN from secrets.
create table if not exists admin (
  id int primary key default 1 check (id = 1),
  pin_hash text not null
);

create table if not exists ledger (
  id bigserial primary key,
  kid_id uuid not null references kids(id),
  amount int not null,
  reason text not null,   -- claim | coop_bonus | purchase | refund | adjustment
  ref text,
  created_at timestamptz not null default now()
);
create index if not exists ledger_kid_idx on ledger(kid_id);

-- RLS on, no policies: only the service key (Streamlit server) gets through.
alter table kids enable row level security;
alter table days enable row level security;
alter table claims enable row level security;
alter table coop_solves enable row level security;
alter table shop_items enable row level security;
alter table purchases enable row level security;
alter table ledger enable row level security;
alter table admin enable row level security;

-- Upgrades for databases created from an older version of this file. Safe to re-run.
alter table kids add column if not exists level text not null default 'easy'
  check (level in ('easy','hard'));
alter table shop_items add column if not exists active boolean not null default true;
update shop_items set per_kid_limit = 1 where per_kid_limit is null;
alter table shop_items alter column per_kid_limit set default 1, alter column per_kid_limit set not null;
alter table shop_items add column if not exists kind text not null default 'voucher'
  check (kind in ('present','voucher'));
alter table shop_items drop column if exists stock_scope;
alter table shop_items add column if not exists image_url text;
-- Tables created before these defaults existed have none, so new kids and days from the seed failed.
alter table kids alter column token set default encode(gen_random_bytes(24), 'hex');
alter table days alter column secret set default encode(gen_random_bytes(6), 'hex');
alter table purchases add column if not exists requested_at timestamptz;
alter table purchases drop constraint if exists purchases_status_check;
alter table purchases add constraint purchases_status_check
  check (status in ('owned','requested','redeemed','cancelled'));
