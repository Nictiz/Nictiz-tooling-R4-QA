#!/usr/bin/env python3

import aiohttp
from aiohttp import web
import argparse
import asyncio
import enum
import fnmatch
import glob
import mimetypes
import os
import pathlib
import re
import requests
import shutil
import stat
import subprocess
import sys
import tempfile
import yaml

REPO_DIR    = "/repo"
TOOLS_DIR   = "/tools"
SCRIPT_DIR  = "/scripts"
CONFIG_FILE = "qa.yaml"

class Printer:
    ''' Class to route and format output to the desired location '''

    ANSI_TO_HTML = {
        "0" : {
            "0": "black",
            "1": "darkred",
            "2": "green",
            "3": "orange",
            "4": "darkblue",
            "5": "purple",
            "6": "lightblue",
            "7": "lightgrey"
        },
        "1" : {
            "0": "black",
            "1": "red",
            "2": "lightgreen",
            "3": "yellow",
            "4": "blue",
            "5": "magenta",
            "6": "cyan",
            "7": "white"
        }
    }

    def __init__(self, write_github = False):
        self.socket = None
        self.write_github = write_github
        os.environ["write_github"] = "1" if write_github else "0"
    
    def setSocket(self, socket):
        ''' Set a web socket to send the output to. '''
        self.socket = socket

    async def writeLine(self, message):
        """ Write a line to the terminal. If a web socket is set and available for writing, the output will be echoed
            there as well. """
        await self.write(message + "\n")

    async def write(self, message):
        """ Write out the output to the terminal. If a web socket is set and available for writing, the output will be
            echoed there as well. """
        print(message, end = '')

        if self.socket != None and not self.socket.closed:
            # Set the message to "terminal colors" (lightgrey on black). Rewrite all ANSI color codes to HTML tags.
            html_msg = re.sub('\x1b\[(0|1);3(.)m', self._ansiToHTML, message)
            html_msg = re.sub('\x1b\[0m', "</span><span style='color: lightgrey'>", html_msg)
            html_msg = f"<span style='color: lightgrey;'>{html_msg}</span>"

            await self.socket.send_json({
                "output": html_msg
            })

    def writeGithubOutput(self, key, value):
        """ Set an output value when executed on Github. """
        if self.write_github:
            with open(os.environ['GITHUB_OUTPUT'], 'w') as github_output:
                github_output.write(f'{key}={value}')

    def startGithubGroup(self, title):
        if self.write_github:
            print(f"::group::{title}")
    
    def endGithubGroup(self):
        if self.write_github:
            print("::endgroup::")

    def _ansiToHTML(self, match_obj):
        ''' Helper method to rewrite an ASNI color code to a HTML style tag. '''
        try:
            color = self.ANSI_TO_HTML[match_obj.group(1)][match_obj.group(2)]
        except KeyError:
            return ""
        
        return f"</span><span style='color: {color}'>"
