#!/usr/bin/python
# -*- coding: utf-8 -*-

import jmespath
import requests
from cached_property import cached_property


def _build_path(*segments):
    return '/'.join([s.strip('/') for s in list(segments) if s and s.strip('/')])


class _Endpoint(object):

    def __init__(self, uri):
        self.endpoint = uri

    def _request(self, method='get', path='', **kwargs):
        if not self.endpoint:
            return None

        url = _build_path(self.endpoint, path)

        try:
            return requests.request(method=method, url=url, **kwargs)
        except requests.ConnectionError:
            return None

    def _json_request(self, method='get', path='', **kwargs):
        params = kwargs.setdefault('params', {})
        params['wt'] = 'json'

        response = self._request(method=method, path=path, **kwargs)
        content_type = response.headers.get('content-type')

        if not content_type or 'application/json' not in content_type:
            return {}

        return response.json()


class SystemAPI(_Endpoint):
    def __init__(self, base_uri):
        self.base_uri = base_uri
        _Endpoint.__init__(self, _build_path(self.base_uri, 'admin'))

    @cached_property
    def _info(self):
        json = self._json_request(path='info/system')

        if type(json) is dict:
            return json

        return {}

    @cached_property
    def cores(self):
        params = {
            'action': 'STATUS',
            'indexInfo': 'false'
        }
        payload = self._json_request(path='cores', params=params)
        if 'status' in payload:
            return payload['status']

        return {}

    def _invalidate_cores(self):
        if 'cores' in self.__dict__:
            del self.__dict__['cores']

    @property
    def home(self):
        return self._info.get('solr_home')

    @property
    def mode(self):
        return self._info.get('mode')

    @property
    def os(self):
        return self._info.get('system')

    @property
    def lucene(self):
        return self._info.get('lucene')

    @property
    def jvm(self):
        return self._info.get('jvm')

    def create_core(self, core, config=None, schema=None):
        params = {
            'action': 'CREATE',
            'name': '%s' % core
        }
        if config:
            params['config'] = config
        if schema:
            params['schema'] = schema

        self._json_request(path='cores', params=params)
        self._invalidate_cores()

    def reload_core(self, core):
        params = {
            'action': 'RELOAD',
            'core': '%s' % core
        }
        return self._json_request(path='cores', params=params)

    def unload_core(self, core):
        params = {
            'action': 'UNLOAD',
            'deleteInstanceDir': 'true',
            'core': '%s' % core
        }
        self._json_request(path='cores', params=params)
        self._invalidate_cores()

    def core_exists(self, core):
        return core in self.cores

    def search_cores(self, path_query):
        return jmespath.search(path_query, self.cores)


class _Base(_Endpoint):
    def __init__(self, base_uri=None, path=None, system=None):
        self.system = system
        if not self.system:
            self.system = SystemAPI(base_uri)

        _Endpoint.__init__(self, _build_path(self.system.base_uri, path))


class Core(object):
    def __init__(self, base_uri, core_name):
        self.name = core_name
        self.system = SystemAPI(base_uri=base_uri)
        self._config = None
        self._schema = None

    def __str__(self):
        return self.name

    @property
    def exists(self):
        return self.system.core_exists(self.name)

    @property
    def instance_dir(self):
        return self.system.search_cores('%s.instanceDir' % self.name)

    @property
    def config(self):
        if not self.exists:
            return self._config

        return self.system.search_cores('%s.config' % self.name)

    @config.setter
    def config(self, value):
        if self.exists:
            return

        self._config = value

    @property
    def schema(self):
        if not self.exists:
            return self._schema

        return self.system.search_cores('%s.schema' % self.name)

    @schema.setter
    def schema(self, value):
        if self.exists:
            return

        self._schema = value

    def path(self, endpoint):
        return _build_path(self.name, endpoint)

    def create(self):
        if not self.exists:
            self.system.create_core(core=self.name, config=self.config, schema=self.schema)

    def reload(self):
        if self.exists:
            return self.system.reload_core(self.name)


class _CoreAware(_Base):
    def __init__(self, base_uri, core, endpoint=None):
        self.core = Core(base_uri=base_uri, core_name=core)
        path = self.core.path(endpoint)
        _Base.__init__(self, path=path, system=self.core.system)


