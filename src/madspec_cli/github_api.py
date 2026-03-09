from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import truststore

DEFAULT_SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


@dataclass(frozen=True)
class ReleaseAsset:
    filename: str
    size: int
    release: str
    asset_url: str


def _github_token(cli_token: str | None = None) -> str | None:
    return (
        (cli_token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    ) or None


def _github_auth_headers(cli_token: str | None = None) -> dict[str, str]:
    token = _github_token(cli_token)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _parse_rate_limit_headers(headers: httpx.Headers) -> dict:
    info: dict[str, object] = {}
    if "X-RateLimit-Limit" in headers:
        info["limit"] = headers.get("X-RateLimit-Limit")
    if "X-RateLimit-Remaining" in headers:
        info["remaining"] = headers.get("X-RateLimit-Remaining")
    if "X-RateLimit-Reset" in headers:
        reset_epoch = int(headers.get("X-RateLimit-Reset", "0"))
        if reset_epoch:
            reset_time = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
            info["reset_epoch"] = reset_epoch
            info["reset_time"] = reset_time
            info["reset_local"] = reset_time.astimezone()
    if "Retry-After" in headers:
        retry_after = headers.get("Retry-After")
        try:
            info["retry_after_seconds"] = int(retry_after)
        except (TypeError, ValueError):
            info["retry_after"] = retry_after
    return info


def _format_rate_limit_error(status_code: int, headers: httpx.Headers, url: str) -> str:
    rate_info = _parse_rate_limit_headers(headers)
    lines = [f"GitHub API returned status {status_code} for {url}", ""]

    if rate_info:
        lines.append("[bold]Rate Limit Information:[/bold]")
        if "limit" in rate_info:
            lines.append(f"  • Rate Limit: {rate_info['limit']} requests/hour")
        if "remaining" in rate_info:
            lines.append(f"  • Remaining: {rate_info['remaining']}")
        if "reset_local" in rate_info:
            reset_str = rate_info["reset_local"].strftime("%Y-%m-%d %H:%M:%S %Z")
            lines.append(f"  • Resets at: {reset_str}")
        if "retry_after_seconds" in rate_info:
            lines.append(f"  • Retry after: {rate_info['retry_after_seconds']} seconds")
        lines.append("")

    lines.append("[bold]Troubleshooting Tips:[/bold]")
    lines.append(
        "  • If you're on a shared CI or corporate environment, you may be rate-limited."
    )
    lines.append(
        "  • Consider using a GitHub token via --github-token or the GH_TOKEN/GITHUB_TOKEN"
    )
    lines.append("    environment variable to increase rate limits.")
    lines.append(
        "  • Authenticated requests have a limit of 5,000/hour vs 60/hour for unauthenticated."
    )
    return "\n".join(lines)


def create_http_client(*, verify: bool | ssl.SSLContext = DEFAULT_SSL_CONTEXT) -> httpx.Client:
    return httpx.Client(verify=verify)


def fetch_latest_release_asset(
    repo_owner: str,
    repo_name: str,
    asset_pattern: str,
    *,
    client: httpx.Client | None = None,
    github_token: str | None = None,
    debug: bool = False,
) -> ReleaseAsset:
    http_client = client or create_http_client()
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    response = http_client.get(
        api_url,
        timeout=30,
        follow_redirects=True,
        headers=_github_auth_headers(github_token),
    )
    if response.status_code != 200:
        error_msg = _format_rate_limit_error(response.status_code, response.headers, api_url)
        if debug:
            error_msg += f"\n\n[dim]Response body (truncated 500):[/dim]\n{response.text[:500]}"
        raise RuntimeError(error_msg)

    try:
        release_data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Failed to parse release JSON: {exc}\nRaw (truncated 400): {response.text[:400]}"
        ) from exc

    assets = release_data.get("assets", [])
    matching_assets = [
        asset
        for asset in assets
        if asset_pattern in asset["name"] and asset["name"].endswith(".zip")
    ]
    if not matching_assets:
        asset_names = [asset.get("name", "?") for asset in assets]
        raise LookupError(
            "\n".join(asset_names)
            or "(no assets)"
        )

    asset = matching_assets[0]
    return ReleaseAsset(
        filename=asset["name"],
        size=asset["size"],
        release=release_data["tag_name"],
        asset_url=asset["browser_download_url"],
    )


def fetch_latest_release_info(
    repo_owner: str,
    repo_name: str,
    *,
    client: httpx.Client | None = None,
    github_token: str | None = None,
) -> dict[str, str]:
    http_client = client or create_http_client()
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    response = http_client.get(
        api_url,
        timeout=10,
        follow_redirects=True,
        headers=_github_auth_headers(github_token),
    )
    if response.status_code != 200:
        raise RuntimeError(_format_rate_limit_error(response.status_code, response.headers, api_url))
    return response.json()
