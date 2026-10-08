# Platform Orchestrator 8.6.0 — MASTER API ACCESS & REVIEW PLAYBOOK

Version: 2026-10-03 (deep review)

## 0. Important boundary
There is no truthful way to promise 100% approval from any platform. Approval is controlled by the provider, account eligibility, policy, requested capability, current product availability, and reviewer judgment. The goal of this document is to maximize the probability of approval by making the integration demonstrably compliant, minimal, testable, and exactly aligned with the requested permission.

Do not increase approval odds by sending repeated identical emails, inventing customers, hiding automation, creating fake usage, or asking for scopes the software does not use. Those actions can reduce trust and can violate platform policy.

## 1. The correct order — use this for every strict provider
1. **Freeze the use case.** Describe exactly one supported workflow: user authorizes → provider API call → result appears in the app → status is reconciled.
2. **Prepare identity.** Real product name, real owner/legal entity, verified domain/business email when required, privacy policy, terms, support contact, and data deletion/withdrawal process where the provider requires it.
3. **Build a dedicated review release.** Never submit an unfinished "roadmap" build. The review build must have only the feature/scopes you are asking to approve.
4. **Use minimum scopes.** Every requested scope must have a visible feature and an API request in the demo.
5. **Create a real test destination.** Use an account/Page/channel/business profile that you own or are explicitly authorized to manage.
6. **Make real successful calls before review.** Token acquisition alone is not evidence of a working integration.
7. **Record a reviewer-grade demo.** Show login/OAuth, consent, the relevant feature, the actual publish/read operation, the result, and the status/error handling. Do not show secrets.
8. **Submit once the evidence pack is complete.** Keep a copy of the exact app configuration and code version submitted.
9. **If rejected, fix the stated blocker only and follow that platform's resubmission rules.** Some programs require a new app after a development-tier rejection (LinkedIn); do not assume all providers use the same mechanism.
10. **After approval, run one live canary.** Only then enable additional account_id entries.

## 2. What the reviewer should be able to verify in under five minutes
```text
A. Who owns this application?
B. What exact provider capability is being requested?
C. Which exact scope/permission enables it?
D. Where in the UI is that capability used?
E. Is the OAuth flow real?
F. Is the resulting API object visible?
G. Can the reviewer reproduce it with the supplied test account?
H. Is privacy/security handling documented?
```

## 3. Review-build policy for this software
Use a provider-specific review build, not a forked product architecture. The core orchestrator should remain the same; what changes between R1/R2 is the provider manifest/configuration, minimal scopes, reviewer instructions, and the exact release fingerprint used for the submission.

**R1:** minimum viable approved use case.
**R2:** only after a rejection; remove the rejected scope/behavior, correct the demo/evidence, or implement the missing requirement.
**R3:** only if the provider explicitly asks for a different product shape or new app. Do not create multiple apps merely to bypass a rejection.

## 3.1 Submission software lifecycle (important)

Do not submit the full multi-provider build just because it contains many adapters. For a review-gated provider, create a provider-specific review build from the same core codebase:

- **R0 — integration build:** the provider transport works against your owner-controlled test destination.
- **R1 — review build:** only the requested provider capability is enabled; unrelated providers and unused permissions are disabled in the submitted configuration.
- **R2 — correction build:** only the reviewer-requested defect/scope/UX issue is changed. Keep the same product identity and document the new build fingerprint.
- **R3 — post-approval production build:** add the approved live account(s), preserve least privilege, and run one live canary before enabling scheduled automation.

The archive contains a build-fingerprint mechanism specifically so a macOS `.app` cannot silently reuse a previous cached runtime with the same semantic version. Every review submission should record the exact fingerprint, requested scopes, redirect URIs, demo URL, and configuration used for that submission.

## 4. Evidence pack to prepare once
### Product identity
- Product name: Platform Orchestrator
- Real owner/legal entity: fill with the actual owner
- Public website on the same domain used in the developer console
- Privacy Policy
- Terms
- Support/contact page
- Data deletion / access-revocation instructions when required

