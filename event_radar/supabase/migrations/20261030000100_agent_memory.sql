-- Stages 11-13: the agent's memory.
-- 1) lessons: one-sentence lessons that signed-in moderators write; the agent loads them before every decision.
-- 2) events.looked_at: what the agent looked at for each post (short-term messages, club list, earlier posts, lessons).
-- 3) events.replaces_id: the earlier card this post updated and retired.

create table if not exists public.lessons (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  lesson text not null check (char_length(lesson) between 1 and 300),
  created_by text not null default ''
);

alter table public.lessons enable row level security;

-- A signed-in user is a moderator (new sign-ups are off, see the moderator sign-in migration).
drop policy if exists "Moderators can read lessons" on public.lessons;
create policy "Moderators can read lessons"
  on public.lessons for select to authenticated using (true);

drop policy if exists "Moderators can write lessons" on public.lessons;
create policy "Moderators can write lessons"
  on public.lessons for insert to authenticated with check (true);

drop policy if exists "Moderators can delete lessons" on public.lessons;
create policy "Moderators can delete lessons"
  on public.lessons for delete to authenticated using (true);

grant select, insert, delete on public.lessons to authenticated;
-- The agent (service_role) reads the lessons before every decision.
grant select on public.lessons to service_role;

alter table public.events add column if not exists looked_at text[] not null default '{}';
alter table public.events add column if not exists replaces_id uuid references public.events (id) on delete set null;

-- Moderators see these columns (they already have select on the whole table); the public website does not.
-- The agent looks up a club's upcoming posts by club + date.
create index if not exists events_club_upcoming on public.events (lower(club), event_date);
