#!/usr/bin/python
# Copyright: 2013 MoinMoin:RogerHaase
# License: GNU GPL v2 (or any later version), see LICENSE.txt for details.

"""
make.py provides a menu of commands frequently used by moin2 developers and desktop wiki users.

    - wraps a few commonly used moin commands, do "moin --help" for infrequently used commands
    - adds default file names for selected moin commands (backup, restore, ...)
    - creates log files for functions with large output, extracts success/failure messages
    - displays error messages if user tries to run commands out of sequence
    - activates the virtual env in a subprocess (no need for user to do ". activate" or "activate")

usage (to display a menu of commands):

    - unix:     ./m
    - windows:  m

For make.py to work, it needs to know the name of a python executable and the location of a
virtual env. These needs are met by running "python quickinstall.py" after cloning the moin2
repository. quickinstall.py creates these files or symlink in the repo root:

    - unix: m, activate
    - windows: m.bat, activate.bat, deactivate.bat

Executing m.bat or ./m will run make.py. The name of the python executable is within the m.bat or ./m
script.  The location of the virtual env is within the activate symlink or activate.bat.
Depending upon the command to be executed, some mix of the python executable
or activate will be used to construct a command string to pass to a subprocess call.

One possible command is "./m quickinstall" which the user may use to occasionally
update the virtual env with newly released supporting software. This same code is
used by quickinstall.py to run itself in a subprocess: hundreds of messages are written
to a file and the few important success/failure messages are extracted and written
to the terminal window.
"""

import os
import sys
import subprocess
import glob
import shutil
import fnmatch
from collections import Counter

import MoinMoin  # validate python version


# text files created by commands with high volume output
QUICKINSTALL = 'm-quickinstall.txt'
PYTEST = 'm-pytest.txt'
CODING_STD = 'm-coding-std.txt'
DOCS = 'm-docs.txt'
NEWWIKI = 'm-new-wiki.txt'
DELWIKI = 'm-delete-wiki.txt'
BACKUPWIKI = 'm-backup-wiki.txt'
DUMPHTML = 'm-dump-html.txt'
EXTRAS = 'm-extras.txt'
DIST = 'm-create-dist.txt'
# default files used for backup and restore
BACKUP_FILENAME = os.path.normpath('wiki/backup.moin')
JUST_IN_CASE_BACKUP = os.path.normpath('wiki/deleted-backup.moin')
DUMP_HTML_DIRECTORY = os.path.normpath('HTML')


if os.name == 'nt':
    M = 'm'  # customize help to local OS
    ACTIVATE = 'activate.bat & '
    SEP = ' & '
    WINDOWS_OS = True
else:
    M = './m'
    # in terminal "source activate" works, but Ubuntu shell requires ". ./activate"
    ACTIVATE = '. ./activate; '
    SEP = ';'
    WINDOWS_OS = False


# commands that create log files
CMD_LOGS = {
    'quickinstall': QUICKINSTALL,
    'tests': PYTEST,
    # 'coding-std': CODING_STD,  # not logged due to small output
    'docs': DOCS,
    'new-wiki': NEWWIKI,
    'del-wiki': DELWIKI,
    'backup': BACKUPWIKI,
    'dump-html': DUMPHTML,
    'extras': EXTRAS,
    'dist': DIST,
}


help = """

usage: "{0} <target>" where <target> is:

quickinstall    update virtual environment with required packages
docs            create moin html documentation
extras          install OpenID, Pillow, pymongo, sqlalchemy, ldap, upload.py
interwiki       refresh contrib/interwiki/intermap.txt (hg version control)
log <target>    view detailed log generated by <target>, omit to see list

new-wiki        create empty wiki
sample          create wiki and load sample data
restore *       create wiki and restore wiki/backup.moin *option, specify file
import <dir>    import a moin 1.9 wiki/data instance from <dir>

run *           run built-in wiki server *options (--port 8081)
backup *        roll 3 prior backups and create new backup *option, specify file
dump-html *     create a static HTML image of wiki *option, specify directory
index           delete and rebuild indexes

css             run Stylus and lessc to update theme CSS files
tests *         run tests, output to pytest.txt *options (-v -k my_test)
coding-std      correct scripts that taint the repository with trailing spaces..
api             update moin api docs (files are under hg version control)

del-all         same as running the 4 del-* commands below
del-orig        delete all files matching *.orig
del-pyc         delete all files matching *.pyc
del-rej         delete all files matching *.rej
del-wiki        create a backup, then delete all wiki data
""".format(M)


