-- Stage 13: lessons (what moderators teach the agent).
-- Only signed-in moderators can write lessons. The agent reads them; it never saves one,
-- and text inside a post can never become a lesson.

create table if not exists public.lessons (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  lesson text not null check (char_length(lesson) between 5 and 300),
  active boolean not null default true,
  created_by text not null default '',
  from_post uuid
);

alter table public.lessons enable row level security;

drop policy if exists "Moderators can read lessons" on public.lessons;
create policy "Moderators can read lessons"
on public.lessons for select
to authenticated
using (true);

drop policy if exists "Moderators can add lessons" on public.lessons;
create policy "Moderators can add lessons"
on public.lessons for insert
to authenticated
with check (true);

drop policy if exists "Moderators can switch lessons on and off" on public.lessons;
create policy "Moderators can switch lessons on and off"
on public.lessons for update
to authenticated
using (true)
with check (true);

revoke all on public.lessons from anon, authenticated;
grant select on public.lessons to authenticated;
grant insert (lesson, created_by, from_post) on public.lessons to authenticated;
grant update (active) on public.lessons to authenticated;
grant select, insert, update, delete on public.lessons to service_role;

-- Which lessons the agent followed for each post.
alter table public.events add column if not exists lessons_used text[] not null default '{}';
