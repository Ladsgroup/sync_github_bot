"""
WIP
It's an script to syncronize github and gerrit


"""

import json
import os
#import codecs
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError
from getpass import getpass
from subprocess import Popen, STDOUT, PIPE

_program_dir = os.path.dirname(os.path.realpath(__file__))
_github_pass = getpass('Githubpass?')
_gerrit_pass = getpass('Gerritpass?')
github_comment = 'This pull request has been automatically duplicated in ' \
    'gerrit'


class NotEnoughDataError(object):
    """docstring for NotEnoughDataError"""


class Project(object):
    """docstring for Project"""
    def __init__(self, name, gerrit_name, org=None):
        if not org:
            if '/' in name:
                self.name = name.split('/')[1]
                self.org = name.split('/')[0]
            else:
                raise NotEnoughDataError
        else:
            self.name = name
            self.org = org
        self.url_name = '%s/%s' % (self.org, self.name)
        self.gerrit_name = gerrit_name


class PullRequest(object):
    """docstring for pull_request"""
    def __init__(self, pull_dict, project):
        self.project = project
        self.user = User(pull_dict['user'])
        self.body = pull_dict['body']
        self.title = pull_dict['title']
        self.html_url = pull_dict['html_url']
        self.patch_url = pull_dict['patch_url']
        self.id = pull_dict['id']
        self.number = pull_dict['number']
        self.clone_url = pull_dict['head']['repo']['clone_url']
        self._load_comments()

    def _load_comments(self):
        self.comments = []
        self.comments_url = '%s/repos/%s/pulls/%s/comments' \
            % ('https://api.github.com', self.project.url_name, self.number)
        try:
            urlopen(self.comments_url).read()
        except HTTPError:
            print('No comments')
            comments = []
        else:
            comments = json.loads(urlopen(self.comments_url).read().decode())
        for comment in comments:
            self.comments.append(Comment(comment))

    def create_comment(self, body):
        comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' \
            % (self.project.url_name, self.number)
        Popen(
            ['curl', '-i', comment_url,
             '-u', '%s:%s' % (bot.username, _github_pass),
             '--data', json.dumps({'body': body})],
            cwd=_program_dir,
            stdout=PIPE, stderr=PIPE).stdout.read()
        #import urllib.request
        #auth_handler = urllib.request.HTTPBasicAuthHandler()
        #auth_handler.add_password(realm=None,
        #                  uri='https://api.github.com',
        #                  user=bot.username,
        #                  passwd=_github_pass)
        #opener = urllib.request.build_opener(auth_handler)
        #urllib.request.install_opener(opener)
        #urllib.request.urlopen(
        #    comment_url, data=bytes(json.dumps({'body': body}), 'utf-8'))


class Comment(object):
    """docstring for Comment"""
    def __init__(self, comment_dict):
        self.user = User(comment_dict['user'])
        self.body = comment_dict['body']
        self.id = comment_dict['id']
        self.path = comment_dict.get('path')
        self.position = comment_dict.get('position')
        self.html_url = comment_dict['html_url']
        self.original_position = comment_dict.get('original_position')


class User(object):
    """docstring for User"""
    def __init__(self, user_dict):
        self.username = user_dict['login']


bot = User({'login': 'syncgithubbot'})


class Bot(object):
    """docstring for Bot"""
    def __init__(self, *args, **kwargs):
        self.project = Project(*args, **kwargs)

    def gen(self):
        url = 'https://api.github.com/repos/%s/pulls' % self.project.url_name
        pulls = json.loads(urlopen(url).read().decode())
        for pull in pulls:
            if pull['state'] != 'open' or pull['locked']:
                continue
            pull_request = PullRequest(pull, self.project)
            for comment in pull_request.comments:
                if bot == comment.user:
                    pull_request.done = True
            if not hasattr(pull_request, 'done'):
                yield pull_request

    def create_commit(self, pull_request, password):
        folder_name = '%s-%s' % (
            pull_request.project.gerrit_name,
            pull_request.number)
        folder_name = folder_name.replace('/', '-')
        print('ssh://%s@gerrit.wikimedia.org:29418/%s.git'
              % (bot.username, pull_request.project.gerrit_name))
        p = Popen(
            ['git',
             'clone',
             'ssh://%s@gerrit.wikimedia.org:29418/%s.git'
                % (bot.username, pull_request.project.gerrit_name),
             '%s/%s' % (_program_dir, folder_name)],
            cwd=_program_dir,
            stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        out = p.communicate(input=bytes(password, 'utf-8'))[0]
        print(out)
        patch_url = pull_request.patch_url
        patch_filename, headers = urlretrieve(patch_url)
        p2 = Popen(
            ['git',
             'apply',
             os.path.join(_program_dir, patch_filename)],
            cwd=os.path.join(_program_dir, folder_name),
            stdout=PIPE, stderr=PIPE).stdout.read()
        print(p2)
        commit_message = '%s\n\n%s\n[Duplicated from: %s by bot]' \
            % (pull_request.title, pull_request.body, pull_request.html_url)
        with open('%s/commit_message' % _program_dir, 'w') as f:
            f.write(commit_message)
        p3 = Popen(
            ['git', 'commit', '-a', '-F', '../commit_message'],
            cwd=os.path.join(_program_dir, folder_name),
            stdout=PIPE, stderr=PIPE).stdout.read()
        print(p3)
        p31 = Popen(
            ['git', 'config', '--global', 'gitreview.username', bot.username],
            cwd=_program_dir,
            stdout=PIPE, stderr=PIPE).stdout.read()
        print(p31)
        p32 = Popen(
            ['git', 'config', '--global',
             'user.email', 'syncgerritgithub@gmail.com'],
            cwd=_program_dir,
            stdout=PIPE, stderr=PIPE).stdout.read()
        print(p32)
        p4 = Popen(
            ['git', 'review', '-R'],
            cwd=os.path.join(_program_dir, folder_name),
            stdout=PIPE, stdin=PIPE, stderr=PIPE)
        p4 = p4.communicate(input=bytes('yes', 'utf-8'))
        print(p4)

    def run(self):
        gen = self.gen()
        for pull_request in gen:
            if pull_request.number != 5:
                continue
            self.create_commit(pull_request, _gerrit_pass)
            pull_request.create_comment()
