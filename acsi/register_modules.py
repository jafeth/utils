#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import glob
import json
from lxml import etree
import jmespath



def _parse_xml(xml_path):
    if not os.path.exists(xml_path):
        return None
    xml_parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, xml_parser)
    return tree


def _normalize_path(base_dir, *paths):
    path = os.path.join(base_dir, *paths)
    path = os.path.expanduser(path)
    return os.path.realpath(path)


class IdeaProject(object):

    def __init__(self, project_dir):
        if not os.path.isdir(project_dir):
            raise FileNotFoundError('%s not found or is not a directory' % project_dir)
        self.project_dir = project_dir

    @property
    def idea_dir(self):
        return '$PROJECT_DIR$/.idea'

    @property
    def vendor_dir(self):
        return '$PROJECT_DIR$/vendor'

    def normalize_path(self, base_dir, *paths):
        path = os.path.join(base_dir, *paths)
        path = os.path.expanduser(path)
        path = path.replace('$PROJECT_DIR$', self.project_dir)
        return os.path.realpath(path)

    def relative_to_project(self, absolute_path):
        return os.path.relpath(absolute_path, self.project_dir)

    def modules_xml(self):
        return

    def parse_idea_xml(self, xml_file_name):
        path = self.normalize_path(self.idea_dir, xml_file_name)
        return _parse_xml(path)


def walk_modules(project_dir):
    glob_path = path_normalize(project_dir, 'vendor', 'acsi', '*', 'composer.json')
    for composer_path in glob.iglob(glob_path):
        json_obj = parse_json(composer_path)
        if json_obj:
            yield composer_path, json_obj


def parse_json(json_path):
    if not os.path.isfile(json_path):
        return None
    with open(json_path, mode='r') as json_file:
        json_obj = json.load(json_file)

    return json_obj


def main(project_dir, print_xml):

    project = IdeaProject(project_dir)


    modules_tree = parse_idea_xml(project_dir, 'modules.xml')

    project_module_path = modules_tree.xpath('string(/project/component/modules/module/@filepath)')

    print(project_module_path)

    # for path, composer_config in walk_modules(project_dir):
    #     if not type(composer_config) == dict:
    #         continue
    #     if 'autoload' not in composer_config:
    #         continue
    #     psr0 = jmespath.search('autoload."psr-0"', composer_config)
    #     if psr0:
    #         print(psr0)
    #     psr4 = jmespath.search('autoload."psr-4"', composer_config)
    #     if psr4:
    #         print(psr4)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Add acsi modules VCS roots to PhpStorm project")
    parser.add_argument('project_root', help="Root of the PhpStorm project")
    parser.add_argument('-p', '--print', help="Print the modified vcs.xml instead of writing it", action="store_true", dest='print_xml')
    args = parser.parse_args()
    main(args.project_root, print_xml=args.print_xml)
