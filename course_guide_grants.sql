-- =========================================================
-- Fix Data API access for MVP tables
-- Run once in Supabase SQL Editor if you see:
--   "permission denied for table …" (42501)
-- RLS still restricts rows to the signed-in user.
-- =========================================================

grant usage on schema public to anon, authenticated;

grant select, insert, update, delete on table
  public.profiles,
  public.student_programs,
  public.transcript_uploads,
  public.student_completed_courses,
  public.student_group_overrides
to authenticated;

-- sequences for identity columns
grant usage, select on all sequences in schema public to authenticated;

-- anon: no table access needed (guests use JSON only)
-- authenticated role is what supabase-js uses after sign-in
