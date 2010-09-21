import httplib2, urllib2, urllib
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
import simplejson as json
from urllib2 import HTTPError
import re
from contextlib import contextmanager
import os

# Register the streaming http handlers with urllib2
register_openers()

BASE_URI                = 'http://api.canoris.com'

URI_FILES               = '/files'
URI_FILE                = '/files/<file_key>'
URI_FILE_SERVE          = '/files/<file_key>/serve'
URI_FILE_ANALYSIS       = '/files/<file_key>/analysis/<filter>'
URI_FILE_CONVERSIONS    = '/files/<file_key>/conversions'
URI_FILE_CONVERSION     = '/files/<file_key>/conversions/<conversion>'
URI_FILE_VISUALIZATIONS = '/files/<file_key>/visualizations'
URI_FILE_VISUALIZATION  = '/files/<file_key>/visualizations/<visualization>'
URI_COLLECTIONS         = '/collections'
URI_COLLECTION          = '/collections/<coll_key>'
URI_COLLECTION_FILES    = '/collections/<coll_key>/files'
URI_COLLECTION_FILE     = '/collections/<coll_key>/files/<file_key>'
URI_COLLECTION_SIMILAR  = '/collections/<coll_key>/similar/<file_key>/<preset>/<results>'
URI_TEMPLATES           = '/processing/templates'
URI_TEMPLATE            = '/processing/templates/<tpl_name>'
URI_TASKS               = '/processing/tasks'
URI_TASK                = '/processing/tasks/<task_id>'
URI_PHONEMES            = '/language/text2phonemes'


def _uri(uri, *args):
    for a in args:
        uri = re.sub('<[\w_]+>', str(a), uri, 1)
    return BASE_URI+uri


class Canoris():

    __api_key = False

    @classmethod
    def set_api_key(cls, key):
        cls.__api_key = key

    @classmethod
    def get_api_key(cls):
        if not cls.__api_key:
            raise Exception("Please set the API key! --> Canoris.set_api_key(<your_key>)")
        return cls.__api_key

    @staticmethod
    @contextmanager
    def with_key(key):
        class _tmp_cls():
            api_key = key
        Canoris = _tmp_cls
        yield


class Licenses(object):
    CC_Attribution                              = 'CC_Attribution'
    CC_AttributionShareAlike                    = 'CC_AttributionShareAlike'
    CC_AttributionNoDerivatives                 = 'CC_AttributionNoDerivatives'
    CC_AttributionNonCommercial                 = 'CC_AttributionNonCommercial'
    CC_AttributionNonCommercialShareAlike       = 'CC_AttributionNonCommercialShareAlike'
    CC_AttributionNonCommercialNoDerivatives    = 'CC_AttributionNonCommercialNoDerivatives'
    AllRightsReserved                           = 'AllRightsReserved'


class RequestWithMethod(urllib2.Request):
    '''
    Workaround for using DELETE with urllib2.

    N.B. Taken from http://www.abhinandh.com/posts/making-a-http-delete-request-with-urllib2/
    '''
    def __init__(self, url, method, data=None, headers={},\
                 origin_req_host=None, unverifiable=False):
        self._method = method
        urllib2.Request.__init__(self, url, data, headers,\
                                 origin_req_host, unverifiable)

    def get_method(self):
        if self._method:
            return self._method
        else:
            return urllib2.Request.get_method(self)


class CanorisObject(object):

    def __init__(self, attrs):
        # If we only set the ref field we will set _loaded to false.
        # This way we can 'lazily' load the resource later on.
        self._loaded = False \
                       if len(attrs.keys())==1 and 'ref' in attrs \
                       else True
        self.attributes = attrs

    def __getitem__(self, name):
        # if the property isn't present, it might be because we haven't
        # loaded all the data yet.
        if not name in self.attributes:
            self.__load()
        # try to get the property
        return self.attributes[name]

    def __setitem__(self, name, val):
        raise NotImplementedError

    def __delitem__(self, name, val):
        raise NotImplementedError

    def keys(self):
        return self.attributes.keys()

    def __load(self):
        self.attributes = json.loads(CanReq.simple_get(self['ref']))

    def get(self, name, default):
        return self.attributes.get(name, default)

    def update(self):
        self.__load()
        return self.attributes


class CanReq(object):

    @classmethod
    def simple_get(cls, uri, params=False):
        return cls._simple_req(uri, 'GET', params)

    @classmethod
    def simple_del(cls, uri, params=False):
        return cls._simple_req(uri, 'DELETE', params)

    @classmethod
    def simple_post(cls, uri, params=False):
        return cls._simple_req(uri, 'POST', False, params)

    @classmethod
    def _simple_req(cls, uri, method, params, data=False):
        p = params if params else {}
        p['api_key'] = Canoris.get_api_key()
        u = '%s?%s' % (uri, urllib.urlencode(p))
        d = urllib.urlencode(data) if data else None
        req = RequestWithMethod(u, method, d)
        try:
            try:
                f = urllib2.urlopen(req)
            except HTTPError, e:
                if e.code >= 200 and e.code < 300:
                    resp = e.read()
                    return resp
                else:
                    raise e
            resp = f.read()
            f.close()
            return resp
        except HTTPError, e:
            print '--- request failed ---'
            print 'code:\t%s' % e.code
            print 'resp:\n%s' % e.read()
            raise e


