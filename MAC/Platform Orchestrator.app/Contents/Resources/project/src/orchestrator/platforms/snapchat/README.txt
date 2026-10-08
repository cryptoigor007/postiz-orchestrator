Snapchat Public Profile API adapter.

Implemented native scope:
- POST /v1/public_profiles/:profileId/stories using a provider media_id
- POST /v1/public_profiles/:profileId/spotlights using a provider media_id
- GET Stories / Spotlights inventory with cursor propagation
- status reconciliation from inventory

The official media upload flow requires client-side encryption metadata, media containers,
and multipart uploads before posting. This module deliberately requires a pre-created
media_id rather than pretending to upload an arbitrary local file without those prerequisites.
Public Profile API access is allowlist-only and requires the appropriate OAuth/business setup.
