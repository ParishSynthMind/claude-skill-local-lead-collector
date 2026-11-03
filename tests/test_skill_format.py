"""Checks SKILL.md against Anthropic's published Skill rules (verified 2026-11-03)."""
import re

from conftest import SKILL

PORTABLE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def frontmatter():
    text = (SKILL / "SKILL.md").read_text()
    assert text.startswith("---\n"), "frontmatter must start on the first line"
    head, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in head.splitlines():
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields, body


def test_required_fields_and_only_portable_ones():
    fields, _ = frontmatter()
    assert {"name", "description"} <= set(fields)
    assert set(fields) <= PORTABLE_FIELDS


def test_name_rules():
    name = frontmatter()[0]["name"]
    assert len(name) <= 64
    assert re.fullmatch(r"[a-z0-9-]+", name)
    assert "claude" not in name and "anthropic" not in name
    assert SKILL.name == name, "folder name must match the skill name for a claude.ai zip upload"


def test_description_rules():
    desc = frontmatter()[0]["description"]
    assert 0 < len(desc) <= 1024
    assert "<" not in desc and ">" not in desc
    assert "Use when" in desc, "description must say when to use it"


def test_body_short_and_links_exist():
    _, body = frontmatter()
    assert len(body.splitlines()) < 500
    for link in re.findall(r"\]\(([^)]+)\)", body):
        assert (SKILL / link).exists(), link
    assert (SKILL / "scripts" / "collect_leads.py").exists()