### Technical proof
- exact release/build ID submitted
- OAuth redirect URIs
- exact requested scopes
- one test destination
- one real test publish/read
- response/resource ID
- error handling for 401/403/429/5xx
- screenshots or screen recording

### Reviewer access
- working test credentials when the platform permits/requires them
- deterministic steps, one action per line
- expected result after every step
- no secrets in the recording

## 5. Strict current platform paths — verified against official docs on 2026-10-03

| Provider | What you need | Review/access gate | Evidence to show | Official sources |
|---|---|---|---|---|
| beehiiv | API key + publication access | Plan/role/provider policy | Verify the plan/role permits posts:write before claiming production support; test one publication-owned post. | https://developers.beehiiv.com/api-reference/posts |
| Bluesky | Handle + App Password | No centralized review for this basic protocol access path | Create an App Password, use official AT Protocol endpoints, never send the account password. | https://docs.bsky.app/docs/advanced-guides/api-directory |
| Dev.to | DEV.to API key | No central app review for basic API key path | Use an account API key and one controlled article publish. | https://developers.forem.com/api/v0 |
| Discord | Discord application or webhook | No generic review for basic webhook/bot usage; server permissions apply | For the current build, prefer webhook messaging. For bots, use OAuth2 install and minimal bot scopes/permissions. | https://discord.com/developers/docs/resources/webhook | https://discord.com/developers/docs/topics/oauth2 |
| Dribbble | Developer app + OAuth2 token | Provider developer-app policy | Use a real designer/team account and demonstrate one image shot operation. | https://developer.dribbble.com/ |
| Facebook Page | Meta app + Page-admin authorization + Page token | Meta App Review / Advanced Access as required | Show Page selection, permission grant, one Page post, and returned post/video ID. | https://developers.facebook.com/ |
| Farcaster (Neynar) | Neynar API key + Farcaster FID/signer | Partner/provider access | Obtain provider access first, then demonstrate one signed cast through the official partner API. | https://docs.neynar.com/ |
| Google Business Profile | Google Cloud project + approved Business Profile API access + OAuth business.manage | Project access approval | Google says access is not public. Demonstrate a real business reason, valid business website, approved project, and owner/manager authorization to the specific profile. | https://developers.google.com/my-business/content/overview | https://developers.google.com/my-business/content/basic-setup | https://developers.google.com/my-business/content/policies |
| Hashnode | Hashnode Personal Access Token + publication ID | Account/publication policy | Use publication you control; one real GraphQL mutation, then reconcile the article ID. | https://docs.hashnode.com/ |
| Instagram | Meta app + Instagram professional account + official OAuth path | Meta App Review / Advanced Access as required by the requested permissions | Use only permissions needed for the exact publish flow; show OAuth, media container creation, publish, and resulting post on an owner-controlled account; keep media URLs reachable. | https://developers.facebook.com/documentation/instagram-platform/content-publishing | https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media_publish |
| Instagram Messaging | Meta access token + Instagram messaging product | Meta messaging requirements | Current build is scaffold; first complete native message transport before seeking production access for this code path. | https://developers.facebook.com/docs/messenger-platform/instagram |
| Kick | Kick OAuth/developer credentials if available for current endpoint set | Provider API eligibility | Current build does not advertise generic video publishing; do not request access under a false upload claim. | https://docs.kick.com/ |
| Lemmy | Account credentials + instance JWT | Per-instance policy | Use the instance API and a normal user account; respect instance moderation rules. | https://join-lemmy.org/docs/en/client_development/01-getting_started.html |
| LINE Official Account | LINE Official Account channel + channel access token | Account/channel policy | Use Messaging API for bot messaging; not a feed publisher. | https://developers.line.biz/en/docs/messaging-api/getting-started/ |
| LinkedIn | LinkedIn developer app tied to real legal organization + verified business email/domain + associated Page | Community Management Development tier, then separate Standard tier request; current official guidance requires vetting and screencast for Standard | Do not start with Standard. First obtain Development, complete the integration, create a real Page post, then submit Standard with a high-resolution downloadable screencast matching every use case. A Development-tier rejection requires a new app before reapplying according to current official guidance. | https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-05 | https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-09 |
| Listmonk | Self-hosted API user/token | No external review; instance admin policy | Create a dedicated API user with only required campaign/list permissions. | https://listmonk.app/docs/apis/apis/ |
| Mastodon | Instance registration + OAuth token | Per-instance policy | Register an app on the target instance and request only the write scopes required. | https://docs.joinmastodon.org/methods/apps/ | https://docs.joinmastodon.org/methods/statuses/ |
| Medium | No new publish API path treated as available by this build | Not applicable | Do not spend review effort; provider is explicitly feasibility/deprecated. | https://github.com/Medium/medium-api-docs |
| Facebook Messenger | Meta Page token + Messenger product | Meta messaging access requirements | Current build is messaging scaffold; do not submit this module as a completed publish integration. | https://developers.facebook.com/docs/messenger-platform/ |
| MeWe | MeWe Open API app/token | App review / provider-specific access | Treat as partial native until provider access and current API terms are confirmed for the target use case. | https://developer.mewe.com/api-docs |
| Moltbook | Service API key | Provider policy | Use documented API and only the account/submolt you control. | https://www.moltbook.com/ |
| Nostr | Private key + relay set | No central review | Treat the private key like a cryptographic secret; use selected relays and publish NIP-01 events. | https://github.com/nostr-protocol/nips/blob/master/01.md |
| Pinterest | Pinterest developer app + OAuth 2.0 + Business account | Trial access first; Standard upgrade requires review evidence | The Standard review must show the live OAuth flow and live Pinterest integration. Privacy policy must be public and hosted on a domain clearly associated with the app/company. Do not use passwords or session cookies. | https://developers.pinterest.com/docs/key-concepts/access-tiers/ | https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/ |
| Reddit | Existing OAuth Data API app + registered app identity | Registration/migration requirement is now time-bound for legacy Data API apps | Register the existing Data API app by 2026-11-30. Plan migration because Reddit says unregistered access starts being removed 2027-01-12 and remaining public API access ends March 2027. | https://developers.reddit.com/app-registration | https://developers.reddit.com/docs/guides/migrate/public-api |
| Rutube | Official partner credentials/contract | Partner access | Do not replace partner access with reverse-engineered/private endpoints. | https://rutube.ru/info/for-developers/ |
| Signal | No verified official publish API contract for this project | Not applicable | Keep this provider fail-closed; do not use unofficial automation as an API substitute. | https://signal.org/docs/ |
| Skool | No stable official publish contract confirmed in this build | Not applicable | Keep fail-closed; do not request unofficial credentials or use browser automation as an API substitute. | https://www.skool.com/ |
| Slack | Slack app + granular bot scopes + OAuth v2 | Workspace install approval; marketplace review only if distributing broadly | Use a modern Slack app, not legacy custom tokens; request the minimum bot scopes such as chat:write. | https://api.slack.com/authentication/oauth-v2 | https://api.slack.com/authentication/quickstart |
| Snapchat | Snap Public Profile API access + OAuth + profile/media identifiers | Provider access / app review as applicable | Current build is partial and expects provider-side media objects. Do not claim arbitrary local-file upload until that path is fully implemented and tested. | https://developers.snap.com/marketing-api/Public-Profile-API/ |
| Telegram | BotFather bot token + channel/group admin rights | No generic app review for the basic Bot API path | Create one bot, add it as admin to the exact destination, verify getMe/getChat, then one test message. | https://core.telegram.org/bots/api | https://core.telegram.org/bots#botfather |
| Threads | Threads/Meta app + Threads OAuth token | Meta App Review / Advanced Access as required | Demonstrate official OAuth, create container, publish, and reconciliation; no passwords/cookies. | https://developers.facebook.com/documentation/threads/get-started | https://developers.facebook.com/documentation/threads/create-posts |
| TikTok | TikTok for Developers app + Content Posting API + creator OAuth | Approval for video.publish plus client audit to lift unaudited private-only restrictions | First pass review should show a working integration in the allowed private/inbox mode; then Direct Post audit with creator_info → init → upload → status. | https://developers.tiktok.com/docs/en/content-posting-api-get-started | https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post | https://developers.tiktok.com/docs/en/content-posting-api-get-started-upload-content |
| Tumblr | Tumblr developer app + OAuth 1.0a credentials | Provider developer-app policy | Use official OAuth 1.0a flow; keep publish scope limited to required blog actions. | https://www.tumblr.com/docs/en/api/v2 |
| Twitch | Twitch app + OAuth user token | No generic upload-approval path for current clip capability | Current module is Clips-oriented, not arbitrary local video upload. Demonstrate clip creation from an eligible stream/VOD. | https://dev.twitch.tv/docs/authentication/register-app/ | https://dev.twitch.tv/docs/api/clips/ |
| Viber | Viber bot + auth token + HTTPS webhook | Partner/business onboarding as applicable | Show webhook verification and one controlled bot message; do not describe this module as generic social posting. | https://developers.viber.com/docs/ |
| VK | VK community/app token + community ID | Account/policy dependent | Use community-owned destination, minimal permissions, test wall/video/photo operation, then production canary. | https://dev.vk.com/ |
| WeChat Official Account | WeChat Official Account AppID/AppSecret | Official-account eligibility and account policy | Use official server-side access_token flow, keep AppSecret private, test with an owned Official Account. | https://developers.weixin.qq.com/doc/offiaccount/en/ |
| WhatsApp Cloud API | Meta Business + WABA + business phone + Cloud API app | Meta business/app review as applicable to the production use case | Treat as messaging, not generic social-feed publishing. Show send/receive with real WABA test assets and only requested messaging permissions. | https://developers.facebook.com/docs/whatsapp/cloud-api/ |
| Whop | Whop developer/app API credentials + destination IDs | Provider/app policy | Show a real Experience/feed content creation call and the returned resource. | https://dev.whop.com/api-reference/v5/apps/feed-content-items/create |
| WordPress | Self-hosted WordPress Application Password, or WordPress.com OAuth for multi-user use | No generic review for own-site Application Password path | For this build, the safest claim is own-site publishing. Do not describe Application Password as generic third-party multi-user OAuth. | https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/ | https://developer.wordpress.com/docs/api/oauth2/ |
| X (Twitter) | X Developer app/project + OAuth 2.0 PKCE + paid API access as applicable | Not a generic approval wall; access level/pricing is controlled by current X API product | Make one authenticated write and one media write; verify scopes and current paid plan before production. | https://docs.x.com/overview |
| YouTube | Google Cloud project + OAuth 2.0 client | OAuth verification may apply to sensitive/restricted scopes when the app is external | Upload one owner-controlled test video; show exact OAuth scopes and end-to-end flow; keep consent screen scopes identical to the submitted scope set. | https://developers.google.com/youtube/v3/getting-started | https://support.google.com/cloud/answer/13463073 | https://support.google.com/cloud/answer/15549135 |

