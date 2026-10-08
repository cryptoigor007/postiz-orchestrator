MeWe Open API group-post adapter.

Confirmed official surface:
- GET /api/dev/me
- POST /api/dev/group/:groupId/post
- GET /api/dev/group/:groupId/postsfeed
- GET /api/dev/group/:groupId/scheduled/posts/calendar

The public developer program is a reviewed/beta access path. This module requires a
pre-obtained MEWE_API_TOKEN and MEWE_APP_ID and posts only to a configured group.
Media upload is intentionally not claimed: image posts use provider-side uploadedPhotoIds.
Post edit/delete are intentionally not claimed because the current public contract used by
this module does not document generic edit/delete operations.
