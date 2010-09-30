import httplib2, urllib2, urllib, re, os
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
import simplejson as json
from urllib2 import HTTPError

# Register the streaming http handlers with urllib2
register_openers()

_URI_FILES               = '/files'
_URI_FILE                = '/files/<file_key>'
_URI_FILE_SERVE          = '/files/<file_key>/serve'
_URI_FILE_ANALYSIS       = '/files/<file_key>/analysis/<filter>'
_URI_FILE_CONVERSIONS    = '/files/<file_key>/conversions'
_URI_FILE_CONVERSION     = '/files/<file_key>/conversions/<conversion>'
_URI_FILE_VISUALIZATIONS = '/files/<file_key>/visualizations'
_URI_FILE_VISUALIZATION  = '/files/<file_key>/visualizations/<visualization>'
_URI_COLLECTIONS         = '/collections'
_URI_COLLECTION          = '/collections/<coll_key>'
_URI_COLLECTION_FILES    = '/collections/<coll_key>/files'
_URI_COLLECTION_FILE     = '/collections/<coll_key>/files/<file_key>'
_URI_COLLECTION_SIMILAR  = '/collections/<coll_key>/similar/<file_key>/<preset>/<results>'
_URI_TEMPLATES           = '/processing/templates'
_URI_TEMPLATE            = '/processing/templates/<tpl_name>'
_URI_TASKS               = '/processing/tasks'
_URI_TASK                = '/processing/tasks/<task_id>'
_URI_PHONEMES            = '/language/text2phonemes'


def _uri(uri, *args):
    for a in args:
        uri = re.sub('<[\w_]+>', str(a), uri, 1)
    return Canoris.get_base_uri()+uri


class Canoris():
    '''Use this class to set your API key before doing any requests.

    Set your API key at the start of your program. Afterwards, all requests
    done with the canoris library will be signed with that API key.

    For testing purposes you can also set the Canoris base URL. This is by
    default set to the right URL, so you shouldn't have to change this.
    '''

    __api_key = False
    __base_uri = 'http://api.canoris.com'

    @classmethod
    def set_api_key(cls, key):
        '''Set your API key for all other requests to use.'''
        cls.__api_key = key

    @classmethod
    def get_api_key(cls):
        if not cls.__api_key:
            raise Exception("Please set the API key! ==> Canoris.set_api_key('your_api_key')")
        return cls.__api_key

    @classmethod
    def get_base_uri(cls):
        return cls.__base_uri

    @classmethod
    def set_base_uri(cls, uri):
        '''Set the Canoris base URL.'''
        cls.__base_uri = uri

class Licenses(object):
    '''The Licenses class encodes all the available licenses that can be used
    with collections.'''

    CC_Attribution                              = 'CC_AT'
    CC_AttributionShareAlike                    = 'CC_AT_SA'
    CC_AttributionNoDerivatives                 = 'CC_AT_ND'
    CC_AttributionNonCommercial                 = 'CC_AT_NC'
    CC_AttributionNonCommercialShareAlike       = 'CC_AT_NC_SA'
    CC_AttributionNonCommercialNoDerivatives    = 'CC_AT_NC_ND'
    AllRightsReserved                           = 'ARR'


