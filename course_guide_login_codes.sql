-- Login codes replace student emails for sign-in.
-- Run in Supabase SQL editor after course_guide_schema_mvp.sql.
-- Also disable email confirmation in Supabase Auth settings (no real inboxes).

alter table public.profiles
  add column if not exists login_code text;

create unique index if not exists profiles_login_code_key
  on public.profiles (login_code)
  where login_code is not null;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  code text;
begin
  code := nullif(trim(new.raw_user_meta_data->>'login_code'), '');
  insert into public.profiles (id, login_code)
  values (new.id, code);
  return new;
end;
$$;
