import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('launcher',Path(__file__).resolve().parents[2]/'scripts/local.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

def test_next_process_title_still_has_verified_workspace_ownership(monkeypatch):
    def run(args,**kwargs):
        return SimpleNamespace(stdout='next-server (v16.4.2)\n' if args[0]=='ps' else 'p123\nn'+str(launcher.ROOT/'apps/web')+'\n')
    monkeypatch.setattr(launcher.subprocess,'run',run)
    assert launcher.owned_process(123,'web')
    def unrelated(args,**kwargs):
        return SimpleNamespace(stdout='next-server (v16.4.2)\n' if args[0]=='ps' else 'p123\nn/tmp/another-project\n')
    monkeypatch.setattr(launcher.subprocess,'run',unrelated)
    assert not launcher.owned_process(123,'web')
