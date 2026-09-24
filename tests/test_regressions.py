from __future__ import annotations
import contextlib
import io
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workflow import workflow as w, prepare, record_image
import project_io
import storyboard_layout
from PIL import Image


def approve_worker(root, sid, event):
    event.wait(10)
    w.approve(Path(root), sid, 'storyboard_prompt', 'Approved by user')


def crash_worker(root):
    root = Path(root)
    writer = w.write_json
    def crash_before_summary(path, data):
        if path == root/'project.json':
            os._exit(7)
        writer(path, data)
    with patch.object(w, 'write_json', side_effect=crash_before_summary):
        w.approve(root, 'shot-01', 'storyboard_prompt', 'Approved')


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        w.init_project(self.root, 'test')

    def pending(self):
        prepare(self.root)
        w.set_status(self.root, 'shot-01', 'storyboard_prompt_pending', True)

    def generate(self):
        self.pending()
        w.approve(self.root, 'shot-01', 'storyboard_prompt', 'Approved')

    def review(self):
        self.generate()
        record_image(self.root)
        w.set_status(self.root, 'shot-01', 'storyboard_review_pending', True)

    def test_missing_prompt_cannot_be_approved(self):
        self.pending()
        (self.root/'shots/shot-01/storyboard-prompt.md').unlink()
        with self.assertRaisesRegex(ValueError, 'artifact'):
            w.approve(self.root, 'shot-01', 'storyboard_prompt', 'Approved')
        self.assertEqual(w.read_json(w.shot_json_path(self.root,'shot-01'))['status'], 'storyboard_prompt_pending')

    def test_blank_prompt_cannot_be_approved(self):
        self.pending()
        (self.root/'shots/shot-01/storyboard-prompt.md').write_text('  ', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Empty text'):
            w.approve(self.root, 'shot-01', 'storyboard_prompt', 'Approved')

    def test_modified_prompt_blocks_generation_and_validation(self):
        self.generate()
        (self.root/'shots/shot-01/storyboard-prompt.md').write_text('new product', encoding='utf-8')
        for fn in (lambda: w.preflight(self.root,'shot-01'), lambda: w.validate(self.root)):
            with self.assertRaisesRegex(ValueError, 'stale'):
                fn()
        w.revise(self.root,'shot-01','storyboard_prompt','User changed product')
        w.approve(self.root,'shot-01','storyboard_prompt','Approved revised version')
        w.preflight(self.root,'shot-01')

    def test_one_generation_per_authorization(self):
        self.generate()
        w.preflight(self.root,'shot-01')
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            w.preflight(self.root,'shot-01')

    def test_failed_attempt_without_image_does_not_reuse_reserved_version(self):
        self.generate()
        w.preflight(self.root,'shot-01')
        w.set_status(self.root,'shot-01','generation_failed',True)
        w.retry_shot(self.root,'shot-01','storyboard_generating','User requested retry')
        w.preflight(self.root,'shot-01')
        self.assertEqual(w.read_json(w.shot_json_path(self.root,'shot-01'))['storyboard_version'],2)

    def test_missing_image_cannot_enter_review(self):
        self.generate()
        w.preflight(self.root,'shot-01')
        with self.assertRaises(ValueError):
            w.set_status(self.root,'shot-01','storyboard_review_pending',True)

    def test_review_retry_requires_explicit_request_and_uses_new_version(self):
        self.review()
        with self.assertRaisesRegex(ValueError, 'Invalid staged transition'):
            w.set_status(self.root,'shot-01','storyboard_generating',True)
        with self.assertRaisesRegex(ValueError, 'explicit request'):
            w.retry_shot(self.root,'shot-01','storyboard_generating',None)
        w.retry_shot(self.root,'shot-01','storyboard_generating','User asked to redo')
        w.preflight(self.root,'shot-01')
        self.assertEqual(w.read_json(w.shot_json_path(self.root,'shot-01'))['storyboard_version'],2)
        self.assertTrue((self.root/'shots/shot-01/storyboard-review-v01.png').exists())

    def test_image_failure_cannot_jump_to_video(self):
        self.generate()
        w.set_status(self.root,'shot-01','generation_failed',True)
        with self.assertRaisesRegex(ValueError, 'Invalid staged retry'):
            w.retry_shot(self.root,'shot-01','video_prompt_pending','Retry image')
        w.retry_shot(self.root,'shot-01','storyboard_generating','Retry image')

    def test_storyboard_only_completes_and_freezes(self):
        self.review()
        w.approve(self.root,'shot-01','storyboard','Approved')
        self.assertEqual(w.read_json(w.shot_json_path(self.root,'shot-01'))['status'],'complete')
        self.assertTrue((self.root/'shots/shot-01/storyboard-final.png').exists())
        w.validate(self.root)

    def test_changed_image_invalidates_completion(self):
        self.review()
        w.approve(self.root,'shot-01','storyboard','Approved')
        Image.new('RGB',(90,160),'red').save(self.root/'shots/shot-01/storyboard-review-v01.png')
        with self.assertRaisesRegex(ValueError,'stale'):
            w.validate(self.root)

    def test_directly_forged_complete_fails_validation(self):
        path = w.shot_json_path(self.root,'shot-01')
        data = w.read_json(path)
        data['status'] = 'complete'
        w.write_json(path,data)
        with self.assertRaises(ValueError):
            w.sync_statuses(self.root)

    def test_single_storyboard_rejects_parallel_registration(self):
        for fn in (lambda: w.set_concurrency(self.root,'all'), lambda: w.register_task(self.root,'shot-01','thread',None)):
            with self.assertRaisesRegex(ValueError,'Single storyboard'):
                fn()

    def test_cli_defaults_to_one_storyboard_only(self):
        root=Path(self.temp.name)/'cli'
        subprocess.run([sys.executable,str(Path(w.__file__)),'init',str(root),'--name','demo'],check=True,capture_output=True)
        data=w.read_json(root/'project.json')
        self.assertEqual(len(data['shots']),1)
        self.assertEqual(data['delivery_scope'],'storyboard_only')
        self.assertEqual(data['workflow']['execution_model'],'current_conversation')

    def test_fast_switch_while_prompt_pending(self):
        self.pending()
        w.set_review_mode(self.root,'shot-01','fast','User explicitly requests fast mode')
        w.set_status(self.root,'shot-01','running',True)
        record_image(self.root)
        w.set_status(self.root,'shot-01','review_pending',True)
        w.approve(self.root,'shot-01','review_package','Approved')
        w.validate(self.root)

    def test_custom_times_allowed_and_invalid_times_rejected(self):
        settings=w.read_json(self.root/'project.json')['defaults']
        settings.update(duration_seconds=8,time_boundaries_seconds=[0,2,4,6,8],time_ranges=['0–2秒','2–4秒','4–6秒','6–8秒'])
        self.assertEqual(w.validate_boundaries(settings),[0,2,4,6,8])
        settings['time_boundaries_seconds']=[0,2,2,6,8]
        with self.assertRaises(ValueError):
            w.validate_boundaries(settings)

    def test_paths_cannot_escape(self):
        for sid in ('../../outside', 'C:/outside', 'a/b'):
            with self.assertRaises(ValueError):
                w.shot_json_path(self.root,sid)

    def test_approval_write_failure_restores_both_files_and_final(self):
        self.review()
        path=w.shot_json_path(self.root,'shot-01')
        original=path.read_bytes()
        writer=w.write_json
        def fail_project(path,data):
            if path==self.root/'project.json':
                raise OSError('simulated failure')
            writer(path,data)
        with patch.object(w,'write_json',side_effect=fail_project), self.assertRaises(OSError):
            w.approve(self.root,'shot-01','storyboard','Approved')
        self.assertEqual(path.read_bytes(),original)
        self.assertFalse((path.parent/'storyboard-final.png').exists())

    def test_migration_failure_restores_every_file_and_can_retry(self):
        root=Path(self.temp.name)/'legacy'
        w.init_project(root,'legacy',2,5)
        project=w.read_json(root/'project.json')
        project['schema_version']=3
        w.write_json(root/'project.json',project)
        saved={path:path.read_bytes() for path in [root/'project.json',w.shot_json_path(root,'shot-01'),w.shot_json_path(root,'shot-02')]}
        writer=w.write_json
        def fail_second(path,data):
            if path==w.shot_json_path(root,'shot-02'):
                raise OSError('disk failure')
            writer(path,data)
        with patch.object(w,'write_json',side_effect=fail_second), self.assertRaises(OSError):
            w.migrate(root)
        for path,value in saved.items():
            self.assertEqual(path.read_bytes(),value)
        self.assertFalse((root/'project.json.bak').exists())
        w.migrate(root)
        self.assertTrue((root/'shots/shot-01/shot.json.bak').exists())

    def test_parallel_process_approvals_keep_both_updates(self):
        root=Path(self.temp.name)/'parallel'
        w.init_project(root,'parallel',2)
        for sid in ('shot-01','shot-02'):
            prepare(root,sid)
            w.set_status(root,sid,'storyboard_prompt_pending',True)
        ctx=multiprocessing.get_context('spawn')
        event=ctx.Event()
        workers=[ctx.Process(target=approve_worker,args=(str(root),sid,event)) for sid in ('shot-01','shot-02')]
        for worker in workers:
            worker.start()
        event.set()
        for worker in workers:
            worker.join(20)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail('Worker hung')
            self.assertEqual(worker.exitcode,0)
        self.assertEqual([x['status'] for x in w.read_json(root/'project.json')['shots']],['storyboard_generating']*2)
        w.validate(root)

    def test_layout_refuses_overwrite_and_bad_dimensions(self):
        output=Path(self.temp.name)/'old.png'
        output.write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            storyboard_layout.compose([output]*4,['a']*4,output,1080,1920,8,None)
        self.assertEqual(output.read_bytes(),b'original')
        with self.assertRaises(ValueError):
            storyboard_layout.compose([output]*4,['a']*4,output.with_name('new.png'),10,0,8,None)

    def test_process_crash_is_recovered_on_next_command(self):
        self.pending()
        original=w.shot_json_path(self.root,'shot-01').read_bytes()
        worker=multiprocessing.get_context('spawn').Process(target=crash_worker,args=(str(self.root),))
        worker.start()
        worker.join(15)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            self.fail('Crash simulation hung')
        self.assertEqual(worker.exitcode,7)
        self.assertTrue((self.root/'.workflow-transaction.json').exists())
        w.validate(self.root)
        self.assertEqual(w.shot_json_path(self.root,'shot-01').read_bytes(),original)
        self.assertFalse((self.root/'.workflow-transaction.json').exists())

    def test_combined_scope_requires_video_and_fast_video_revision_reuses_image(self):
        project=w.read_json(self.root/'project.json')
        project['delivery_scope']='storyboard_and_video_prompt'
        w.write_json(self.root/'project.json',project)
        prepare(self.root)
        w.set_review_mode(self.root,'shot-01','fast','User requested fast mode')
        w.set_status(self.root,'shot-01','running',True)
        record_image(self.root)
        with self.assertRaisesRegex(ValueError,'artifact'):
            w.set_status(self.root,'shot-01','review_pending',True)
        video=self.root/'shots/shot-01/video-prompt.md'
        video.write_text('First draft',encoding='utf-8')
        w.set_status(self.root,'shot-01','review_pending',True)
        w.approve(self.root,'shot-01','review_package','Approved')
        w.revise(self.root,'shot-01','video_prompt','User requested new copy')
        video.write_text('Second draft',encoding='utf-8')
        w.approve(self.root,'shot-01','review_package','Approved revised package')
        w.validate(self.root)
        self.assertEqual(w.read_json(w.shot_json_path(self.root,'shot-01'))['storyboard_version'],1)

    def test_source_change_blocks_generation(self):
        self.generate()
        Image.new('RGB',(16,16),'green').save(self.root/'sources/image-01.png')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            w.preflight(self.root,'shot-01')

    def test_changed_video_invalidates_completion(self):
        project=w.read_json(self.root/'project.json')
        project['delivery_scope']='storyboard_and_video_prompt'
        w.write_json(self.root/'project.json',project)
        self.review()
        w.approve(self.root,'shot-01','storyboard','Approved')
        video=self.root/'shots/shot-01/video-prompt.md'
        video.write_text('Approved video',encoding='utf-8')
        w.set_status(self.root,'shot-01','video_prompt_review_pending',True)
        w.approve(self.root,'shot-01','video_prompt','Approved')
        video.write_text('Different video',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'stale'):
            w.validate(self.root)

    def test_split_and_layout_preserve_panel_order(self):
        folder=Path(self.temp.name)
        source=folder/'grid.png'
        image=Image.new('RGB',(360,640))
        colors=['red','green','blue','yellow']
        for color,xy in zip(colors,[(0,0),(180,0),(0,320),(180,320)]):
            image.paste(Image.new('RGB',(180,320),color),xy)
        image.save(source)
        paths=storyboard_layout.split_grid(source,folder/'panels',1)
        output=folder/'review.png'
        storyboard_layout.compose(paths,['0–1秒 外观','1–2秒 结构','2–3秒 使用','3–4秒 定格'],output,1080,1920,8,None)
        with Image.open(output) as rendered:
            self.assertEqual(rendered.size,(1080,1920))
            for xy,color in zip([(100,100),(650,100),(100,1100),(650,1100)],[(255,0,0),(0,128,0),(0,0,255),(255,255,0)]):
                self.assertEqual(rendered.getpixel(xy),color)
        with self.assertRaises(FileExistsError):
            storyboard_layout.split_grid(source,folder/'panels',1)

    def test_legacy_mutation_requires_migration(self):
        project=w.read_json(self.root/'project.json')
        project['schema_version']=3
        w.write_json(self.root/'project.json',project)
        with self.assertRaisesRegex(ValueError,'migrate'):
            w.set_status(self.root,'shot-01','complete',True)


if __name__=='__main__':
    unittest.main()
