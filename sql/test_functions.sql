-- Self-check for functions.sql. Runs inside a transaction and rolls back, so it leaves no rows behind.
-- Run after schema.sql + functions.sql (Supabase SQL editor or any Postgres). Fails with the assert message.
begin;
do $$
declare
  a uuid; b uuid; s1 int; s2 int; pricey int; off int; coop int; std int; fut int; pid uuid;
  bal_a int;
begin
  insert into kids(name, pin_hash) values ('__test_a', 'x') returning id into a;
  insert into kids(name, pin_hash) values ('__test_b', 'x') returning id into b;
  insert into ledger(kid_id, amount, reason) values (a, 100, 'adjustment'), (b, 100, 'adjustment');

  -- buy_cart
  insert into shop_items(name, price, stock, per_kid_limit) values ('__test_s1', 10, 1, 5) returning id into s1;
  insert into shop_items(name, price, stock, per_kid_limit) values ('__test_s2', 10, 5, 2) returning id into s2;
  insert into shop_items(name, price, stock) values ('__test_pricey', 1000, 9) returning id into pricey;
  insert into shop_items(name, price, stock, active) values ('__test_off', 1, 9, false) returning id into off;

  assert (buy_cart(a, array[s1, s2, s2])->>'cost')::int = 30, 'a buys a mixed cart';
  assert buy_cart(b, array[s1])->>'reason' = 'sold_out', 'stock is one pool for all kids';
  assert buy_cart(a, array[s2])->>'reason' = 'limit', 'per_kid_limit counts earlier purchases';
  assert buy_cart(b, array[s2, s2, s2])->>'reason' = 'limit', 'per_kid_limit counts pieces in the cart';
  assert buy_cart(b, array[s2, pricey])->>'reason' = 'no_coins', 'balance checked against the cart total';
  assert buy_cart(b, array[off])->>'reason' = 'not_found', 'inactive item refused';
  assert buy_cart(b, array[-1])->>'reason' = 'not_found', 'unknown item refused';
  assert not exists (select 1 from purchases where kid_id = b), 'refused carts write nothing';
  select sum(amount) into bal_a from ledger where kid_id = a;
  assert bal_a = 70, format('a spent 30, balance %s', bal_a);

  -- cancel_purchase refunds and frees the stock
  select id into pid from purchases where kid_id = a and item_id = s1;
  assert (cancel_purchase(pid)->>'ok')::bool, 'cancel s1';
  assert not (cancel_purchase(pid)->>'ok')::bool, 'cancel twice refused';
  select sum(amount) into bal_a from ledger where kid_id = a;
  assert bal_a = 80, format('refund booked, balance %s', bal_a);
  assert (buy_cart(b, array[s1])->>'ok')::bool, 'cancelled purchase frees stock';
  select id into pid from purchases where kid_id = a and item_id = s2 limit 1;
  update purchases set status = 'requested' where id = pid;
  assert (cancel_purchase(pid)->>'ok')::bool, 'requested voucher can be cancelled';

  -- claim_day
  insert into days(date, day_type, chapter_text, secret, base_coins) values ('1999-12-01', 'standard', 't', '__test_std', 7) returning id into std;
  insert into days(date, day_type, chapter_text, secret) values ('2999-12-01', 'standard', 't', '__test_fut') returning id into fut;
  assert (claim_day(a, '__test_std')->>'coins')::int = 7, 'claim pays base_coins';
  assert claim_day(a, '__test_std')->>'reason' = 'already', 'claim once per kid';
  assert claim_day(a, '__test_fut')->>'reason' = 'future', 'future claim refused';
  assert claim_day(a, '__nope__')->>'reason' = 'invalid', 'unknown secret refused';

  -- record_coop_solve
  insert into days(date, day_type, chapter_text, secret, answer, coop_bonus) values ('1999-12-02', 'coop', 't', '__test_coop', 'Reno', 5) returning id into coop;
  assert record_coop_solve(a, coop, 'zorro')->>'reason' = 'wrong', 'wrong answer refused';
  assert record_coop_solve(a, coop, null)->>'reason' = 'wrong', 'null answer refused';
  assert record_coop_solve(a, std, 'Reno')->>'reason' = 'invalid', 'non-coop day refused';
  assert not (record_coop_solve(a, coop, '  reno ')->>'bonus_paid')::bool, 'first solver waits';
  assert (record_coop_solve(b, coop, 'RENO')->>'bonus_paid')::bool, 'second solver triggers bonus';
  assert not (record_coop_solve(b, coop, 'Reno')->>'bonus_paid')::bool, 'bonus paid once';
  assert (select count(*) from ledger where reason = 'coop_bonus' and ref = coop::text) = 2, 'one bonus row per kid';

  raise notice 'functions.sql self-check OK';
end $$;
rollback;
