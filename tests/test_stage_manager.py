"""Unit tests for the stage manager."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase2_whatsapp.stage_manager import (
    Stage,
    advance,
    can_advance,
    get_missing_fields,
    get_next_stage,
    get_stage,
    has_all_required_fields,
)


class TestGetStage:
    def test_valid_stage(self):
        assert get_stage("WELCOME") == Stage.WELCOME
        assert get_stage("REQUIREMENTS") == Stage.REQUIREMENTS
        assert get_stage("PACKAGE") == Stage.PACKAGE

    def test_case_insensitive(self):
        assert get_stage("welcome") == Stage.WELCOME
        assert get_stage("Welcome") == Stage.WELCOME

    def test_invalid_defaults_to_welcome(self):
        assert get_stage("INVALID") == Stage.WELCOME
        assert get_stage("") == Stage.WELCOME


class TestTransitions:
    def test_welcome_to_requirements(self):
        assert can_advance(Stage.WELCOME, Stage.REQUIREMENTS)

    def test_requirements_to_package(self):
        assert can_advance(Stage.REQUIREMENTS, Stage.PACKAGE)

    def test_package_to_done(self):
        assert can_advance(Stage.PACKAGE, Stage.DONE)

    def test_not_interested_from_any(self):
        assert can_advance(Stage.WELCOME, Stage.NOT_INTERESTED)
        assert can_advance(Stage.REQUIREMENTS, Stage.NOT_INTERESTED)
        assert can_advance(Stage.PACKAGE, Stage.NOT_INTERESTED)

    def test_invalid_backward_transition(self):
        assert not can_advance(Stage.REQUIREMENTS, Stage.WELCOME)
        assert not can_advance(Stage.PACKAGE, Stage.REQUIREMENTS)

    def test_invalid_skip_transition(self):
        assert not can_advance(Stage.WELCOME, Stage.PACKAGE)
        assert not can_advance(Stage.WELCOME, Stage.DONE)

    def test_done_cannot_advance(self):
        assert not can_advance(Stage.DONE, Stage.WELCOME)

    def test_not_interested_cannot_advance(self):
        assert not can_advance(Stage.NOT_INTERESTED, Stage.WELCOME)


class TestAdvance:
    def test_valid_advance(self):
        result = advance(Stage.WELCOME, Stage.REQUIREMENTS)
        assert result == Stage.REQUIREMENTS

    def test_invalid_advance_stays(self):
        result = advance(Stage.WELCOME, Stage.PACKAGE)
        assert result == Stage.WELCOME


class TestGetNextStage:
    def test_welcome_next(self):
        assert get_next_stage(Stage.WELCOME) == Stage.REQUIREMENTS

    def test_requirements_next(self):
        assert get_next_stage(Stage.REQUIREMENTS) == Stage.PACKAGE

    def test_package_next(self):
        assert get_next_stage(Stage.PACKAGE) == Stage.DONE

    def test_done_has_no_next(self):
        assert get_next_stage(Stage.DONE) is None


class TestRequiredFields:
    def test_has_all_fields(self):
        data = {
            "business_name": "Chai Wala",
            "services_description": "Tea and snacks",
            "pages_needed": "3",
        }
        assert has_all_required_fields(data)

    def test_missing_field(self):
        data = {"business_name": "Chai Wala"}
        assert not has_all_required_fields(data)

    def test_empty_field(self):
        data = {
            "business_name": "Chai Wala",
            "services_description": "",
            "pages_needed": "3",
        }
        assert not has_all_required_fields(data)

    def test_get_missing(self):
        data = {"business_name": "Chai Wala"}
        missing = get_missing_fields(data)
        assert "services_description" in missing
        assert "pages_needed" in missing
        assert "business_name" not in missing
