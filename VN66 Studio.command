#!/bin/bash
# macOS launcher. Needs Python 3 and: pip3 install hidapi
cd "$(dirname "$0")"
exec python3 -m vn66.app "$@"
