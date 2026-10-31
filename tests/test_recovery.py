import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import pytest

spec=importlib.util.spec_from_file_location('recovery_script',Path(__file__).parents[1]/'deploy/lighthouse/recovery_check.py')
recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)


def test_artifact_corruption_rejected(tmp_path):
    for name in ['database.dump','uploads.tar']:(tmp_path/name).write_bytes(b'example')
    manifest={'artifacts':{n:recovery.checksum(tmp_path/n) for n in ['database.dump','uploads.tar']}}
    recovery.verify_artifacts(tmp_path,manifest)
    (tmp_path/'database.dump').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError,match='checksum mismatch'):recovery.verify_artifacts(tmp_path,manifest)


def test_upload_archive_restores_bytes_and_rejects_tampering(tmp_path):
    archive=tmp_path/'uploads.tar';destination=tmp_path/'restored';destination.mkdir()
    body=b'Fictional recovery fixture'
    with tarfile.open(archive,'w') as tar:
        item=tarfile.TarInfo('quarantine/1/fixture.txt');item.size=len(body);tar.addfile(item,io.BytesIO(body))
    ref={'relative':'quarantine/1/fixture.txt','sha256':hashlib.sha256(body).hexdigest()}
    recovery.verify_files(archive,[ref],destination)
    assert (destination/ref['relative']).read_bytes()==body
    with pytest.raises(RuntimeError,match='do not match'):recovery.verify_files(archive,[{**ref,'sha256':'wrong'}],destination)
    with pytest.raises(RuntimeError,match='Unsafe document'):recovery.verify_files(archive,[{**ref,'relative':'../escape'}],destination)


def test_unsafe_archive_member_rejected(tmp_path):
    archive=tmp_path/'unsafe.tar';destination=tmp_path/'restored';destination.mkdir()
    with tarfile.open(archive,'w') as tar:tar.addfile(tarfile.TarInfo('../escape'))
    with pytest.raises(RuntimeError,match='Unsafe upload'):recovery.verify_files(archive,[],destination)
    assert not (tmp_path/'escape').exists()


def test_clone_probe_refuses_live_or_arbitrary_database():
    from mamatch.recovery_probe import verify_clone
    with pytest.raises(RuntimeError,match='non-scratch'):verify_clone('mamatch')


def test_deploy_orders_backup_rehearsal_before_migration_and_restart():
    script=(Path(__file__).parents[1]/'deploy/lighthouse/deploy.sh').read_text()
    assert script.index('recovery_check.py')<script.index('mamatch.migrations upgrade')<script.index('up -d --no-build')
    assert 'docker image prune' not in script


def test_snapshot_file_export_checks_hash_and_path(tmp_path):
    from mamatch.recovery_files import export_referenced
    root=tmp_path/'source';root.mkdir();path=root/'fixture.txt';body=b'Private fictional fixture';path.write_bytes(body)
    ref={'path':str(path),'sha256':hashlib.sha256(body).hexdigest()}
    output=io.BytesIO();export_referenced([ref],root,output)
    with tarfile.open(fileobj=io.BytesIO(output.getvalue())) as archive:
        assert archive.extractfile('fixture.txt').read()==body
    with pytest.raises(RuntimeError,match='integrity'):export_referenced([{**ref,'sha256':'bad'}],root,io.BytesIO())
    with pytest.raises(RuntimeError,match='Invalid document'):export_referenced([ref],root/'other',io.BytesIO())
