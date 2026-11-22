-- Run after schema.sql. Safe to re-run.

-- Drop first: create or replace can't change a function's return type, and an older draft may have used
-- another one. Nothing depends on these functions, and the revoke at the end runs after the new creates.
drop function if exists claim_day(uuid, text);
drop function if exists record_coop_solve(uuid, int);         -- pre-answer signature
drop function if exists record_coop_solve(uuid, int, text);
drop function if exists buy_item(uuid, int);                  -- single-item predecessor of buy_cart
drop function if exists buy_cart(uuid, int[]);
drop function if exists cancel_purchase(uuid);

-- Claim a day by QR secret. Returns json {ok, reason, coins, day_id}.
create or replace function claim_day(p_kid uuid, p_secret text)
returns json language plpgsql security definer set search_path = public as $$
declare d days%rowtype; today date := (now() at time zone 'Europe/Berlin')::date;
begin
  select * into d from days where secret = p_secret;
  if not found then return json_build_object('ok', false, 'reason', 'invalid'); end if;
  if d.date > today then return json_build_object('ok', false, 'reason', 'future'); end if;
  if exists (select 1 from claims where kid_id = p_kid and day_id = d.id) then
    return json_build_object('ok', false, 'reason', 'already', 'day_id', d.id);
  end if;
  insert into claims(kid_id, day_id) values (p_kid, d.id);
  insert into ledger(kid_id, amount, reason, ref) values (p_kid, d.base_coins, 'claim', d.id::text);
  return json_build_object('ok', true, 'coins', d.base_coins, 'day_id', d.id);
end $$;

-- Check a co-op answer; once both kids solved it, pay the bonus to both exactly once.
-- Returns json {ok, reason, bonus_paid, bonus}.
create or replace function record_coop_solve(p_kid uuid, p_day int, p_answer text)
returns json language plpgsql security definer set search_path = public as $$
declare d days%rowtype; n int; k record; today date := (now() at time zone 'Europe/Berlin')::date;
begin
  select * into d from days where id = p_day and day_type = 'coop' for update;   -- serialises both kids
  if not found then return json_build_object('ok', false, 'reason', 'invalid'); end if;
  if d.date > today then return json_build_object('ok', false, 'reason', 'future'); end if;
  if d.answer is null or lower(btrim(p_answer)) is distinct from lower(btrim(d.answer)) then
    return json_build_object('ok', false, 'reason', 'wrong');
  end if;
  insert into coop_solves(kid_id, day_id) values (p_kid, p_day) on conflict do nothing;
  select count(distinct kid_id) into n from coop_solves where day_id = p_day;
  if n >= 2 and not exists (select 1 from ledger where reason = 'coop_bonus' and ref = p_day::text) then
    for k in select distinct kid_id from coop_solves where day_id = p_day loop
      insert into ledger(kid_id, amount, reason, ref) values (k.kid_id, d.coop_bonus, 'coop_bonus', p_day::text);
    end loop;
    return json_build_object('ok', true, 'bonus_paid', true, 'bonus', d.coop_bonus);
  end if;
  return json_build_object('ok', true, 'bonus_paid', false);
end $$;

-- Atomic checkout. p_items holds one item id per piece, so array[3, 3, 5] buys two of item 3 and one of item 5.
-- Each item has `stock` pieces for all kids together and at most `per_kid_limit` per kid.
-- Every check runs before the first insert, so a refused cart writes nothing.
-- Returns json {ok, reason, item_id, cost}.
create or replace function buy_cart(p_kid uuid, p_items int[])
returns json language plpgsql security definer set search_path = public as $$
declare it record; bal int; cost int := 0;
begin
  perform 1 from kids where id = p_kid for update;                                      -- one checkout per kid at a time
  perform 1 from shop_items where id = any(p_items) order by id for update;             -- id order: two carts can't deadlock
  for it in
    select c.item_id, c.qty, i.price, i.stock, i.per_kid_limit, i.active,
           count(p.id) filter (where p.status <> 'cancelled') as sold,
           count(p.id) filter (where p.status <> 'cancelled' and p.kid_id = p_kid) as mine
    from (select x as item_id, count(*) as qty from unnest(p_items) x group by x) c
    left join shop_items i on i.id = c.item_id
    left join purchases p on p.item_id = c.item_id
    group by c.item_id, c.qty, i.price, i.stock, i.per_kid_limit, i.active
  loop
    if it.price is null or not it.active then
      return json_build_object('ok', false, 'reason', 'not_found', 'item_id', it.item_id);
    end if;
    if it.sold + it.qty > it.stock then
      return json_build_object('ok', false, 'reason', 'sold_out', 'item_id', it.item_id);
    end if;
    if it.mine + it.qty > it.per_kid_limit then
      return json_build_object('ok', false, 'reason', 'limit', 'item_id', it.item_id);
    end if;
    cost := cost + it.price * it.qty;
  end loop;
  select coalesce(sum(amount), 0) into bal from ledger where kid_id = p_kid;
  if bal < cost then return json_build_object('ok', false, 'reason', 'no_coins'); end if;
  with bought as (
    insert into purchases(kid_id, item_id, price_paid)
    select p_kid, i.id, i.price from unnest(p_items) x join shop_items i on i.id = x
    returning id, price_paid
  )
  insert into ledger(kid_id, amount, reason, ref) select p_kid, -price_paid, 'purchase', id::text from bought;
  return json_build_object('ok', true, 'cost', cost);
end $$;

-- Cancel an open purchase with refund (admin). A requested voucher counts as open.
create or replace function cancel_purchase(p_purchase uuid)
returns json language plpgsql security definer set search_path = public as $$
declare p purchases%rowtype;
begin
  select * into p from purchases where id = p_purchase for update;
  if not found or p.status not in ('owned', 'requested') then return json_build_object('ok', false); end if;
  update purchases set status = 'cancelled' where id = p_purchase;
  insert into ledger(kid_id, amount, reason, ref) values (p.kid_id, p.price_paid, 'refund', p_purchase::text);
  return json_build_object('ok', true);
end $$;

-- Lock the RPCs to the service role.
revoke execute on function claim_day, record_coop_solve, buy_cart, cancel_purchase from public, anon, authenticated;
