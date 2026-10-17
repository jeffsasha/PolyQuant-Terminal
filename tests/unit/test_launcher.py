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

def test_ready_cannot_accept_health_from_a_different_listener(tmp_path,monkeypatch):
    import pytest
    monkeypatch.setattr(launcher,'DATA',tmp_path);(tmp_path/'backend.pid').write_text('123')
    monkeypatch.setattr(launcher,'owned_process',lambda pid,name:True)
    monkeypatch.setattr(launcher,'listener_pids',lambda name:[999],raising=False)
    monkeypatch.setattr(launcher.time,'sleep',lambda value:None)
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(launcher.urllib.request,'urlopen',lambda *args,**kwargs:Response())
    with pytest.raises(RuntimeError):launcher.ready('backend')


def test_stop_recovers_only_the_verified_workspace_listener(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'DATA',tmp_path);(tmp_path/'backend.pid').write_text('123')
    alive=[True];stopped=[]
    monkeypatch.setattr(launcher,'owned_process',lambda pid,name:pid==77 and alive[0])
    monkeypatch.setattr(launcher,'listener_pids',lambda name:[77],raising=False)
    def kill(pid,signal):stopped.append(pid);alive[0]=False
    monkeypatch.setattr(launcher.os,'kill',kill)
    launcher.stop_process('backend')
    assert stopped==[77]
    assert not (tmp_path/'backend.pid').exists()


def test_stop_recovers_owned_listener_when_pid_file_is_missing(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'DATA',tmp_path)
    alive=[True];stopped=[]
    monkeypatch.setattr(launcher,'owned_process',lambda pid,name:pid==77 and alive[0])
    monkeypatch.setattr(launcher,'listener_pids',lambda name:[77])
    def kill(pid,signal):stopped.append(pid);alive[0]=False
    monkeypatch.setattr(launcher.os,'kill',kill)
    launcher.stop_process('backend')
    assert stopped==[77]
