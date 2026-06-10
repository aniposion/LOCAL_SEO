"""Tests for posts endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PublishJob, PublishJobStatus


class TestCreatePost:
    """Tests for post creation."""

    def test_create_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
    ) -> None:
        """Test successful post creation."""
        response = client.post(
            "/posts",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "platform": "GBP",
                "title": "Test Post",
                "body": "This is a test post body",
                "hashtags": ["test", "local"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Post"
        assert data["platform"] == "GBP"
        assert data["status"] == "draft"

    def test_create_post_invalid_location(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test post creation with invalid location."""
        from uuid import uuid4

        response = client.post(
            "/posts",
            headers=auth_headers,
            json={
                "location_id": str(uuid4()),
                "platform": "GBP",
                "title": "Test Post",
            },
        )
        assert response.status_code == 404

    def test_create_post_forbidden_other_accounts_location(
        self, client: TestClient, auth_headers: dict[str, str], other_location: Location
    ) -> None:
        """Test a user cannot create a post for another account's location."""
        response = client.post(
            "/posts",
            headers=auth_headers,
            json={
                "location_id": str(other_location.id),
                "platform": "GBP",
                "title": "Unauthorized Post",
            },
        )
        assert response.status_code == 404


class TestListPosts:
    """Tests for listing posts."""

    def test_list_posts_empty(
        self, client: TestClient, auth_headers: dict[str, str], test_location: Location
    ) -> None:
        """Test listing posts when none exist."""
        response = client.get(
            f"/posts?location_id={test_location.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_posts_with_filter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test listing posts with platform filter."""
        # Create test posts
        from uuid import uuid4

        post1 = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="GBP Post",
        )
        post2 = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.DRAFT,
            title="IG Post",
        )
        db.add_all([post1, post2])
        db.commit()

        # Filter by platform
        response = client.get(
            f"/posts?location_id={test_location.id}&platform=GBP",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "GBP"

    def test_get_publish_job_history(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Publish job history should be returned newest first."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="History post",
        )
        first_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="first failure",
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        second_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.COMPLETED,
            tries=2,
            max_tries=5,
            platform_post_id="ig-post-2",
            created_at=datetime.now(UTC),
        )
        db.add_all([post, first_job, second_job])
        db.commit()

        response = client.get(f"/posts/{post.id}/publish-jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == str(second_job.id)
        assert data["items"][1]["id"] == str(first_job.id)

    def test_get_publish_job_history_with_filters_and_pagination(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Publish job history should support status, search, limit, and offset."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Filtered history post",
        )
        failed_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="token expired",
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        completed_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.COMPLETED,
            tries=2,
            max_tries=5,
            platform_post_id="ig-post-success",
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        pending_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.PENDING,
            tries=0,
            max_tries=5,
            created_at=datetime.now(UTC),
        )
        db.add_all([post, failed_job, completed_job, pending_job])
        db.commit()

        filtered_response = client.get(
            f"/posts/{post.id}/publish-jobs?status=failed&search=token&limit=1&offset=0",
            headers=auth_headers,
        )
        assert filtered_response.status_code == 200
        filtered_data = filtered_response.json()
        assert filtered_data["total"] == 1
        assert filtered_data["limit"] == 1
        assert filtered_data["offset"] == 0
        assert len(filtered_data["items"]) == 1
        assert filtered_data["items"][0]["id"] == str(failed_job.id)

        paged_response = client.get(
            f"/posts/{post.id}/publish-jobs?limit=1&offset=1",
            headers=auth_headers,
        )
        assert paged_response.status_code == 200
        paged_data = paged_response.json()
        assert paged_data["total"] == 3
        assert len(paged_data["items"]) == 1
        assert paged_data["items"][0]["id"] == str(completed_job.id)

    def test_export_publish_job_history_csv(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Publish job history should export as CSV with operational fields."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Export history post",
        )
        failed_job = PublishJob(
            id=uuid4(),
            post_id=post.id,
            platform="INSTAGRAM",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="permission denied",
            error_code="TOKEN_EXPIRED",
            created_at=datetime.now(UTC),
        )
        db.add_all([post, failed_job])
        db.commit()

        response = client.get(
            f"/posts/{post.id}/publish-jobs/export?status=failed&search=permission",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment;" in response.headers["content-disposition"]
        body = response.text
        assert "created_at,status,platform,tries,max_tries,error_code,last_error" in body
        assert "TOKEN_EXPIRED" in body
        assert "permission denied" in body

    def test_list_publish_issues_returns_latest_actionable_issues_only(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Publish issue summary should return only the latest actionable job per post."""
        from uuid import uuid4

        failed_post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Instagram issue",
        )
        retrying_post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.QUEUED,
            title="Retry scheduled",
        )
        recovered_post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.POSTED,
            title="Recovered publish",
        )
        old_failed_job = PublishJob(
            id=uuid4(),
            post_id=recovered_post.id,
            platform="gbp",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="old failure",
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        latest_success_job = PublishJob(
            id=uuid4(),
            post_id=recovered_post.id,
            platform="gbp",
            status=PublishJobStatus.COMPLETED,
            tries=2,
            max_tries=5,
            platform_post_id="gbp-success",
            created_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        failed_job = PublishJob(
            id=uuid4(),
            post_id=failed_post.id,
            platform="instagram",
            status=PublishJobStatus.FAILED,
            tries=2,
            max_tries=5,
            last_error="instagram token expired",
            error_code="TOKEN_EXPIRED",
            created_at=datetime.now(UTC) - timedelta(minutes=4),
        )
        retrying_job = PublishJob(
            id=uuid4(),
            post_id=retrying_post.id,
            platform="gbp",
            status=PublishJobStatus.PENDING,
            tries=1,
            max_tries=5,
            last_error="temporary provider outage",
            error_code="RATE_LIMITED",
            next_run_at=datetime.now(UTC) + timedelta(minutes=15),
            created_at=datetime.now(UTC),
        )
        db.add_all(
            [
                failed_post,
                retrying_post,
                recovered_post,
                old_failed_job,
                latest_success_job,
                failed_job,
                retrying_job,
            ]
        )
        db.commit()

        response = client.get("/posts/publish-issues", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["failed"] == 1
        assert data["retrying"] == 1
        assert len(data["items"]) == 2
        assert data["items"][0]["job_id"] == str(retrying_job.id)
        assert data["items"][0]["location_name"] == test_location.name
        assert data["items"][0]["can_retry"] is True
        assert data["items"][1]["job_id"] == str(failed_job.id)
        assert all(item["job_id"] != str(old_failed_job.id) for item in data["items"])

    def test_list_publish_issues_supports_filters_and_search(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        test_user,
        db: Session,
    ) -> None:
        """Publish issue summary should support location, platform, and search filters."""
        from uuid import uuid4

        second_location = Location(
            id=uuid4(),
            account_id=test_user.id,
            name="North Branch",
            country="US",
        )
        instagram_post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Token broken",
        )
        website_post = Post(
            id=uuid4(),
            location_id=second_location.id,
            platform=Platform.WEBSITE,
            status=PostStatus.FAILED,
            title="Website sync broken",
        )
        instagram_job = PublishJob(
            id=uuid4(),
            post_id=instagram_post.id,
            platform="instagram",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="token expired for instagram",
            created_at=datetime.now(UTC),
        )
        website_job = PublishJob(
            id=uuid4(),
            post_id=website_post.id,
            platform="website",
            status=PublishJobStatus.FAILED,
            tries=1,
            max_tries=5,
            last_error="website publish failed",
            created_at=datetime.now(UTC) - timedelta(minutes=2),
        )
        db.add_all([second_location, instagram_post, website_post, instagram_job, website_job])
        db.commit()

        response = client.get(
            f"/posts/publish-issues?location_id={test_location.id}&platform=INSTAGRAM&search=token",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["failed"] == 1
        assert data["retrying"] == 0
        assert data["items"][0]["job_id"] == str(instagram_job.id)
        assert data["items"][0]["location_id"] == str(test_location.id)
        assert data["items"][0]["platform"] == "instagram"


class TestUpdatePost:
    """Tests for updating posts."""

    def test_update_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test updating a post."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Original Title",
        )
        db.add(post)
        db.commit()

        response = client.patch(
            f"/posts/{post.id}",
            headers=auth_headers,
            json={"title": "Updated Title", "status": "queued"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "queued"

    def test_update_post_forbidden_other_accounts_post(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location: Location,
        db: Session,
    ) -> None:
        """Test a user cannot update another account's post."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=other_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Other Account Post",
        )
        db.add(post)
        db.commit()

        response = client.patch(
            f"/posts/{post.id}",
            headers=auth_headers,
            json={"title": "Hijacked"},
        )
        assert response.status_code == 404


class TestDeletePost:
    """Tests for deleting posts."""

    def test_delete_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Test deleting a post."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
        )
        db.add(post)
        db.commit()

        response = client.delete(
            f"/posts/{post.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


class TestPublishPost:
    """Tests for publish endpoint behavior."""

    def test_publish_instagram_requires_image_and_logs_failure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
    ) -> None:
        """Instagram publishing should fail clearly when no image is available."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.APPROVED,
            title="Instagram post without image",
            body="Caption only",
        )
        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.CONNECTED,
            is_active=True,
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

        db.add_all([post, channel])
        db.commit()

        response = client.post(f"/posts/{post.id}/publish", headers=auth_headers)
        assert response.status_code == 500
        assert response.json()["detail"] == "Instagram publishing requires an image"

        db.refresh(post)
        db.refresh(channel)

        assert post.status == PostStatus.FAILED
        assert post.error_message == "Instagram publishing requires an image"
        assert channel.status == ChannelStatus.ERROR
        assert channel.error_message == "Instagram publishing requires an image"

        publish_job = db.query(PublishJob).filter(PublishJob.post_id == post.id).one()
        assert publish_job.status == PublishJobStatus.FAILED
        assert publish_job.last_error == "Instagram publishing requires an image"

    def test_publish_failure_preserves_original_error_when_notification_fails(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """A broken alert channel must not replace the actionable publish error."""
        from uuid import uuid4

        async def exploding_notification(*args, **kwargs):
            raise RuntimeError("notification channel offline")

        monkeypatch.setattr(
            "app.services.notification.NotificationService.send_notification",
            exploding_notification,
        )

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.APPROVED,
            title="Instagram post without image",
            body="Caption only",
        )
        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.CONNECTED,
            is_active=True,
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

        db.add_all([post, channel])
        db.commit()

        response = client.post(f"/posts/{post.id}/publish", headers=auth_headers)

        assert response.status_code == 500
        assert response.json()["detail"] == "Instagram publishing requires an image"

        db.refresh(post)
        db.refresh(channel)
        assert post.error_message == "Instagram publishing requires an image"
        assert channel.error_message == "Instagram publishing requires an image"

        publish_job = db.query(PublishJob).filter(PublishJob.post_id == post.id).one()
        assert publish_job.status == PublishJobStatus.FAILED
        assert publish_job.last_error == "Instagram publishing requires an image"

    def test_publish_instagram_success_creates_audit_job(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Successful Instagram publishing should record an audit job."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.APPROVED,
            title="Instagram ready",
            body="Caption",
            image_url="https://example.com/post.jpg",
        )
        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.CONNECTED,
            is_active=True,
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

        db.add_all([post, channel])
        db.commit()

        async def fake_publish_image(self, image_url: str, caption: str, hashtags=None) -> str:
            assert image_url == "https://example.com/post.jpg"
            assert caption == "Caption"
            return "ig-provider-post-123"

        monkeypatch.setattr(
            "app.services.publisher.InstagramClient.publish_image",
            fake_publish_image,
        )

        response = client.post(f"/posts/{post.id}/publish", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "posted"
        assert data["provider_post_id"] == "ig-provider-post-123"

        db.refresh(post)
        db.refresh(channel)
        publish_job = db.query(PublishJob).filter(PublishJob.post_id == post.id).one()

        assert post.status == PostStatus.POSTED
        assert channel.status == ChannelStatus.CONNECTED
        assert channel.error_message is None
        assert publish_job.status == PublishJobStatus.COMPLETED
        assert publish_job.platform_post_id == "ig-provider-post-123"

    def test_retry_publish_failed_instagram_post(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Failed Instagram posts should be retryable through the retry endpoint."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.INSTAGRAM,
            status=PostStatus.FAILED,
            title="Retry me",
            body="Caption",
            image_url="https://example.com/retry.jpg",
        )
        channel = Channel(
            id=uuid4(),
            location_id=test_location.id,
            type=ChannelType.INSTAGRAM,
            status=ChannelStatus.ERROR,
            is_active=True,
        )
        channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

        db.add_all([post, channel])
        db.commit()

        async def fake_publish_image(self, image_url: str, caption: str, hashtags=None) -> str:
            return "ig-provider-retry-123"

        monkeypatch.setattr(
            "app.services.publisher.InstagramClient.publish_image",
            fake_publish_image,
        )

        response = client.post(f"/posts/{post.id}/retry-publish", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "posted"
        assert data["provider_post_id"] == "ig-provider-retry-123"
        assert data["latest_publish_job"]["status"] == "completed"

    def test_publish_post_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Test publishing updates status to posted."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.APPROVED,
            title="Ready to publish",
        )
        db.add(post)
        db.commit()

        async def fake_publish(_self, publish_post: Post) -> None:
            publish_post.status = PostStatus.POSTED
            publish_post.posted_at = datetime.now(UTC)
            publish_post.provider_post_id = "provider-post-123"
            publish_post.error_message = None
            db.commit()

        monkeypatch.setattr(
            "app.routers.posts.PublisherService.publish_post",
            fake_publish,
        )

        response = client.post(f"/posts/{post.id}/publish", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "posted"
        assert data["provider_post_id"] == "provider-post-123"

    def test_publish_post_failure_marks_failed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Test publish failures mark the post as failed."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.APPROVED,
            title="Will fail",
        )
        db.add(post)
        db.commit()

        async def fake_publish(_self, _post: Post) -> None:
            raise RuntimeError("publish failed")

        monkeypatch.setattr(
            "app.routers.posts.PublisherService.publish_post",
            fake_publish,
        )

        response = client.post(f"/posts/{post.id}/publish", headers=auth_headers)
        assert response.status_code == 500
        assert response.json()["detail"] == "publish failed"

        db.refresh(post)
        assert post.status == PostStatus.FAILED
        assert post.error_message == "publish failed"


class TestApprovalNotification:
    """Tests for approval notification failure and resend flows."""

    def test_request_approval_failure_keeps_pending_state(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Notification failure should return 502 after moving the post to pending approval."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title="Needs approval",
        )
        db.add(post)
        db.commit()

        async def fake_send_approval_request(*_args, **_kwargs) -> bool:
            return False

        monkeypatch.setattr(
            "app.routers.posts.NotificationService.send_approval_request",
            fake_send_approval_request,
        )

        response = client.post(
            f"/posts/{post.id}/request-approval",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 502
        assert "notification delivery failed" in response.json()["detail"]

        db.refresh(post)
        assert post.status == PostStatus.PENDING_APPROVAL
        assert post.approval_token is not None
        assert post.approval_requested_at is not None

    def test_resend_approval_notification_success(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location: Location,
        db: Session,
        monkeypatch,
    ) -> None:
        """Manual resend endpoint should return success payload."""
        from uuid import uuid4

        post = Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.PENDING_APPROVAL,
            title="Pending notification",
            approval_token="resend-token",
        )
        db.add(post)
        db.commit()

        async def fake_send_notification(self, post_id, channel, phone_number=None):
            return {
                "success": True,
                "post_id": str(post_id),
                "channel": channel,
                "phone_number": phone_number,
            }

        def fake_magic_init(self, db_session):
            self.db = db_session

        monkeypatch.setattr(
            "app.services.magic_link.ApprovalWorkflowService.__init__",
            fake_magic_init,
        )
        monkeypatch.setattr(
            "app.services.magic_link.ApprovalWorkflowService.send_approval_notification",
            fake_send_notification,
        )

        response = client.post(
            f"/approval/posts/{post.id}/send-notification",
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "email"
        assert data["result"]["post_id"] == str(post.id)
