#!/usr/bin/env python3
"""Build the explicit D9 reference fixture from a spec-only background trace.

This is not a candidate-output normalizer. It changes no expected screen:
the pinned reference will build that from the repaired byte stream.
"""

def repair(data):
    return data, []