class FileCollection(dict):
    class Mode(enum.Enum):
        ALL = 1
        FILTERED = 2
        CHANGED = 3

    def __init__(self, config, mode = Mode.CHANGED, on_github = False):
        if "patterns" in config:
            self.patterns = config["patterns"]
        else:
            self.patterns = []
        
        for pattern_name in self.patterns:
            self[pattern_name] = []
        
        if "main branch" in config:
            self.main_branch = config["main branch"]
        else:
            self.main_branch = "origin/main"

        self.setMode(mode)

        if on_github:
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", os.getcwd()])

    def setMode(self, mode, file_name_filters = None):
        self.mode = mode
        if self.mode == FileCollection.Mode.ALL:
            self.file_name_globs = ["*"]
        elif self.mode == FileCollection.Mode.FILTERED:
            if file_name_filters == None:
                self.file_name_globs = ["*"]
            else:
                self.file_name_globs = [f"*{filter.strip()}*" for filter in file_name_filters]
   
    def resolve(self):
        # Reset all file lists
        for pattern_name in self.keys():
            self[pattern_name] = []

        if self.mode == FileCollection.Mode.CHANGED:
            # If we're only interested in the files that are new or changed compared to the main branch, we first ask
            # git for a list of all these files, committed or not
            committed   = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACM", self.main_branch], capture_output = True)
            uncommitted = subprocess.run(["git", "ls-files", "--others"], capture_output = True)
            if committed and uncommitted:
                changed_files =  committed.stdout.decode("UTF-8").split("\n")
                changed_files += uncommitted.stdout.decode("UTF-8").split("\n")
        else:
            # Otherwise we need to keep track of the files that we already encountered
            combined = []
            
        for pattern_name in self.patterns:
            patterns = self.patterns[pattern_name]
            # Each pattern name can be associated with multiple patterns, so make sure we always have a list
            if type(patterns) == str:
                patterns = [patterns]
            
            # Now add all files that match the pattern and that have not been seen before, optionally filtered by the
            # file name globs
            for pattern in patterns:
                for file_path in pathlib.Path().glob(pattern):
                    if self.mode == FileCollection.Mode.CHANGED:
                        if file_path.as_posix() in changed_files:
                            self[pattern_name].append(file_path.as_posix())
                            changed_files.remove(file_path.as_posix())
                    elif (file_path not in combined) and any([fnmatch.fnmatch(file_path.name, fn_glob) for fn_glob in self.file_name_globs]):
                        self[pattern_name].append(file_path.as_posix())
                        combined.append(file_path)