def search_for_phrase(filename):
    """Search a text file for key phrases and print the lines of interest or print a count by phrase."""
    files = {
        # filename: (list of phrases)
        QUICKINSTALL: ('could not find', 'error', 'fail', 'timeout', 'traceback', 'success', 'cache location', 'must be deactivated', ),
        NEWWIKI: ('error', 'fail', 'timeout', 'traceback', 'success', ),
        BACKUPWIKI: ('error', 'fail', 'timeout', 'traceback', 'success', ),
        DUMPHTML: ('fail', 'timeout', 'traceback', 'success', 'cannot', 'denied', ),
        # use of 'error ' below is to avoid matching .../Modules/errors.o....
        EXTRAS: ('error ', 'error:', 'error.', 'error,', 'fail', 'timeout', 'traceback', 'success', 'already satisfied', 'active version', 'installed', 'finished', ),
        PYTEST: ('seconds =', 'INTERNALERROR', 'traceback', ),
        CODING_STD: ('remove trailing blanks', 'dos line endings', 'unix line endings', 'remove empty lines', ),
        DIST: ('creating', 'copying', 'adding', 'hard linking', ),
        DOCS: ('build finished', 'build succeeded', 'traceback', 'failed', 'error', 'usage', 'importerror', 'Exception occurred', )
    }
    # for these file names, display a count of occurrances rather than each found line
    print_counts = (CODING_STD, DIST, )

    with open(filename, "r") as f:
        lines = f.readlines()
    name = os.path.split(filename)[1]
    phrases = files[name]
    counts = Counter()
    for idx, line in enumerate(lines):
        line = line.lower()
        for phrase in phrases:
            if phrase in line:
                if filename in print_counts:
                    counts[phrase] += 1
                else:
                    print idx + 1, line.rstrip()
                    break
    for key in counts:
        print 'The phrase "%s" was found %s times.' % (key, counts[key])


def wiki_exists():
    """Return true if a wiki exists."""
    return bool(glob.glob('wiki/index/_all_revs_*.toc'))


def make_wiki(command, mode='w', msg='\nSuccess: a new wiki has been created.'):
    """Process command to create a new wiki."""
    if wiki_exists() and mode == 'w':
        print 'Error: a wiki exists, delete it and try again.'
    else:
        print 'Output messages redirected to {0}.'.format(NEWWIKI)
        with open(NEWWIKI, mode) as messages:
            result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
        if result == 0:
            print msg
            return True
        else:
            print 'Important messages from %s are shown below:' % NEWWIKI
            search_for_phrase(NEWWIKI)
            print '\nError: attempt to create wiki failed. Do "%s log new-wiki" to see complete log.' % M
            return False


def put_items(dir='contrib/sample/'):
    """Load sample items into wiki"""
    metas = []
    datas = []
    files = []
    for (dirpath, dirnames, filenames) in os.walk(dir):
        files.extend(filenames)
        break
    for file in files:
        if file.endswith('.meta'):
            metas.append(file)
        if file.endswith('.data'):
            datas.append(file)
    if not len(datas) == len(metas):
        print 'Error: the number of .data and .meta files should be equal'
        return False
    commands = []
    command = 'moin item-put --meta {0} --data {1}'
    for meta in metas:
        data = meta.replace('.meta', '.data')
        if data in datas:
            commands.append(command.format(dir + meta, dir + data))
        else:
            print 'Error: file "{0} is missing'.format(data)
            return False
    commands = ACTIVATE + SEP.join(commands)

    with open(NEWWIKI, 'a') as messages:
        result = subprocess.call(commands, shell=True, stderr=messages, stdout=messages)
    if result == 0:
        print '{0} items were added to wiki'.format(len(metas))
        return True
    else:
        print 'Important messages from %s are shown below:' % NEWWIKI
        search_for_phrase(NEWWIKI)
        print '\nError: attempt to add items to wiki failed. Do "%s log new-wiki" to see complete log.' % M
        return False


def delete_files(pattern):
    """Recursively delete all files matching pattern."""
    matches = 0
    for root, dirnames, filenames in os.walk(os.path.abspath(os.path.dirname(__file__))):
        for filename in fnmatch.filter(filenames, pattern):
            os.remove(os.path.join(root, filename))
            matches += 1
    print 'Deleted %s files matching "%s".' % (matches, pattern)


