# Secrets & Credentials Runbook

How VenueFlow handles credentials, today and as we move to production. Read this before you ship anything that touches Stripe or Cloud Run.

## Principle

**No human-to-human credential sharing.** Each founder has their own login to each service, with the right IAM role. The service does the sharing — not Slack, not email, not a screenshot. Production secrets live in Google Secret Manager and are injected into Cloud Run at runtime; they should never exist on a laptop.

## Layers

| Layer | What lives here | Tool |
|---|---|---|
| Personal vault | Account logins, recovery codes, short-lived team shares | 1Password / Bitwarden |
| Local dev secrets | Test-mode API keys, personal Gemini key | `backend/.env` (gitignored) |
| Production secrets | Live API keys, webhook signing secrets | Google Secret Manager |
| Code | Variable *names* and an `.env.example` template | git (this repo) |

If a real secret value ever appears in a git diff, that's a bug — the pre-commit `gitleaks` hook is set up to catch it. If it somehow does land in history, rotate the key immediately (don't try to scrub the commit; assume it's leaked).

## Per service

### 1Password / Bitwarden

Today. Both founders sign up, create a shared "VenueFlow" vault. The vault holds:
- Logins for GCP, Stripe, Streamlit Cloud, GitHub
- Recovery / backup codes for MFA
- *Time-limited* shares for one-off "I need to give Atharva this thing for 24 hours" cases

The vault does **not** hold production API keys. Those live in Google Secret Manager.

### GCP

One project (`venueflow-prod`). Both founders are Owners (or Atharva Owner + Alan Editor if you want billing separation).

Local dev auth:
```bash
gcloud auth application-default login
```
Short-lived token tied to your personal Google account, MFA-enforced. **Never download service account JSON keys** to a laptop — if a key file exists, treat it as already leaked.

Production auth: service accounts attached to Cloud Run instances. Keys never leave Google. Founders read secrets via:
```bash
gcloud secrets versions access latest --secret=gemini-api-key
```
…when debugging. They don't copy them locally.

### Stripe

Alan creates the account (becomes Owner). Adds Atharva with **Developer** role — can manage API keys + webhooks, cannot change billing / payouts / team. Each founder has their own dashboard login with MFA on.

Test mode (`sk_test_...`): fine in `.env.local`. Can't move real money.

Live mode (`sk_live_...`): only in Google Secret Manager. Use **restricted keys** for the Cloud Run worker — scope to "Checkout + Customer" rather than full account access. One restricted key per service.

Webhook signing secrets: one per environment (test/live), in Secret Manager. Rotate when the endpoint URL changes.

### AWS (only if/when)

We don't use AWS yet. If we ever do: same shape — IAM users per person, MFA enforced, no root login after setup, AWS Secrets Manager for runtime. **Do not set this up speculatively** — GCP covers everything we need for now.

## Local dev setup (5 minutes per founder)

```bash
# 1. Clone the repo
git clone git@github.com:alanmaizon/VenueFlow.git
cd VenueFlow

# 2. Activate the gitleaks pre-commit hook (blocks secrets from landing in commits)
brew install gitleaks pre-commit
pre-commit install

# 3. Set up your local env
cp backend/.env.example backend/.env
# Edit backend/.env: paste your personal Gemini key, leave Stripe blank until W2

# 4. Run the app
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

`.env` is in `.gitignore`. Verify with `git check-ignore -v backend/.env` — should print the matching rule.

## Pre-commit secret scanning (gitleaks)

The repo ships with a `.pre-commit-config.yaml` that runs `gitleaks protect --staged` on every commit. If you accidentally stage a file containing what looks like an API key, the commit is rejected.

To install (one-time per machine):
```bash
brew install gitleaks pre-commit
cd /path/to/VenueFlow
pre-commit install
```

To test manually:
```bash
pre-commit run --all-files                    # scan everything
pre-commit run gitleaks --hook-stage=pre-commit  # just the secret scan
gitleaks detect --source . --no-banner        # full repo scan, ignores hook config
```

False positives (rare): add the line to `.gitleaksignore` with the fingerprint gitleaks prints. Real positives: remove the secret, rotate the key, force the laptop to forget it.

## Production deployment (Week 2 onward, when Cloud Run lands)

1. Create secrets in Secret Manager:
   ```bash
   echo -n "sk_live_..." | gcloud secrets create stripe-secret-key --data-file=-
   ```
2. Grant the Cloud Run service account read access:
   ```bash
   gcloud secrets add-iam-policy-binding stripe-secret-key \
     --member=serviceAccount:venueflow-runner@$PROJECT.iam.gserviceaccount.com \
     --role=roles/secretmanager.secretAccessor
   ```
3. Mount on the Cloud Run service:
   ```bash
   gcloud run services update venueflow-app \
     --update-secrets=STRIPE_SECRET_KEY=stripe-secret-key:latest
   ```
4. Application code reads `os.environ["STRIPE_SECRET_KEY"]` — identical to local dev. The source differs; the code doesn't.

## What NOT to do

- Don't share one Google account or one Stripe login between founders.
- Don't email / Slack / Notion an API key, even "just to copy paste."
- Don't put keys in commit messages, PR descriptions, or issue comments.
- Don't commit `.env` or `.env.local`. Only `.env.example`.
- Don't reuse the same key across dev / staging / prod — separate keys per environment so revoking dev doesn't break prod.
- Don't disable the gitleaks hook with `--no-verify`. If gitleaks blocks a commit you believe is legitimate, take 10 seconds to verify before bypassing.
- Don't expose the Gemini API key through the Streamlit sidebar in production. The sidebar input is fine for the local mock; before Streamlit Cloud deploy, route it to env-only.

## When credentials leak (it happens)

1. **Rotate immediately.** Stripe / Gemini / GCP all let you regenerate keys in seconds.
2. Update the new value in Google Secret Manager. The Cloud Run service picks it up on next deploy or re-pull.
3. Update the shared vault entry.
4. Notify the other founder so they update their `.env.local` if applicable.
5. **Don't try to rewrite git history to "scrub" the leak.** Assume any pushed commit is permanent and possibly indexed. Rotation is the only real fix.

## Onboarding checklist

When a new contributor joins (post-submission, hypothetically):

- [ ] Added to the 1Password vault
- [ ] Added to GCP project with Editor role (Owner only if they need IAM)
- [ ] Added to Stripe with Developer role (or Read-Only if they don't need to ship)
- [ ] Cloned the repo, ran `pre-commit install`
- [ ] Copied `.env.example` → `.env`, generated personal Gemini key
- [ ] Verified `git check-ignore -v backend/.env` passes
