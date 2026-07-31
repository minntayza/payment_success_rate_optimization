-- Run this file in the Supabase SQL editor. It is safe to run more than once.

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table if not exists public.transactions (
  transaction_id text primary key,
  sender_account_id text not null,
  receiver_account_id text not null,
  transaction_amount numeric(12, 2) not null check (transaction_amount >= 0),
  transaction_type text not null check (transaction_type in ('Transfer', 'Deposit', 'Withdrawal')),
  transaction_timestamp timestamptz not null,
  transaction_status text not null check (transaction_status in ('Success', 'Failed')),
  fraud_flag boolean not null,
  geolocation text not null,
  device_used text not null check (device_used in ('Mobile', 'Desktop')),
  network_slice_id text not null,
  latency_ms numeric not null check (latency_ms >= 0),
  slice_bandwidth_mbps numeric not null check (slice_bandwidth_mbps >= 0),
  pin_code text not null,
  bank_gateway text not null check (bank_gateway in ('Gateway A', 'Gateway B', 'Gateway C', 'Gateway D')),
  is_deleted boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  created_by uuid references auth.users(id),
  updated_by uuid references auth.users(id),
  deleted_by uuid references auth.users(id)
);

create table if not exists public.transaction_audit_log (
  audit_id bigint generated always as identity primary key,
  transaction_id text not null,
  action text not null check (action in ('INSERT', 'UPDATE', 'SOFT_DELETE')),
  actor_id uuid,
  changed_at timestamptz not null default now(),
  old_row jsonb,
  new_row jsonb
);

create index if not exists transactions_active_timestamp_idx
  on public.transactions (transaction_timestamp) where is_deleted = false;
create index if not exists transactions_gateway_status_idx
  on public.transactions (bank_gateway, transaction_status);

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.admin_users where user_id = auth.uid()
  );
$$;

create or replace function public.set_transaction_metadata()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    new.created_by := coalesce(auth.uid(), new.created_by);
  end if;
  new.updated_at := now();
  new.updated_by := coalesce(auth.uid(), new.updated_by);
  if tg_op = 'UPDATE' and new.is_deleted and not old.is_deleted then
    new.deleted_at := now();
    new.deleted_by := auth.uid();
  end if;
  return new;
end;
$$;

create or replace function public.audit_transaction_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  audit_action text;
begin
  audit_action := tg_op;
  if tg_op = 'UPDATE' and new.is_deleted and not old.is_deleted then
    audit_action := 'SOFT_DELETE';
  end if;
  insert into public.transaction_audit_log (
    transaction_id, action, actor_id, old_row, new_row
  ) values (
    new.transaction_id,
    audit_action,
    auth.uid(),
    case when tg_op = 'INSERT' then null else to_jsonb(old) end,
    to_jsonb(new)
  );
  return new;
end;
$$;

drop trigger if exists transactions_metadata_trigger on public.transactions;
create trigger transactions_metadata_trigger
before insert or update on public.transactions
for each row execute function public.set_transaction_metadata();

drop trigger if exists transactions_audit_trigger on public.transactions;
create trigger transactions_audit_trigger
after insert or update on public.transactions
for each row execute function public.audit_transaction_change();

alter table public.admin_users enable row level security;
alter table public.transactions enable row level security;
alter table public.transaction_audit_log enable row level security;

drop policy if exists "active transactions are publicly readable" on public.transactions;
create policy "active transactions are publicly readable"
on public.transactions for select
using (is_deleted = false);

drop policy if exists "admins insert transactions" on public.transactions;
create policy "admins insert transactions"
on public.transactions for insert to authenticated
with check (public.is_admin());

drop policy if exists "admins update transactions" on public.transactions;
create policy "admins update transactions"
on public.transactions for update to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "admins can verify membership" on public.admin_users;
create policy "admins can verify membership"
on public.admin_users for select to authenticated
using (user_id = auth.uid());

drop policy if exists "admins read audit log" on public.transaction_audit_log;
create policy "admins read audit log"
on public.transaction_audit_log for select to authenticated
using (public.is_admin());

revoke insert, update, delete on public.transaction_audit_log from anon, authenticated;