## 6. Platform-specific rules that materially change your odds

### LinkedIn
LinkedIn currently separates Community Management Development and Standard tiers. Their official review page says applicants must provide a real business identity, verified business email, verified organization/domain, and the application must be verified by the associated LinkedIn Page. Standard access requires that the integration already be built and tested, plus a downloadable high-resolution screencast covering each declared use case. If a development-tier request is rejected, LinkedIn currently instructs the developer to create a new app before reapplying.

### Pinterest
Pinterest is unusually explicit about what can cause a Standard-access denial: an incomplete privacy policy, an unclear app description, a demo that does not show OAuth authentication, or a demo that does not show live Pinterest integration. The official guidance also says not to use user passwords or Pinterest session cookies instead of OAuth.

### TikTok
TikTok requires a registered developer app and the Content Posting API product. Direct Post requires approval/authorization of `video.publish`; unaudited clients are restricted to private visibility, and a client audit is required to lift those restrictions. The current docs also show that Content Posting API now supports photos, so adding photo support is a possible future code upgrade, but this build deliberately keeps its default publish contract video/inbox-only.

### YouTube / Google OAuth
Google requires the OAuth consent configuration and the verification submission to match the scopes actually requested. For sensitive/restricted scopes, Google may require verification; its current guidance also recommends using a staging project when preparing verification. The demo video should show the complete OAuth grant and every integration point that uses the requested scopes.