class File(CanorisObject):

    @staticmethod
    def get_file(key):
        return File.get_file_from_ref(_uri(URI_FILE, key))

    @staticmethod
    def get_file_from_ref(ref):
        return File(json.loads(CanReq.simple_get(ref)))

    @staticmethod
    def create_file(path, name=None, temporary=None):
        args = {"file": open(path, "rb")}
        if name != None:
            args['name'] = str(name)
        if temporary != None:
            args['temporary'] = 1 if temporary else 0
        args['api_key'] = Canoris.get_api_key()
        datagen, headers = multipart_encode(args)
        request = urllib2.Request(_uri(URI_FILES), datagen, headers)
        resp = urllib2.urlopen(request).read()
        return File(json.loads(resp))

    def delete(self):
        return CanReq.simple_del(self['ref'])

    def get_analysis(self, *filter):
        return json.loads(CanReq.simple_get(_uri(URI_FILE_ANALYSIS, self['key'],
                                               '/'.join(filter))))

    def retrieve(self):
        return CanReq.simple_get(self['serve'])

    def get_conversions(self):
        return json.loads(CanReq.simple_get(self['conversions']))

    def get_conversion(self, conv_key):
        return CanReq.simple_get(_uri(URI_FILE_CONVERSION, self['key'],
                                      conv_key))

    def get_visualizations(self):
        return json.loads(CanReq.simple_get(self['visualizations']))

    def get_visualization(self, vis_key):
        return CanReq.simple_get(_uri(URI_FILE_VISUALIZATION,
                                      self['key'], vis_key))

    def __repr__(self):
        return '<File: key="%s", name="%s">' % \
                (self['key'], self.get('name', 'n.a.'))


class Collection(CanorisObject):

    @staticmethod
    def get_collection(key):
        return Collection(json.loads(CanReq.simple_get(_uri(URI_COLLECTION,
                                                            key))))

    @staticmethod
    def create_collection(name, public, license):
        params = {'name': name, 'public': public, 'license': license}
        resp = CanReq.simple_post(_uri(URI_COLLECTIONS), params)
        return json.loads(resp)

    def delete(self):
        return CanReq.simple_del(self['ref'])

    def add_file(self, file):
        '''
        ``file`` can be either a File object or a key.
        '''
        params = {'filekey': file['key'] if isinstance(file, File) else file}
        return CanReq.simple_post(self['files'], params)

    def remove_file(self, file):
        uri = _uri(URI_COLLECTION_FILE, self['key'],
                   file['key'] if isinstance(file, File) else file)
        return CanReq.simple_del(uri)

    def files(self, page=0):
        return json.loads(CanReq.simple_get(self['files'], params={'page': page} ))

    def get_similar(self, query_file, preset, num_results):
        '''
        ``target_file`` can be a file key or a file object.
        '''
        fkey = query_file['key'] if isinstance(query_file, File) else query_file
        uri  = _uri(URI_COLLECTION_SIMILAR, self['key'],
                    fkey, preset, num_results)
        return [{'similarity': result['similarity'],
                 'file': File({'ref': result['ref']})} \
                 for result in json.loads(CanReq.simple_get(uri))]

    def __repr__(self):
        return '<File: key="%s", name="%s">' % (self['key'], self['name'])



class Template(CanorisObject):

    @staticmethod
    def get_template(name):
        return Template(json.loads(CanReq.simple_get(_uri(URI_TEMPLATE, name))))

    @staticmethod
    def create_template(name, steps):
        args = {'name': name,
                'template': json.dumps(steps)}
        return Template(json.loads(CanReq.simple_post(_uri(URI_TEMPLATES), args)))

    def delete(self):
        return CanReq.simple_del(self['ref'])


class Task(CanorisObject):

    @staticmethod
    def get_task(task_id):
        return Task(json.loads(CanReq.simple_get(_uri(URI_TASK, task_id))))

    @staticmethod
    def create_task(template, parameters):
        '''
        ``parameters`` is a dictionary of template variables to replace.
        '''
        return Task(json.loads(CanReq.simple_post(
                                    _uri(URI_TASKS),
                                    {'template': template,
                                     'parameters': json.dumps(parameters)})))

    def __repr__(self):
        return '<File: task_id="%s", completed="%s", successful="%s">' % \
                (self['task_id'], self['complete'], self['successful'])


class Text2Phonemes(object):

    @staticmethod
    def translate(text, voice=False, language=False):
        lang = language if language else 'spanish'
        args = {'language': lang,
                'text': text}
        if voice:
            args['voice'] = str(voice)
        return json.loads(CanReq.simple_get(_uri(URI_PHONEMES), args))




'''
Canoris.set_api_key('12d6dc5486554e278e370cdc49935905')
s = {"sequence": "<melody ticklength='0.01'><note duration='45' pitch='58' velocity='110' phonemes='m a s'/></melody>"}
t = Task.create_task('vocaloid', s)
print t
import time
time.sleep(3)
t.update()
print t
'''
