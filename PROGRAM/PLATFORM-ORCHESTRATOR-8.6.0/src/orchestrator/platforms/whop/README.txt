Whop App API feed-content adapter.

Confirmed official surface:
- POST /v5/app/feed_content_items
- Bearer App API key authentication

The adapter maps feed content creation into the publish contract. It supports text and
remote file attachments for image/video. Edit/delete/status are intentionally not claimed
without a documented feed-content lifecycle endpoint in the current contract used here.
