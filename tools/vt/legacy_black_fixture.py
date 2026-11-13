"""D13 reference input: spell legacy black as explicit indexed black.

Basic30 is normalized before a later bold can trigger the legacy mapping;
without bold these forms already agree. Exact full-frame deltas still need
per-cell validation before any repaired result is an expected frame.
"""
from report_fixture import controls


def repair(data):
    output=bytearray();edits=[];end=0
    for match in controls(data,rb'\x1b\[([0-9:;]*)m'):
        if b':' in match[1]:raise ValueError('owned legacy fixture accepts semicolon SGR only')
        values=[int(part or b'0') for part in match[1].split(b';')]
        rewritten=[];at=0
        while at<len(values):
            code=values[at]
            if code in (38,48,58):
                if at+1>=len(values) or values[at+1] not in (2,5):raise ValueError('unsupported colour form')
                length=3 if values[at+1]==5 else 5
                if at+length>len(values):raise ValueError('truncated colour arguments')
                rewritten.extend(values[at:at+length]);at+=length;continue
            rewritten.extend([38,5,0] if code==30 else [code]);at+=1
        if rewritten==values:continue
        replacement=b'\x1b['+b';'.join(str(value).encode() for value in rewritten)+b'm'
        output+=data[end:match.start()]+replacement
        edits.append({'offset':match.start(),'original_hex':match[0].hex(),'replacement_hex':replacement.hex()});end=match.end()
    output+=data[end:]
    return bytes(output),edits
