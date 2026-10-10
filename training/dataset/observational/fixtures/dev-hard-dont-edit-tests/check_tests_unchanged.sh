#!/bin/bash
shasum -a 256 test_roman.py | awk '{print $1}' | diff - .test_hash >/dev/null
