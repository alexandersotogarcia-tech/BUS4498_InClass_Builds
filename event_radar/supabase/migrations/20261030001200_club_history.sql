-- Stage 12: the club's earlier posts (memory of what happened).
-- A fifth status, "replaced", marks a post that a newer update has taken over.

alter table public.events drop constraint if exists events_status_check;
alter table public.events add constraint events_status_check
  check (status in ('published', 'waiting', 'rejected', 'archived', 'replaced'));

alter table public.events add column if not exists replaced_by uuid;  -- the newer post that replaced this one
alter table public.events add column if not exists updates_id uuid;   -- the earlier post this waiting post would replace

-- Moderators may now also set a post to "replaced" (when they approve an update).
drop policy if exists "Moderators can approve or reject" on public.events;
create policy "Moderators can approve or reject"
on public.events for update
to authenticated
using (true)
with check (status in ('published', 'waiting', 'rejected', 'replaced'));
