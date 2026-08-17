-- =========================================================
-- COURSE GUIDE SCHEMA — Supabase (Postgres)
-- =========================================================

-- ---------- ENUM TYPES ----------
create type requirement_type as enum ('course_count', 'credit_count');

-- ---------- PROFILES ----------
-- Extends Supabase's built-in auth.users
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- ---------- MAJORS ----------
create table majors (
  id bigint generated always as identity primary key,
  name text not null unique
);

-- ---------- COURSES ----------
create table courses (
  id bigint generated always as identity primary key,
  code text not null unique,       -- e.g. 'CS 301'
  title text not null,
  credits numeric not null check (credits > 0)
);

-- ---------- REQUIREMENTS ----------
create table requirements (
  id bigint generated always as identity primary key,
  major_id bigint not null references majors(id) on delete cascade,
  name text not null,                          -- e.g. 'Upper Division Electives'
  requirement_type requirement_type not null,  -- 'course_count' or 'credit_count'
  threshold numeric not null check (threshold > 0)
);

-- ---------- REQUIREMENT <-> COURSE (many-to-many) ----------
create table requirement_courses (
  requirement_id bigint not null references requirements(id) on delete cascade,
  course_id bigint not null references courses(id) on delete cascade,
  primary key (requirement_id, course_id)
);

-- ---------- STUDENT <-> MAJOR (many-to-many) ----------
create table student_majors (
  student_id uuid not null references profiles(id) on delete cascade,
  major_id bigint not null references majors(id) on delete cascade,
  primary key (student_id, major_id)
);

-- ---------- STUDENT COMPLETED COURSES ----------
create table student_completed_courses (
  student_id uuid not null references profiles(id) on delete cascade,
  course_id bigint not null references courses(id) on delete cascade,
  term_completed text,               -- e.g. 'Fall 2025'
  credits_earned numeric,            -- optional override; falls back to courses.credits if null
  primary key (student_id, course_id)
);

-- =========================================================
-- INDEXES (speed up the common lookups)
-- =========================================================
create index idx_requirements_major_id on requirements(major_id);
create index idx_requirement_courses_course_id on requirement_courses(course_id);
create index idx_student_majors_major_id on student_majors(major_id);
create index idx_student_completed_courses_course_id on student_completed_courses(course_id);

-- =========================================================
-- ROW LEVEL SECURITY
-- =========================================================

-- Reference data (majors, courses, requirements, requirement_courses)
-- is readable by any logged-in user, writable only by service role / admins.

alter table majors enable row level security;
alter table courses enable row level security;
alter table requirements enable row level security;
alter table requirement_courses enable row level security;

create policy "Public read access to majors"
  on majors for select
  to authenticated
  using (true);

create policy "Public read access to courses"
  on courses for select
  to authenticated
  using (true);

create policy "Public read access to requirements"
  on requirements for select
  to authenticated
  using (true);

create policy "Public read access to requirement_courses"
  on requirement_courses for select
  to authenticated
  using (true);

-- No insert/update/delete policies for authenticated users on reference
-- tables means only the service role (e.g. an admin dashboard or seed
-- script using the service key) can modify them.

-- ---------- profiles ----------
alter table profiles enable row level security;

create policy "Users can view their own profile"
  on profiles for select
  to authenticated
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on profiles for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

create policy "Users can insert their own profile"
  on profiles for insert
  to authenticated
  with check (auth.uid() = id);

-- ---------- student_majors ----------
alter table student_majors enable row level security;

create policy "Users can view their own majors"
  on student_majors for select
  to authenticated
  using (auth.uid() = student_id);

create policy "Users can add their own majors"
  on student_majors for insert
  to authenticated
  with check (auth.uid() = student_id);

create policy "Users can remove their own majors"
  on student_majors for delete
  to authenticated
  using (auth.uid() = student_id);

-- ---------- student_completed_courses ----------
alter table student_completed_courses enable row level security;

create policy "Users can view their own completed courses"
  on student_completed_courses for select
  to authenticated
  using (auth.uid() = student_id);

create policy "Users can add their own completed courses"
  on student_completed_courses for insert
  to authenticated
  with check (auth.uid() = student_id);

create policy "Users can update their own completed courses"
  on student_completed_courses for update
  to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Users can delete their own completed courses"
  on student_completed_courses for delete
  to authenticated
  using (auth.uid() = student_id);

-- =========================================================
-- HELPER VIEW / FUNCTION: outstanding requirements for a student
-- =========================================================
-- Returns only the requirements a student has NOT yet satisfied,
-- for a given major. This is what the "hide completed requirements"
-- feature in the UI should query.

create or replace function get_outstanding_requirements(
  p_student_id uuid,
  p_major_id bigint
)
returns table (
  requirement_id bigint,
  requirement_name text,
  requirement_type requirement_type,
  threshold numeric,
  progress numeric
)
language sql
stable
as $$
  select
    r.id,
    r.name,
    r.requirement_type,
    r.threshold,
    case
      when r.requirement_type = 'course_count'
        then count(scc.course_id)
      else
        coalesce(sum(coalesce(scc.credits_earned, c.credits))
                 filter (where scc.course_id is not null), 0)
    end as progress
  from requirements r
  join requirement_courses rc on rc.requirement_id = r.id
  join courses c on c.id = rc.course_id
  left join student_completed_courses scc
    on scc.course_id = rc.course_id
   and scc.student_id = p_student_id
  where r.major_id = p_major_id
  group by r.id
  having
    case
      when r.requirement_type = 'course_count'
        then count(scc.course_id)
      else
        coalesce(sum(coalesce(scc.credits_earned, c.credits))
                 filter (where scc.course_id is not null), 0)
    end < r.threshold;
$$;

-- Usage from the client (Supabase JS):
-- const { data, error } = await supabase.rpc('get_outstanding_requirements', {
--   p_student_id: userId,
--   p_major_id: majorId
-- });