class StepExecutor:
    def __init__(self, config, file_collection, printer, fail_at, verbosity_level):
        if "steps" in config:
            self.steps = config["steps"]
        else:
            self.steps = {}

        self.tx_disabled            = False
        self.fail_at                = fail_at
        self.verbosity_level        = verbosity_level
        self.best_practice_warnings = True
        self.file_collection        = file_collection
        self.printer                = printer

        # By default, we handle the Nictiz profiling guidelines package. Additional ig's may be defined in the config file.
        self.igs = ["nictiz.fhir.nl.r4.profilingguidelines"]
        if "igs" in config:
            self.igs += [ig for ig in config["igs"]]

        self.ignored_issues = None
        if "ignored issues" in config:
            self.ignored_issues = config["ignored issues"]

        self.debug = False

        self.script_dir = None
        if "script dir" in config:
            self.script_dir = config["script dir"]

        # Export the variables for external scripts to use
        os.environ["tools_dir"]  = TOOLS_DIR
        os.environ["work_dir"]   = REPO_DIR
        os.environ["script_dir"] = SCRIPT_DIR
    
    def getSteps(self):
        return self.steps.keys()
    
    def setDebugging(self, debug):
        self.debug = debug
    
    def setTerminologyOptions(self, disabled = None, extensible_binding_warnings = None, suppress_display_issues = None):
        if disabled != None:
            self.tx_disabled = disabled
        if extensible_binding_warnings != None:
            self.extensible_binding_warnings = extensible_binding_warnings
        if suppress_display_issues != None:
            self.suppress_display_issues = suppress_display_issues

    def setLevels(self, verbosity = None, fail_at = None):
        if verbosity != None:
            self.verbosity_level = verbosity
        if fail_at != None:
            self.fail_at = fail_at

    def setBestPracticeWarnings(self, best_practice_warnings):
        self.best_practice_warnings = best_practice_warnings

    async def execute(self, *step_names):
        os.environ["debug"] = "1" if self.debug else "0"
        os.environ["changed_only"] = "1" if self.file_collection.mode == FileCollection.Mode.CHANGED else "0"
        os.environ["fail_at"] = self.fail_at

        self._copyScripts()
        self.file_collection.resolve()
    
        overall_success = True
        for step_name in step_names:
            step = self.steps[step_name]
            
            await self.printer.writeLine("\033[1;37m" + "#" * (len(step_name) + 10) + "\033[0m")
            await self.printer.writeLine("\033[1;37m" + "#### " + step_name + " ####" + "\033[0m")
            await self.printer.writeLine("\033[1;37m" + "#" * (len(step_name) + 10) + "\033[0m\n")
            
            files = []
            if "patterns" in step:
                patterns = step["patterns"]
                if type(patterns) == str:
                    patterns = [patterns]
                for pattern in patterns:
                    files += self.file_collection[pattern]
        
            if len(files) == 0:
                await self.printer.writeLine("\033[1;37mNothing to check, skipping\033[0m")
                self.printer.writeGithubOutput(f"step[{step_name}][skipped]", "true")
            else:
                self.printer.writeGithubOutput(f"step[{step_name}][skipped]", "false")
                if "profile" in step:
                    success = await self._runValidator(step["profile"], files)
                elif "script" in step:
                    success = await self._runExternalCommand(step["script"], files)
                else:
                    success = await self._runValidator(None, files)
                overall_success &= success

                if success:
                    await self.printer.writeLine(f'\n\033[1;32mPass: "{step_name}"\033[0m')
                else:
                    await self.printer.writeLine(f'\n\033[1;31m"Fail: "{step_name}"\033[0m')
                self.printer.writeGithubOutput(f"step[{step_name}][result]", "success" if success else "failure")

            await self.printer.writeLine("")
        
        return overall_success

    def _copyScripts(self):
        """ Create a fresh copy of the scripts dir so that script files have their line endings normalized and have
            the proper permissions for executing. """
        shutil.rmtree(SCRIPT_DIR)
        os.mkdir(SCRIPT_DIR)
        if (self.script_dir):
            curr_dir = os.getcwd()
            os.chdir(os.path.join(REPO_DIR, self.script_dir))
            for file_name in glob.glob("*", recursive = False):
                with open(file_name, "rt") as src_file:
                    dst_path = os.path.join(SCRIPT_DIR, file_name)
                    with open(dst_path, "wt") as dest_file:
                        for line in src_file.readlines():
                            dest_file.write(line)
                    os.chmod(dst_path, stat.S_IRUSR | stat.S_IXUSR)
            os.chdir(curr_dir)

    async def _runValidator(self, profile, files):
        # Get a name for a temp file, but remove the file itself so we can check if the Validator produced the required
        # output
        out_file = tempfile.mkstemp(".xml")
        os.unlink(out_file[1])

        # We're opiniated about terminology checking. We want to allow Dutch display values and we don't consider
        # display issues errors.
        tx_opt = ["-sct", "nl", "-display-issues-are-warnings"]
        if not self.extensible_binding_warnings: # Our flag is the opposite of the default behaviour of the Validtor
            tx_opt += ["-no-extensible-binding-warnings"]
        if self.tx_disabled:
            tx_opt += ["-tx", "n/a"]
        best_practices_opt = ["-best-practice", "warning" if self.best_practice_warnings else "ignore"]

        igs = []
        for ig in self.igs:
            igs += ["-ig", ig]

        if profile is not None:
            profile_flag = ["-profile", profile]
        else:
            profile_flag = []
        command = [
            "java", "-jar", "/tools/validator/validator.jar",
            '-version', "4.0.1"] + igs + ["-recurse"] + profile_flag + tx_opt + best_practices_opt + [
            "-output", out_file[1]] + files
        
        self.printer.startGithubGroup("Run validator")
        if self.debug or self.printer.write_github:
            suppress_output = False
        else:
            suppress_output = True
        await self._popen(command, suppress_output=suppress_output)
        self.printer.endGithubGroup()
        
        success = False
        if os.path.exists(out_file[1]):
            fail_at         = "error" if self.fail_at == "fatal"         else self.fail_at
            verbosity_level = "error" if self.verbosity_level == "fatal" else self.verbosity_level
            command = ["python3", "/tools/hl7-fhir-validator-action/analyze_results.py",  "--colorize", "--fail-at", fail_at, "--verbosity-level", verbosity_level]
            if printer.write_github:
                command.append("--github")
            if self.suppress_display_issues:
                command.append("--suppress-display-issues")
            if self.ignored_issues:
                command += ["--ignored-issues", self.ignored_issues]
            command += [out_file[1]]
            result = await self._popen(command)
            if result == 0:
                success = True
        elif not self.debug:
            await self.printer.writeLine("\033[0;33mThere was an error running the validator. Re-run with the --debug option to see the output.\033[0m")
        
        os.unlink(out_file[1])
        return success 
  
    async def _runExternalCommand(self, command, files):
        if not self.script_dir:
            await self.printer.writeLine("'script dir' is not set in qa.yaml!")
            return False
        result = await self._popen(SCRIPT_DIR + "/" + command + " " + " ".join(files), shell = True)
        return result == 0

    async def _popen(self, command, shell = False, suppress_output = False):
        ''' Helper method to open a subprocess, send the output to the Printer as it comes in, and return the results. '''
        if suppress_output:
            stdout = subprocess.DEVNULL
        else:
            stdout = subprocess.PIPE
        proc = subprocess.Popen(command, stdout = stdout, stderr = subprocess.STDOUT, universal_newlines = True, bufsize = 1, shell = shell)
        
        if not suppress_output:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                await self.printer.write(line)
        proc.wait()
        return proc.returncode

