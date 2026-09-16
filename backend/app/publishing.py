"""M10 LinkedIn publishing abstraction (text posts only, no analytics).

- REAL mode posts through the documented member ugcPosts flow using the
  server-side decrypted token. A post counts as published only on HTTP 201
  with an X-RestLi-Id response header.
- MOCK mode never contacts LinkedIn and returns a clearly fake identifier.
- Tokens are never logged, never returned, and never leave this module
  except inside the Authorization header of the provider request.
"""

import httpx

UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
PUBLISH_SCOPE = "w_member_social"
TEXT_MAX = 3000


class PublishUpstreamError(Exception):
    """LinkedIn answered with an error. No publication may be assumed."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class PublishTimeoutUnknown(Exception):
    """Transport failed before any LinkedIn verdict. Outcome unknown:
    never mark published, never assume failure is final."""

    def __init__(self):
        super().__init__("linkedin_timeout_unknown")
        self.detail = "linkedin_timeout_unknown"


def mock_publish(item_id: int) -> dict:
    return {"post_id": f"mock:linkedin-post:{item_id}", "mock": True}


def real_publish(access_token: str, member_id: str, text: str) -> dict:
    body = {
        "author": f"urn:li:person:{member_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        res = httpx.post(
            UGC_POSTS_URL,
            headers={
                "X-Restli-Protocol-Version": "2.0.0",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=20,
        )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise PublishTimeoutUnknown() from exc
    except httpx.HTTPError as exc:
        raise PublishUpstreamError("linkedin_network_error") from exc
    if res.status_code == 429:
        raise PublishUpstreamError("linkedin_rate_limited")
    if res.status_code != 201:
        raise PublishUpstreamError(f"linkedin_upstream_{res.status_code}")
    post_id = res.headers.get("x-restli-id", "")
    if not post_id:
        raise PublishUpstreamError("linkedin_missing_post_id")
    return {"post_id": post_id, "mock": False}
