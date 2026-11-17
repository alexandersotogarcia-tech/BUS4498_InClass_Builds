# Memory plan

| Memory type | What is stored | Where | Retention |
|---|---|---|---|
| Short-term (per run) | The current email thread and classification | In-process only | Discarded after run |
| Long-term: requests | Sender, category, summary, status, timestamps | Supabase table `requests` | 12 months |
| Long-term: customer notes | Bike type, past repairs, preferences | Supabase table `customers` | Until customer asks to delete |
| Long-term: shop knowledge | Hours, price list, warranty policy | Supabase table `knowledge` (owner-edited) | Updated by owner only |
| Reply examples | Owner-approved past replies used as style guide | Supabase table `approved_replies` | 12 months |

**Rules:**
- The agent only reads `knowledge` and may *propose* edits, never writes to it directly.
- No payment info, passwords, or full email bodies are stored. Store a short summary only.
- Deletion: owner can delete any customer row; the agent re-checks memory each run so deletions take effect immediately.
- Memory is retrieved by sender email + category, capped at the 5 most recent items to limit token cost and avoid stale context.

