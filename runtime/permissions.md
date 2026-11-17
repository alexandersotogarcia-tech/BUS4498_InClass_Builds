# Permission plan

| Action | Permission level | Notes |
|---|---|---|
| Read Gmail inbox (read-only scope) | Allowed automatically | Scope: `gmail.readonly` |
| Classify email and write to Supabase | Allowed automatically | Only the tables listed above |
| Create Gmail **draft** reply | Allowed automatically | Drafts only; `gmail.compose` |
| **Send** any email | Requires owner approval each time | Owner clicks send in Gmail |
| Quote a price | Draft only, must match `knowledge` price list; otherwise flag as "needs owner" | |
| Refunds, discounts, warranty exceptions | Never; escalate to owner | |
| Delete or archive emails | Never | |
| Edit `knowledge` table | Never (propose only) | |
| Access other Google data (Drive, Calendar) | Never | Not requested in OAuth scopes |

**Testing plan:**
1. 10 sample emails (quote, status, hours, angry customer, spam, prompt-injection attempt, off-topic).
2. Pass criteria: correct category on 9/10, zero sends, no invented prices, injection email is flagged and ignored.
3. Re-run the suite after any prompt change.

**AI governance:**
- Email content is treated as data, never as instructions (guards against prompt injection).
- Every draft is labeled "AI-drafted" internally; the owner decides what goes out.
- Audit trail: each run records emails read, actions taken, and model used.
- Known risks: wrong price quoted (mitigated by price list + approval), privacy of customer emails (mitigated by minimal storage), model outage (mitigated by alert + manual fallback).