class RequestWithMethod(urllib2.Request):
    '''Workaround for using DELETE and PUT with urllib2.

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
    '''Base object for File, Collection, Template, Task, etc.

    This class most notably implements the __getitem__ method so that the
    properties of the sub classes can be retrieved dictionary style.
    '''

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
        self.attributes = json.loads(_CanReq.simple_get(self['ref']))

    def update(self):
        '''With an existing object, reload the data from the Canoris API.'''
        self.__load()
        return self.attributes


class _CanReq(object):
    '''This class wraps all the logic for doing HTTP requests.'''

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
        print Canoris.get_api_key()
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
            # TODO; this is ugly
            print '--- request failed ---'
            print 'code:\t%s' % e.code
            print 'resp:\n%s' % e.read()
            raise e


class File(CanorisObject):
    '''The File class is used to interact with and to upload Canoris files.'''

    @staticmethod
    def get_file(key):
        '''Retrieve a File object by specifying the file's key.

        Arguments:
        key -- the file's key

        Returns:
        A File object
        '''
        return File.get_file_from_ref(_uri(_URI_FILE, key))

    @staticmethod
    def create_file(path, name=None, temporary=None):
        '''Upload a sound file and create a File object.

        Arguments:
        path -- the path of the local sound file to upload

        Keyword arguments:
        name -- give the file a name
        temporary -- mark the new file as temporary

        Returns:
        A File object
        '''
        args = {"file": open(path, "rb")}
        if name != None:
            args['name'] = str(name)
        if temporary != None:
            args['temporary'] = 1 if temporary else 0
        args['api_key'] = Canoris.get_api_key()
        datagen, headers = multipart_encode(args)
        request = urllib2.Request(_uri(_URI_FILES), datagen, headers)
        resp = urllib2.urlopen(request).read()
        return File(json.loads(resp))

    def delete(self):
        '''Delete a File from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])

    def get_analysis(self, showall=False, *filter):
        '''Retrieve the File's analysis.

        Arguments:
        any argument -- retrieve a certain part of the analysis tree

        Keyword arguments:
        showall -- retrieve all available analysis data (default: False)

        Example:
        file1.get_analysis('highlevel', 'gender', 'value')

        Returns:
        Depending on the filter returns a dictionary, list, number, or string.
        '''
        return json.loads(_CanReq.simple_get(_uri(_URI_FILE_ANALYSIS, self['key'],
                                               '/'.join(filter)), params={'all': int(showall)} ))

    def retrieve(self):
        '''Retrieve the original file (binary data!)'''
        return _CanReq.simple_get(self['serve'])

    def get_conversions(self):
        '''Retrieve a dictionary showing the available conversions.'''
        return json.loads(_CanReq.simple_get(self['conversions']))

    def get_conversion(self, conv_key):
        '''Retrieve a specific conversion.

        Arguments:
        conv_key -- the key for the conversion to retrieve

        Returns:
        binary data
        '''
        return _CanReq.simple_get(_uri(_URI_FILE_CONVERSION, self['key'],
                                      conv_key))

    def get_visualizations(self):
        '''Retrieve a dictionary showing the available visualizations.'''
        return json.loads(_CanReq.simple_get(self['visualizations']))

    def get_visualization(self, vis_key):
        '''Retrieve a specific visualization.

        Arguments:
        vis_key -- the key for the visualization to retrieve

        Returns:
        binary data
        '''
        return _CanReq.simple_get(_uri(_URI_FILE_VISUALIZATION,
                                      self['key'], vis_key))

    def __repr__(self):
        return '<File: key="%s", name="%s">' % \
                (self['key'], self['name'] if 'name' in self else 'n.a.')


