"""Comprehensive tests for /api/meetings endpoints."""

from unittest.mock import patch


class TestUploadMeeting:
    """POST /api/meetings/upload"""

    def test_upload_text_success(self, client):
        """その場で文字入力した面談メモが登録される。"""
        with patch("app.routers.meetings.register_to_database", return_value={"status": "success"}):
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "田中太郎", "title": "初回面談", "note": "テストメモ", "text": "面談の内容です。"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transcript"] == "面談の内容です。"
        assert data["meeting_id"] is not None

    def test_upload_document_success(self, client):
        """文書ファイルからテキストを抽出して登録される。"""
        with patch("app.routers.meetings.read_file", return_value="文書のテキスト"), \
             patch("app.routers.meetings.register_to_database", return_value={"status": "success"}):
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "田中太郎", "title": "記録", "note": ""},
                files={"file": ("test.docx", b"fake docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transcript"] == "文書のテキスト"

    def test_upload_document_read_failure(self, client):
        """文書からテキストを読み取れない場合はエラーを返す。"""
        with patch("app.routers.meetings.read_file", side_effect=ValueError("broken")):
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "田中太郎", "title": "", "note": ""},
                files={"file": ("test.pdf", b"fake pdf", "application/pdf")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "読み取れませんでした" in data["message"]

    def test_upload_audio_rejected(self, client):
        """音声ファイルは廃止済みのため拒否される。"""
        audio_files = [
            ("test.mp3", "audio/mpeg"),
            ("test.wav", "audio/wav"),
            ("test.m4a", "audio/x-m4a"),
        ]
        for filename, mime_type in audio_files:
            resp = client.post(
                "/api/meetings/upload",
                data={"client_name": "テスト", "title": "", "note": ""},
                files={"file": (filename, b"audio data", mime_type)},
            )
            assert resp.status_code == 200, f"Failed for {filename}"
            data = resp.json()
            assert data["status"] == "error", f"Should reject {filename}"
            assert "対応していないファイル形式" in data["message"]

    def test_upload_supported_document_formats(self, client):
        """対応する文書形式（docx/xlsx/pdf/txt）はすべて受け付ける。"""
        formats = [
            ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("test.pdf", "application/pdf"),
            ("test.txt", "text/plain"),
        ]
        for filename, mime_type in formats:
            with patch("app.routers.meetings.read_file", return_value="ok"), \
                 patch("app.routers.meetings.register_to_database", return_value={"status": "success"}):
                resp = client.post(
                    "/api/meetings/upload",
                    data={"client_name": "テスト", "title": "", "note": ""},
                    files={"file": (filename, b"doc data", mime_type)},
                )
            assert resp.status_code == 200, f"Failed for {filename}"
            assert resp.json()["status"] == "success", f"Failed for {filename}"

    def test_upload_no_content(self, client):
        """本文もファイルもない場合はエラーを返す。"""
        resp = client.post(
            "/api/meetings/upload",
            data={"client_name": "テスト", "title": "", "note": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "内容がありません" in data["message"]

    def test_upload_missing_client_name(self, client):
        resp = client.post(
            "/api/meetings/upload",
            files={"file": ("test.docx", b"doc", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
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
