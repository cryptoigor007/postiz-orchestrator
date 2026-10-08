# Provider Coverage Matrix — Audited Current Snapshot

Date: 2026-10-01


This matrix is generated from the current provider catalog and provider manifests. It is the runtime-facing summary; historical roadmap/checkpoint documents are not authoritative for current state.


Legend:
- `IMPLEMENTED` / `IMPLEMENTED_NATIVE` — native transport exists for the declared scope.
- `IMPLEMENTED_INBOX` — provider path exists but publishing is deliberately constrained to inbox/manual semantics.
- `PARTIAL_NATIVE` — native transport exists, but declared production scope still has known gaps.
- `PARTNER` — native code is gated by external partner/commercial access.
- `FEASIBILITY` — explicit boundary; native production publish is not advertised.
- `SCAFFOLD` — registered/limited module without production publish transport.


## agent_native

| ID | Provider | State | Capability family |
|---|---|---|---|
| moltbook | moltbook | IMPLEMENTED_NATIVE | Publishing + Identity + Media |

## business

| ID | Provider | State | Capability family |
|---|---|---|---|
| google_business | google_business | IMPLEMENTED_NATIVE | Publishing + Identity + Media |

## cms

| ID | Provider | State | Capability family |
|---|---|---|---|
| wordpress | wordpress | IMPLEMENTED_NATIVE | Publishing + Media |

## community

| ID | Provider | State | Capability family |
|---|---|---|---|
| lemmy | lemmy | IMPLEMENTED_NATIVE | Publishing + Identity |
| mewe | mewe | PARTIAL_NATIVE | Publishing + Identity + Media |
| reddit | reddit | PARTIAL_NATIVE | Publishing + Identity + Media |
| skool | skool | SCAFFOLD | Identity |
| whop | whop | PARTIAL_NATIVE | Publishing + Identity + Media |

## creative_community

| ID | Provider | State | Capability family |
|---|---|---|---|
| dribbble | dribbble | IMPLEMENTED_NATIVE | Publishing + Identity + Media |

## messaging

| ID | Provider | State | Capability family |
|---|---|---|---|
| instagram_messaging | instagram_messaging | SCAFFOLD | Identity + Webhook |
| line | line | PARTIAL_NATIVE | Messaging + Identity + Webhook |
| messenger | messenger | SCAFFOLD | Identity + Webhook |
| signal | signal | FEASIBILITY | Identity |
| viber | viber | PARTIAL_NATIVE | Messaging + Identity + Webhook |
| wechat | wechat | IMPLEMENTED_NATIVE | Publishing + Identity |
| whatsapp | whatsapp | PARTIAL_NATIVE | Messaging + Identity + Webhook + Media |

## messaging/community

| ID | Provider | State | Capability family |
|---|---|---|---|
| discord | discord | PARTIAL_NATIVE | Messaging + Identity + Webhook |
| slack | slack | PARTIAL_NATIVE | Messaging + Identity + Webhook |

## messaging/publishing

| ID | Provider | State | Capability family |
|---|---|---|---|
| telegram | telegram | IMPLEMENTED | Publishing + Identity + Webhook + Media |

## newsletter

| ID | Provider | State | Capability family |
|---|---|---|---|
| beehiiv | beehiiv | IMPLEMENTED_NATIVE | Publishing + Media |
| listmonk | listmonk | IMPLEMENTED_NATIVE | Publishing |

## partner_video

| ID | Provider | State | Capability family |
|---|---|---|---|
| rutube | rutube | PARTNER | Publishing + Identity + Media |

## protocol_social

| ID | Provider | State | Capability family |
|---|---|---|---|
| bluesky | bluesky | PARTIAL_NATIVE | Publishing + Identity + Media |
| farcaster | farcaster | PARTNER | Publishing + Identity + Media |
| mastodon | mastodon | IMPLEMENTED_NATIVE | Publishing + Identity + Media |
| nostr | nostr | IMPLEMENTED_NATIVE | Publishing + Identity + Media |

## publishing

| ID | Provider | State | Capability family |
|---|---|---|---|
| devto | devto | IMPLEMENTED_NATIVE | Publishing + Identity + Media |
| hashnode | hashnode | IMPLEMENTED_NATIVE | Publishing + Identity + Media |
| medium | medium | FEASIBILITY | Identity |

## social

| ID | Provider | State | Capability family |
|---|---|---|---|
| linkedin | linkedin | PARTIAL_NATIVE | Publishing + Identity + Media |
| pinterest | pinterest | PARTIAL_NATIVE | Publishing + Identity + Media |
| snapchat | snapchat | PARTIAL_NATIVE | Publishing + Identity + Media |
| threads | threads | IMPLEMENTED | Publishing + Identity + Webhook + Media |
| tumblr | tumblr | PARTIAL_NATIVE | Publishing + Identity |
| x | x | IMPLEMENTED | Publishing + Identity + Media |

## social/video

| ID | Provider | State | Capability family |
|---|---|---|---|
| facebook | facebook | IMPLEMENTED | Publishing + Identity + Webhook + Media |
| instagram | instagram | IMPLEMENTED | Publishing + Identity + Webhook + Media |
| tiktok | tiktok | IMPLEMENTED_INBOX | Publishing + Identity + Webhook + Media |
| vk | vk | IMPLEMENTED | Publishing + Identity + Media |
| youtube | youtube | IMPLEMENTED | Publishing + Identity + Webhook + Media |

## streaming

| ID | Provider | State | Capability family |
|---|---|---|---|
| kick | kick | PARTIAL_NATIVE | Publishing + Identity + Media |
| twitch | twitch | PARTIAL_NATIVE | Identity |

## Canonical count

- **42 executable module IDs**.
- The catalog is the authoritative list for the current implementation state.
- A provider is not LIVE merely because native code exists.

## LIVE definition

A provider is LIVE only when code, authentication, required access/scopes, media transfer, publish/send success, authoritative status/reconciliation, webhooks where required, retry/idempotency recovery, quota/rate handling, health/alerting, and a real canary have all passed.