### Google Business Profile
Business Profile API access is not open by default. Google currently requires a valid Google account, a legitimate business reason, a valid Cloud project, and a business website URL; the project must be approved before the related APIs become available. There is no sandbox, so testing must use the real account/profile model, with `validateOnly` where supported. Google also says that API access does not itself grant access to a business profile: the OAuth user must have access to that specific profile.

### Reddit
Reddit has an urgent lifecycle issue for this codebase. Reddit currently asks existing Data API apps to register with the Developer Platform by **November 30, 2026**. It says API access for unregistered apps/users starts being removed **January 12, 2027**, with the remaining public API ending in **March 2027**. Therefore the current legacy OAuth module should be treated as a migration track, not a permanent approval path.

### X
The current X developer documentation advertises the X API as pay-per-use and an Enterprise product with custom limits. The code therefore should not promise a permanently free or universally unlimited API tier; confirm the current paid access level and usage limits in the X Developer Console before production.

## 6.1 What materially increases approval probability

The strongest evidence pattern is: real identity + exact use case + minimum permission set + working OAuth + real owner-controlled destination + successful API operation + reproducible reviewer steps + public privacy/support pages + clean error handling.

The following practices are specifically counterproductive: requesting future/unimplemented scopes, presenting browser automation/cookie reuse as an API integration, showing a mock instead of a real provider response, giving a reviewer a dead test account, or submitting a demo that performs actions outside the requested permission.

