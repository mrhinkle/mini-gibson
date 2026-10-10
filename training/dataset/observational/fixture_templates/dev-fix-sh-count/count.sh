#!/bin/bash
# BUG: counts lines wrong (uses wc -c)
wc -c "$1" | awk '{print $1}'
