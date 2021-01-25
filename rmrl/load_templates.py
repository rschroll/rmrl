'''
Copyright 2021 Robert Schroll

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import argparse
import subprocess
import sys
import textwrap

from .constants import TEMPLATE_PATH, VERSION

def main():
    parser = argparse.ArgumentParser(description="Load the templates from a Remarkable device for use with rmrl")
    parser.add_argument('ip', nargs='?', default='10.11.99.1', help="""
        IP address of Remarkable device.  Defaults to the value used when
        plugged in via USB.  Possible values can be found under Settings >
        Help > Copyrights and licenses, under the GPLv3 Compliance section.""")
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()

    print(textwrap.dedent(f"""
        About to connect to your Remarkable device at {args.ip}.

        If this is the first time SSHing into your Remarkable device, you may
        see a warning that the authenticity of the host can't be established.
        This is expected; type 'yes' to continue.

        If you have not set up SSH keys on your Remarkable device, you will be
        prompted to enter a password.  This is NOT your lock screen passcode.
        It can be found under Settings > Help > Copyrights and licences, under
        the GPLv3 Compliance section.
    """).strip())
    print("")

    TEMPLATE_PATH.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(['scp', f'root@{args.ip}:/usr/share/remarkable/templates/*.svg', TEMPLATE_PATH],
            stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    except FileNotFoundError:
        print("Could not find the 'scp' program.")
        print("This should be installed as part of SSH.")
        return 1

    if completed.returncode == 0:
        print("")
        print(f"Templates copied to {TEMPLATE_PATH}")
    else:
        print("")
        print(f"Error: Got return code of {completed.returncode}")
        print("The cause may be indicated in the output above.")
    return completed.returncode

if __name__ == '__main__':
    sys.exit(main())
