"""Test PROCESS.md table parsing fallback."""

import pytest
from cap_evolve.harness import _parse_process_md_tables


def test_parse_ranked_issue_list():
    """Test parsing the Ranked issue list table."""
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | **A** | task1, task2 | Formula handling issue | CONTRACT | Fix caching |
| 2 | B | task3 | Sort order problem | KNOWLEDGE | Update logic |
"""
    
    result = _parse_process_md_tables(process_text, {"task1", "task2", "task3"})
    
    assert result is not None
    assert len(result["clusters"]) == 2
    
    # Check first cluster (markdown stripped, ID is rank)
    cluster_a = result["clusters"][0]
    assert cluster_a["id"] == "1"
    assert cluster_a["tasks"] == ["task1", "task2"]
    assert "Formula handling" in cluster_a["detail"]
    assert cluster_a["tag"] == "CONTRACT"
    
    # Check second cluster
    cluster_b = result["clusters"][1]
    assert cluster_b["id"] == "2"
    assert cluster_b["tasks"] == ["task3"]


def test_parse_changes_made_table():
    """Test parsing the Changes made this iteration table."""
    process_text = """
## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|-----------|-------------|------------|-------------------|
| A | CONTRACT | `prompt.md` | Carry cached values forward | yes |
| B | KNOWLEDGE | prompt.md, task_template.md | Remove tie-breaker | partial |
"""
    
    result = _parse_process_md_tables(process_text)
    
    assert result is not None
    assert len(result["edits"]) == 2
    
    # Check first edit (markdown stripped from file name)
    edit1 = result["edits"][0]
    assert edit1["id"] == "E1"
    assert "Carry cached values" in edit1["title"]
    assert edit1["files"] == ["prompt.md"]
    assert edit1["lever"] == "CONTRACT"
    assert edit1["clusters"] == ["A"]
    
    # Check second edit
    edit2 = result["edits"][1]
    assert edit2["id"] == "E2"
    assert edit2["files"] == ["prompt.md", "task_template.md"]


def test_parse_with_invalid_task_ids():
    """Test that invalid task IDs are filtered out when val_task_ids provided."""
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag |
|------|---------|-------|-------------------|-----|
| 1 | A | task1, (task99+) | Test issue | CONTRACT |
"""
    
    result = _parse_process_md_tables(process_text, {"task1", "task2"})
    
    assert result is not None
    cluster = result["clusters"][0]
    # Only task1 should be included, task99 is not in val split
    assert cluster["tasks"] == ["task1"]


def test_parse_with_markdown_formatting():
    """Test that markdown formatting is stripped from cells."""
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag |
|------|---------|-------|-------------------|-----|
| 1 | **bold_cluster** | `task1` | *italic text* with **bold** | `CODE` |
"""
    
    result = _parse_process_md_tables(process_text)
    
    assert result is not None
    cluster = result["clusters"][0]
    assert cluster["id"] == "1"  # ID is rank, not cluster name
    assert cluster["tasks"] == ["task1"]  # Backticks stripped
    assert "italic text" in cluster["detail"]  # Italic stripped
    assert "bold" in cluster["detail"]  # Bold stripped
    assert cluster["tag"] == "CODE"  # Backticks stripped


def test_parse_empty_tables():
    """Test that empty or missing tables return None."""
    # No tables at all
    result = _parse_process_md_tables("# Some other content\n\nNo tables here.")
    assert result is None
    
    # Empty string
    result = _parse_process_md_tables("")
    assert result is None
    
    # None input
    result = _parse_process_md_tables(None)
    assert result is None


def test_parse_real_cand_0001_format():
    """Test parsing a real PROCESS.md from cand_0001 format."""
    # This is based on the actual format mentioned in the issue
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | **formula written instead of a value** | 37378, 51-12 | Formula cells not evaluated | CONTRACT | Fix evaluation |
| 2 | comparison operators | 53647 | Incorrect comparison | KNOWLEDGE | Update logic |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|-----------|-------------|------------|-------------------|
| **formula written instead of a value** | CONTRACT | prompt.md | Evaluate formulas before writing | yes |
| comparison operators | KNOWLEDGE | prompt.md | Fix < vs <= | partial |
"""
    
    result = _parse_process_md_tables(process_text, {"37378", "51-12", "53647"})
    
    assert result is not None
    assert len(result["clusters"]) == 2
    assert len(result["edits"]) == 2
    
    # Check that ID is rank, not cluster name
    cluster1 = result["clusters"][0]
    assert cluster1["id"] == "1"
    assert set(cluster1["tasks"]) == {"37378", "51-12"}
    
    # Check edit references the cluster
    edit1 = result["edits"][0]
    assert edit1["clusters"] == ["formula written instead of a value"]


def test_parse_with_parentheses_in_tasks():
    """Test parsing task IDs with parentheses like (37378+)."""
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag |
|------|---------|-------|-------------------|-----|
| 1 | A | (37378+) and task2 | Test | CONTRACT |
"""
    
    result = _parse_process_md_tables(process_text, {"37378", "task2"})
    
    assert result is not None
    cluster = result["clusters"][0]
    # Should extract both task IDs, ignoring parentheses and +
    assert "37378" in cluster["tasks"]
    assert "task2" in cluster["tasks"]


def test_source_marker():
    """Test that parsed result includes source marker."""
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag |
|------|---------|-------|-------------------|-----|
| 1 | A | task1 | Test | CONTRACT |
"""
    
    result = _parse_process_md_tables(process_text)
    
    assert result is not None
    assert result["_source"] == "process_md_fallback"
    assert result["headline"] == "Parsed from PROCESS.md tables"
