-- =========================================================
-- COURSE GUIDE — MVP SCHEMA (Supabase / Postgres)
-- =========================================================
-- User state only. Major requirement lists, openGroups, and
-- groupRules stay in Planner/config/majors/*.json + courses.json
-- for now (avoids syncing thousands of catalog rows + open bands).
--
-- Phase 2 can add normalized majors/requirements tables later.
-- See also: course_guide_schema.sql (earlier full-catalog draft).
-- =========================================================

-- ---------- ENUM TYPES ----------
create type program_type as enum ('major', 'minor', 'submajor');
create type course_source as enum ('pdf', 'manual');

-- ---------- PROFILES ----------
-- Extends Supabase auth.users
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- STUDENT PROGRAMS (declared majors / minors) ----------
-- config_id matches Planner/config/majors/<id>.json "id" field
-- e.g. 'computer-engineering', 'biology-health-and-society--...'
create table student_programs (
  id bigint generated always as identity primary key,
  student_id uuid not null references profiles(id) on delete cascade,
  config_id text not null,
  display_name text,                 -- optional cache of config displayName
  program_type program_type not null default 'major',
  created_at timestamptz not null default now(),
  unique (student_id, config_id)
);

create index idx_student_programs_student on student_programs(student_id);
create index idx_student_programs_config on student_programs(config_id);

-- ---------- TRANSCRIPT UPLOADS (optional audit / re-parse) ----------
-- Prefer deleting storage objects after confirm; keep row for history if useful.
create table transcript_uploads (
  id bigint generated always as identity primary key,
  student_id uuid not null references profiles(id) on delete cascade,
  storage_path text,                 -- supabase storage path; null if deleted after import
  original_filename text,
  status text not null default 'pending'
    check (status in ('pending', 'parsed', 'confirmed', 'failed')),
  error_message text,
  created_at timestamptz not null default now(),
  confirmed_at timestamptz
);

create index idx_transcript_uploads_student on transcript_uploads(student_id);

-- ---------- STUDENT COMPLETED COURSES ----------
-- course_code is the source of truth for matching JSON configs / courses.json
-- (UMich style: 'EECS 280', 'BIOLOGY 171'). No FK to a catalog table in MVP,
-- so PDF import can save codes that aren't in courses.json yet.
create table student_completed_courses (
  id bigint generated always as identity primary key,
  student_id uuid not null references profiles(id) on delete cascade,
  course_code text not null,         -- normalized 'SUBJECT CATALOG'
  title text,                        -- from transcript if available
  credits numeric check (credits is null or credits > 0),
  term_completed text,               -- e.g. 'Fall 2025'
  source course_source not null default 'manual',
  transcript_upload_id bigint references transcript_uploads(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (student_id, course_code)
);

create index idx_student_completed_courses_student
  on student_completed_courses(student_id);
create index idx_student_completed_courses_code
  on student_completed_courses(course_code);

-- ---------- MANUAL GROUP OVERRIDES ----------
-- For groupRules with completion: "manual" (messy prerequisites, credit pools)
-- or student disagreement with auto progress.
create table student_group_overrides (
  id bigint generated always as identity primary key,
  student_id uuid not null references profiles(id) on delete cascade,
  config_id text not null,           -- major config id
  group_name text not null,          -- must match requirementGroups key in JSON
  marked_complete boolean not null default true,
  note text,
  updated_at timestamptz not null default now(),
  unique (student_id, config_id, group_name)
);

create index idx_student_group_overrides_student
  on student_group_overrides(student_id);

-- =========================================================
-- ROW LEVEL SECURITY
-- =========================================================

alter table profiles enable row level security;
alter table student_programs enable row level security;
alter table transcript_uploads enable row level security;
alter table student_completed_courses enable row level security;
alter table student_group_overrides enable row level security;

-- ---------- profiles ----------
create policy "Users can view own profile"
  on profiles for select to authenticated
  using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Insert normally via trigger (security definer). Allow self-insert as fallback.
create policy "Users can insert own profile"
  on profiles for insert to authenticated
  with check (auth.uid() = id);

-- ---------- student_programs ----------
create policy "Users can view own programs"
  on student_programs for select to authenticated
  using (auth.uid() = student_id);

create policy "Users can insert own programs"
  on student_programs for insert to authenticated
  with check (auth.uid() = student_id);

create policy "Users can update own programs"
  on student_programs for update to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Users can delete own programs"
  on student_programs for delete to authenticated
  using (auth.uid() = student_id);

-- ---------- transcript_uploads ----------
create policy "Users can view own uploads"
  on transcript_uploads for select to authenticated
  using (auth.uid() = student_id);

create policy "Users can insert own uploads"
  on transcript_uploads for insert to authenticated
  with check (auth.uid() = student_id);

create policy "Users can update own uploads"
  on transcript_uploads for update to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Users can delete own uploads"
  on transcript_uploads for delete to authenticated
  using (auth.uid() = student_id);

-- ---------- student_completed_courses ----------
create policy "Users can view own completed courses"
  on student_completed_courses for select to authenticated
  using (auth.uid() = student_id);

create policy "Users can insert own completed courses"
  on student_completed_courses for insert to authenticated
  with check (auth.uid() = student_id);

create policy "Users can update own completed courses"
  on student_completed_courses for update to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Users can delete own completed courses"
  on student_completed_courses for delete to authenticated
  using (auth.uid() = student_id);

-- ---------- student_group_overrides ----------
create policy "Users can view own group overrides"
  on student_group_overrides for select to authenticated
  using (auth.uid() = student_id);

create policy "Users can insert own group overrides"
  on student_group_overrides for insert to authenticated
  with check (auth.uid() = student_id);

create policy "Users can update own group overrides"
  on student_group_overrides for update to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Users can delete own group overrides"
  on student_group_overrides for delete to authenticated
  using (auth.uid() = student_id);

-- =========================================================
-- HELPERS — always scoped to auth.uid() (no student_id arg)
-- Progress vs groupRules is computed in the app against JSON.
-- =========================================================

create or replace function get_my_completed_course_codes()
returns text[]
language sql
stable
security invoker
as $$
  select coalesce(array_agg(course_code order by course_code), '{}')
  from student_completed_courses
  where student_id = auth.uid();
$$;

create or replace function get_my_program_config_ids()
returns text[]
language sql
stable
security invoker
as $$
  select coalesce(array_agg(config_id order by config_id), '{}')
  from student_programs
  where student_id = auth.uid();
$$;

-- =========================================================
-- CLIENT USAGE (sketch)
-- =========================================================
-- 1) Guest: no Supabase calls — browse JSON as today.
-- 2) After login:
--    supabase.from('student_programs').select('*')
--    supabase.from('student_completed_courses').select('*')
--    supabase.from('student_group_overrides').select('*')
-- 3) Completion: isGroupComplete(...) in JS using Planner JSON groupRules.
-- 4) PDF: Storage upload → parse edge fn → insert source='pdf' → user confirms.
--
-- Phase 2: optional normalized majors/requirements tables when openGroups
-- and dual minCourses/minCredits are modeled in SQL.
-- See course_guide_schema.sql for an earlier full-catalog draft.
