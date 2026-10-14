# Vendored ACE files

Copied **unmodified** from [`ace-agent/ace-appworld`](https://github.com/ace-agent/ace-appworld) at
commit `928e86877d34cd10eaba159606386f93a1765090` (Apache-2.0, see `LICENSE`), per
`docs/EVAL_SMOKE_TEST_ACE.md` section 8.1. Only `__init__.py` is ours (it makes the directory a
package so that `playbook.py`'s relative import of `utils` works). The logic of `reflector_call`
and `curator_call` from `experiments/code/ace/adaptation_react.py` is ported in `../run_ace.py`
(that module imports ACE's AppWorld fork, so it cannot be imported here).

| file here | source path in ace-appworld | sha256 |
|---|---|---|
| `prompts/appworld_react_reflector_no_gt_prompt.txt` | `experiments/prompts/appworld_react_reflector_no_gt_prompt.txt` | `7769bda89a9dd08044ee92823cde1d494bd8f06a562446f5ee6ff3821307c3c6` |
| `prompts/appworld_react_curator_prompt.txt` | `experiments/prompts/appworld_react_curator_prompt.txt` | `27b7d9dd2dcfe85646bf19ea7be387760874b70c0f9f27b1bed38d8f3e11e2bc` |
| `playbooks/appworld_initial_playbook.txt` | `experiments/playbooks/appworld_initial_playbook.txt` | `3c4f46888c9159088c3eb8f70e879d4d28a5704ab9f15d132563ba0ee2730b7b` |
| `playbook.py` | `experiments/code/ace/playbook.py` | `84a9a7b999680b061cf37ed1bf32d2188d79684337ff44f71c5ba7c00e36d2a7` |
| `utils.py` | `experiments/code/ace/utils.py` | `99f9edb2bdf9acc043d716fda6788e45ff57e10c90b167bb7548f61796de8ac5` |
| `bulletpoint_analyzer.py` | `experiments/code/ace/bulletpoint_analyzer.py` | `77e411e5fafeff838966619159bae3dd7060fed4f247f9d60fa6909bf35b0015` |
| `LICENSE` | `LICENSE` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
