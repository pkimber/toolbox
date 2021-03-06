# -*- encoding: utf-8 -*-
import argparse
import attr
import logging
import os
import semantic_version

from git import Repo
from urllib.parse import urlparse


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s: %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)
GIT_COMMIT_COUNT = 30


@attr.s
class App:
    name = attr.ib()
    branch = attr.ib()
    tag = attr.ib()
    semantic_version = attr.ib()


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
        raise Exception(
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
                raise Exception(
                    "'{}', branch {} has changes ('is_dirty')".format(
                        app.name, repo.active_branch.name
                    )
                )
            else:
                repo.git.checkout(app.branch)
            result = app.branch == repo.active_branch.name
    except TypeError as e:
        raise Exception(
            "app '{}', branch '{}': {}".format(app.name, app.branch, str(e))
        )
    return result


def branches_equal(x_apps, y_apps, x_caption, y_caption):
    x_data = set(["{}@{}".format(x.name, x.branch) for x in x_apps])
    y_data = set(["{}@{}".format(y.name, y.branch) for y in y_apps])
    result_a = x_data - y_data
    result_b = y_data - x_data
    if result_a or result_b:
        raise Exception(
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
    args = parser.parse_args()
    if args.pull:
        print("  pulling the latest app code from git...")
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
