import httplib2, urllib2, urllib, re, os, uuid
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
import simplejson as json
from urllib2 import HTTPError
from urlparse import urlparse, urlunparse
from cgi import parse_qsl

VERSION = '0.10'

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
    if len(args) >= 1 and (args[0].startswith('http://') or args[0].startswith('https://')):
        return args[0]
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


class _RequestWithMethod(urllib2.Request):
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
        up = urlparse(uri)
        dqsl = dict(parse_qsl(up.query))
        dqsl['api_key'] = Canoris.get_api_key()
        if params and isinstance(params, dict):
            dqsl.update(params)
        uri = urlunparse([up.scheme, up.netloc, up.path, up.params,
                          urllib.urlencode(dqsl), up.fragment])
        d = urllib.urlencode(data) if data else None
        req = _RequestWithMethod(uri, method, d)
        return cls._handle_errors(req)

    @classmethod
    def _handle_errors(cls, req):
        try:
            try:
                f = urllib2.urlopen(req)
                resp = f.read()
                f.close()
                return resp
            except HTTPError, e:
                if e.code >= 200 and e.code < 300:
                    resp = e.read()
                    return resp
                else:
                    raise e
        except HTTPError, e:
            resp = e.read()
            try:
                error = json.loads(resp)
            except:
                # not a json response, something is really wrong!
                raise Exception(resp)
            raise CanorisException(error.get('status_code', 500),
                                   error.get('explanation', ''),
                                   error.get('type', ''),
                                   error.get('throttled', False),
                                   error.get('debug', ''))

    @classmethod
    def post_file(cls, uri, args):
        datagen, headers = multipart_encode(args)
        req = urllib2.Request(_uri(_URI_FILES), datagen, headers)
        return cls._handle_errors(req)

    @classmethod
    def retrieve(cls, url, path):
        return _CanRetriever().retrieve('%s?api_key=%s' % (url, Canoris.get_api_key()), path)


class CanorisException(Exception):
    def __init__(self, code, explanation, type, throttled=False, debug=''):
        self.code = code
        self.explanation = explanation
        self.type = type
        self.throttled = throttled
        self.debug = debug

    def __str__(self):
        return '<CanorisException: code=%s, type="%s", explanation="%s", throttled=%s>' % \
                (self.code, self.type, self.explanation, self.throttled)