def get_bootstrap_data_location():
    """Return the virtualenv site-packages/xstatic/pkg/bootstrap/data location."""
    command = ACTIVATE + 'python -c "from xstatic.pkg.bootstrap import BASE_DIR; print BASE_DIR"'
    return subprocess.check_output(command, shell=True)


def get_pygments_data_location():
    """Return the virtualenv site-packages/xstatic/pkg/pygments/data location."""
    command = ACTIVATE + 'python -c "from xstatic.pkg.pygments import BASE_DIR; print BASE_DIR"'
    return subprocess.check_output(command, shell=True)


def get_sitepackages_location():
    """Return the location of the virtualenv site-packages directory."""
    command = ACTIVATE + 'python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()"'
    return subprocess.check_output(command, shell=True).strip()


class Commands(object):
    """Each cmd_ method processes a choice on the menu."""
    def __init__(self):
        pass

    def cmd_quickinstall(self, *args):
        """create or update a virtual environment with the required packages"""
        command = '{0} quickinstall.py {1}'.format(sys.executable, ' '.join(args))
        print 'Running quickinstall.py... output messages redirected to {0}'.format(QUICKINSTALL)
        with open(QUICKINSTALL, 'w') as messages:
            result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
        if result != 0:
            open(QUICKINSTALL, 'a').write('Error: quickinstall passed non-zero return code: {0}'.format(result))
        print 'Searching {0}, important messages are shown below... Do "{1} log quickinstall" to see complete log.\n'.format(QUICKINSTALL, M)
        search_for_phrase(QUICKINSTALL)

    def cmd_docs(self, *args):
        """create local Sphinx html documentation"""
        command = '{0}cd docs{1} make html'.format(ACTIVATE, SEP)
        print 'Creating HTML docs... output messages written to {0}.'.format(DOCS)
        with open(DOCS, 'w') as messages:
            result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
        print 'Searching {0}, important messages are shown below...\n'.format(DOCS)
        search_for_phrase(DOCS)
        if result == 0:
            print 'HTML docs successfully created in {0}.'.format(os.path.normpath('docs/_build/html'))
        else:
            print 'Error: creation of HTML docs failed with return code "{0}". Do "{1} log docs" to see complete log.'.format(result, M)

    def cmd_extras(self, *args):
        """install optional packages: OpenID, Pillow, pymongo, sqlalchemy, ldap; and upload.py"""
        sp_dir = get_sitepackages_location()
        upload = '{0} MoinMoin/script/win/wget.py https://codereview.appspot.com/static/upload.py upload.py'.format(sys.executable)
        # TODO oldsessions is short term fix for obsolete OpenID 2.0, see #515
        # http://pythonhosted.org//Flask-OldSessions/ docs are broken see https://github.com/mitsuhiko/flask-oldsessions/issues/1
        # we do wget of flask_oldsessions.py to site-packages as another workaround
        oldsessions = '{0} MoinMoin/script/win/wget.py https://raw.githubusercontent.com/mitsuhiko/flask-oldsessions/master/flask_oldsessions.py {1}/flask_oldsessions.py'.format(sys.executable, sp_dir)
        packages = ['python-openid', 'pillow', 'pymongo', 'sqlalchemy', ]
        if WINDOWS_OS:
            installer = 'easy_install --upgrade '
            # TODO: "easy_install python-ldap" fails on windows. Try google: installing python-ldap in a virtualenv on windows
            # or, download from http://www.lfd.uci.edu/~gohlke/pythonlibs/#python-ldap
            #     activate.bat
            #     easy_install <path to downloaded .exe file>
        else:
            installer = 'pip install --upgrade '
            packages.append('python-ldap')
        command = ACTIVATE + installer + (SEP + installer).join(packages) + SEP + upload + SEP + oldsessions
        print 'Installing {0}, upload.py... output messages written to {1}.'.format(', '.join(packages), EXTRAS)
        with open(EXTRAS, 'w') as messages:
            subprocess.call(command, shell=True, stderr=messages, stdout=messages)
        print 'Important messages from {0} are shown below. Do "{1} log extras" to see complete log.'.format(EXTRAS, M)
        search_for_phrase(EXTRAS)

    def cmd_interwiki(self, *args):
        """refresh contrib/interwiki/intermap.txt"""
        print 'Refreshing {0}...'.format(os.path.normpath('contrib/interwiki/intermap.txt'))
        command = '{0} MoinMoin/script/win/wget.py http://master19.moinmo.in/InterWikiMap?action=raw contrib/interwiki/intermap.txt'.format(sys.executable)
        subprocess.call(command, shell=True)

    def cmd_log(self, *args):
        """View a log file with the default text editor"""

        def log_help(logs):
            """Print list of available logs to view."""
            print "usage: {0} log <target> where <target> is:\n\n".format(M)
            choices = '{0: <16}- {1}'
            for log in sorted(logs):
                if os.path.isfile(CMD_LOGS[log]):
                    print choices.format(log, CMD_LOGS[log])
                else:
                    print choices.format(log, '* file does not exist')

        logs = set(CMD_LOGS.keys())
        if args and args[0] in logs and os.path.isfile(CMD_LOGS[args[0]]):
            if WINDOWS_OS:
                command = 'start {0}'.format(CMD_LOGS[args[0]])
            else:
                # .format requires {{ and }} to escape { and }
                command = '${{VISUAL:-${{FCEDIT:-${{EDITOR:-less}}}}}} {0}'.format(CMD_LOGS[args[0]])
            subprocess.call(command, shell=True)
        else:
            log_help(logs)

    def cmd_new_wiki(self, *args):
        """create empty wiki"""
        command = '{0}moin index-create -s -i'.format(ACTIVATE)
        print 'Creating a new empty wiki...'
        make_wiki(command)  # share code with loading sample data and restoring backups

    def cmd_sample_old(self, *args):
        """
        create wiki and load sample data; obsolete, but still works with './m sample_old'

        TODO: delete this and contrib/serialized/ sometime in 2017
        """
        command = '{0}moin index-create -s -i{1} moin load --file contrib/serialized/items.moin{1} moin index-build'.format(ACTIVATE, SEP)
        print 'Creating a new wiki populated with sample data...'
        make_wiki(command)

    def cmd_sample(self, *args):
        """create wiki and load sample data"""
        # load items with non-ASCII names from a serialized backup
        command = '{0}moin index-create -s -i{1} moin load --file contrib/sample/unicode.moin'.format(ACTIVATE, SEP)
        print 'Creating a new wiki populated with sample data...'
        success = make_wiki(command, msg='\nSuccess: a new wiki has been created... working...')
        # build the index
        if success:
            command = '{0}moin index-build'.format(ACTIVATE, SEP)
            success = make_wiki(command, mode='a', msg='\nSuccess: the index has been created for the sample wiki... working...')
        # load individual items from contrib/sample, index will be updated
        if success:
            success = put_items()

    def cmd_restore(self, *args):
        """create wiki and load data from wiki/backup.moin or user specified path"""
        command = '{0} moin index-create -s -i{1} moin load --file %s{1} moin index-build'.format(ACTIVATE, SEP)
        filename = BACKUP_FILENAME
        if args:
            filename = args[0]
        if os.path.isfile(filename):
            command = command % filename
            print 'Creating a new wiki and loading it with data from {0}...'.format(filename)
            make_wiki(command)
        else:
            print 'Error: cannot create wiki because {0} does not exist.'.format(filename)

    def cmd_import(self, *args):
        """import a moin 1.9 wiki directory named dir"""
        if args:
            dirname = args[0]
            if os.path.isdir(dirname):
                command = '{0}moin import19 -s -i --data_dir {1}'.format(ACTIVATE, dirname)
                print 'Creating a new wiki populated with data from {0}...'.format(dirname)
                make_wiki(command)
            else:
                print 'Error: cannot create wiki because {0} does not exist.'.format(dirname)
        else:
            print 'Error: a path to the Moin 1.9 wiki/data data directory is required.'

    def cmd_index(self, *args):
        """delete and rebuild index"""
        if wiki_exists():
            command = '{0}moin index-create -i{1} moin index-build'.format(ACTIVATE, SEP)
            print 'Rebuilding indexes...(ignore log messages from rst parser)...'
            try:
                subprocess.call(command, shell=True)
            except KeyboardInterrupt:
                pass  # eliminates traceback on windows
        else:
            print 'Error: a wiki must be created before rebuilding the indexes.'

    def cmd_run(self, *args):
        """run built-in wiki server"""
        if wiki_exists():
            if WINDOWS_OS:
                args += ('--threaded', )
            command = '{0}moin moin {1}'.format(ACTIVATE, ' '.join(args))
            try:
                subprocess.call(command, shell=True)
            except KeyboardInterrupt:
                pass  # eliminates traceback on windows
        else:
            print 'Error: a wiki must be created before running the built-in server.'

    def cmd_backup(self, *args):
        """roll 3 prior backups and create new wiki/backup.moin or backup to user specified file"""
        if wiki_exists():
            filename = BACKUP_FILENAME
            if args:
                filename = args[0]
                print 'Creating a wiki backup to {0}...'.format(filename)
            else:
                print 'Creating a wiki backup to {0} after rolling 3 prior backups...'.format(filename)
                b3 = BACKUP_FILENAME.replace('.', '3.')
                b2 = BACKUP_FILENAME.replace('.', '2.')
                b1 = BACKUP_FILENAME.replace('.', '1.')
                if os.path.exists(b3):
                    os.remove(b3)
                for src, dst in ((b2, b3), (b1, b2), (BACKUP_FILENAME, b1)):
                    if os.path.exists(src):
                        os.rename(src, dst)

            command = '{0}moin save --all-backends --file {1}'.format(ACTIVATE, filename)
            with open(BACKUPWIKI, 'w') as messages:
                result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
            if result == 0:
                print 'Success: wiki was backed up to {0}'.format(filename)
            else:
                print 'Important messages from {0} are shown below. Do "{1} log backup" to see complete log.'.format(BACKUPWIKI, M)
                search_for_phrase(BACKUPWIKI)
                print '\nError: attempt to backup wiki failed.'
        else:
            print 'Error: cannot backup wiki because it has not been created.'

    def cmd_dump_html(self, *args):
        """create a static html dump of this wiki"""
        if wiki_exists():
            directory = DUMP_HTML_DIRECTORY
            if args:
                directory = args[0]
                print 'Creating static HTML image of wiki to {0}...'.format(directory)
            command = '{0}moin dump-html --directory {1} --theme topside_cms'.format(ACTIVATE, directory)
            with open(DUMPHTML, 'w') as messages:
                result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
            if result == 0:
                print 'Success: wiki was dumped to directory {0}'.format(directory)
            else:
                print '\nError: attempt to dump wiki to html files failed.'
            # always show errors because individual items may fail
            print 'Important messages from {0} are shown below. Do "{1} log dump-html" to see complete log.'.format(DUMPHTML, M)
            search_for_phrase(DUMPHTML)
        else:
            print 'Error: cannot dump wiki because it has not been created.'

    def cmd_css(self, *args):
        """run Stylus and lessc to update CSS files"""
        # Note: we use / below within file paths; this works in Windows XP, 2000, 7, 8, 10
        bootstrap_loc = get_bootstrap_data_location().strip() + '/less'
        pygments_loc = get_pygments_data_location().strip() + '/css'
        modernized_loc = 'MoinMoin/themes/modernized/static/css/stylus'
        basic_loc = 'MoinMoin/themes/basic/static/custom-less'

        print 'Running Stylus to update Modernized theme CSS files...'
        command = 'cd {0}{1}stylus --include {2} --include-css --compress < theme.styl > ../theme.css'.format(modernized_loc, SEP, pygments_loc)
        result = subprocess.call(command, shell=True)
        if result == 0:
            print 'Success: Modernized CSS files updated.'
        else:
            print 'Error: stylus failed to update css files, see error messages above.'
        # stylus adds too many blank lines at end of modernized theme.css, fix it by running coding_std against css directory
        command = 'python contrib/pep8/coding_std.py MoinMoin/themes/modernized/static/css'
        result = subprocess.call(command, shell=True)
        if result != 0:
            print 'Error: failure running coding_std.py against modernized css files'

        print 'Running lessc to update Basic theme CSS files...'
        if WINDOWS_OS:
            data_loc = '{0};{1}'.format(bootstrap_loc, pygments_loc)
        else:
            data_loc = '{0}:{1}'.format(bootstrap_loc, pygments_loc)
        include = '--include-path=' + data_loc
        command = 'cd {0}{1}lessc {2} theme.less ../css/theme.css'.format(basic_loc, SEP, include)
        result = subprocess.call(command, shell=True)
        if result == 0:
            print 'Success: Basic theme CSS files updated.'
        else:
            print 'Error: Basic theme CSS files update failed, see error messages above.'

    def cmd_tests(self, *args):
        """run tests, output goes to m-pytest.txt"""
        print 'Running tests... output written to {0}.'.format(PYTEST)
        command = '{0}py.test --pep8 > {1} {2} 2>&1'.format(ACTIVATE, PYTEST, ' '.join(args))
        result = subprocess.call(command, shell=True)
        print 'Important messages from {0} are shown below. Do "{1} log tests" to see complete log.'.format(PYTEST, M)
        search_for_phrase(PYTEST)

    def cmd_coding_std(self, *args):
        """correct scripts that taint the HG repository and clutter subsequent code reviews"""
        print 'Checking for trailing blanks, DOS line endings, Unix line endings, empty lines at eof...'
        command = '%s contrib/pep8/coding_std.py' % sys.executable
        subprocess.call(command, shell=True)

    def cmd_api(self, *args):
        """update Sphinx API docs, these docs are under hg version control"""
        print 'Refreshing api docs...'
        if WINDOWS_OS:
            # after update, convert DOS line endings to unix
            command = '{0}sphinx-apidoc -f -o docs/devel/api MoinMoin & {1} MoinMoin/script/win/dos2unix.py docs/devel/api'.format(ACTIVATE, sys.executable)
        else:
            command = '{0}sphinx-apidoc -f -o docs/devel/api MoinMoin'.format(ACTIVATE)
        result = subprocess.call(command, shell=True)

    # not on menu, rarely used, similar code was in moin 1.9
    def cmd_dist(self, *args):
        """create distribution archive in dist/"""
        print 'Deleting wiki data, then creating distribution archive in /dist, output written to {0}.'.format(DIST)
        self.cmd_del_wiki(*args)
        command = '{0} setup.py sdist'.format(sys.executable)
        with open(DIST, 'w') as messages:
            result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
        print 'Summary message from {0} is shown below:'.format(DIST)
        search_for_phrase(DIST)
        if result == 0:
            print 'Success: a distribution archive was created in {0}.'.format(os.path.normpath('/dist'))
        else:
            print 'Error: create dist failed with return code = {0}. Do "{1} log dist" to see complete log.'.format(result, M)

    def cmd_del_all(self, *args):
        """same as running the 4 del-* commands below"""
        self.cmd_del_orig(*args)
        self.cmd_del_pyc(*args)
        self.cmd_del_rej(*args)
        self.cmd_del_wiki(*args)

    def cmd_del_orig(self, *args):
        """delete all files matching *.orig"""
        delete_files('*.orig')

    def cmd_del_pyc(self, *args):
        """delete all files matching *.pyc"""
        delete_files('*.pyc')

    def cmd_del_rej(self, *args):
        """delete all files matching *.rej"""
        delete_files('*.rej')

    def cmd_del_wiki(self, *args):
        """create a just-in-case backup, then delete all wiki data"""
        command = '{0}moin save --all-backends --file {1}'.format(ACTIVATE, JUST_IN_CASE_BACKUP)
        if wiki_exists():
            print 'Creating a backup named {0}; then deleting all wiki data and indexes...'.format(JUST_IN_CASE_BACKUP)
            with open(DELWIKI, 'w') as messages:
                result = subprocess.call(command, shell=True, stderr=messages, stdout=messages)
            if result != 0:
                print 'Error: backup failed with return code = {0}. Complete log is in {1}.'.format(result, DELWIKI)
        # destroy wiki even if backup fails
        if os.path.isdir('wiki/data') or os.path.isdir('wiki/index'):
            shutil.rmtree('wiki/data')
            shutil.rmtree('wiki/index')
            print 'Wiki data successfully deleted.'
        else:
            print 'Wiki data not deleted because it does not exist.'


if __name__ == '__main__':
    # create a set of valid menu choices
    commands = Commands()
    choices = set()
    names = dir(commands)
    for name in names:
        if name.startswith('cmd_'):
            choices.add(name)

    if len(sys.argv) == 1 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
        print help
    else:
        if sys.argv[1] != 'quickinstall' and not (os.path.isfile('activate') or os.path.isfile('activate.bat')):
            print 'Error: files created by quickinstall are missing, run "%s quickinstall" and try again.' % M
        else:
            choice = 'cmd_%s' % sys.argv[1]
            choice = choice.replace('-', '_')
            if choice in choices:
                choice = getattr(commands, choice)
                choice(*sys.argv[2:])
            else:
                print help
                print 'Error: unknown menu selection "%s"' % sys.argv[1]