class ConfigAPI(_CoreAware):
    def __init__(self, base_uri, core):
        _CoreAware.__init__(self, base_uri=base_uri, core=core, endpoint='config')


class SchemaAdmin(_CoreAware):
    _element_map = {
        'field': 'fields',
        'field-type': 'fieldTypes',
        'copy-field': 'copyFields',
        'dynamic-field': 'dynamicFields'
    }

    def __init__(self, base_uri, core):
        _CoreAware.__init__(self, base_uri=base_uri, core=core, endpoint='schema')

    @cached_property
    def schema(self):
        if self.core.exists:
            json = self._json_request()
            if 'schema' in json:
                return json['schema']

        return {}

    def _invalidate_schema(self):
        if 'schema' in self.__dict__:
            del self.__dict__['schema']

    @property
    def schema_xml(self):
        response = self._request(method='get', params={'wt': 'schema.xml'})
        return response.content

    @property
    def unique_key(self):
        return self.search('uniqueKey')

    @property
    def name(self):
        return self.search('name')

    @property
    def version(self):
        return self.search('version')

    def search(self, path_query):
        return jmespath.search(path_query, self.schema)

    def get_element(self, element_type, element):
        if element_type not in self._element_map:
            return None

        name = None

        if type(element) is dict and 'name' in element:
            name = element['name']

        if type(element) is str:
            name = element

        if not name:
            return None

        path_query = "%s[?name=='%s'] | [0]" % (self._element_map[element_type], name)

        return self.search(path_query)

    def modify_element(self, element_type, element):
        if element_type not in self._element_map:
            return None

        if type(element) is not dict or 'name' not in element:
            return None

        action = 'add'

        if bool(self.get_element(element_type, element)):
            action = 'replace'

        element_action = '%s-%s' % (action, element_type)

        self._json_request(method='post', json={element_action: element})
        self._invalidate_schema()

        return self.get_element(element_type, element)

    def delete_element(self, element_type, element):
        if not bool(self.get_element(element_type, element)):
            return

        element_action = 'delete-%s' % element_type

        self._json_request(method='post', json={element_action: element})
        self._invalidate_schema()


class ManagedResources(_CoreAware):
    _managed_classes = {
        'stopwords': 'org.apache.solr.rest.schema.analysis.ManagedWordSetResource',
        'synonyms': 'org.apache.solr.rest.schema.analysis.ManagedSynonymFilterFactory$SynonymManager'
    }

    def __init__(self, base_uri, core):
        _CoreAware.__init__(self, base_uri=base_uri, core=core)

    @cached_property
    def resources(self):
        if not self.core.exists:
            return None

        json = self._json_request(path='/schema/managed')
        if 'managedResources' in json:
            return json['managedResources']

        return {}

    def _invalidate_resources(self):
        if 'resources' in self.__dict__:
            del self.__dict__['resources']

    def get_resource(self, type_name, resource_name):
        path = '/schema/analysis/%s/%s' % (type_name, resource_name)
        return next((res for res in self.resources if res['resourceId'] == path), None)

    def resource_exists(self, type_name, resource_name):
        return bool(self.get_resource(type_name, resource_name))

    def create_resource(self, type_name, resource_name):
        if type_name not in self._managed_classes:
            return None

        resource = self.get_resource(type_name, resource_name)
        if resource:
            return resource

        data = {'class': self._managed_classes[type_name]}
        path = '/schema/analysis/%s/%s' % (type_name, resource_name)
        self._json_request(method='put', path=path, json=data)
        self._invalidate_resources()

        return self.get_resource(type_name, resource_name)

    def delete_resource(self, type_name, resource_name):
        resource = self.get_resource(type_name, resource_name)
        if not resource:
            return None

        self._json_request(method='delete', path=resource['resourceId'])
        self._invalidate_resources()
        return resource


