-- Stage 11: the club list (knowledge).
-- The agent reads this table on every post. A moderator edits it in the Table Editor,
-- so what the agent knows changes without redeploying anything.

create table if not exists public.clubs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  name text not null unique,
  nicknames text not null default '',            -- comma-separated, e.g. "BGG, board game club"
  usual_place_code text not null default '',     -- a hint for the moderator only, never filled in by the agent
  usual_place_detail text not null default '',
  active boolean not null default true,
  note text not null default ''
);

alter table public.clubs enable row level security;

drop policy if exists "Anyone can read active clubs" on public.clubs;
create policy "Anyone can read active clubs"
on public.clubs for select
to anon, authenticated
using (active);

-- Some projects hand every new table to visitors by default, so remove that first.
revoke all on public.clubs from anon, authenticated;
grant select (id, name, nicknames, active) on public.clubs to anon, authenticated;
grant select, insert, update, delete on public.clubs to service_role;

insert into public.clubs (name, nicknames, usual_place_code, usual_place_detail) values
  ('Board Game Guild', 'BGG, board game club', 'UU', 'Room 220'),
  ('Mustang Pitch Society', 'pitch society, MPS', 'UU-PLAZA', ''),
  ('Women in Finance Circle', 'WIFC, finance circle', 'BUSINESS', ''),
  ('Sustainability Crew', 'sustainability, green crew', 'DEXTER-LAWN', ''),
  ('Accounting Society', 'acct society, accounting club', 'BUSINESS', 'Room 212'),
  ('Cal Poly Ski & Snowboard Club', 'ski club, snowboard club, ski and snowboard', 'REC-CENTER', '')
on conflict (name) do nothing;

-- What the agent looked at, saved with every decision (shown to the poster and the moderator).
alter table public.events add column if not exists agent_notes text[] not null default '{}';

-- A moderator may clear the board (the Tools tab).
drop policy if exists "Moderators can delete posts" on public.events;
create policy "Moderators can delete posts"
on public.events for delete
to authenticated
using (true);
grant delete on public.events to authenticated;
