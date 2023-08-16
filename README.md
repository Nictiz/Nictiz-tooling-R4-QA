# Nictiz QA tooling for FHIR R4 conformance resources

This repository contains automated tooling for FHIR R4 conformance resources (profiles, terminology resources, etc.) which are produced according the [Nictiz profiling guidelines](https://informatiestandaarden.nictiz.nl/wiki/FHIR:V1.0_FHIR_Profiling_Guidelines_R4). These tools aim to check as much of these guidelines (and general adherence to the FHIR specs) as is possible in an automated fashion. In addition, custom checks can be defined.

To provide a consistent experience across platforms, these tools are packaged in a Docker container, based on Alpine Linux. They can be invoked either on a local system or as part of a Github workflow.

## Functionality

At its heart, this tool allows an author of FHIR conformance resources to quickly create a set of automated checks on the files in the repository. The result can be used both for manual inspection and for automated workflows. _How_ this can be done is described in the next section; this section aims to summarize _what_ it does (and why).

### Resource validation

Although the tool can easily be extended with all kinds of custom scripts and tooling specific for a project, the core of checking conformance to the profiling guidelines is formed by checking FHIR resources against a profile, using the HL7 FHIR Validator. When checking against the FHIR profiling guidelines, this means using the profiles defined by these guidelins for the various types conformance resources: profiles and extensions, terminology resources (ValueSets, CodeSystems, NamingSystems and ConceptMaps), infrastructural resources (SearchParameters and CapabilityStatements) and example resources.

Validating FHIR resources however is not always an exact science: there's a plethora of options available regarding terminology, dependency's and error levels, and often false positives abound, either because of flaws in the validator or termninology server, or because there's a good reason to deviate from the rules. This tool offers the knobs to tune this validation process.

### Manual and automated usage

An important feature of this tool is to allow the same checks to be used in a manual (for human inspection) and automated (e.g. on pull requests) fashion. For manual usage, a web based user interface is available which allows a user to set options and select the checks to perform. For automated checks, a batch mode is available where the checks and options can be defined using the parameters, and where the result is communicated using the exit status code. (Of course, the batch mode can be used for manual checks as well if you're that type of person. It is, however, out of scope for this README).

### Terminology checking

Terminology checking is one of the most complex topics of profile validation. One has to deal with national versions of code systems -- the Dutch edition of SNOMED in particular for our use case and with poor behaviour regarding display values.

By default terminology checking it is opiniated about several of options:
* The Dutch version of SNOMED is used, and both Dutch and English are allowed for display values.
* Display issues are reported as warnings, not as errors (the default behaviour of the Validator is to report them as errors).
* When a code is encountered that falls outside an extensible bound ValueSet, no warning is emitted (the default behaviour of the Validator is to emit a warning). This can be overridden in the different usage scenarios.

### Silencing issues

False positives are an inevitable part of automated checks. This tool offers the option to suppress, in a very fine-grained manner, the errors and warnings that occur during the validation (both for the purpose of human inspection and automated checks).

These suppressed issue are described in a YAML file, which should be (reasonably) human-readable. The format is described here: This is described in [https://github.com/pieter-edelman-nictiz/hl7-fhir-validator-action#suppressing-messages]

### Custom tools

Lastly, the tool offers an environment for custom scripts, which can make use of the same terminology capabilities and variables defined as for the profile checks.

## Using this tooling in a project

### The qa.yaml file

To use these tools from a repository, a file called `qa.yaml` needs to be placed on the root level of the repository. This file describes the checks that can be performed on the various parts of the repo. This is a two-step process:

1. First the different kind of files (like profiles, extensions, ValueSets, etc.) in the repo need to be mapped to named patterns. This is done using the "patterns" section. Each entry in this section is the name of the pattern, followed by one or more file name patterns using wildcards. Files are substracted from a pattern if they are already defined in a previous pattern. This allows to define patterns for the "rest of the files".
2. Then, using these patterns, the steps that may be performed as part of the tool chain need to be described. This is done using the "steps" section. Each entry in this section should be a unique name with the following keys:
  * "patterns": one or more of the defined patterns that will be used in the check.
  * "description" (optional): A description of the check.
  * "profile" (optional): If present, this should be the canonical URL of a FHIR profile to check the files in the pattern against.
  * "script" (optional): The name of a custom script file in the "script dir" directory (see the section on extending below).
  If neither "profile" or "script" is present, the action will validate the files defined by the pattern against the known IG(s).

In addition, the `qa.yaml` file recognizes the following keys:

- "main branch": The name of the main production branch of this repository. This is needed when the tools need to inspect only the resources that have been changed/added compared to the main branch.
- "ignored issues": The path to a file describing the reported issues that should be ignored. See the section on "Silencing issues" for more information.
- "igs": A list of directories that should be considered part of the ig when running the validator.
- "script dir": A path to the directory containing custom scripts, relative to the root of the repository, in Unix notation.

For example, a `qa.yaml` file might look like this:

```yaml
main branch: origin/main
ignored issues: known-issues.yml
igs:
  - resources

patterns:
  zib profiles: resources/zib/zib-*.xml
  other profiles:
  - resources/zib/*.xml
  - resources/nl-core/*.xml
  conceptmaps: resources/**/conceptmap-*.xml

steps:
  validate zib profiles:
    description: Validate the zib profiles using the HL7 Validator
    patterns: zib profiles
    profile: http://nictiz.nl/fhir/StructureDefinition/ProfilingGuidelinesR4-StructureDefinitions-Zib-Profiles
  check formatting:
    patterns:
      - zib profiles
      - other profiles
      - conceptmaps
    script: scripts/check-formatting.sh
```

### Running locally

To run the docker image, a file called `docker-compose.yml` needs to be defined somewhere in the repository (it doesn't matter where). When there's no need to extend the tooling, it should looks like this:

```yaml
version: "3.9"
services:
  nictiz-r4-qa:
    image: ghcr.io/nictiz/nictiz-tooling-r4-qa
    container_name: nictiz-r4-qa-[repo name]
    volumes:
      - type: bind
        source: [relative path to the root of the repo, from the path where this file resides]
        target: /repo
        read_only: true
    environment:
      - MENU_PORT=9000
      - TX_MENU_PORT=9001
    ports:
      - 8081:8081
      - 9000:9000
      - 9001:9001
```

Next, install and run [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or just Docker engine if you know how this works). Then, the following command should be executed from the directory where the docker-compose.yml file resides (it makes sense to put this in a .bat file):

> docker compose up nictiz-r4-qa

This starts a local webserver that communicates with the tools. Go to http://localhost:9000 to run the steps defined in the qa.yaml file.

It can take a while to start validation when this command is executed for the first time. This is because the Docker image needs to be downloaded. Subsequent runs will start a lot faster.

### On Github

To use this tool on Github, a [workflow description file](https://docs.github.com/en/actions/using-workflows/about-workflows) needs to be defined with a `uses` key for this repo (note: so here you don't specify the image like you do in `docker-compose.yml`; the image is still used, but some metadata from the `action.yml` file in this repo is needed to do so). If needed, the steps to perform can be restricted using the `steps` key. For example:

```yaml
name: Profile QA - changed files
on: [pull_request]

jobs:
  nictiz-r4-qa:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v2
        with:
          fetch-depth: 0
      - name: Docker
        uses: Nictiz/Nictiz-tooling-R4-QA@docker
        with:
          steps: "validate zib profiles, check formatting"
```

It makes sense to create a branch protection rule which requires these checks to pass.

## Extending

As described above, custom checks can be added using the `script` key in the `qa.yaml` file. The default Alpine Linux environment is available plus the following:

* Bash
* Java (OpenJDK 11)
* Python (and Pip)
* Git
* The HL7 Validator, which can be found in `/$tool_dir/validator/validator.jar`

### Writing scripts

Scripts can reside anywhere in the repository and are interpreted as standard Linux shell scripts. They can be written in any scripting language available in the Alpine Linux environment, like bash, Python, etc. To write a script:

* Make sure to include the interpreter using the [shebang notation](https://linuxhandbook.com/shebang/).
* The files that need to be checked are passed as positional arguments to the script.
* The exit code should reflect the status of the check: 0 means success, anything else means failure.
* Since the repository is mounted in the Docker container, make sure to use absolute paths in the scripts based on the variables below.
* The following environment variables are available:
  * `tools_dir`: The base dir where all local tools are stored, like the HL7 validator or its output wrapper.
  * `work_dir`: The repository directory, or rather, a one-time copy of the repository directory. The repository itself is read-only so there's no change of destroying any data. A fresh copy is made each time the tool _chain_ is run. 
  * `script_dir`: The dir that hosts the (copy of the) custom scripts during execution. See the remark below.
  * `debug`: flag to define if the tools are run in debug mode ("1" is true and "0" is false)
  * `changed_only`: flag to determine if we need to check changed files only ("1" is true and "0" is false)
  * `write_github`: check to determine if we're writing output as part of a Github workflow ("1" is true and "0" is false)
  * `fail_at`: the issue level at which the check should be considered failed. The possible value are "fatal", "error" or "warning".
* Shell scripts are sensitive to line endings (that is, they MUST be in Unix format for them to work) and file attributes, which do not always carry over to git repositories on Windows. For this reason, the scripts are copied and normalized to `script_dir` before being executed.

### Installing additional software

If additional software is needed for the script, you can simply install this from the script. This only needs to be done once; the Docker container is re-used on subsequent runs (so make sure to include a check to see if the software is already installed). 

Note: this is only true for local builds. On Github, software will be installed over and over again. In the future, an image based approach might be more efficient, but that's out of scope for the moment.
