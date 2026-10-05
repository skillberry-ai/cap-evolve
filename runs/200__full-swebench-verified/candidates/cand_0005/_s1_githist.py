import subprocess, sys

def show(rev, path):
    r = subprocess.run(['git', 'show', f'{rev}:{path}'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f'<missing {rev} {path}>'

seed_skill = show('8617c6b', 'candidates/seed/SKILL.md')
c2_skill = show('b30cf23', 'candidates/cand_0002/SKILL.md')
c4_skill = show('0aec155', 'candidates/cand_0004/SKILL.md')
c3_skill = show('01730dd', 'candidates/cand_0003/SKILL.md')

print("=== seed SKILL.md ===")
print(seed_skill[:200])
print("=== cand_0002 SKILL.md same as seed? ===", seed_skill == c2_skill)
print("=== cand_0003 SKILL.md same as seed? ===", seed_skill == c3_skill)
print("=== cand_0004 SKILL.md same as seed? ===", seed_skill == c4_skill)

# prompt.md
seed_p = show('8617c6b', 'candidates/seed/prompt.md')
c2_p = show('b30cf23', 'candidates/cand_0002/prompt.md')
c3_p = show('01730dd', 'candidates/cand_0003/prompt.md')
c4_p = show('0aec155', 'candidates/cand_0004/prompt.md')
print("=== cand_0002 prompt same as seed? ===", seed_p == c2_p)
print("=== cand_0003 prompt same as seed? ===", seed_p == c3_p)
print("=== cand_0004 prompt same as seed? ===", seed_p == c4_p)

# find diffs
import difflib
if seed_p != c2_p:
    print('--- prompt seed -> cand2 diff ---')
    for l in difflib.unified_diff(seed_p.splitlines(), c2_p.splitlines(), lineterm=''):
        print(l)
