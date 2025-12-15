"""Website/Blog integration (Git-based or WordPress)."""

import base64
from typing import Any

import httpx


class WebsiteClient:
    """Client for website content publishing."""

    def __init__(self, credentials: dict) -> None:
        self.provider = credentials.get("provider", "github")  # github, gitlab, wordpress
        self.access_token = credentials.get("access_token")
        self.repo = credentials.get("repo")  # owner/repo for git
        self.branch = credentials.get("branch", "main")
        self.content_path = credentials.get("content_path", "content/blog")
        self.wp_url = credentials.get("wp_url")  # For WordPress
        self.timeout = httpx.Timeout(30.0)

    async def publish_markdown(
        self,
        title: str | None,
        content: str,
        slug: str | None = None,
    ) -> str:
        """Publish markdown content."""
        if self.provider == "github":
            return await self._publish_github(title, content, slug)
        elif self.provider == "gitlab":
            return await self._publish_gitlab(title, content, slug)
        elif self.provider == "wordpress":
            return await self._publish_wordpress(title, content, slug)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _publish_github(
        self,
        title: str | None,
        content: str,
        slug: str | None,
    ) -> str:
        """Publish to GitHub repository."""
        from datetime import datetime

        # Generate slug from title if not provided
        if not slug and title:
            slug = title.lower().replace(" ", "-")[:50]
        slug = slug or f"post-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create frontmatter
        frontmatter = f"""---
title: "{title or 'Untitled'}"
date: "{datetime.now().isoformat()}"
draft: false
---

"""
        full_content = frontmatter + content

        # GitHub API
        file_path = f"{self.content_path}/{slug}.md"
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"

        # Check if file exists
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Try to get existing file
            existing_sha = None
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    existing_sha = response.json().get("sha")
            except Exception:
                pass

            # Create or update file
            data: dict[str, Any] = {
                "message": f"Add/update post: {title or slug}",
                "content": base64.b64encode(full_content.encode()).decode(),
                "branch": self.branch,
            }
            if existing_sha:
                data["sha"] = existing_sha

            response = await client.put(url, headers=headers, json=data)

            if response.status_code not in [200, 201]:
                raise Exception(f"GitHub API error: {response.status_code} - {response.text}")

            return response.json().get("content", {}).get("sha", slug)

    async def _publish_gitlab(
        self,
        title: str | None,
        content: str,
        slug: str | None,
    ) -> str:
        """Publish to GitLab repository."""
        from datetime import datetime
        import urllib.parse

        slug = slug or f"post-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        frontmatter = f"""---
title: "{title or 'Untitled'}"
date: "{datetime.now().isoformat()}"
---

"""
        full_content = frontmatter + content

        file_path = f"{self.content_path}/{slug}.md"
        encoded_path = urllib.parse.quote(file_path, safe="")
        encoded_repo = urllib.parse.quote(self.repo, safe="")

        url = f"https://gitlab.com/api/v4/projects/{encoded_repo}/repository/files/{encoded_path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"PRIVATE-TOKEN": self.access_token}

            # Check if file exists
            response = await client.get(url, headers=headers, params={"ref": self.branch})
            method = "PUT" if response.status_code == 200 else "POST"

            data = {
                "branch": self.branch,
                "content": full_content,
                "commit_message": f"Add/update post: {title or slug}",
            }

            response = await client.request(method, url, headers=headers, json=data)

            if response.status_code not in [200, 201]:
                raise Exception(f"GitLab API error: {response.status_code} - {response.text}")

            return slug

    async def _publish_wordpress(
        self,
        title: str | None,
        content: str,
        slug: str | None,
    ) -> str:
        """Publish to WordPress via REST API."""
        import markdown

        # Convert markdown to HTML
        html_content = markdown.markdown(content)

        url = f"{self.wp_url}/wp-json/wp/v2/posts"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            data: dict[str, Any] = {
                "title": title or "Untitled",
                "content": html_content,
                "status": "publish",
            }
            if slug:
                data["slug"] = slug

            response = await client.post(url, headers=headers, json=data)

            if response.status_code not in [200, 201]:
                raise Exception(f"WordPress API error: {response.status_code} - {response.text}")

            return str(response.json().get("id", ""))
