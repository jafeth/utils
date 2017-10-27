from module_utils.solr import api as solr
from lxml import etree
from io import BytesIO
# import jmespath
# from ansible.module_utils.basic import AnsibleModule


def main():
    # module = AnsibleModule(
    #     argument_spec=dict(
    #         core=dict(required=True),
    #         path=dict(type='path', required=True),
    #         api=dict(required=True),
    #         force=dict(type='bool', default=True),
    #         managed_synonyms=dict(type='bool', default=True)
    #     ),
    #     add_file_common_args=True,
    #     supports_check_mode=True,
    # )
    #
    # params = module.params
    api = solr.FileAdmin('http://dev.acsi.lan:8983/solr', 'autocomplete')

    config_tree = etree.parse(BytesIO(api.config))

    schema_factory = config_tree.xpath('/config/schemaFactory')[0]

    print etree.tostring(schema_factory)

    etree.SubElement(schema_factory, 'bool', attrib={'name': 'mutable'}).text = 'true'
    etree.SubElement(schema_factory, 'str', attrib={'name': 'managedSchemaResourceName'}).text = 'managed-schema'

    schema_factory.set('class', 'ManagedIndexSchemaFactory')
    print etree.tostring(schema_factory)

    # print jmespath.search("fieldTypes[].analyzer.filters[?class==`solr.SynonymFilterFactory`][].{file: synonyms}", api.schema)
    # print jmespath.search("fieldTypes[?analyzer].{name: name, file: analyzer.filters[?class==`solr.SynonymFilterFactory`][].synonyms | [0]}", api.schema)

    # print api.schema


if __name__ == '__main__':
    main()
