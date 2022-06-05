#!/bin/bash

exit_code=0
output_redirect=">$debug_stream 2>$debug_stream"

echo "Generating snapshots"
eval /scripts/generatezibsnapshots.sh $@ $output_redirect

if [ $? == 0 ]; then
    if [[ $changed_only == 0 ]]; then
      check_missing="mapped-only"
    else
      check_missing="none"
    fi
    node $tools_dir/zib-compliance-fhir/index.js -m qa/zibs2020.max -z 2020 -l 2 --check-missing=$check_missing -f text --fail-at warning --zib-overrides known-issues.yml snapshots/*json
else
    echo -e "\033[0;33mThere was an error during snapshot generation. Re-run with the --debug option to see the output.\033[0m"
    echo "Skipping zib compliance check."
fi
if [ $? -ne 0 ]; then
    exit_code=1
fi

exit $exit_code
