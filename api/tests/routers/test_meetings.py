"""Comprehensive tests for /api/meetings endpoints."""

from unittest.mock import patch, AsyncMock, MagicMock


class TestUploadMeeting:
    """POST /api/meetings/upload"""

    def test_upload_success(self, client):
        with patch("app.routers.meetings._transcribe_with_gemini", new_callable=AsyncMock, return_value="テスト文字起こし"), \
             patch("app.routers.meetings.register_to_database", return_value={"status": "success"}), \
             patch("app.routers.meetings.embed_text", new_callable=AsyncMock, return_value=[0.1] * 768), \
             patch("app.routers.meetings.run_query", return_value=[]):
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "田中太郎", "title": "初回面談", "note": "テストメモ"},
                files={"file": ("test.mp3", b"fake audio content", "audio/mpeg")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transcript"] == "テスト文字起こし"
        assert data["meeting_id"] is not None

    def test_upload_unsupported_format(self, client):
        resp = client.post(
            "/api/meetings/upload",
            data={"client_name": "田中太郎", "title": "テスト", "note": ""},
            files={"file": ("test.txt", b"text content", "text/plain")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "Unsupported" in data["message"]

    def test_upload_transcription_failure(self, client):
        """If transcription fails, meeting is still registered (transcript is empty)."""
        with patch("app.routers.meetings._transcribe_with_gemini", new_callable=AsyncMock, return_value=None), \
             patch("app.routers.meetings.register_to_database", return_value={"status": "success"}):
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "田中太郎", "title": "テスト", "note": ""},
                files={"file": ("test.wav", b"fake wav", "audio/wav")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transcript"] is None

    def test_upload_various_audio_formats(self, client):
        """All supported audio formats should be accepted."""
        formats = [
            ("test.mp3", "audio/mpeg"),
            ("test.wav", "audio/wav"),
            ("test.ogg", "audio/ogg"),
            ("test.webm", "audio/webm"),
            ("test.flac", "audio/flac"),
            ("test.m4a", "audio/x-m4a"),
        ]
        for filename, mime_type in formats:
            with patch("app.routers.meetings._transcribe_with_gemini", new_callable=AsyncMock, return_value="ok"), \
                 patch("app.routers.meetings.register_to_database", return_value={"status": "success"}), \
                 patch("app.routers.meetings.embed_text", new_callable=AsyncMock, return_value=[0.1] * 768), \
                 patch("app.routers.meetings.run_query", return_value=[]):
                resp = client.post(
                    "/api/meetings/upload",
                    data={"client_name": "テスト", "title": "", "note": ""},
                    files={"file": (filename, b"audio data", mime_type)},
                )
            assert resp.status_code == 200, f"Failed for {filename}"
            assert resp.json()["status"] == "success", f"Failed for {filename}"

    def test_upload_unsupported_extensions(self, client):
        """Non-audio files should be rejected."""
        bad_files = [
            ("test.pdf", "application/pdf"),
            ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("test.jpg", "image/jpeg"),
        ]
        for filename, mime_type in bad_files:
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "テスト", "title": "", "note": ""},
                files={"file": (filename, b"data", mime_type)},
            )
            assert resp.json()["status"] == "error", f"Should reject {filename}"

    def test_upload_missing_client_name(self, client):
        resp = client.post(
            "/api/meetings/upload",
            files={"file": ("test.mp3", b"audio", "audio/mpeg")},
        )
        assert resp.status_code == 422


class TestListMeetings:
    """GET /api/meetings/{client_name}"""

    def test_list_meetings_success(self, client):
        mock_records = [
            {
                "date": "2026-04-01",
                "title": "初回面談",
                "duration": "30分",
                "transcript": "テスト文字起こし",
                "note": "メモ",
                "file_path": "/tmp/test.mp3",
                "client_name": "田中太郎",
            },
        ]
        with patch("app.routers.meetings.run_query", return_value=mock_records):
            resp = client.get("/api/meetings/田中太郎")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "初回面談"
        assert data[0]["client_name"] == "田中太郎"

    def test_list_meetings_empty(self, client):
        with patch("app.routers.meetings.run_query", return_value=[]):
            resp = client.get("/api/meetings/テスト太郎")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_meetings_multiple_records(self, client):
        mock_records = [
            {"date": "2026-04-01", "title": "第2回", "duration": None, "transcript": "", "note": "", "file_path": None, "client_name": "テスト"},
            {"date": "2026-03-15", "title": "初回", "duration": None, "transcript": "", "note": "", "file_path": None, "client_name": "テスト"},
        ]
        with patch("app.routers.meetings.run_query", return_value=mock_records):
            resp = client.get("/api/meetings/テスト")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Should be in date DESC order (as mocked)
        assert data[0]["title"] == "第2回"
