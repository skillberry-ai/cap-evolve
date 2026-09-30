"""Test PROCESS.md table fallback parsing."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def test_parse_process_md_tables_with_markdown_formatting():
    """Parser should strip markdown formatting from table cells."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | **A** | `t1`, t2 | **Bold root cause** with *italic* | CONTRACT | fix |
| 2 | B | t3 | Normal text | KNOWLEDGE | update |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|------------|-------------|------------|-------------------|
| **A** | CONTRACT | `prompt.md` | Fix **bold** issue | yes |
| B | KNOWLEDGE | task_template.md | Update *italic* text | no |
"""
    
    result = _parse_process_md_tables(process_text, val_task_ids={'t1', 't2', 't3'})
    
    assert result is not None
    assert len(result['clusters']) == 2
    assert len(result['edits']) == 2
    
    # Check markdown was stripped from cluster IDs and names
    # Cluster ID is now the rank (1, 2), not the cluster name
    assert result['clusters'][0]['id'] == '1'
    # Name comes from "cluster" column, detail from "shared root cause" column
    assert result['clusters'][0]['name'] == 'A'
    assert 'Bold root cause' in result['clusters'][0]['detail']
    assert '**' not in result['clusters'][0]['detail']
    assert '*' not in result['clusters'][0]['detail']
    
    # Check markdown was stripped from edit titles
    assert 'bold' in result['edits'][0]['title'].lower()
    assert '**' not in result['edits'][0]['title']


def test_extract_task_ids_validates_against_val_split():
    """Parser should only extract task IDs that exist in val split."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | A | t1, t2, invalid_task, t99 | Root cause | CONTRACT | fix |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|------------|-------------|------------|-------------------|
| A | CONTRACT | prompt.md | Fix issue | yes |
"""
    
    val_task_ids = {'t1', 't2', 't3'}
    result = _parse_process_md_tables(process_text, val_task_ids=val_task_ids)
    
    assert result is not None
    assert len(result['clusters']) == 1
    
    # Should only include t1 and t2, not invalid_task or t99
    assert set(result['clusters'][0]['tasks']) == {'t1', 't2'}


def test_parse_process_md_tables_with_parentheses_and_delimiters():
    """Parser should handle task IDs with various delimiters."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | A | (t1 + t2) | Root cause | CONTRACT | fix |
| 2 | B | t3, t4 and t5 | Another cause | KNOWLEDGE | update |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|------------|-------------|------------|-------------------|
| A | CONTRACT | prompt.md | Fix issue | yes |
"""
    
    val_task_ids = {'t1', 't2', 't3', 't4', 't5'}
    result = _parse_process_md_tables(process_text, val_task_ids=val_task_ids)
    
    assert result is not None
    assert len(result['clusters']) == 2
    
    # Check cluster 1 (rank 1) has t1 and t2
    cluster_1 = next(c for c in result['clusters'] if c['id'] == '1')
    assert set(cluster_1['tasks']) == {'t1', 't2'}
    
    # Check cluster 2 (rank 2) has t3, t4, t5
    cluster_2 = next(c for c in result['clusters'] if c['id'] == '2')
    assert set(cluster_2['tasks']) == {'t3', 't4', 't5'}


def test_parse_process_md_tables_returns_none_when_no_tables():
    """Parser should return None when tables are missing."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
# Some other content

This is just prose, no tables.
"""
    
    result = _parse_process_md_tables(process_text)
    assert result is None


def test_parse_process_md_tables_handles_empty_cells():
    """Parser should handle empty or missing cells gracefully."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | A | | Empty tasks | CONTRACT | fix |
| 2 | | t1 | No cluster ID | KNOWLEDGE | update |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|------------|-------------|------------|-------------------|
| A | CONTRACT | | No files | yes |
"""
    
    result = _parse_process_md_tables(process_text, val_task_ids={'t1'})
    
    assert result is not None
    # Should still parse what's available
    assert len(result['clusters']) >= 1
    assert len(result['edits']) >= 1


def test_edit_refs_resolve_to_cluster_ids():
    """Edit cluster refs should resolve to cluster IDs (rank, not name)."""
    from cap_evolve.harness import _parse_process_md_tables
    
    process_text = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | formula written instead of a value | t1, t2 | Root cause A | CONTRACT | fix |
| 2 | INPUT formula erased | t3 | Root cause B | KNOWLEDGE | update |
| 3 | Another cluster | t4 | Root cause C | CONTRACT | fix |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|------------|-------------|------------|-------------------|
| 1 | CONTRACT | prompt.md | Fix issue A | yes |
| 2 | KNOWLEDGE | task_template.md | Fix issue B | no |
| 1, 3 | CONTRACT | prompt.md | Fix issues A and C | yes |
"""
    
    val_task_ids = {'t1', 't2', 't3', 't4'}
    result = _parse_process_md_tables(process_text, val_task_ids=val_task_ids)
    
    assert result is not None
    assert len(result['clusters']) == 3
    assert len(result['edits']) == 3
    
    # Clusters should have rank as ID
    cluster_ids = {c['id'] for c in result['clusters']}
    assert cluster_ids == {'1', '2', '3'}
    
    # Cluster names should come from the "cluster" column, not "shared root cause"
    cluster_1 = next(c for c in result['clusters'] if c['id'] == '1')
    assert cluster_1['name'] == 'formula written instead of a value'
    assert cluster_1['detail'] == 'Root cause A'
    
    cluster_2 = next(c for c in result['clusters'] if c['id'] == '2')
    assert cluster_2['name'] == 'INPUT formula erased'
    assert cluster_2['detail'] == 'Root cause B'
    
    # Every edit ref should resolve to a cluster ID
    for edit in result['edits']:
        for cluster_ref in edit['clusters']:
            assert cluster_ref in cluster_ids, f"Edit {edit['id']} references unknown cluster {cluster_ref}"
    
    # Check specific edit refs
    assert result['edits'][0]['clusters'] == ['1']
    assert result['edits'][1]['clusters'] == ['2']
    assert set(result['edits'][2]['clusters']) == {'1', '3'}
