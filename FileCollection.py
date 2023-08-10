class FileCollection(dict):
    def __init__(self, config, changed_only = True):
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