There is no numerical approval probability that can be honestly assigned in advance. The provider can deny access for policy, eligibility, market/product decisions, account history, or reviewer reasons not exposed in the public API documentation.

## 7. Why "4 emails" is not the right strategy
The correct interpretation is usually **multiple evidence stages**, not multiple support messages. A platform can require business verification, developer/app registration, a permission/product request, a test integration, and then a higher access tier. Those are separate workflow stages. Sending four identical messages does not create an approval entitlement.

## 8. Exact screencast script
```text
00:00–00:15  App name + one-sentence use case
00:15–00:45  Open provider authorization flow
00:45–01:15  Show exact requested scope(s) in consent
01:15–02:30  Perform the exact feature under review
02:30–03:00  Show returned resource/post ID and status
03:00–03:30  Show revoke/disconnect or account-management path
03:30–04:00  Show error handling / safe refusal where relevant
04:00–04:30  Finish with privacy/security note and test-account instructions
```
Do not show passwords, client secrets, refresh tokens, private keys, or unrelated applications.

## 9. Exact reviewer note template
```text
Application: Platform Orchestrator
Use case: [one exact provider capability]
Destination: [provider account/page/channel/business profile owned or authorized by us]
Authorization: Official OAuth/API authorization only; no password or cookie collection.
Requested permissions: [minimal list]
How the permissions are used: [one sentence per permission]
Reviewer test steps:
1. [step]
2. [step]
3. [step]
Expected result: [result]
Security: Tokens are stored securely and are not committed to source control.
Privacy: [privacy URL]
Support: [support URL]
Demo: [publicly accessible video URL]
```

## 10. Rejection playbook
1. Save the exact rejection text and the exact app build submitted.
2. Classify the failure: identity / policy / scope / demo / test access / technical / product eligibility.
3. Fix only the failing dimension first.
4. Update the review build and record a new release fingerprint.
5. Follow the provider-specific resubmission rule — for example, LinkedIn may require a new app after a Development rejection.
6. Never claim a capability that the current manifest or code does not actually implement.

