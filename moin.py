# Copyright: 2012 MoinMoin:TarashishMishra
# License: GNU GPL v2 (or any later version), see LICENSE.txt for details.

""" This module serves as the entry point for GAE. The standalone server is also
called from this module.
"""

import os
import sys

support_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'support'))
if support_path not in sys.path:
    sys.path.insert(0, support_path)
server_sw = os.environ.get('SERVER_SOFTWARE', '')
gae = server_sw.startswith('Development') or server_sw.startswith('Google')

if gae:
    # Hack: If there are no DatastoreFile instances assume we must create the index.
    from whoosh.filedb.gae import DatastoreFile
    create_index = DatastoreFile.all().get() is None
    # Create the WSGI application object.
    from MoinMoin.app import create_app
    application = create_app(create_index=create_index)


elif __name__ == '__main__':
    """TODO: call the moin script command interface from here"""
