-- Stage 14: read posts from a chat group (GroupMe).
-- The reader (Edge Function "read-channel") runs every minute, reads new messages, and sends each to the agent.

alter table public.events add column if not exists source text not null default '';
alter table public.events add column if not exists source_id text not null default '';
alter table public.events add column if not exists source_name text not null default '';

-- One decision per chat message: a database rule, not an instruction.
create unique index if not exists events_one_per_message
  on public.events (source, source_id)
  where source_id <> '';

-- The reader's bookmark: which message it read last.
create table if not exists public.channel_cursor (
  source text primary key,
  last_id text not null default '',
  read_count integer not null default 0,
  updated_at timestamptz not null default now()
);

alter table public.channel_cursor enable row level security;
revoke all on public.channel_cursor from anon, authenticated;
grant select, insert, update, delete on public.channel_cursor to service_role;

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Every minute, ask the reader to look for new messages. Scheduling the same name again replaces the job.
select cron.schedule(
  'read-chat-channel',
  '* * * * *',
  $$
    select net.http_post(
      url := 'https://etrulhpqodyjmtfraglg.supabase.co/functions/v1/read-channel',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'apikey', 'sb_publishable_5rXWCzPoQJ0rmovPb2j2hw_uKkushdK'
      ),
      body := '{}'::jsonb
    );
  $$
);
