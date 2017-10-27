#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
import os
import pygit2
from termcolor import cprint


def path_normalize(root, *paths):
    path = os.path.join(root, *paths)
    path = os.path.expanduser(path)
    return os.path.realpath(path)


def walk_module_dirs(project_dir):
    glob_path = path_normalize(project_dir, 'vendor', 'acsi', '*', '.git')
    for git_dir in glob.iglob(glob_path):
        yield git_dir


def checkout_branch(git_dir, branch_name, base_dir):
    repo = pygit2.Repository(git_dir)
    rel_dir = os.path.relpath(git_dir, base_dir)
    if repo.head.shorthand == branch_name:
        cprint('skipping: `%s` branch is already checked out for repo (%s)' % (branch_name, rel_dir), 'cyan')
        return
    branch_ref = repo.lookup_branch(branch_name)
    if not branch_ref:
        cprint('error: `%s` branch not found in repo (%s)' % (branch_name, rel_dir), 'red')
        return
    if bool(repo.status()):
        cprint('error: the current branch (%s) has uncommited work in repo (%s)' % (repo.head.shorthand, rel_dir), 'red')
        return
    repo.checkout(branch_ref)
    cprint('success: `%s` branch not checked out for repo (%s)' % (branch_name, rel_dir), 'green')


def main(project_dir, branch):
    for git_dir in walk_module_dirs(project_dir=project_dir):
        checkout_branch(git_dir=git_dir, branch_name=branch, base_dir=project_dir)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Checkout branch for all acsi modules")
    parser.add_argument('project_root', help="Root of the PhpStorm project")
    parser.add_argument('-b', '--branch', help="branch to checkout (default: master)", default='master')
    args = parser.parse_args()
    main(args.project_root, args.branch)