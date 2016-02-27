#!/usr/bin/env python3
"""
A LaTeX change tracking tool.

File: zaphod.py

Copyright 2016 Ankur Sinha
Author: Ankur Sinha <sanjay DOT ankur AT gmail DOT com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import sys
import textwrap
import subprocess
import os
import fnmatch
import re
import datetime
import shutil


class _HelpAction(argparse._HelpAction):

    """
    Custom help handler.

    http://stackoverflow.com/a/24122778/375067
    """

    def __call__(self, parser, namespace, values, option_string=None):
        """Custom call method."""
        parser.print_help()
        print("\n")

        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)]
        for subparsers_action in subparsers_actions:
            for choice, subparser in subparsers_action.choices.items():
                print("Subcommand: '{}'".format(choice))
                print(subparser.format_help())


class Zaphod:

    """Something something."""

    def __init__(self):
        """Init method."""
        self.usage_message = textwrap.dedent(
            """
        NOTES:
            The idea of this program is to help LaTeX users track, review, and
            see changes that have been made in their source files. The script
            only works when git is used as a version control system.

        Expected workflow:
            *) Make changes, commit
            *) Run this program:
                It will generate a pdf with differences between the two
                provided Git revisions using latexdiff. It will also commit the
                annotated TeX sources in a new Git branch called "changes".
                *) Review commits using generated PDF.
                *) Accept/ignore changes.
                *) Commit once finished.
                *) Merge to master branch.
                *) Profit.

        Requires:
            *) latexdiff
            *) Git
            *) pdflatex
            *) bibtex
            *) Python3

            """)

        self.commandList = ["pdflatex", "latexdiff", "git"]
        self.timenow = datetime.datetime.strftime(datetime.datetime.today(),
                                                  "%Y%m%d%H%M")
        self.rev1Branch = self.timenow + "-latexdiff-rev1"
        self.rev2Branch = self.timenow + "-latexdiff-rev2"
        self.finalBranch = self.timenow + "-latexdiff-annotated"

        self.filelist = []
        self.rev1filelist = []
        self.rev2filelist = []
        self.modifiedfiles = []

        self.gitResetCommand = "git reset HEAD --hard".split()
        self.gitCheckoutCommand = "git checkout".split()
        self.gitAddCommand = "git add .".split()
        self.gitCommitCommand = "git commit -m".split()
        self.pdflatexCommand = "pdflatex -interaction batchmode".split()
        self.bibtexCommand = ["bibtex"]

        # regular expressions for revision
        self.rpDelbegin = re.compile(r'\\DIFdelbegin\s*')
        self.rpDelend = re.compile(r'\\DIFdelend\s*')

        self.rpAddbegin = re.compile(r'\\DIFaddbegin\s*')
        self.rpAddend = re.compile(r'\\DIFaddend\s*')

        self.rpPreamble = (r'%DIF PREAMBLE EXTENSION ADDED BY LATEXDIFF.*' +
                           r'%DIF END PREAMBLE EXTENSION ADDED BY LATEXDIFF\n')
        self.rpStray = (r'(\\DIFaddbegin\s*)|(\\DIFaddend\s*)' +
                        r'(\\DIFdelbegin\s*)|(\\DIFdelend\s*)')

    def diff(self, args):
        """Do the diff part."""
        print("Generating full file list.")
        # Get all latex files in rev1
        command = (self.gitCheckoutCommand + (" -b " +
                                              self.rev1Branch).split() +
                   [self.optionsDict['rev1']])
        p = subprocess.Popen(command)
        p.wait()
        self.filelist += self.get_latex_files()

        # Get all latex files in rev2
        command = (self.gitCheckoutCommand + (" -b " +
                                              self.rev2Branch).split() +
                   [self.optionsDict['rev2']])
        p = subprocess.Popen(command)
        p.wait()
        self.filelist += self.get_latex_files()
        # remove duplicates
        self.filelist = list(set(self.filelist))
        print("File list generated:\n{}".format(self.filelist))

        # Now that we have a complete list, we get to work
        print("Checking out revision 1: {}".format(self.optionsDict['rev1']))
        command = (self.gitCheckoutCommand + [self.rev1Branch])
        p = subprocess.Popen(command)
        p.wait()
        self.rev1filelist = self.generate_rev_filenames(
            self.optionsDict['rev1'])

        # Rename files
        for i in range(0, len(self.filelist)):
            # if a file doesn't exist in this revision, it has been removed, so
            # I create an empty file for latexdiff
            if not os.path.isfile(self.filelist[i]):
                open(self.filelist[i], 'a').close()
            os.rename(self.filelist[i], self.rev1filelist[i])

        # Check out revision 2
        print("Checking out revision 2: {}".format(self.optionsDict['rev2']))
        command = (self.gitCheckoutCommand + [self.rev2Branch])
        p = subprocess.Popen(command)
        p.wait()

        # Reset the state so that the files we deleted earlier are back
        subprocess.call(self.gitResetCommand)

        print("Checking out branch to save changes.")
        command = (self.gitCheckoutCommand + (" -b " +
                                              self.finalBranch).split() +
                   [self.rev2Branch])
        subprocess.call(command)

        self.rev2filelist = self.generate_rev_filenames(
            self.optionsDict['rev2'])
        # Rename files
        for i in range(0, len(self.filelist)):
            if not os.path.isfile(self.filelist[i]):
                open(self.filelist[i], 'a').close()
            os.rename(self.filelist[i], self.rev2filelist[i])

        # Generate diffs
        for i in range(0, len(self.filelist)):
            command = (["latexdiff"] + ("--type=" + self.optionsDict['type'] +
                                        " --exclude-textcmd=" +
                                        self.optionsDict['exclude']).split() +
                       [self.rev1filelist[i], self.rev2filelist[i]])
            print(command)
            changedtext = None
            changedtext = subprocess.check_output(command)
            if changedtext is None:
                print("Something went wrong " +
                      "- not modifying file: {}\n".format(self.filelist[i]) +
                      "Exiting!", file=stderr)
            else:
                newfile = open(self.filelist[i], 'w')
                newfile.write(changedtext.decode("ascii"))
                newfile.close()

            os.remove(self.rev1filelist[i])
            os.remove(self.rev2filelist[i])

        self.generate_pdf("diff-" + self.optionsDict['rev1'] + "-" +
                          self.optionsDict['rev2'])

        subprocess.call(self.gitAddCommand)

        command = (self.gitCommitCommand + ["Save annotated changes between " +
                                            self.optionsDict['rev1'] + " and "
                                            + self.optionsDict['rev2']])
        subprocess.call(command)

        print("\nCOMPLETE: The following branches have been created:\n" +
              self.rev1Branch + ": Revision 1.\n" +
              self.rev2Branch + ": Revision 2.\n" +
              self.finalBranch +
              ": Branch with annotated versions of sources and diff pdf.\n")

    def revise(self, args):
        """Do the revise part."""
        self.filelist = self.get_modified_latex_files()
        while len(self.filelist) > 0:
            while True:
                print("LaTeX files with annotations:")
                for i in range(0, len(self.filelist)):
                    print("[{}] {}".format(i+1, self.filelist[i]))
                print()
                filenumber = input("Pick file to revise? " +
                                   "1-{}/Q/q: ".format(len(self.filelist)))

                if filenumber.isalpha():
                    if filenumber == 'Q' or filenumber == 'q':
                        self.generate_pdf("accepted")
                        self.save_changes()

                if filenumber.isdigit():
                    filenumber = int(filenumber)
                else:
                    print("\nInvalid input. Please try again.",
                          file=sys.stderr)
                    continue

                if filenumber > 0 and filenumber <= len(self.filelist):
                    break
                else:
                    print("\nInvalid input. Please try again.",
                          file=sys.stderr)

            filetorevise = self.filelist[filenumber - 1]
            filetext = ""
            revisedfiletext = ""
            # Token at the head of a token
            head = 0
            # Token at the tail of previous token
            tail = 0
            with open(filetorevise, "r") as thisfile:
                filetext = thisfile.read()

            # Replace preamble additions
            filetext = re.sub(pattern=self.rpPreamble,
                              repl='',
                              string=filetext,
                              flags=re.DOTALL)

            print("Working on file: {}.".format(filetorevise))
            while head < len(filetext):
                # what's next - addition or deletion?
                del_start = 0
                delcheck = self.rpDelbegin.search(filetext[head:])
                add_start = 0
                addcheck = self.rpAddbegin.search(filetext[head:])
                if delcheck is None:
                    del_start = len(filetext)
                else:
                    del_start = delcheck.start()
                if addcheck is None:
                    add_start = len(filetext)
                else:
                    add_start = addcheck.start()

                # If both are at EOL
                if add_start == del_start:
                    revisedfiletext += filetext[head:]
                    # print("{}, {}".format(del_start, add_start))
                    break

                if del_start < add_start:
                    # It's a deletion
                    head = del_start + tail
                    revisedfiletext += filetext[tail:head]
                    tail = (self.rpDelbegin.search(filetext[head:]).end() +
                            head)
                    head = (self.rpDelend.search(filetext[tail:]).start() +
                            tail)
                    deletion = filetext[tail:head]
                    deletion = re.sub(r'\\DIFdel\{(.*?)\}', r'\1', deletion,
                                      flags=re.DOTALL)
                    print("======\nFile under revision: {}".format(
                        filetorevise))
                    print("Deletion found:\n---\n{}\n---".format(deletion))
                    while True:
                        userinput = input("Delete? Y/N/Q/y/n/q: ")
                        if not userinput.isalpha():
                            print("\nInvalid input. Try again.\n")
                            continue

                        if userinput == "Y" or userinput == "y":
                            print("Deleted.")
                            break
                        elif userinput == "N" or userinput == "n":
                            print("Skipped.")
                            revisedfiletext += deletion
                            break
                        elif userinput == "Q" or userinput == "q":
                            self.generate_pdf("accepted")
                            self.save_changes()
                        else:
                            print("\nInvalid input. Try again.\n")
                    head = (self.rpDelend.search(filetext[tail:]).end() + tail)
                    tail = head
                else:
                    # It's an addition
                    head = add_start + tail
                    revisedfiletext += filetext[tail:head]
                    tail = (self.rpAddbegin.search(filetext[head:]).end() +
                            head)
                    head = (self.rpAddend.search(filetext[tail:]).start() +
                            tail)
                    addition = filetext[tail:head]
                    addition = re.sub(r'\\DIFadd\{(.*?)\}', r'\1', addition,
                                      flags=re.DOTALL)
                    print("======\nFile under revision: {}".format(
                        filetorevise))
                    print("Addition found:\n+++\n{}\n+++".format(addition))
                    while True:
                        userinput = input("Add? Y/N/Q/y/n/q: ")
                        if not userinput.isalpha():
                            print("\nInvalid input. Try again.\n")
                            continue

                        if userinput == "Y" or userinput == "y":
                            print("Added.")
                            revisedfiletext += addition
                            break
                        elif userinput == "N" or userinput == "n":
                            print("Skipped.")
                            break
                        elif userinput == "Q" or userinput == "q":
                            self.generate_pdf("accepted")
                            self.save_changes()
                        else:
                            print("\nInvalid input. Try again.\n")
                    head = (self.rpAddend.search(filetext[tail:]).end() + tail)
                    tail = head

            outputfile = open(filetorevise, 'w')
            outputfile.write(revisedfiletext)
            outputfile.close()
            self.modifiedfiles += [filetorevise]
            print("======\nFile {} revised and saved.\n".format(filetorevise))
            self.filelist.remove(filetorevise)

        # Generate pdf
        self.generate_pdf("accepted")
        self.save_changes()

    def save_changes(self):
        """Commit changes."""
        if len(self.modifiedfiles) > 0:
            print("\nFollowing files have been modified:")
            for i in range(0, len(self.modifiedfiles)):
                print("[{}] {}".format(i+1, self.modifiedfiles[i]))

            print()
            while True:
                savechanges = input("Commit current changes? Y/y/N/n: ")
                if savechanges == "y" or savechanges == "Y":
                    subprocess.call(self.gitAddCommand)
                    commitmessage = input("Enter commit message: ")

                    command = (self.gitCommitCommand + [commitmessage])
                    subprocess.call(command)
                    print("Changes committed.\n" +
                          "You can merge this branch to master if you wish.\n")
                    break
                elif savechanges == "n" or savechanges == "N":
                    print("Exiting without committing.")
                    break
                else:
                    print("\nInvalid input. Please try again.",
                          file=sys.stderr)
        else:
            print("No files modified. Exiting.")

        sys.exit(0)

    def generate_pdf(self, filename):
        """Generate pdf file."""
        if len(self.modifiedfiles) > 0:
            print("\nFollowing files have been modified:")
            for i in range(0, len(self.modifiedfiles)):
                print("[{}] {}".format(i+1, self.modifiedfiles[i]))

            print()
            while True:
                generatepdf = input("Generate pdf? Y/y/N/n: ")

                if generatepdf == "Y" or generatepdf == "y":
                    command = (self.pdflatexCommand +
                               ("-jobname=" + filename).split() +
                               [self.optionsDict['main']])
                    subprocess.call(command, cwd=self.optionsDict['subdir'])

                    if self.optionsDict['citations']:
                        print("User has specified citations -" +
                              " rerunning pdflatex" +
                              " and bibtex as requird.")
                        commandb = (self.bibtexCommand +
                                    [self.optionsDict['main']])
                        subprocess.call(command,
                                        cwd=self.optionsDict['subdir'])
                        # command is already the pdflatex command
                        subprocess.call(command,
                                        cwd=self.optionsDict['subdir'])
                        subprocess.call(command,
                                        cwd=self.optionsDict['subdir'])

                    print("PDF generated: " +
                          self.optionsDict['subdir'] + "/" +
                          filename + ".pdf")
                    break
                elif generatepdf == "N" or generatepdf == "n":
                    print("Not generating pdf.")
                    break
                else:
                    print("\nInvalid input. Please try again.",
                          file=sys.stderr)

    def get_latex_files(self):
        """Get list of files with extension .tex."""
        filelist = []
        for root, dirs, files in os.walk(self.optionsDict['subdir']):
            for filename in fnmatch.filter(files, "*.tex"):
                if filename not in filelist:
                    filelist.append(os.path.join(root, filename))
        if not len(filelist) > 0:
            print("No tex files found in this directory", file=sys.stderr)
            sys.exit(-1)
        # print(filelist)
        return filelist

    def get_modified_latex_files(self):
        """Get list of files with latexdiff annotations."""
        filelist = []
        modifield_filelist = []
        for root, dirs, files in os.walk(self.optionsDict['subdir']):
            for filename in fnmatch.filter(files, "*.tex"):
                if filename not in filelist:
                    filelist.append(os.path.join(root, filename))
        if not len(filelist) > 0:
            print("No tex files found in this directory", file=sys.stderr)
            sys.exit(-1)

        for i in range(0, len(filelist)):
            filetorevise = filelist[i]

            with open(filetorevise, "r") as thisfile:
                filetext = thisfile.read()

            # Replace preamble additions
            filetext = re.sub(pattern=self.rpPreamble,
                              repl='',
                              string=filetext,
                              flags=re.DOTALL)

            # Check for annotations
            del_start = 0
            delcheck = self.rpDelbegin.search(filetext[:])
            add_start = 0
            addcheck = self.rpAddbegin.search(filetext[:])
            if delcheck is None:
                del_start = len(filetext)
            else:
                del_start = delcheck.start()
            if addcheck is None:
                add_start = len(filetext)
            else:
                add_start = addcheck.start()

            # If both are at EOL remove from file list
            if not add_start == del_start:
                modifield_filelist += [filetorevise]

        return modifield_filelist

    def generate_rev_filenames(self, rev):
        """Rename files as required for diff."""
        revfilelist = []
        for filename in self.filelist:
            revname = (filename[:-4] + "-" + rev + ".tex")
            revfilelist.append(revname)
        return revfilelist

    def setup(self):
        """Setup things."""
        self.parser = argparse.ArgumentParser(
            prog="zaphod",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self.usage_message,
            add_help=False
        )

        self.parser.add_argument("-h", "--help", action=_HelpAction,
                                 help="View subcommand help")

        self.subparser = self.parser.add_subparsers(
            help="additional help")

        self.revise_parser = self.subparser.add_parser(
            "revise",
            help="Interactive revision\n",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="TIP: To accept all - switch to rev2 branch/revision.\n" +
            "TIP: To reject all - switch to rev1 branch/revision.\n" +
            "Yay! Git!"
        )
        self.revise_parser.set_defaults(func=self.revise)
        self.revise_parser.add_argument("-m", "--main",
                                        action="store",
                                        default="main.tex",
                                        help="Name of main file. Only used to \
                                        generate final pdf with changes. \n\
                                        Default: main.tex")
        self.revise_parser.add_argument("-s", "--subdir",
                                        default=".",
                                        action="store",
                                        help="Name of subdirectory where main \
                                        file resides.\n\
                                        Default: ."
                                        )
        self.revise_parser.add_argument("-c", "--citations",
                                        action="store_true",
                                        default=False,
                                        help="Document contains citations.\n\
                                        Will run pdflatex and bibtex as \
                                        required. \nDefault: False"
                                        )

        self.diff_parser = self.subparser.add_parser(
            "diff",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            help="Generate changes output"
        )
        self.diff_parser.set_defaults(func=self.diff)
        self.diff_parser.add_argument("-r", "--rev1",
                                      default="master^",
                                      action="store",
                                      help="First revision to diff against")
        self.diff_parser.add_argument("-t", "--rev2",
                                      default="master",
                                      action="store",
                                      help="Second revision to diff with.")
        self.diff_parser.add_argument("-m", "--main",
                                      action="store",
                                      default="main.tex",
                                      help="Name of main file. Only used to \
                                      generate final pdf with changes. \n\
                                      Default: main.tex")
        self.diff_parser.add_argument("-s", "--subdir",
                                      default=".",
                                      action="store",
                                      help="Name of subdirectory where main \
                                      file resides.\n\
                                      Default: ."
                                      )
        self.diff_parser.add_argument("-e", "--exclude",
                                      default="\"\"",
                                      action="store",
                                      help="Pass exclude options to latexdiff. \
                                      Please read man latexdiff for \
                                      information on --exclude-textcmd \
                                      and related options."
                                      )
        self.diff_parser.add_argument("-p", "--type",
                                      default="UNDERLINE",
                                      action="store",
                                      help="Pass markup type option to latexdiff. \
                                      Please read man latexdiff for options."
                                      )
        self.diff_parser.add_argument("-c", "--citations",
                                      action="store_true",
                                      default=False,
                                      help="Document contains citations.\n\
                                      Will run pdflatex and bibtex as \
                                      required.\nDefault: False"
                                      )

    def check_setup(self):
        """Check if Git directory is clean."""
        command = "git status --porcelain".split()
        ps = subprocess.check_output(command)
        rpModified = re.compile(r'^\s*M')
        rpUntracked = re.compile(r'^\s*\?\?')

        if rpModified.search(ps.decode("ascii")) is not None or \
                rpUntracked.search(ps.decode("ascii")) is not None:
            print("Modifed or untracked files found files found.\n" +
                  "git status output:\n" +
                  ps.decode("ascii") +
                  "\nPlease stash or commit and rerun Zaphod.",
                  file=sys.stderr)
            sys.exit(-3)

        if self.optionsDict['subdir'] and not \
                os.path.isdir(self.optionsDict['subdir']):
            print("Specified subdirectory not found at {}!\n".format(
                self.optionsDict['subdir']) +
                "Please check your arguments.", file=stderr)
            sys.exit(-4)

        if self.optionsDict['main'] and self.optionsDict['subdir'] \
                and not \
                os.path.isfile(os.path.join(self.optionsDict['subdir'],
                                            self.optionsDict['main'])):
            print("Specified main file not found at {}!\n".format(
                os.path.join(self.optionsDict['subdir'],
                             self.optionsDict['main'])) +
                  "Please check your arguments.", file=stderr)
            sys.exit(-4)

        for command in self.commandList:
            if not shutil.which(command):
                print(command + " not found! Exiting!",
                      file=stderr)
                sys.exit(-5)

        if self.optionsDict['citations'] and not shutil.which("bibtex"):
            print("bibtex not found! Exiting!",
                  file=stderr)
            sys.exit(-6)

    def run(self):
        """Main runner method."""
        if len(sys.argv) == 1:
            self.parser.print_help()
            sys.exit(1)

        self.options = self.parser.parse_args()
        self.optionsDict = vars(self.options)
        if len(self.optionsDict) != 0:
            # Check for latex files and get a list
            self.check_setup()
            print(self.optionsDict)
            self.options.func(self.options)

if __name__ == "__main__":
    runner_instance = Zaphod()
    runner_instance.setup()
    runner_instance.run()
    sys.exit(0)
