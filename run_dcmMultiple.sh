#!/bin/bash

# Run dcmsend commands simultaneously
dcmsend -v -aec ae_site1_1 127.0.0.1 65302 --scan-directories /Users/subhrasis/Documents/Rapid_pythonScripts/Performance/Testdatagenerator/GoldenSet/Hyper/Dataset/ &
dcmsend -v -aec ae_two_dup 127.0.0.1 65324 --scan-directories /Users/subhrasis/Documents/Rapid_pythonScripts/Performance/Testdatagenerator/GoldenSet/Hypo/Dataset/ &
dcmsend -v -aec three_ae 127.0.0.1 65409 --scan-directories /Users/subhrasis/Documents/Rapid_pythonScripts/Performance/Testdatagenerator/GoldenSet/RVLV/Dataset/ &
dcmsend -v -aec four_ae 127.0.0.1 65452 --scan-directories /Users/subhrasis/Documents/Rapid_pythonScripts/Performance/Testdatagenerator/GoldenSet/PETN/Dataset/ &

# Wait for all background processes to finish
wait

echo "All dcmsend commands have completed."
