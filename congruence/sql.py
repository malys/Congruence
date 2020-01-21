#  congruence: A command line interface to Confluence
#  Copyright (C) 2020  Adrian Vollmer
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from congruence.logging import log

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import xdg

DB_FILE = os.path.join(xdg.XDG_DATA_HOME, "congruence", "db.sqlite")
if not os.path.exists(os.path.dirname(DB_FILE)):
    os.makedirs(os.path.dirname(DB_FILE))
log.info("Connecting to database at %s" % DB_FILE)
engine = create_engine('sqlite:///' + DB_FILE)
connection = engine.connect()
Session = sessionmaker(bind=engine)