class _CanRetriever(urllib.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        # TODO: possibly DRY this out
        resp = fp.read()
        try:
            error = json.loads(resp)
        except:
            raise Exception(resp)
        raise CanorisException(errcode,
                               error.get('explanation', ''),
                               error.get('type', ''),
                               error.get('throttled', False))


class PageException(Exception):
    pass


class Pager(CanorisObject):
    '''Pagers are used to paginate through your Canoris files, collections, and
    collection files.
    '''

    @classmethod
    def files_page(cls, page=0, start=None, limit=20):
        '''Retrieve a paginator object for paging through your files.

        TODO: document arguments, etc.
        '''
        return cls._load_page(_uri(_URI_FILES), page, start, limit)

    @classmethod
    def collection_page(cls, key, page=0, start=None, limit=20):
        '''Retrieve a paginator object for paging through the files in a
        collection.
        '''
        return cls._load_page(_uri(_URI_COLLECTION_FILES, key),
                              page, start, limit)

    @classmethod
    def collections_page(cls, page=0, start=None, limit=20):
        '''Retrieve a paginator object for paging through your collections.
        '''
        return cls._load_page(_uri(_URI_COLLECTIONS), page, start, limit)

    @classmethod
    def _load_page(cls, uri, page=None, start=None, limit=20):
        '''
        If page, start, and limit are all None we will assume the URI has the
        right parameters already set. Otherwise we will build the right URI.
        '''
        if page==None and start==None:
            params = {}
        else:
            # if start is not None we will ignore page
            params = {'limit': limit}
            if start != None:
                if not isinstance(start, int) or start < 0:
                    raise PageException('Use a sane value for start (>=0).')
                params['start'] = start
            else:
                if page == None or not isinstance(page, int) or page < 0:
                    raise PageException('Please use either page or start and with a sane value for page (>=0).')
                params['page'] = page
        atts = json.loads(_CanReq.simple_get(uri, params))
        return Pager(atts)

    def next(self):
        '''Load the next page.'''
        if not 'next' in self.attributes:
            raise PageException('No more pages available.')
        self.__prev_next('next')

    def previous(self):
        '''Load the previous page.'''
        if not 'previous' in self.attributes:
            raise PageException('You are already at page 0.')
        self.__prev_next('previous')

    def __prev_next(self, direction):
        uri = self.attributes[direction]
        new_attrs = json.loads(_CanReq.simple_get(uri, {}))
        self.attributes.update(new_attrs)



class File(CanorisObject):
    '''The File class is used to interact with and to upload Canoris files.'''

    @staticmethod
    def get_file(key):
        '''Retrieve a File object by specifying the file's key or ref.

        Arguments:

        key
          the file's key or ref

        Returns:

        A File object
        '''
        res = _CanReq.simple_get(_uri(_URI_FILE, key))
        return File(json.loads(res))

    @staticmethod
    def create_file(path, name=None, temporary=None):
        '''Upload a sound file and create a File object.

        Arguments:

        path
          the path of the local sound file to upload -or- the url of a file on the web

        Keyword arguments:

        name
          give the file a name
        temporary
          mark the new file as temporary

        Returns:

        a File object
        '''
        args = {}
        if path.startswith('http'):
            args['url'] = path
        else:
            args['file'] = open(path, "rb")
        if name != None:
            args['name'] = str(name)
        if temporary != None:
            args['temporary'] = 1 if temporary else 0
        args['api_key'] = Canoris.get_api_key()
        try:
            resp = _CanReq.post_file(_uri(_URI_FILES), args)
            return File(json.loads(resp))
        finally:
            if 'file' in args:
                args['file'].close()


    def delete(self):
        '''Delete a File from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])

    def get_analysis(self, *filter, **kwargs):
        '''Retrieve the File's analysis.

        Arguments:

        any argument
          retrieve a certain part of the analysis tree

        Keyword arguments:

        showall
          retrieve all available analysis data (default: False)

        Example:

        ::

          file1.get_analysis('highlevel', 'gender', 'value')
          file2.get_analysis(showall=True)

        Returns:

        Depending on the filter returns a dictionary, list, number, or string.
        '''
        return json.loads(
                 _CanReq.simple_get(
                    _uri(_URI_FILE_ANALYSIS, self['key'], '/'.join(filter)),
                    params={'all': '1' if kwargs.get('showall', False) else '0'}))

    def retrieve_analysis_frames(self, path):
        '''Retrieve the json file with the analysis data for all the frames.

        Arguments:

        path
          Save the file here.

        Returns:

        a tuple: (<path>, <httplib.HTTPMessage instance>)
        '''
        return _CanReq.retrieve(self['analysis_frames'], path)

    def retrieve(self, directory, name=False):
        '''Retrieve the original file and save it to disk.

        Arguments:

        directory
          save the file in this directory

        Keyword arguments:

        name
          save the file under this name, if not present uses the original file name

        Returns:

        a tuple: (<path>, <httplib.HTTPMessage instance>)
        '''
        file_name = name if name else self.attributes.get('name', str(uuid.uuid4()))
        path = os.path.join(directory, file_name)
        return _CanReq.retrieve(self['serve'], path)

    def get_conversions(self):
        '''Retrieve a dictionary showing the available conversions.'''
        return json.loads(_CanReq.simple_get(self['conversions']))

    def retrieve_conversion(self, conv_key, path):
        '''Retrieve a specific conversion and save it to disk.

        Arguments:

        conv_key
          the key for the conversion to retrieve
        path
          save the file to this path

        Returns:

        a tuple: (<path>, <httplib.HTTPMessage instance>)
        '''
        return _CanReq.retrieve(_uri(_URI_FILE_CONVERSION,
                                     self['key'], conv_key),
                                path)

    def get_visualizations(self):
        '''Retrieve a dictionary showing the available visualizations.'''
        return json.loads(_CanReq.simple_get(self['visualizations']))

    def retrieve_visualization(self, vis_key, path):
        '''Retrieve a specific visualization and save it to disk.

        Arguments:

        vis_key
          the key for the visualization to retrieve
        path
          save the file to this path

        N.B. waveform is png, spectrum is jpg

        Returns:

        a tuple: (<path>, <httplib.HTTPMessage instance>)
        '''
        return _CanReq.retrieve(_uri(_URI_FILE_VISUALIZATION,
                                     self['key'], vis_key),
                                path)

    def __repr__(self):
        return '<File: key="%s", name="%s">' % \
                (self['key'], self['name'] if 'name' in self.attributes else 'n.a.')


class Collection(CanorisObject):
    '''The Collection class is used to interact with and to create Canoris collections.'''

    @staticmethod
    def get_collection(key):
        '''Retrieve a Collection object by specifying the collection's key or ref.

        Arguments:

        key
          the collection's key

        Returns:

        a Collection object
        '''
        return Collection(json.loads(_CanReq.simple_get(_uri(_URI_COLLECTION,
                                                            key))))

    @staticmethod
    def create_collection(name, public=True, license=Licenses.AllRightsReserved):
        '''Create a new collection.

        Arguments:

        name
          the name of the new collection

        Keyword arguments:

        public
          whether the collection can later be accessed by other users (default: True)
        license
          if public, the files in the collection can be used under this license (default: AllRightsReserved)

        N.B. The Licenses class contains all the licenses that can be used.

        Returns:

        a Collection object
        '''
        public = '1' if public else '0'
        params = {'name': name, 'public': public, 'license': license}
        return Collection(json.loads(_CanReq.simple_post(_uri(_URI_COLLECTIONS), params)))

    def delete(self):
        '''Delete the Collection from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])

    def add_file(self, file):
        '''Add an existing File object to the Collection.

        Arguments:

        file
          can be either a File object or a file's key

        Returns:

        None
        '''
        params = {'filekey': file['key'] if isinstance(file, File) else file}
        _CanReq.simple_post(self['files'], params)

    def remove_file(self, file):
        '''Remove a File from the Collection.

        Arguments:

        file
          can be either a File object or a file's key

        Returns:

        None
        '''
        uri = _uri(_URI_COLLECTION_FILE, self['key'],
                   file['key'] if isinstance(file, File) else file)
        _CanReq.simple_del(uri)

    def get_similar(self, query_file, preset, num_results=10):
        '''Perform a similarity search in this Collection.

        Arguments:

        query_file
          can be either a File or a file's key
        preset
          the similarity search preset to use ('music', 'rhythm', or 'lowlevel')

        Keyword arguments:

        num_results
          the number of results to return

        Returns:

        a list with the search results
        '''
        fkey = query_file['key'] if isinstance(query_file, File) else query_file
        uri  = _uri(_URI_COLLECTION_SIMILAR, self['key'],
                    fkey, preset, num_results)
        return [{'distance': result['distance'],
                 'file': File({'ref': result['ref']})} \
                 for result in json.loads(_CanReq.simple_get(uri))]

    def __repr__(self):
        return '<Collection: key="%s", name="%s">' % (self['key'], self['name'])



