-- =========================================================
-- Drop unused columns (run in Supabase SQL Editor)
-- =========================================================

alter table public.profiles
  drop column if exists full_name;

alter table public.student_completed_courses
  drop column if exists grade;

-- Keep profile auto-create in sync (id only)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;
