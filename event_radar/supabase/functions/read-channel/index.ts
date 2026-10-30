// Club Event Radar: the chat-channel reader for GroupMe (Supabase Edge Function "read-channel").
//
// A scheduled job calls it every minute. It reads the group's new messages, sends each one to the agent
// ("submit-event") with the sender's earlier messages as context, and posts the agent's decision back to the group.
// The GroupMe token, group id, and bot id live in Supabase Secrets (GROUPME_TOKEN, GROUPME_GROUP_ID, GROUPME_BOT_ID).
// Deploy with JWT verification off (verify_jwt = false).

import { createClient } from "npm:@supabase/supabase-js@2.117.2";

const SOURCE = "groupme";
const API = "https://api.groupme.com/v3";
const MAX_MESSAGES = 20;
const THREAD_MINUTES = 10;
const THREAD_MAX = 4;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

// deno-lint-ignore no-explicit-any
type Msg = Record<string, any>;

function reply(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

function serverKey(): string {
  const keys = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (keys) {
    try {
      const k = JSON.parse(keys)["default"];
      if (k) return k;
    } catch (_) { /* fall back to the legacy key below */ }
  }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
}

function publishableKey(): string {
  const keys = Deno.env.get("SUPABASE_PUBLISHABLE_KEYS");
  if (keys) {
    try {
      return JSON.parse(keys)["default"] ?? "";
    } catch (_) { /* optional */ }
  }
  return "";
}

const token = () => Deno.env.get("GROUPME_TOKEN") ?? "";
const groupId = () => Deno.env.get("GROUPME_GROUP_ID") ?? "";
const botId = () => Deno.env.get("GROUPME_BOT_ID") ?? "";

async function groupme(path: string): Promise<{ status: number; messages: Msg[]; group?: Msg }> {
  const res = await fetch(`${API}${path}`, { headers: { "X-Access-Token": token() } });
  if (res.status === 304) return { status: 304, messages: [] };
  if (!res.ok) return { status: res.status, messages: [] };
  const json = await res.json();
  return { status: res.status, messages: json?.response?.messages ?? [], group: json?.response };
}

const byTime = (a: Msg, b: Msg) => Number(a.created_at) - Number(b.created_at);

// The same sender's messages from the 10 minutes before this one, oldest first, at most 4.
async function threadFor(msg: Msg): Promise<string[]> {
  const r = await groupme(`/groups/${groupId()}/messages?before_id=${msg.id}&limit=${MAX_MESSAGES}`);
  const from = Number(msg.created_at) - THREAD_MINUTES * 60;
  return r.messages
    .filter((m) => m.sender_id === msg.sender_id && m.sender_type !== "bot" && m.sender_type !== "system" && m.text && Number(m.created_at) >= from)
    .sort(byTime)
    .slice(-THREAD_MAX)
    .map((m) => String(m.text));
}

async function say(text: string) {
  if (!botId()) return;
  await fetch(`${API}/bots/post`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_id: botId(), text: text.slice(0, 1000) }),
  });
}

function decisionText(name: string, data: Msg): string {
  const ev = data.event ?? {};
  const what = ev.title ? `"${ev.title}"` : "your post";
  const reasons = Array.isArray(data.reasons) && data.reasons.length ? ` ${data.reasons.join(" ")}` : "";
  return `${name}: ${what}: ${data.message ?? data.status}${data.status === "published" ? "" : reasons}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const db = createClient(Deno.env.get("SUPABASE_URL")!, serverKey(), { auth: { persistSession: false } });
  const { data: cursor } = await db.from("channel_cursor").select("last_id, read_count").eq("source", SOURCE).maybeSingle();

  if (req.method === "GET") {
    const url = new URL(req.url);
    if (url.searchParams.get("check") === "groupme") {
      // Results only, never values.
      const r = token() && groupId() ? await groupme(`/groups/${groupId()}`) : null;
      return reply(200, {
        ok: true,
        token_set: Boolean(token()),
        group_id_set: Boolean(groupId()),
        bot_id_set: Boolean(botId()),
        group_reachable: r ? r.status === 200 : false,
        group_name: r?.group?.name ?? "",
        message: !token() || !groupId() ? "GROUPME_TOKEN or GROUPME_GROUP_ID is missing in Edge Functions → Secrets."
          : r?.status === 200 ? "GroupMe accepted the token and the group works." : `GroupMe answered ${r?.status}. Check the token and the group id.`,
      });
    }
    return reply(200, {
      ok: true,
      ready: Boolean(token() && groupId()),
      last_message_id: cursor?.last_id ?? "",
      read_count: cursor?.read_count ?? 0,
      bot: Boolean(botId()),
    });
  }
  if (req.method !== "POST") return reply(405, { ok: false, message: "Send a POST request." });

  try {
    if (!token() || !groupId()) return reply(503, { ok: false, message: "GROUPME_TOKEN or GROUPME_GROUP_ID is missing in Edge Functions → Secrets." });

    // First run: remember the newest message and stop. Old history is never read.
    if (!cursor?.last_id) {
      const first = await groupme(`/groups/${groupId()}/messages?limit=1`);
      if (first.status !== 200) return reply(502, { ok: false, message: `GroupMe answered ${first.status}. Check the token and the group id.` });
      const newest = first.messages[0]?.id ?? "";
      await db.from("channel_cursor").upsert({ source: SOURCE, last_id: newest, read_count: 0, updated_at: new Date().toISOString() });
      return reply(200, { ok: true, first_run: true, message: "Bookmark saved. Only new messages will be read.", read: 0 });
    }

    const r = await groupme(`/groups/${groupId()}/messages?after_id=${cursor.last_id}&limit=${MAX_MESSAGES}`);
    if (r.status === 304 || !r.messages.length) return reply(200, { ok: true, read: 0, message: "No new messages." });
    if (r.status !== 200) return reply(502, { ok: false, message: `GroupMe answered ${r.status}.` });

    const agent = `${Deno.env.get("SUPABASE_URL")}/functions/v1/submit-event`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (publishableKey()) headers["apikey"] = publishableKey();

    let read = cursor.read_count ?? 0, handled = 0;
    for (const msg of r.messages.sort(byTime)) {
      // Move the bookmark past every message, including the ones we skip.
      const skip = msg.sender_type === "bot" || msg.sender_type === "system" || !String(msg.text ?? "").trim();
      if (!skip) {
        const thread = await threadFor(msg);
        const res = await fetch(agent, {
          method: "POST",
          headers,
          body: JSON.stringify({ announcement: String(msg.text), source: SOURCE, source_id: String(msg.id), source_name: String(msg.name ?? ""), thread }),
        });
        const data: Msg = await res.json().catch(() => ({ ok: false, message: `The agent answered ${res.status}.` }));
        handled++;
        if (!data.already_read) await say(decisionText(String(msg.name ?? "Thanks"), data));
      }
      read++;
      await db.from("channel_cursor").upsert({ source: SOURCE, last_id: String(msg.id), read_count: read, updated_at: new Date().toISOString() });
    }
    return reply(200, { ok: true, read: r.messages.length, sent_to_agent: handled });
  } catch (err) {
    console.error(err);
    return reply(500, { ok: false, message: "Something went wrong in the reader. Check the function logs in Supabase." });
  }
});
