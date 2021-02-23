# -*- encoding: utf-8 -*-
import argparse
import attr
import glob
import logging
import os
import semantic_version
import subprocess
import sys
import yaml

from git import Repo
from pkg_resources import safe_name
from rich import print as rprint
from rich.prompt import Prompt
from urllib.parse import urlparse
from walkdir import filtered_walk


FILENAME_SETUP_YAML = "setup.yaml"
GIT_COMMIT_COUNT = 30
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s: %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


@attr.s
class App:
    name = attr.ib()
    branch = attr.ib()
    tag = attr.ib()
    semantic_version = attr.ib()


class KbError(Exception):
    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr("%s, %s" % (self.__class__.__name__, self.value))


class Release:
    TESTING = False
    YAPSY_PLUGIN_EXT = "yapsy-plugin"

    def __init__(self, prefix, pypi):
        self.prefix = prefix
        self.pypi = pypi

    def _check_is_project_or_app(self):
        """An app should have an 'project' folder or an 'example' folder."""
        rprint("[yellow]check is app or project...")
        found = False
        for name in ("project", "example"):
            folder = _wildcard_folder(name)
            if folder:
                found = True
                break
        if not found:
            abort("Not a project or app (need a 'project' or 'example' folder)")

    def _check_requirements(self, is_project):
        if is_project:
            rprint("[yellow]check requirements...")
            file_name = os.path.join(
                os.getcwd(), "requirements-{}.txt".format(prefix)
            )
            if os.path.exists(file_name):
                with open(file_name) as f:
                    content = f.readlines()
                rprint(
                    "[white]Please check the app version numbers for this project:"
                )
                for line in content:
                    name, version = line.strip().split("==")
                    if name and version:
                        rprint("[cyan]{:<30} {:<10}".format(name, version))
                    else:
                        msg = (
                            "Dependency in '{0}' does not have a name and "
                            "version number: {1}".format(file_name, line)
                        )
                        rprint("[red]{}".format(msg))
                        raise KbError(msg)
                confirm = ""
                while confirm not in ("Y", "N"):
                    confirm = prompt(
                        "Are these the correct dependencies and versions (Y/N)?"
                    )
                    confirm = confirm.strip().upper()
                if not confirm == "Y":
                    abort(
                        "Please check and correct the dependencies and their versions..."
                    )

    def _check_scm_status(self):
        rprint("[yellow]check version control status...")
        scm = Scm(os.getcwd())
        status = scm.get_status()
        for name in status:
            if name not in ("kb.py", "setup.py"):
                msg = (
                    "The following files have not been committed:\n{0}".format(
                        status
                    )
                )
                rprint("[red]{}".format(msg))
                raise KbError(msg)

    def _commit_and_tag(self, version):
        rprint("[yellow]version control - commit and tag...")
        scm = Scm(os.getcwd())
        scm.commit_and_tag(version)

    def _get_description(self):
        rprint("[yellow]get description...")
        check_setup_yaml_exists()
        with open(FILENAME_SETUP_YAML) as f:
            data = yaml.safe_load(f)
        if not "description" in data:
            abort("Package 'description' not found in 'setup.yaml'")
        return data["description"]

    def _get_name(self):
        check_setup_yaml_exists()
        with open(FILENAME_SETUP_YAML) as f:
            data = yaml.safe_load(f)
        if not "name" in data:
            abort("Package 'name' not found in 'setup.yaml'")
        return data["name"]

    def _get_next_version(self, current_version):
        elems = current_version.split(".")
        if not len(elems) == 3:
            msg = "Current version number should contain only three sections: {}".format(
                current_version
            )
            rprint("[red]{}".format(msg))
            raise KbError(msg)
        for e in elems:
            if not e.isdigit():
                msg = "Current version number should only contain numbers: {}".format(
                    current_version
                )
                rprint("[red]{}".format(msg))
                raise KbError(msg)
        return "{}.{}.{:02d}".format(elems[0], elems[1], int(elems[2]) + 1)

    def _get_package_data(self, packages):
        rprint("[yellow]get package data...")
        result = {}
        for package in packages:
            if os.path.exists(package) and os.path.isdir(package):
                for folder_name in os.listdir(package):
                    if folder_name in ("data", "static", "templates"):
                        folder = os.path.join(package, folder_name)
                        if os.path.isdir(folder):
                            walk = filtered_walk(folder)
                            for path, subdirs, files in walk:
                                if package not in result:
                                    result[package] = []
                                # remove package folder name
                                result[package].append(
                                    os.path.join(*path.split(os.sep)[1:])
                                )
        return result

    def _get_packages(self):
        rprint("[yellow]get packages...")
        excluded_dirs = [
            ".git",
            ".hg",
            "dist",
            "front",
            "node_modules",
            "shiny",
            "templates",
            "venv-*",
        ]
        example_folder = _wildcard_folder("example")
        if example_folder:
            excluded_dirs.append(example_folder)
        walk = filtered_walk(
            ".", included_files=["__init__.py"], excluded_dirs=excluded_dirs
        )
        result = []
        for path, subdirs, files in walk:
            if len(files):
                path = path.replace(os.sep, ".").strip(".")
                if path:
                    result.append("{0}".format(path))
        app_names = ["app"]
        if example_folder:
            app_names.append(example_folder)
        for name in app_names:
            if name in result:
                result.remove(name)
                result.insert(0, name)
        return result

    def _get_scm_config(self):
        rprint("[yellow]get version control config...")
        scm = Scm(os.getcwd())
        return scm.get_config()

    def _get_version(self):
        check_setup_yaml_exists()
        with open(FILENAME_SETUP_YAML) as f:
            data = yaml.safe_load(f)
        current_version = data["version"]
        next_version = self._get_next_version(current_version)
        version = input
        version = Prompt.ask(
            "Version number to release (previous {})".format(current_version),
            default=next_version,
        )
        version = self._validate_version(version)
        data["version"] = version
        if not self.TESTING:
            with open(FILENAME_SETUP_YAML, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        rprint("[green]Release version: {0}".format(version))
        return version

    def _has_project_package(self, packages):
        if "project" in packages:
            return True
        return False

    def _validate_version(self, version):
        elem = version.split(".")
        for e in elem:
            if not e.isdigit():
                raise Exception(
                    "Not a valid version number: {0} (should contain only digits)".format(
                        version
                    )
                )
        if not len(elem) == 3:
            raise Exception(
                "Not a valid version number: {0} (should contain three elements)".format(
                    version
                )
            )
        confirm = Prompt.ask(
            "Please confirm you want to release version {0} (Y/N)".format(
                version
            ),
            choices=["Y", "N"],
            default="N",
        )
        # confirm = ""
        # while confirm not in ("Y", "N"):
        #     confirm = prompt(
        #         "Please confirm you want to release version {0} (Y/N)".format(
        #             version
        #         )
        #     )
        #     confirm = confirm.strip().upper()
        if confirm == "Y":
            return version
        else:
            raise Exception("Please re-enter the version number")

    def _write_manifest_in(self, is_project, packages):
        rprint("[yellow]write MANIFEST.in...")
        folders = ["doc_src", "docs"]
        for p in packages:
            if not "." in p:
                folders = folders + [
                    os.path.join("{0}".format(p), "static"),
                    os.path.join("{0}".format(p), "templates"),
                ]
        content = []
        for f in folders:
            folder = os.path.join(os.getcwd(), f)
            if os.path.exists(folder) and os.path.isdir(folder):
                content.append("recursive-include {0} *".format(f))
        content = content + ["", "include LICENSE"]
        if is_project:
            content.append("include manage.py")
        content = content + [
            "include README",
            "include requirements/*.txt",
            "include *.txt",
            "",
        ]
        # .yapsy-plugin
        walk = filtered_walk(
            ".", included_files=["*.{}".format(self.YAPSY_PLUGIN_EXT)]
        )
        for path, subdirs, files in walk:
            if files:
                content = content + [
                    "include {}/*.{}".format(path[2:], self.YAPSY_PLUGIN_EXT)
                ]
        # example folder
        example_folder = _wildcard_folder("example")
        if example_folder:
            content = content + ["prune {}/".format(example_folder)]
        with open("MANIFEST.in", "w") as f:
            f.write("\n".join(content))

    def _write_setup(
        self,
        name,
        packages,
        package_data,
        version,
        url,
        author,
        email,
        description,
        prefix,
    ):
        """
        Prefix name so 'pip' doesn't get confused with packages on PyPI
        """
        rprint("[yellow]write setup.py...")
        content = """import os
from distutils.core import setup


def read_file_into_string(filename):
    path = os.path.abspath(os.path.dirname(__file__))
    filepath = os.path.join(path, filename)
    try:
        return open(filepath).read()
    except IOError:
        return ''


def get_readme():
    for name in ('README', 'README.rst', 'README.md'):
        if os.path.exists(name):
            return read_file_into_string(name)
    return ''


setup(
    name='%s-%s',
    packages=%s,%s
    version='%s',
    description='%s',
    author='%s',
    author_email='%s',
    url='%s',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Framework :: Django :: 1.8',
        'Topic :: Office/Business :: Scheduling',
    ],
    long_description=get_readme(),
)"""
        packages_delim = []
        for p in packages:
            packages_delim.append("'{0}'".format(p))
        data = ""
        if package_data:
            data = "\n    package_data={"
            for p, folders in package_data.items():
                data = data + "\n{}'{}': [\n".format(" " * 8, p)
                folders.sort()
                for f in folders:
                    data = data + "{}'{}',\n".format(
                        " " * 12, os.path.join(f, "*.*")
                    )
                data = data + "{}],\n".format(" " * 8)
            data = data + "    },"
        with open("setup.py", "w") as f:
            f.write(
                content
                % (
                    prefix,
                    safe_name(name),
                    "[{0}]".format(", ".join(packages_delim)),
                    data,
                    version,
                    description,
                    author,
                    email,
                    url,
                )
            )

    def release(self):
        if not self.prefix:
            msg = "Cannot release a project without a 'prefix'"
            rprint("[red]{}".format(msg))
            raise KbError(msg)
        self._check_is_project_or_app()
        url, user, email = self._get_scm_config()
        if not self.TESTING:
            self._check_scm_status()
        description = self._get_description()
        packages = self._get_packages()
        package_data = self._get_package_data(packages)
        is_project = self._has_project_package(packages)
        name = self._get_name()
        self._check_requirements(is_project)
        version = self._get_version()
        self._write_manifest_in(is_project, packages)
        self._write_setup(
            name,
            packages,
            package_data,
            version,
            url,
            user,
            email,
            description,
            self.prefix,
        )
        if not self.TESTING:
            self._commit_and_tag(version)
            # command = "python setup.py clean sdist upload -r {}".format(
            #    self.pypi
            # )
            rprint("[blue]clean sdist upload...")
            try:
                result = subprocess.run(
                    [
                        "python",
                        "setup.py",
                        "clean",
                        "sdist",
                        "upload",
                        "-r",
                        self.pypi,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    rprint("[green]sucess...")
                else:
                    for x in result.stderr.split("\n"):
                        rprint("[red]{}".format(x))
                    raise KbError("Failed to run the 'sdist upload' process")
            except Exception as e:
                raise KbError("Failed to run the 'sdist upload' process", e)


class Scm:
    def __init__(self, folder):
        self.folder = folder
        self._is_hg = self.is_mercurial()
        if not self._is_hg:
            if not self.is_git():
                raise KbError(
                    "Must be a Mercurial or GIT repository: {}".format(
                        self.folder
                    )
                )

    def _get_hg_repo(self):
        # return hgapi.Repo(self.folder)
        pass

    def _get_git_repo(self):
        return Repo(self.folder)

    def is_git(self):
        try:
            self._get_git_repo()
            return True
        except InvalidGitRepositoryError:
            return False

    def is_mercurial(self):
        """None of our repositories are using Mercurial."""
        return False
        # result = False
        # repo = self._get_hg_repo()
        # try:
        #     repo.hg_status()
        #     result = True
        # except hgapi.HgException as ev:
        #     if not 'no repository found' in ev.message:
        #         raise TaskError(
        #             "Unexpected exception thrown by 'hg_status': {}".format(
        #                 ev.message
        #             )
        #         )
        # return result

    def get_config(self):
        if self._is_hg:
            repo = self._get_hg_repo()
            path = repo.config("paths", "default")
            username = repo.config("ui", "username")
            pos_start = username.find("<")
            pos_end = username.find(">")
            author = username[:pos_start].strip()
            email = username[pos_start + 1 : pos_end]
            if "bitbucket" in path:
                result = path, author, email
            else:
                raise KbError(
                    "Cannot find bitbucket path to repository: {0}".format(path)
                )
        else:
            repo = self._get_git_repo()
            if len(repo.remotes) == 1:
                remote = repo.remotes[0]
                path = remote.url
                name = repo.config_reader(config_level="global").get(
                    "user", "name"
                )
                email = repo.config_reader(config_level="global").get(
                    "user", "email"
                )
                result = path, name, email
            else:
                raise KbError(
                    "GIT repo has more than one remote.  Don't know what to do!"
                )
        return result

    def get_status(self):
        result = []
        if self._is_hg:
            repo = self._get_hg_repo()
            for status, files in repo.hg_status().iteritems():
                for name in files:
                    result.append(name)
        else:
            repo = self._get_git_repo()
            out = repo.git.status("--porcelain")
            for line in out.splitlines():
                name = line.strip()
                pos = name.find(" ")
                if pos == -1:
                    raise KbError(
                        "GIT status filename does not contain a space: {}".format(
                            line
                        )
                    )
                result.append(name[pos + 1 :])
        return result

    def commit_and_tag(self, version):
        status = self.get_status()
        for name in status:
            pos = name.find(" ")
            if pos > -1:
                raise KbError(
                    "Version control 'status' - filename contains a space: {}".format(
                        name
                    )
                )
        if len(self.get_status()):
            message = "version {0}".format(version)
            tag = "{0}".format(version)
            if self._is_hg:
                repo = self._get_hg_repo()
                repo.hg_commit(message)
                repo.hg_tag(tag)
            else:
                repo = self._get_git_repo()
                index = repo.index
                index.add(status)
                index.commit(message)
                repo.create_tag(tag)


def _wildcard_folder(prefix):
    """
    Search the current folder for a directory where the name starts with
    'prefix'.  Check there is just one folder starting with that name and
    return the actual name without the path e.g::

    folder = _wildcard_folder('example')
    if folder:
        print(folder)
        # 'example-block'
    """
    result = None
    folder = os.path.join(os.getcwd(), prefix)
    match = glob.glob("{}*".format(folder))
    match_count = len(match)
    if match_count == 1:
        found = match[0]
        if os.path.isdir(found):
            result = os.path.basename(found)
    elif match_count > 1:
        abort("Found more than one folder starting with: '{}'".format(prefix))
    return result


def app_name(name):
    return name.replace("-", "_")


def app_to_folder(name):
    return name.replace("_", "-")


def apps_equal(x_apps, y_apps, x_caption, y_caption):
    result_a = set([x.name for x in x_apps]) - set([y.name for y in y_apps])
    result_b = set([y.name for y in y_apps]) - set([x.name for x in x_apps])
    if result_a or result_b:
        print([x.name for x in x_apps])
        print([y.name for y in y_apps])
        raise KbError(
            "'{}' has different apps to '{}': {}".format(
                x_caption, y_caption, result_a or result_b
            )
        )
    else:
        logger.info(
            "'{}' has the same apps as '{}'".format(x_caption, y_caption)
        )


def branch_is_equal(app, repo, checkout):
    result = False
    try:
        if app.branch == repo.active_branch.name:
            result = True
        elif checkout:
            logger.info("'{}' checkout '{}'".format(app.name, app.branch))
            if repo.is_dirty():
                raise KbError(
                    "'{}', branch {} has changes ('is_dirty')".format(
                        app.name, repo.active_branch.name
                    )
                )
            else:
                repo.git.checkout(app.branch)
            result = app.branch == repo.active_branch.name
    except TypeError as e:
        raise KbError(
            "app '{}', branch '{}': {}".format(app.name, app.branch, str(e))
        )
    return result


def branches_equal(x_apps, y_apps, x_caption, y_caption):
    x_data = set(["{}@{}".format(x.name, x.branch) for x in x_apps])
    y_data = set(["{}@{}".format(y.name, y.branch) for y in y_apps])
    result_a = x_data - y_data
    result_b = y_data - x_data
    if result_a or result_b:
        raise KbError(
            "'{}' has different branches to '{}': {}".format(
                x_caption, y_caption, result_a or result_b
            )
        )
    else:
        logger.info(
            "'{}' has the same branches as '{}'".format(x_caption, y_caption)
        )


def branch():
    result = []
    with open(os.path.join("requirements", "branch.txt")) as f:
        for line in f:
            name, branch = line.strip().split("|")
            result.append(
                App(
                    name=app_name(name),
                    branch=branch,
                    tag=None,
                    semantic_version=None,
                )
            )
    return result


def check_setup_yaml_exists():
    """ The file, 'setup.yaml' looks like the 'sample_data' below: """
    if not os.path.exists(FILENAME_SETUP_YAML):
        sample_data = {
            "description": "User Auth",
            "name": "user-auth",
            "version": "0.2.0",
        }
        msg = "File '{0}' does not exist.  Please create in the following format:\n{1}".format(
            FILENAME_SETUP_YAML,
            yaml.dump(sample_data, default_flow_style=False),
        )
        raise KbError(msg)


def ci():
    """Parse the CI requirements.

    Example::

      -r base.txt
      -e .
      -e git+https://gitlab.com/kb/base.git#egg=base
      pytest-django

    """
    result = []
    with open(os.path.join("requirements", "ci.txt")) as f:
        for line in f:
            branch = None
            pos = line.find("http")
            if pos == -1:
                pass
            else:
                url = line[pos:]
                p = urlparse(url)
                pos = p.path.find("@")
                if pos == -1:
                    # no branch name e.g. '@3189-lms-models'
                    branch = "master"
                else:
                    branch = p.path[pos + 1 :]
                # find the app name e.g. '/kb/exam.git@3189-lms-models'
                pos_sla = p.path.rfind("/")
                pos_dot = p.path.rfind(".")
                name = p.path[pos_sla + 1 : pos_dot]
                result.append(
                    App(
                        name=app_name(name),
                        branch=branch,
                        tag=None,
                        semantic_version=None,
                    )
                )
    return result


def get_is_project():
    is_app = is_project = False
    current_folder = os.path.dirname(os.path.realpath(__file__))
    if "/app/" in current_folder:
        is_app = True
    if "/project/" in current_folder:
        is_project = True
    if is_app and is_project:
        raise Exception(
            "Cannot decide if this is an app or a project: {}".format(
                current_folder
            )
        )
    return is_project


def git(apps_with_branch, apps_with_tag, is_project, checkout, pull):
    """Check each app is on the expected branch."""
    tags = {x.name: x.semantic_version for x in apps_with_tag}
    for app in apps_with_branch:
        repo = git_repo(app)
        if branch_is_equal(app, repo, checkout):
            # only check tags if this is a project
            if is_project:
                first = None
                found = False
                outstanding = []
                tag_to_find = tags[app.name]
                if pull:
                    print("pulling from {}".format(app.name))
                    fetch_info = repo.remotes.origin.pull()
                    for x in fetch_info:
                        if x.note:
                            print("  {}".format(x.note))
                # PJK 06/05/2019, For some reason tags are not appearing.
                # We should check the fabric scripts to find out why.
                # for tag in repo.tags:
                #    if tag.commit in commits and tag.name == tag_to_find:
                #        found = True
                #        break
                # check commit messages to try and find the version number
                commits = list(
                    repo.iter_commits(app.branch, max_count=GIT_COMMIT_COUNT)
                )
                for commit in commits:
                    if commit.message.startswith("version "):
                        pos = commit.message.find(" ")
                        if pos == -1:
                            raise Exception(
                                "The commit message has a space, but we "
                                "can't find it: {}".format(commit.message)
                            )
                        else:
                            semver = tag_to_semver(commit.message[pos + 1 :])
                            if semver == tag_to_find:
                                found = True
                                if first and first > semver:
                                    print(
                                        "* Warning: version {} of '{}' has "
                                        "been released. You are using version "
                                        "{}.".format(first, app.name, semver)
                                    )
                                if outstanding:
                                    print(
                                        "* Warning: there are {} changes on {} "
                                        "which have not been released.".format(
                                            len(outstanding), app.name
                                        )
                                    )
                                    for count, x in enumerate(outstanding, 1):
                                        first_line = x.split("\n")[0].strip()
                                        print(
                                            "  {}. {}".format(count, first_line)
                                        )
                                break
                            if not first:
                                first = semver
                    outstanding.append(
                        "{} ({})".format(commit.message.strip(), commit.author)
                    )
                if not found:
                    raise Exception(
                        "Cannot find tag '{}' on the '{}' branch of "
                        "'{}'".format(
                            tag_to_find, app.branch, app_to_folder(app.name)
                        )
                    )
        else:
            raise Exception(
                "Expecting the '{}' app to be on the '{}' branch but it is "
                "on '{}'".format(app.name, app.branch, repo.active_branch)
            )


def git_repo(app):
    folder = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "..",
            "..",
            "app",
            app_to_folder(app.name),
        )
    )
    if os.path.exists(folder):
        return Repo(folder)
    else:
        raise Exception("App folder does not exist: {}".format(folder))


def local(is_project):
    """Parse the local requirements.

    Example::

      -r base.txt
      -e .
      -e ../../app/base
      black

    """
    result = []
    with open(os.path.join("requirements", "local.txt")) as f:
        for line in f:
            if is_project:
                token = "/app/"
            else:
                token = "../"
            pos = line.find(token)
            if pos == -1:
                pass
            else:
                name = line[pos + len(token) :].strip()
                result.append(
                    App(
                        name=app_name(name),
                        branch=None,
                        tag=None,
                        semantic_version=None,
                    )
                )
    return result


def production():
    """Parse the production requirements.

    Example::

      kb-base==0.2.55

    """
    result = []
    with open(os.path.join("requirements", "production.txt")) as f:
        for line in f:
            pos_dash = line.find("kb-")
            pos_equal = line.find("==")
            if pos_dash == -1:
                pass
            else:
                name = line[pos_dash + 3 : pos_equal]
                tag = line[pos_equal + 2 :].strip()
                result.append(
                    App(
                        name=app_name(name),
                        branch=None,
                        tag=tag,
                        semantic_version=tag_to_semver(tag),
                    )
                )
    return result


def tag_to_semver(tag):
    """Convert a KB version number e.g. '0.2.05' to a semantic version.

    .. note: The KB version numbers are invalid
             e.g. the number should not contain leading zeros
             - so ``0.2.05`` should be ``0.2.5``.

    """
    major, minor, patch = tag.split(".")
    return semantic_version.Version(
        major=int(major), minor=int(minor), patch=int(patch)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check the requirements for your project or app"
    )
    parser.add_argument(
        "--checkout",
        action="store_true",
        help="pull the latest app code from git",
    )
    parser.add_argument(
        "--pull", action="store_true", help="pull the latest app code from git"
    )
    parser.add_argument(
        "--release", action="store_true", help="release the app (or project)"
    )
    parser.add_argument("--prefix", help="prefix for the company e.g. 'kb'")
    parser.add_argument(
        "--pypi", help="the name of the pypi in your '~/.pypirc' file"
    )
    args = parser.parse_args()
    if args.pull:
        print("  pulling the latest app code from git...")
    if args.release:
        if not args.prefix:
            exit("'release' requires the company prefix")
        if not args.pypi:
            exit("'release' requires the pypi name")
    is_project = get_is_project()
    ci_apps = ci()
    branch_apps = branch()
    local_apps = local(is_project)
    if is_project:
        production_apps = production()
    else:
        production_apps = []
    # check
    apps_equal(ci_apps, branch_apps, "ci.txt", "branch.txt")
    apps_equal(ci_apps, local_apps, "ci.txt", "local.txt")
    if is_project:
        apps_equal(ci_apps, production_apps, "ci.txt", "production.txt")
    branches_equal(ci_apps, branch_apps, "ci.txt", "branch.txt")
    git(ci_apps, production_apps, is_project, args.checkout, args.pull)
    if not is_project:
        logger.info(
            "Note: This is an 'app', so we are not checking 'production.txt'"
        )
    logger.info("All looking good :)")
    if args.release:
        Release(args.prefix, args.pypi).release()
