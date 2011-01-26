from __future__ import with_statement
import unittest, os, time, sys
import simplejson as json
from canoris import Canoris, File, Collection, Licenses, Pager, Task, \
    Template, Text2Phonemes, CanorisException, PageException
from random import choice
from settings import *



class CanorisTests(unittest.TestCase):


    def setUp(self):
        Canoris.set_api_key(API_KEY)
        Canoris.set_base_uri(API_BASE)

    def tearDown(self):
        pass

    # File tests

    def test_upload_file(self):
        f = File.create_file(TEST_URL_AUDIO_FILE, temporary=True)

    def test_upload_url(self):
        f = File.create_file(TEST_URL_AUDIO_FILE, temporary=True)

    def test_upload_delete(self):
        f = File.create_file(TEST_LOCAL_AUDIO_FILE, os.path.basename(TEST_LOCAL_AUDIO_FILE), True)
        f.delete()

    def test_upload_retrieve_analysis_frames(self):
        f = File.create_file(TEST_LOCAL_AUDIO_FILE, os.path.basename(TEST_LOCAL_AUDIO_FILE), True)
        key = f['key']
        self.assertRaises(Exception, f.get_analysis)
        while True:
            try:
                f = File.get_file(key)
                f.get_analysis()
                break
            except CanorisException, e:
                # check whether the file is indeed still processing
                assert(e.code == 409)
                sys.stdout.write(',')
                sys.stdout.flush()
                time.sleep(1)

    def test_get_file(self):
        f1 = File.get_file(CERTAIN_FILE_KEY)
        f2 = File.get_file('http://api-test.canoris.com/files/' + CERTAIN_FILE_KEY)
        assert(f1['key'] == f2['key'])

    def test_retrieve_analysis_frames(self):
        f = File.get_file(CERTAIN_FILE_KEY)
        path, _ = f.retrieve_analysis_frames('/tmp/42976b41ec7c417ba0db174871eba7c1_frames.json')
        fp = open(path)
        json.load(fp)
        fp.close()

    def test_retrieve_visualization(self):
        f = File.get_file(CERTAIN_FILE_KEY)
        viss = f.get_visualizations()
        assert('spectrum' in viss)
        assert('waveform' in viss)
        path, _ = f.retrieve_visualization('spectrum', '/tmp/42976b41ec7c417ba0db174871eba7c1_spectrum.png')
        fp = open(path)
        fp.close()

    def test_retrieve_conversion(self):
        f = File.get_file(CERTAIN_FILE_KEY)
        path = '/tmp/%s.wav' % CERTAIN_FILE_KEY
        # This conversion doesn't consist for this file
        self.assertRaises(CanorisException, f.retrieve_conversion, 'wave_22050', path)
        # This conversion does exist
        f.retrieve_conversion('wave_44100', path)

    def test_retrieve_file_upload(self):
        f = File.create_file(TEST_LOCAL_AUDIO_FILE, temporary=True)
        path, _ = f.retrieve('/tmp/')
        fp = open(path)
        fp.close()
        f.delete()

    def test_retrieve_file_url(self):
        '''Cannot retrieve a file uploaded by url.'''
        f = File.create_file(TEST_URL_AUDIO_FILE, temporary=True)
        self.assertRaises(KeyError, f.retrieve, '/tmp/')
        f.delete()

    # Collection tests

    def test_create_delete_collection(self):
        c = Collection.create_collection('test_coll')
        assert(c['name'] == 'test_coll')
        c.delete()

    def test_create_small_collection(self):
        number = 30
        files = self.__filter_audio_files(TEST_AUDIO_DIR)
        presets = ['music', 'lowlevel', 'rhythm']
        can_files = []
        c = Collection.create_collection('test_coll')
        for _ in xrange(number):
            f = File.create_file(choice(files), temporary=False)
            c.add_file(f)
            can_files.append(f)
        successful_searches = 0
        while True:
            try:
                c.get_similar(choice(can_files), choice(presets), 20)
                successful_searches += 1
                sys.stdout.write('+')
                sys.stdout.flush()
                if successful_searches > 100:
                    break
            except CanorisException, e:
                # 409 when the collection isn't ready yet
                # 404 when the file wasn't yet analyzed
                if e.code == 409 or (e.code == 404 and e.type == "NotReadyYet"):
                    sys.stdout.write(',')
                    sys.stdout.flush()
                    time.sleep(1)
                else:
                    raise e

    def test_collection_pager(self):
        p = Pager.collection_page(CERTAIN_COLLECTION_KEY, 0)
        self.assertRaises(PageException, p.previous)
        if p['total'] <= 20:
            self.assertRaises(PageException, p.next)
        else:
            p.next()

    def test_files_pager(self):
        p = Pager.files_page(0)
        if p['total'] <= 20:
            self.assertRaises(PageException, p.next)
        else:
            p.next()

    def test_collections_pager(self):
        p = Pager.collections_page(0)
        self.assertRaises(PageException, p.previous)
        if p['total'] <= 20:
            self.assertRaises(PageException, p.next)
        else:
            p.next()

    @staticmethod
    def __filter_audio_files(directory):
        possible = ['.aiff', '.aif', '.wav', '.mp3']
        files = [os.path.join(directory, x) for x in os.listdir(directory) if os.path.splitext(x)[1] in possible]
        return files




if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