class Collection(CanorisObject):
    '''The Collection class is used to interact with and to create Canoris collections.'''

    @staticmethod
    def get_collection(key):
        '''Retrieve a Collection object by specifying the collection's key.

        Arguments:
        key -- the collection's key

        Returns:
        A Collection object
        '''
        return Collection(json.loads(_CanReq.simple_get(_uri(_URI_COLLECTION,
                                                            key))))

    @staticmethod
    def create_collection(name, public=True, license=Licenses.AllRightsReserved):
        '''Create a new collection.

        Arguments:
        name -- the name of the new collection

        Keyword arguments:
        public -- whether the collection can later be accessed by other users (default: True)
        license -- if public, the files in the collection can be used under this license (default: AllRightsReserved)

        N.B. The Licenses class contains all the licenses that can be used.

        Returns:
        A Collection object
        '''
        public = '1' if public else '0'
        params = {'name': name, 'public': public, 'license': license}
        resp = _CanReq.simple_post(_uri(_URI_COLLECTIONS), params)
        return json.loads(resp)

    def delete(self):
        '''Delete the Collection from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])

    def add_file(self, file):
        '''Add an existing File object to the Collection.

        Arguments:
        file -- can be either a File object or a file's key

        Returns:
        None
        '''
        params = {'filekey': file['key'] if isinstance(file, File) else file}
        _CanReq.simple_post(self['files'], params)

    def remove_file(self, file):
        '''Remove a File from the Collection.

        Arguments:
        file -- can be either a File object or a file's key

        Returns:
        None
        '''
        uri = _uri(_URI_COLLECTION_FILE, self['key'],
                   file['key'] if isinstance(file, File) else file)
        _CanReq.simple_del(uri)

    def files(self, page=0):
        '''Get a list of Files in the Collection.

        Keyword arguments:
        page -- the page of files to retrieve, each page contains 20 files (default: 0)

        Returns:
        A dictionary representing a paginated list.
        '''
        return json.loads(_CanReq.simple_get(self['files'], params={'page': page} ))

    def get_similar(self, query_file, preset, num_results=10):
        '''Perform a similarity search in this Collection.

        Arguments:
        query_file -- can be either a File or a file's key
        preset -- the similarity search preset to use ('music', 'rhythm', or 'lowlevel')

        Keyword arguments:
        num_results -- the number of results to return

        Returns:
        A list with the search results
        '''
        fkey = query_file['key'] if isinstance(query_file, File) else query_file
        uri  = _uri(_URI_COLLECTION_SIMILAR, self['key'],
                    fkey, preset, num_results)
        return [{'distance': result['distance'],
                 'file': File({'ref': result['ref']})} \
                 for result in json.loads(_CanReq.simple_get(uri))]

    def __repr__(self):
        return '<File: key="%s", name="%s">' % (self['key'], self['name'])



class Template(CanorisObject):
    '''The Template class is used to interact with and to create Canoris templates.'''

    @staticmethod
    def get_template(name):
        '''Retrieve a template by specifying it's name.

        Arguments:
        name -- the template's name

        Returns:
        a Template object
        '''
        return Template(json.loads(_CanReq.simple_get(_uri(_URI_TEMPLATE, name))))

    @staticmethod
    def create_template(name, steps):
        '''Create a new template.

        Arguments:
        name -- the template's name
        steps -- a Python list

        Returns:
        a Template object
        '''
        args = {'name': name,
                'template': json.dumps(steps)}
        return Template(json.loads(_CanReq.simple_post(_uri(_URI_TEMPLATES), args)))

    def delete(self):
        '''Delete the Template from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])


class Task(CanorisObject):
    '''The Task class is used to interact with and to create Canoris tasks.'''

    @staticmethod
    def get_task(task_id):
        '''Retrieve a Task object by specifying it's id.

        Arguments:
        task_id -- the task's id

        Returns:
        a Task object
        '''
        return Task(json.loads(_CanReq.simple_get(_uri(_URI_TASK, task_id))))

    @staticmethod
    def create_task(template, parameters):
        '''Create a new processing task.

        Arguments:
        template -- the template's name to generate the task from
        parameters -- a Python dictionary of template variables to replace

        Returns:
        a Task object
        '''
        return Task(json.loads(_CanReq.simple_post(
                                    _uri(_URI_TASKS),
                                    {'template': template,
                                     'parameters': json.dumps(parameters)})))

    def __repr__(self):
        return '<File: task_id="%s", completed="%s", successful="%s">' % \
                (self['task_id'], self['complete'], self['successful'])


class Text2Phonemes(object):
    '''Translate text into phonemes.'''

    @staticmethod
    def translate(text, voice=False, language=False):
        '''Translate text into phonemes.

        Arguments:
        text -- the text to translate

        Keyword arguments:
        voice -- the Vocaloid voice to fine tune the phonemes for (ona, lara, or arnau)
        language -- the language of the text (english, or spanish)

        Returns:
        a dictionary representing the translation
        '''
        lang = language if language else 'spanish'
        args = {'language': lang,
                'text': text}
        if voice:
            args['voice'] = str(voice)
        return json.loads(_CanReq.simple_get(_uri(_URI_PHONEMES), args))

