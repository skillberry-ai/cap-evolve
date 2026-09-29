"""Tests for DIAGNOSIS.json validation in harness."""

import json
import tempfile
from pathlib import Path

import pytest

from cap_evolve import harness


def test_validate_diagnosis_json_missing_file():
    """When DIAGNOSIS.json doesn't exist, return None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        result = harness._validate_diagnosis_json(cand_dir)
        assert result is None


def test_validate_diagnosis_json_invalid_json():
    """Invalid JSON produces warnings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        diag_path.write_text("not valid json{", encoding="utf-8")
        
        result = harness._validate_diagnosis_json(cand_dir)
        assert result is not None
        assert "warnings" in result
        assert len(result["warnings"]) > 0
        assert "not valid JSON" in result["warnings"][0]


def test_validate_diagnosis_json_valid_minimal():
    """Valid minimal DIAGNOSIS.json passes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        diag = {
            "candidate": "cand_0001",
            "headline": "Test iteration",
            "clusters": [],
            "edits": [],
            "skipped": [],
            "techniques": []
        }
        diag_path.write_text(json.dumps(diag), encoding="utf-8")
        
        result = harness._validate_diagnosis_json(cand_dir)
        assert result is not None
        assert "warnings" in result
        assert len(result["warnings"]) == 0
        assert "diagnosis" in result
        assert result["diagnosis"]["candidate"] == "cand_0001"


def test_validate_diagnosis_json_unknown_task_id():
    """Task ID not in val split produces warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        diag = {
            "candidate": "cand_0001",
            "clusters": [
                {
                    "id": "A",
                    "name": "Test cluster",
                    "tasks": ["task1", "task2", "unknown_task"]
                }
            ],
            "edits": []
        }
        diag_path.write_text(json.dumps(diag), encoding="utf-8")
        
        val_tasks = ["task1", "task2"]
        result = harness._validate_diagnosis_json(cand_dir, val_tasks=val_tasks)
        assert result is not None
        assert len(result["warnings"]) > 0
        assert any("unknown_task" in w and "not in val split" in w 
                  for w in result["warnings"])


def test_validate_diagnosis_json_unknown_cluster_reference():
    """Edit referencing non-existent cluster produces warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        diag = {
            "candidate": "cand_0001",
            "clusters": [{"id": "A", "name": "Cluster A"}],
            "edits": [
                {
                    "id": "E1",
                    "title": "Fix something",
                    "clusters": ["A", "B"]  # B doesn't exist
                }
            ]
        }
        diag_path.write_text(json.dumps(diag), encoding="utf-8")
        
        result = harness._validate_diagnosis_json(cand_dir)
        assert result is not None
        assert len(result["warnings"]) > 0
        assert any("unknown cluster 'B'" in w for w in result["warnings"])


def test_validate_diagnosis_json_missing_file_reference():
    """Edit referencing non-existent file produces warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        diag = {
            "candidate": "cand_0001",
            "clusters": [],
            "edits": [
                {
                    "id": "E1",
                    "title": "Edit prompt",
                    "files": ["prompt.md", "missing.txt"]
                }
            ]
        }
        diag_path.write_text(json.dumps(diag), encoding="utf-8")
        
        # Create prompt.md but not missing.txt
        (cand_dir / "prompt.md").write_text("test", encoding="utf-8")
        
        result = harness._validate_diagnosis_json(cand_dir)
        assert result is not None
        assert len(result["warnings"]) > 0
        assert any("non-existent file 'missing.txt'" in w 
                  for w in result["warnings"])


def test_validate_diagnosis_json_complete_valid():
    """Complete valid DIAGNOSIS.json with all fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cand_dir = Path(tmpdir)
        diag_path = cand_dir / "DIAGNOSIS.json"
        
        # Create referenced files
        (cand_dir / "prompt.md").write_text("test", encoding="utf-8")
        (cand_dir / "task_template.md").write_text("test", encoding="utf-8")
        
        diag = {
            "candidate": "cand_0001",
            "headline": "Fix input formula handling",
            "clusters": [
                {
                    "id": "A",
                    "name": "INPUT formula erased",
                    "detail": "wb.save() erases cached values",
                    "tasks": ["task1", "task2"],
                    "scope": "BOUNDED",
                    "latent": False,
                    "tag": "CONTRACT"
                }
            ],
            "edits": [
                {
                    "id": "E1",
                    "title": "Carry cached values forward",
                    "files": ["prompt.md"],
                    "lever": "CONTRACT",
                    "clusters": ["A"],
                    "blast_radius": "BOUNDED",
                    "verified": "tested on synthetic workbook"
                }
            ],
            "skipped": [
                {
                    "title": "General comparison fix",
                    "reason": "would break passing tasks"
                }
            ],
            "techniques": ["replayed rollouts", "synthetic test"]
        }
        diag_path.write_text(json.dumps(diag), encoding="utf-8")
        
        val_tasks = ["task1", "task2", "task3"]
        result = harness._validate_diagnosis_json(cand_dir, val_tasks=val_tasks)
        assert result is not None
        assert len(result["warnings"]) == 0
        assert result["diagnosis"]["candidate"] == "cand_0001"
        assert len(result["diagnosis"]["clusters"]) == 1
        assert len(result["diagnosis"]["edits"]) == 1


def test_parse_process_md_tables_empty():
    """Empty or missing PROCESS.md returns None."""
    result = harness._parse_process_md_tables("")
    assert result is None
    
    result = harness._parse_process_md_tables(None)
    assert result is None


def test_parse_process_md_tables_with_ranked_list():
    """Parse ranked issue list table from PROCESS.md."""
    process_text = """
# PROCESS

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A | task1, task2 | Formula caching issue | KNOWLEDGE | Contract fix |
| 2 | B | task3 | Wrong comparison | BEHAVIORAL | Logic update |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
"""
    
    result = harness._parse_process_md_tables(process_text)
    assert result is not None
    assert len(result["clusters"]) == 2
    assert result["clusters"][0]["id"] == "A"
    assert "task1" in result["clusters"][0]["tasks"]
    assert "task2" in result["clusters"][0]["tasks"]
    assert result["clusters"][1]["id"] == "B"


def test_parse_process_md_tables_with_changes():
    """Parse changes table from PROCESS.md."""
    process_text = """
# PROCESS

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | CONTRACT | prompt.md | Carry cached values forward | Yes |
| B | BEHAVIORAL | task_template.md | Fix comparison logic | Partial |
"""
    
    result = harness._parse_process_md_tables(process_text)
    assert result is not None
    assert len(result["edits"]) == 2
    assert result["edits"][0]["lever"] == "CONTRACT"
    assert "prompt.md" in result["edits"][0]["files"]
    assert result["edits"][0]["clusters"] == ["A"]
    assert result["edits"][1]["clusters"] == ["B"]


def test_parse_process_md_tables_no_tables():
    """PROCESS.md without tables returns None."""
    process_text = """
# PROCESS

This iteration I fixed some things.

No tables here.
"""
    
    result = harness._parse_process_md_tables(process_text)
    assert result is None
