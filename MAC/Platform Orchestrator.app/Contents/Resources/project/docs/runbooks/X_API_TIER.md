# X (Twitter) API Tier

## Decision
- Free tier: very low write limits — keep `daily_limit` ≤ 10 and `enabled: false` by default.
- Basic / Pro: raise limits in config after billing.

## Auth
OAuth 2.0 PKCE user context. Store in `tokens/x.json` (0600).

## Capabilities (module 0.1.0)
- Text + up to 4 images
- Delete tweet
- Schedule: **orchestrator-side only** (native limited)
- List remote: partial / paid

## Templates
`description_templates.x_promo`: `{title} {description_short} {link} {hashtags}` — truncate to 280 (or Premium long-form via max_chars).