class SynonymResource(_Base):
    def __init__(self, base_uri, core, name):
        self.name = name
        self.api = ManagedResources(base_uri=base_uri, core=core)
        path = _build_path(self.api.core.name, self.resource['resourceId'])
        _Base.__init__(self, path=path, system=self.api.system)

    @cached_property
    def resource(self):
        return self.api.create_resource('synonyms', self.name)

    @cached_property
    def synonyms(self):
        json = self._json_request()
        if 'synonymMappings' in json:
            return json['synonymMappings']

        return {}

    def _invalidate_synonyms(self):
        if 'synonyms' in self.__dict__:
            del self.__dict__['synonyms']

    @property
    def map(self):
        if 'managedMap' in self.synonyms:
            return self.synonyms['managedMap']
        return {}

    @property
    def init_args(self):
        if 'initArgs' in self.synonyms:
            return self.synonyms['initArgs']
        return {}

    @init_args.setter
    def init_args(self, value):
        data = {'initArgs': value}
        self._json_request(method='post', json=data)
        self._invalidate_synonyms()

    def delete_synonym(self, synonym):
        if synonym not in self.synonyms:
            return self
        self._json_request(method='delete', path=synonym)
        self._invalidate_synonyms()
        return self

    def append_synonyms(self, synonym_map):
        if self.in_map(synonym_map):
            return self

        self._json_request(method='put', json=synonym_map)
        self._invalidate_synonyms()
        return self

    def in_map(self, synonym_map):
        mapped = self.map_list(synonym_map)
        for key, synonyms in mapped.iteritems():
            if key not in self.map:
                return False
            if not set(synonyms) <= set(self.map[key]):
                return False

        return True

    @staticmethod
    def map_list(synonym_map):
        if type(synonym_map) is dict:
            return synonym_map
        if type(synonym_map) is not list:
            return {}
        mapped = {}
        for synonym in synonym_map:
            mapped[synonym] = synonym_map
        return mapped


class FileAdmin(_CoreAware):
    def __init__(self, base_uri, core):
        _CoreAware.__init__(self, base_uri=base_uri, core=core, endpoint='admin/file')

    def _get_fs(self, path):
        json = self._json_request(params={'file': _build_path(path)})
        if 'files' not in json:
            return []

        paths = []
        for p, f in json['files'].items():
            if 'directory' not in f:
                paths.append(_build_path(path, p))
                continue

            paths += self._get_fs(_build_path(path, p))

        return paths

    @cached_property
    def paths(self):
        if not self.core.exists:
            return []

        return self._get_fs('/')

    def file_exists(self, file_path):
        return _build_path(file_path) in self.paths

    def get_file_content(self, file_path):
        if not self.file_exists(file_path):
            return None

        params = {'file': _build_path(file_path)}

        response = self._request(method='get', params=params)
        if response.status_code == requests.codes.not_found:
            return None

        return response.content

    @cached_property
    def config(self):
        return self.get_file_content(self.core.config)

    @cached_property
    def schema(self):
        return self.get_file_content(self.core.schema)


def main():

    # pass
    s = FileAdmin('http://10.0.0.20:8983/solr', 'acsi')

    print s.core.schema
    # print s.name
    # print s.unique_key
    # print s.version
    # print s.schema
    # print s.info.home
    #
    # print s.search("fieldTypes[?name=='text_general'] | [0]")
    # fts = s.search("fieldTypes[?analyzer.filters[?class=='solr.SynonymFilterFactory']]")
    # #
    # for fieldType in fts:
    #     for f in fieldType['analyzer']['filters']:
    #         if f['class'] != 'solr.SynonymFilterFactory':
    #             continue
    #         f['class'] = 'solr.ManagedSynonymFilterFactory'
    #         del f['synonyms']
    #
    # print fts

    # # resources = SolrManagedResources('http://10.0.0.20:8983/solr', 'autocomplete')
    # # resources.delete_resource('synonyms', 'autocomplete')
    #
    # f = FileAdmin('http://dev.acsi.lan:8983/solr', 'autocomplete')
    # # print f.get_file_contents('/lang/stopwords_ja.txt')
    # print f.get_file_contents('schema.xml')
    # # print managed.set_init_args({'ignoreCase': 'true'})
    # # print schema.add_field_type({'name':'daterange', 'class': 'solr.DateRangeField'})
    # # print schema.get_field_type('daterange')
    # # print managed.set_synonyms([''])
    # # print managed.resource
    # # print managed.resources


if __name__ == '__main__':
    main()
