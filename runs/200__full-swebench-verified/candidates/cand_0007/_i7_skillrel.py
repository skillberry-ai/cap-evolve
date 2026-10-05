skill = open("SKILL.md").read()
prompt = open("prompt.md").read()
print("SKILL.md is prefix of prompt.md:", prompt.startswith(skill))
print("skill len:", len(skill), "prompt len:", len(prompt))
if prompt.startswith(skill):
    print("prompt extra tail:", repr(prompt[len(skill):][:400]))
else:
    # find common prefix
    i = 0
    while i < min(len(skill), len(prompt)) and skill[i] == prompt[i]:
        i += 1
    print("common prefix len:", i)
    print("skill diverges:", repr(skill[i:i+200]))
    print("prompt diverges:", repr(prompt[i:i+200]))
