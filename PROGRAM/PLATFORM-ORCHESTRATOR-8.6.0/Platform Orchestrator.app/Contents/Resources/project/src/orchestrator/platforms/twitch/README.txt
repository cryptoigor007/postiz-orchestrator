Twitch: native Helix adapter for Clips.

The current Helix API supports creating clips from a live broadcaster stream and creating clips from VODs. It does not provide an arbitrary local-media upload/publish path, so PlatformModule.publish remains intentionally unsupported; use create_clip/create_clip_from_vod instead.
