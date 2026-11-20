-- Run after schema.sql. Safe to re-run.

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
drop function if exists record_coop_solve(uuid, int);   -- pre-answer signature
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

-- Atomic purchase. Returns json {ok, reason, purchase_id}.
-- shared scope: one pool of `stock` for all kids, at most `per_kid_limit` each.
-- per_kid scope: every kid can buy up to `stock`.
create or replace function buy_item(p_kid uuid, p_item int)
returns json language plpgsql security definer set search_path = public as $$
declare it shop_items%rowtype; bal int; mine int; total int; cap int; pid uuid;
begin
  select * into it from shop_items where id = p_item and active for update;      -- lock item
  if not found then return json_build_object('ok', false, 'reason', 'not_found'); end if;
  perform 1 from kids where id = p_kid for update;                                -- lock kid
  select coalesce(sum(amount), 0) into bal from ledger where kid_id = p_kid;
  if bal < it.price then return json_build_object('ok', false, 'reason', 'no_coins'); end if;
  select count(*) filter (where kid_id = p_kid), count(*) into mine, total
    from purchases where item_id = p_item and status <> 'cancelled';
  if it.stock_scope = 'shared' and total >= it.stock then
    return json_build_object('ok', false, 'reason', 'sold_out');
  end if;
  cap := case it.stock_scope when 'shared' then it.per_kid_limit else it.stock end;   -- not inline: plpgsql IF stops at the first THEN
  if mine >= cap then
    return json_build_object('ok', false, 'reason', 'limit');
  end if;
  insert into purchases(kid_id, item_id, price_paid) values (p_kid, p_item, it.price) returning id into pid;
  insert into ledger(kid_id, amount, reason, ref) values (p_kid, -it.price, 'purchase', pid::text);
  return json_build_object('ok', true, 'purchase_id', pid);
end $$;

-- Cancel a purchase with refund (admin).
create or replace function cancel_purchase(p_purchase uuid)
returns json language plpgsql security definer set search_path = public as $$
declare p purchases%rowtype;
begin
  select * into p from purchases where id = p_purchase for update;
  if not found or p.status <> 'owned' then return json_build_object('ok', false); end if;
  update purchases set status = 'cancelled' where id = p_purchase;
  insert into ledger(kid_id, amount, reason, ref) values (p.kid_id, p.price_paid, 'refund', p_purchase::text);
  return json_build_object('ok', true);
end $$;

-- Lock the RPCs to the service role.
revoke execute on function claim_day, record_coop_solve, buy_item, cancel_purchase from public, anon, authenticated;
