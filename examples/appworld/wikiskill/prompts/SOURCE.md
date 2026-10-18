# Source of the WikiSkill prompts

`wiki_maintainer.paper.txt` and `skill_proposer.paper.txt` are the Wiki Maintainer and Skill Proposer system
prompts of the WikiSkill paper, Appendix E.2 and E.3 (Tang, Rashtchian, Ferng, Tomkins, Juan, Vu,
"WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution", arXiv:2608.27454v1,
CC BY 4.0), extracted from the arXiv HTML on 2026-10-17. Paragraph breaks are normalized; the text is
otherwise as published. The plan (§7.3) asks to restore them in place of the condensed prompts of the
kenhuangus/wikiskill reimplementation (vendor/prompts.py, kept unmodified for reference).

The driver adds, outside the paper's text: the AppWorld task description for `{task_desc}`, a "How to call the tools" section (one JSON tool call per reply — the paper names read_file and finish but not their call syntax, and the vendored ReAct parser expects JSON), a short
"## Budget and AppWorld rules" section (the 30,000-char / M_cap budget for all skills together and the
generic-guidance rule of the lints), and nothing else.
