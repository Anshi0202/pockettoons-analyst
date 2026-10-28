# PocketToons: Answer Key (story.md)

This file is the hidden truth behind the synthetic data. The agent never sees it.
We use it to check whether the agent found the real story.

## The setup

- **Data window:** 1 Apr – 30 Sep 2026 (Q2 vs Q3).
  The app launched in Oct 2025, so users who signed up Oct 2025 – Mar 2026 are in `users`,
  but sessions, views, transactions and marketing spend start on 1 Apr 2026.
- **Countries:** US · Southeast Asia (ID, PH, TH, VN) · Latin America (BR, MX, CO)
- **Prices:** subscription $9.99/month · PPV $1.99 per premium episode · no price changes
- **Free tier:** 8 free episodes per user per day
- **Acquisition sources:** organic, referral, google, meta, tiktok

## The headline (what the GM sees)

| Metric                              | Q2     | Q3     | Change         |
| ----------------------------------- | ------ | ------ | -------------- |
| MAU (average of the 3 monthly MAUs) | ~5,000 | ~6,000 | **+20%**       |
| Revenue (net)                       | ~$15K  | ~$15K  | **within ±3%** |

## Metric definitions

- **MAU:** distinct users with at least one session in a calendar month. Quarter MAU = average of its 3 months.
- **Revenue:** successful subscription + PPV payments, minus refunds, in USD.
- **Conversion:** % of a month's new signups with a successful first subscription payment within 30 days.
- **Real user:** any user who is not a bot/test account (see Cause 4).

## The story

### Cause 1: Marketing moves to cheap channels (from 1 July)

Marketing shifts most paid spend from Google (US) to TikTok and Meta ads aimed at SEA and LatAm.
Total spend stays roughly the same, but an install there costs ~$0.40 instead of ~$3 in the US.
So signups roughly double: **~1,000/month in Q2 → ~2,000/month in Q3.**

### Cause 2: The new users don't pay (from 1 July)

Every user gets a hidden "intent" level from their country and channel.
Low-intent users watch a few free episodes, rarely hit the 8/day limit, and so rarely see the paywall.

Hidden 30-day conversion by segment (lives only in generate.py, never in the DB):

| Segment                       | Conversion |
| ----------------------------- | ---------- |
| US organic / referral         | ~10%       |
| US paid (Google, Meta)        | ~7%        |
| SEA/LatAm organic             | ~3%        |
| SEA/LatAm paid (TikTok, Meta) | ~1%        |

These rates **do not change** between Q2 and Q3. Only the **mix** of users changes.
Blended conversion falls from **~6% (Q2 signups) to ~2–3% (Q3 signups)**.
Signups double, but the number of new paying users per month stays about flat.

### Cause 3: LatAm payments break (from 1 August)

On 1 Aug, a new local payment method (`local_wallet`) becomes the default in BR, MX and CO.
About 70% of LatAm payments go through it, and about half of those fail.
LatAm payment failure rate jumps from **~5% to ~35%**. All other countries and methods stay at ~5%.

- Failed first payment → the user stays on free (a lost conversion).
- Failed renewal → the subscription ends (`subscription_status = 'churned'`). This is involuntary churn.

**How the causes link:** Cause 1 sent many more users to LatAm, so Cause 3 hits a much bigger group.

### Cause 4 (data quality): bot and test accounts (Jul – Sep)

About 1,500 fake accounts are created in bursts (~500/month). They:

- have `acquisition_source = 'unknown'`
- have sessions of 1–10 seconds
- watch no content and never pay

They add ~400 to each monthly MAU in Q3. **Without them, real MAU growth is ~12%, not 20%.**

## Red herring (not a cause)

Android's share of sessions rises in Q3, because most new SEA/LatAm users are on Android.
It looks like a platform problem, but within each country Android and iOS users convert about the same.
A good agent tests this and rejects it.

## Kept constant (so nothing else explains the gap)

Price, free limit, content release pace, US organic signups, refund rate (~2% of payments).

## What a correct investigation finds

1. MAU growth is overstated: ~12% real, not 20%, because of bot/test accounts.
2. Real growth came from cheap TikTok/Meta installs in SEA and LatAm.
3. Those users convert far less; the conversion drop is a mix shift, not existing segments getting worse.
4. LatAm payment failures (`local_wallet`, from 1 Aug) block new subscriptions and cause involuntary churn.
5. Cause 1 makes Cause 3 worse.
6. The Android explanation is tested and rejected.

## Rules for the generator (no leaks)

- `intent` exists only inside generate.py and is never written to the DB.
- No `is_bot` column. Bots can only be spotted by how they behave.
- Code comments explain the story; the DB itself contains no hints.
- Fixed random seed, so anyone can recreate the exact same DB.

## Actual numbers (fill in after Step 3)

| Check                                 | Target                   | Actual |
| ------------------------------------- | ------------------------ | ------ |
| MAU change Q3 vs Q2, all users        | +20%                     |        |
| MAU change Q3 vs Q2, excluding bots   | ~+12%                    |        |
| Revenue change Q3 vs Q2               | within ±3%               |        |
| Conversion, Q2 vs Q3 signups          | ~6% vs ~2–3%             |        |
| LatAm payment failure rate, Aug – Sep | ~35%                     |        |
| Revenue lost to each cause ($)        | from counterfactual runs |        |
