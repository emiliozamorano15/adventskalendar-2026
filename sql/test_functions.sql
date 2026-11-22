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

  -- p_today (debug mode) moves "today" for claims and co-op answers
  assert (claim_day(b, '__test_fut', '2999-12-01')->>'ok')::bool, 'p_today unlocks a future day';
  assert claim_day(b, '__test_std', '1999-11-30')->>'reason' = 'future', 'p_today in the past locks a day';

  -- kid_state
  assert (kid_state(a)->>'balance')::int = (select sum(amount) from ledger where kid_id = a), 'kid_state balance';
  assert json_array_length(kid_state(a)->'claimed') = 1, 'kid_state claimed days';
  assert (select (x->>'remaining')::int from json_array_elements(kid_state(a)->'items') x
          where (x->>'id')::int = s2) = 4, 'kid_state remaining stock skips cancelled';
  assert (select (x->>'mine')::int from json_array_elements(kid_state(a)->'items') x
          where (x->>'id')::int = s2) = 1, 'kid_state counts this kid only';
  assert not exists (select 1 from json_array_elements(kid_state(a)->'items') x where (x->>'id')::int = off),
         'kid_state hides inactive items';
  assert json_array_length(kid_state(a)->'purchases') = 1, 'kid_state hides cancelled purchases';
  assert (select x::jsonb ? 'image_url' from json_array_elements(kid_state(a)->'items') x limit 1), 'kid_state sends image_url';

  -- adjust_coins
  select sum(amount) into bal_a from ledger where kid_id = a;
  assert (adjust_coins(a, 5, ' bonus ')->>'balance')::int = bal_a + 5, 'adjust adds coins';
  assert (select ref from ledger where kid_id = a and reason = 'adjustment' order by id desc limit 1) = 'bonus', 'note trimmed';
  assert adjust_coins(a, 0, null)->>'reason' = 'zero', 'zero refused';
  assert adjust_coins(a, -100000, null)->>'reason' = 'negative', 'balance never below zero';
  assert adjust_coins(gen_random_uuid(), 5, null)->>'reason' = 'invalid', 'unknown kid refused';

  -- debug_reset_kid
  assert (debug_reset_kid(a)->>'ok')::bool, 'reset';
  assert (kid_state(a)->>'balance')::int = 0 and json_array_length(kid_state(a)->'purchases') = 0, 'reset wipes a';
  assert (kid_state(b)->>'balance')::int > 0, 'reset leaves b alone';

  raise notice 'functions.sql self-check OK';
end $$;
rollback;
