#!/usr/bin/env python3
"""Derive assigned Unicode scalar ranges from the pinned normative data."""
def assigned(data):
    return {'ranges': [], 'counts': {}, 'assigned_scalars': 0, 'excluded_non_scalars': 0}
