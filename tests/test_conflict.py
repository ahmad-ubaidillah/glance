"""Tests for conflict detector."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestConflictDetector:
    @pytest.fixture
    def temp_repo(self, tmp_path):
        return tmp_path

    def test_detect_no_conflicts(self, temp_repo):
        from glance.conflict import ConflictDetector

        (temp_repo / "clean.py").write_text("def foo():\n    pass\n")

        detector = ConflictDetector(temp_repo)
        conflicts = detector.get_all_conflicts()

        assert conflicts == []

    def test_detect_single_conflict(self, temp_repo):
        from glance.conflict import ConflictDetector

        content = """def login(user):
<<<<<<< HEAD
    return bcrypt.hash(user.password)
=======
    return bcrypt.hash(user.passwd)
>>>>>>> feature/login

def logout():
    pass
"""
        (temp_repo / "auth.py").write_text(content)

        detector = ConflictDetector(temp_repo)
        conflicts = detector.get_all_conflicts()

        assert len(conflicts) == 1
        assert conflicts[0].path == "auth.py"
        assert len(conflicts[0].conflicts) == 1

        region = conflicts[0].conflicts[0]
        assert region.our_content.strip() == "return bcrypt.hash(user.password)"
        assert region.their_content.strip() == "return bcrypt.hash(user.passwd)"

    def test_detect_multiple_conflicts(self, temp_repo):
        from glance.conflict import ConflictDetector

        content = """<<<<<<< HEAD
x = 1
=======
x = 2
>>>>>>> feature

y = 1

<<<<<<< HEAD
def foo():
    return True
=======
async def foo():
    return await db.query()
>>>>>>> feature
"""
        (temp_repo / "main.py").write_text(content)

        detector = ConflictDetector(temp_repo)
        conflicts = detector.get_all_conflicts()

        assert len(conflicts) == 1
        assert len(conflicts[0].conflicts) == 2

    def test_parse_specific_file(self, temp_repo):
        from glance.conflict import ConflictDetector

        content = """<<<<<<< HEAD
def test():
    pass
=======
def test():
    assert True
>>>>>>> feature
"""
        (temp_repo / "test.py").write_text(content)

        detector = ConflictDetector(temp_repo)
        result = detector.parse_file("test.py")

        assert result is not None
        assert result.path == "test.py"
        assert len(result.conflicts) == 1


class TestConflictResolver:
    @pytest.fixture
    def temp_repo(self, tmp_path):
        return tmp_path

    def test_resolve_keep_ours(self, temp_repo):
        from glance.conflict import ConflictResolver

        content = """<<<<<<< HEAD
def login(user):
    return bcrypt.hash(user.password)
=======
def login(user):
    return bcrypt.hash(user.passwd)
>>>>>>> feature
"""
        (temp_repo / "auth.py").write_text(content)

        resolver = ConflictResolver(temp_repo)
        resolver.resolve_file("auth.py", {1: "A"})

        result = (temp_repo / "auth.py").read_text()
        assert "user.password" in result
        assert "<<<<<<" not in result

    def test_resolve_keep_theirs(self, temp_repo):
        from glance.conflict import ConflictResolver

        content = """<<<<<<< HEAD
def login(user):
    return bcrypt.hash(user.password)
=======
def login(user):
    return bcrypt.hash(user.passwd)
>>>>>>> feature
"""
        (temp_repo / "auth.py").write_text(content)

        resolver = ConflictResolver(temp_repo)
        resolver.resolve_file("auth.py", {1: "B"})

        result = (temp_repo / "auth.py").read_text()
        assert "user.passwd" in result
        assert "<<<<<<" not in result


class TestConflictReporter:
    def test_no_conflicts_report(self):
        from glance.conflict import ConflictReporter

        reporter = ConflictReporter()
        report = reporter.generate_report([], 0)

        assert "No merge conflicts" in report
        assert "✅" in report

    def test_generate_summary(self):
        from glance.conflict import ConflictAnalysis, ConflictReporter, RiskLevel

        reporter = ConflictReporter()
        analyses = [
            ConflictAnalysis(
                conflict_id=1,
                file_path="auth.py",
                start_line=10,
                our_version="x = 1",
                their_version="x = 2",
                risk_level=RiskLevel.CRITICAL,
                suggested_choice="our",
                reasoning="Minor change",
            ),
            ConflictAnalysis(
                conflict_id=2,
                file_path="main.py",
                start_line=20,
                our_version="y = 1",
                their_version="y = 1",
                risk_level=RiskLevel.LOW,
                suggested_choice="both",
                reasoning="Same content",
            ),
        ]

        summary = reporter.generate_summary(analyses)
        assert "2 merge conflicts" in summary
        assert "1" in summary
        assert "1" in summary