class Template(CanorisObject):
    '''The Template class is used to interact with and to create Canoris templates.'''

    @staticmethod
    def get_template(name):
        '''Retrieve a template by specifying it's name or ref.

        Arguments:

        name
          the template's name

        Returns:

        a Template object
        '''
        return Template(json.loads(_CanReq.simple_get(_uri(_URI_TEMPLATE, name))))

    @staticmethod
    def create_template(name, steps):
        '''Create a new template.

        Arguments:

        name
          the template's name
        steps
          a Python list

        Returns:

        a Template object
        '''
        args = {'name': name,
                'template': json.dumps(steps)}
        return Template(json.loads(_CanReq.simple_post(_uri(_URI_TEMPLATES), args)))

    def delete(self):
        '''Delete the Template from the Canoris API.'''
        return _CanReq.simple_del(self['ref'])

    def __repr__(self):
        return '<Template: name="%s">' % self['name']


class Task(CanorisObject):
    '''The Task class is used to interact with and to create Canoris tasks.'''

    @staticmethod
    def get_task(task_id):
        '''Retrieve a Task object by specifying it's id or ref.

        Arguments:

        task_id
          the task's id

        Returns:

        a Task object
        '''
        return Task(json.loads(_CanReq.simple_get(_uri(_URI_TASK, task_id))))

    @staticmethod
    def create_task(template, parameters):
        '''Create a new processing task.

        Arguments:

        template
          the template's name to generate the task from
        parameters
          a Python dictionary of template variables to replace

        Returns:

        a Task object
        '''
        return Task(json.loads(_CanReq.simple_post(
                                    _uri(_URI_TASKS),
                                    {'template': template,
                                     'parameters': json.dumps(parameters)})))

    def __repr__(self):
        return '<Task: task_id="%s", completed="%s", successful="%s">' % \
                (self['task_id'], self['complete'], self['successful'])


class Text2Phonemes(object):
    '''Translate text into phonemes.'''

    @staticmethod
    def translate(text, voice=False, language=False):
        '''Translate text into phonemes.

        Arguments:

        text
          the text to translate

        Keyword arguments:

        voice
          the Vocaloid voice to fine tune the phonemes for (ona, lara, or arnau)
        language
          the language of the text (english, or spanish)

        Returns:

        a dictionary representing the translation
        '''
        lang = language if language else 'spanish'
        args = {'language': lang,
                'text': text}
        if voice:
            args['voice'] = str(voice)
        return json.loads(_CanReq.simple_get(_uri(_URI_PHONEMES), args))