class QAServer:
    ''' Class to serve an interactive menu using a web interface. '''

    def __init__(self, executor):
        self.executor = executor

        self.app = web.Application()
        self.app.router.add_get("/ws",                 self._handleWebsocket)
        self.app.router.add_get("/",                   self._handleGet)
        self.app.router.add_post("/file_name_filters", self._handleFileNameFilters)
        self.app.router.add_get("/{file}",             self._handleGet)
        self.app.router.add_post("/",                  self._handlePost)

        self.ws = web.WebSocketResponse()
    
    def run(self):
        web.run_app(self.app, port = MENU_PORT)

    async def _handleWebsocket(self, request):
        ''' Create and return a websocket when getting a GET request on /ws '''
        if self.ws.closed:
            self.ws = web.WebSocketResponse()
        await self.ws.prepare(request)

        # We don't actually expect communication _from_ the socket, but this is the way to keep it open
        await self.ws.receive()

        return self.ws

    async def _handleGet(self, request):
        ''' Handle GET request, which we do expect in two flavors: on the base or on a particular file. Any other
            request will result in a 404. '''

        requested_file = request.match_info.get('file', 'index.html')
        try:
            content = open("/server/" + requested_file).read()
            content_type = mimetypes.guess_type("/server/" + requested_file)[0]
        except IOError:
            return web.Response(status = 404)    
        if requested_file == 'index.html':
            # The menu HTML. We need to insert the steps that we know of in the static file that's loaded from disk.
            content_type = 'text/html'

            task_html = ""
            for step in self.executor.getSteps():
                task_html += f"<input type='checkbox' name='step_{step}'/>"
                # TODO: Sanitize input for name use
                task_html += f"<label for='step_{step}'>{step}</label><br />"
            content = content.replace('<legend>Perform steps:</legend>', "<legend>Perform steps:</legend>" + task_html)
        
        return web.Response(body = content, content_type = content_type)

    async def _handlePost(self, request):
        content = await request.post()

        if "check_what" in content:
            if content["check_what"] == "filtered":
                self.executor.file_collection.setMode(FileCollection.Mode.FILTERED, content["file_name_filters"].split(","))
            elif content["check_what"] == "changed":
                self.executor.file_collection.setMode(FileCollection.Mode.CHANGED)
            else:
                self.executor.file_collection.setMode(FileCollection.Mode.ALL)

        steps = []
        for key in content:
            if key.startswith("step_"):
                steps.append(key.replace("step_", ""))

        if "terminology" in content:
            if content["terminology"] == "disabled":
                self.executor.setTerminologyOptions(disabled = True)
            elif content["terminology"] == "default_tx":
                self.executor.setTerminologyOptions(disabled = False)

        if "suppress_display_issues" in content:
            self.executor.setTerminologyOptions(suppress_display_issues = True)
        if "verbosity_level" in content:
            self.executor.setLevels(verbosity = content["verbosity_level"])
        if "fail_at" in content:
            self.executor.setLevels(fail_at = content["fail_at"])

        self.executor.setTerminologyOptions(extensible_binding_warnings = ("extensible_binding_warnings" in content))
        self.executor.setBestPracticeWarnings("best_practice_warnings" in content)
        self.executor.setDebugging("debug" in content)
        
        self.executor.printer.setSocket(self.ws)
        asyncio.create_task(self._executeAndReport(steps))
        return web.Response()

    async def _handleFileNameFilters(self, request):
        """ Set file name filters for the file selection. The request is expected to have two fields:
            * step_names: the current selection of steps to execute
            * file_name_filters: a comma-separated list of file name filters
        """

        content = await request.post()

        if content["step_names"] == "":
            return web.json_response({"files": []})
        step_names = content["step_names"].split(",")

        self.executor.file_collection.setMode(FileCollection.Mode.FILTERED, content["file_name_filters"].split(","))
        self.executor.file_collection.resolve()
        files = []
        for step_name in step_names:
            step = self.executor.steps[step_name]
                       
            if "patterns" in step:
                patterns = step["patterns"]
                if type(patterns) == str:
                    patterns = [patterns]
                for pattern in patterns:
                    files += self.executor.file_collection[pattern]

        return web.json_response({"files": files})
        
    async def _executeAndReport(self, steps):
        """ Execute the QA tooling and report back the result when done using the open web socket. """
        await self.ws.send_json({"status": "running"})
        result = await executor.execute(*steps)
        status = "success" if result else "failure"
        await self.ws.send_json({"result": status})

