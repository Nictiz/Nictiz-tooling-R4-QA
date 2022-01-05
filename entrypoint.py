#!/usr/bin/env python3

import argparse
import glob
import yaml
import os
import subprocess
import tempfile

class FileCollection(dict):
    def __init__(self, config, changed_only = True):
        if "patterns" in config:
            self.patterns = config["patterns"]
        else:
            self.patterns = []
        
        for pattern_name in self.patterns:
            self[pattern_name] = []
            
        self.changed_only = changed_only
            
    def setChangedOnly(self, changed_only):
        self.changed_only = changed_only
        
    def resolve(self):
        # Reset all file lists
        for pattern_name in self.keys():
            self[pattern_name] = []
            
        if self.changed_only:
            # If we're only interested in the files that are new or changed compared to the main branch, we first ask
            # git for a list of all these files, committed or not
            committed   = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACM", "origin/main"], capture_output = True)
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
            
            # Now add all files that match the pattern and that have not been seen before
            for pattern in patterns:
                for file_name in glob.glob(pattern, recursive = True):
                    if self.changed_only:
                        if file_name in changed_files:
                            self[pattern_name].append(file_name)
                            changed_files.remove(file_name)                   
                    else:
                        if file_name not in combined:
                            self[pattern_name].append(file_name)
                            combined.append(file_name)

class StepExecutor:
    def __init__(self, config, file_collection):
        if "steps" in config:
            self.steps = config["steps"]
        else:
            self.steps = []

        self.file_collection = file_collection
        self.debug = False
    
    def getSteps(self):
        return self.steps.keys()
    
    def setDebugging(self, debug):
        self.debug = debug
    
    def execute(self, *step_names):
        os.environ["debug"] = "1" if self.debug else "0"
        os.environ["changed_only"] = "1" if self.file_collection.changed_only else "0"
        self.file_collection.resolve()
    
        for step_name in step_names:
            step = self.steps[step_name]
            
            print("\033[1;37m+++ " + step_name + "\033[0m")
            
            files = []
            if "patterns" in step:
                patterns = step["patterns"]
                if type(patterns) == str:
                    patterns = [patterns]
                for pattern in patterns:
                    files += self.file_collection[pattern]
        
            if len(files) == 0:
                print("Nothing to check, skipping")
                return True
                    
            if "profile" in step:
                self._runValidator(step["profile"], files)
            elif "script" in step:
                self._runExternalCommand(step["script"], files)
    
    def _runValidator(self, profile, files):
        out_file = tempfile.mkstemp(".xml")
        command = [
            "java", "-jar", "/home/pieter/winhome/Downloads/validator_cli.jar",
            "-ig", "qa", "-ig", "resources", "-recurse",
            "-profile", profile,
            "-output", out_file[1]] + files
        
        if self.debug:
            result_validator = subprocess.run(command)
        else:
            result_validator = subprocess.run(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        
        success = False
        if result_validator:
            result = subprocess.run(["python3", "/home/pieter/winhome/hl7-validator-action/analyze_results.py",  "--colorize", "--fail-at", "error", "--ignored-issues", "known-issues.yml", out_file[1]])
            if result:
                success = True
        elif not self.debug:
            print("\033[0;33mThere was an error running the validator. Re-run with the --debug option to see the output.\033[0m")
        
        os.unlink(out_file[1])
        return success 
        
    def _runExternalCommand(self, command, files):
        result = subprocess.run(command + " " + " ".join(files), shell = True)
        return result.returncode == 0

class Menu:
    def __init__(self, executor):
        self.executor = executor
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Perform QA on FHIR materials")
    parser.add_argument("-c", "--config", type = str, required = True,
                        help = "The YAML file to configure the QA process")
    parser.add_argument("--menu", type = bool, default = False,
                        help = "Display a menu rather than running in batch mode")
    parser.add_argument("--steps", type = str, nargs = "*",
                        help = "The steps to execute (make sure to quote them if they contain spaces). If absent, all steps will be executed.")
    parser.add_argument("--changed-only", type = bool, default = False,
                        help = "Only validate changed files rather than all files (compared to the main branch)")
    parser.add_argument("--debug", type = bool, default = False,
                        help = "Display debugging information for when something goes wrong")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
    file_collection = FileCollection(config, args.changed_only)
    executor = StepExecutor(config, file_collection)
    executor.setDebugging(args.debug)
   
    if args.steps != None:
        steps = args.steps
    else:
        steps = executor.getSteps()
    
    if args.menu:
        pass
    else:
        executor.execute(*steps)        