## 11. Final pre-submission gate
```text
[ ] public website works
[ ] privacy policy works
[ ] terms/support work
[ ] exact app name/logo are final
[ ] exact scopes match code
[ ] exact redirect URIs match console
[ ] owner/test destination is real and authorized
[ ] one real API call succeeds
[ ] one real result is visible
[ ] demo video is public and complete
[ ] reviewer instructions are deterministic
[ ] no secret appears in video/logs
[ ] provider-specific access prerequisite is satisfied
[ ] exact submitted build is archived
[ ] live canary is still OFF until approval is confirmed
```

## 12. Current code boundaries to state honestly in every application
- TikTok defaults to inbox/manual semantics in this build; Direct Post is a separate audited path.
- Twitch is Clips-oriented in this build, not arbitrary local-video upload.
- Kick is metadata-oriented in this build; generic video publishing is not advertised.
- Messenger and Instagram Messaging are messaging scaffolds, not completed generic feed publishers.
- Signal, Skool, Medium and RUTUBE remain fail-closed/feasibility/partner boundaries rather than pretending to have a public self-service publish API.
- Reddit is a migration track because of the 2026–2027 Data API lifecycle.

## 12.1 First-run launch by operating system

### macOS
Preferred path: unzip the delivery archive and double-click **Platform Orchestrator.app**. The app copies the immutable runtime into `~/Library/Application Support/Platform Orchestrator/`, preserves user state there, and launches `START.command` in Terminal. The app uses a build fingerprint, so a new build with the same semantic version does not silently reuse an older cached runtime.

Because this app is distributed outside the Mac App Store, macOS may attach a quarantine attribute. If Finder blocks the first launch with a security warning, use Finder's **Open** action once. As a last-resort operator step, after verifying the archive checksum, the owner can clear the quarantine attribute with:

```bash
xattr -dr com.apple.quarantine "/path/to/Platform Orchestrator.app"
```

Do not disable Gatekeeper system-wide. This project does not claim Apple notarization unless the owner has separately signed and notarized the `.app` with a Developer ID certificate.

### Linux / macOS terminal

```bash
chmod +x install.sh start.sh START.command
./install.sh
```

`install.sh` creates the virtual environment, installs the pinned dependency lock, creates local state directories, performs version/import/dry-run smoke checks, and starts the daemon unless `--no-start` is supplied. `start.sh` can subsequently be used as the normal foreground/daemon launcher.

### Windows

Double-click `install.bat` once, then `start.bat`. Both scripts use a SHA-256 stamp of the dependency lock, so changing the lock forces a reinstall rather than relying on a timestamp. Windows SmartScreen may also require the owner to choose **More info → Run anyway** for an unsigned local distribution; this is an OS trust warning, not an application error.

## 13. Sources checked on 2026-10-03
- LinkedIn Community Management review/access: https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-05
- LinkedIn access tiers: https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-09
- Pinterest access tiers: https://developers.pinterest.com/docs/key-concepts/access-tiers/
- Pinterest OAuth: https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/
- TikTok Content Posting API: https://developers.tiktok.com/docs/en/content-posting-api-get-started
- TikTok Direct Post: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- YouTube Data API: https://developers.google.com/youtube/v3/getting-started
- Google OAuth verification: https://support.google.com/cloud/answer/13463073
- Google verification demo requirements: https://support.google.com/cloud/answer/15549135
- Google Business Profile setup/access: https://developers.google.com/my-business/content/basic-setup
- Google Business Profile policy: https://developers.google.com/my-business/content/policies
- Reddit registration: https://developers.reddit.com/app-registration
- Reddit Data API migration: https://developers.reddit.com/docs/guides/migrate/public-api
- X developer platform: https://docs.x.com/overview
- Slack OAuth v2: https://api.slack.com/authentication/oauth-v2
- Discord OAuth2: https://discord.com/developers/docs/topics/oauth2