if __name__ == "__main__":
    def __interpretStringAsBool(value):
        if isinstance(value, bool):
            return value
        if value.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif value.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    parser = argparse.ArgumentParser(description = "Perform QA on FHIR materials")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--batch", action = "store_true",
                       help = "Run in batch mode rather then starting a web server to control the process.")
    parser.add_argument("--changed-only", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Only validate changed files rather than all files (compared to the main branch).")
    parser.add_argument("--no-tx", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Disable the use of a terminology server all together.")
    parser.add_argument("--extensible-binding-warnings", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Emit a warning for codes that are not in an extensible bound ValueSet.")
    parser.add_argument("--best-practice-warnings", type = __interpretStringAsBool, nargs = "?", const = True, default = True, metavar = "boolean",
                        help = "Emit a warning when best practices aren't followed")
    parser.add_argument("--suppress-display-issues", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Suppress all reported issues about incorrect terminology displays")
    parser.add_argument("--fail-at", choices = ["fatal", "error", "warning"], default = "error",
                        help = "The test fails when an issue with this gravity is encountered.")
    parser.add_argument("--verbosity-level", choices = ["fatal", "error", "warning", "information"], default = "information",
                        help = "Show messages from this level onwards.")
    parser.add_argument("--debug", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Display debugging information for when something goes wrong.")
    parser.add_argument("--github", type = __interpretStringAsBool, nargs = '?', const = True, default = False, metavar = 'boolean',
                        help = "Add output in Github format. Implies --batch.")
    parser.add_argument("steps", type = str, nargs = "*", metavar = "step",
                        help = "The steps to execute (make sure to quote them if they contain spaces). If absent, all steps will be executed.")
    args = parser.parse_args()
    if args.github:
        args.batch = True

    try:
        MENU_PORT = os.environ["MENU_PORT"]
    except KeyError:
        MENU_PORT = 9000

    if args.github and "GITHUB_WORKSPACE" in os.environ:
        REPO_DIR = os.environ["GITHUB_WORKSPACE"]

    os.chdir(REPO_DIR)

    with open(CONFIG_FILE) as config_file:
        config = yaml.safe_load(config_file)
    file_collection = FileCollection(config, FileCollection.Mode.CHANGED if args.changed_only else FileCollection.Mode.ALL, args.github)
    printer = Printer(args.github)
    executor = StepExecutor(config, file_collection, printer, args.fail_at, args.verbosity_level)
    executor.setTerminologyOptions(disabled = args.no_tx, extensible_binding_warnings = args.extensible_binding_warnings, suppress_display_issues = args.suppress_display_issues)
    executor.setBestPracticeWarnings(args.best_practice_warnings)
    executor.setDebugging(args.debug)
   
    if len(args.steps) > 1:
        steps = args.steps
    elif len(args.steps) == 1 and args.steps[0].strip() != "":
        steps = [step.strip() for step in args.steps[0].split(",")]
    else:
        steps = executor.getSteps()

    if args.batch:
        result = asyncio.run(executor.execute(*steps))
        if not result:
            sys.exit(1)
    else:
        server = QAServer(executor)
        server.run()
