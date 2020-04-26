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


"""
This file contains classes which represent content objects in Confluence.
"""

from congruence.interface import convert_date, html_to_text, md_to_html
from congruence.logging import log
from congruence.interface import make_request
from congruence.args import config

import json
import re
from uuid import uuid4
from abc import ABC, abstractmethod


class ConfluenceObject(ABC):
    """Base class for all Confluence content objects

    Can be a page, a comment, a user, a space, anything.

    """

    def __init__(self, data):
        self._data = data
        #  log.debug(json.dumps(data, indent=2))
        self.type = self._data['type']

    @abstractmethod
    def get_title(self):
        """Subclasses who implement this must return a string"""
        pass

    @abstractmethod
    def get_columns(self):
        """Subclasses who implement this must return a list of length five

        This function is used for representing the object in a list entry.
        """
        pass

    def get_json(self):
        return json.dumps(self._data, indent=2, sort_keys=True)

    def get_content(self):
        """Represents the body of a carded list entry"""

        return ""

    def get_head(self):
        """Represents the head of a carded list entry"""

        return self.get_title()


class Content(ConfluenceObject):
    """Base class for Pages, Blogposts, Comments, Attachments"""

    def __init__(self, data):
        super().__init__(data)
        self.title = self._data['title']
        self.id = self._data['id']
        self.versionby = User(self._data['history']['lastUpdated']['by'])
        try:
            self.space = Space(self._data['space'])
        except KeyError:
            self.space = None
        self.versionby = User(self._data['history']['lastUpdated']['by'])

        self.liked = False  # TODO determine

    def get_title(self):
        return self._data['title']

    def get_columns(self):
        content = self._data
        lastUpdated = content['history']['lastUpdated']
        result = [
            self.type[0].upper(),
            self.space.key if self.space else '?',
            self.versionby.display_name,
            convert_date(lastUpdated['when'], 'friendly'),
            self.get_title(),
        ]
        return result

    #  def get_like_status(self):

    def like(self):
        id = self.id
        log.debug("Liking %s" % id)
        headers = {
            'Content-Type': 'application/json',
        }
        r = make_request(f'rest/likes/1.0/content/{id}/likes',
                         method='POST',
                         headers=headers,
                         data='')
        if r.status_code == 200:
            self.liked = True
            return True
        if r.status_code == 400:
            # already liked
            self.liked = True
        log.error("Like failed")
        return False

    def unlike(self):
        id = self.id
        log.debug("Unliking %s" % id)
        r = make_request(f'rest/likes/1.0/content/{id}/likes',
                         method='DELETE',
                         #  headers=headers,
                         data="")

        if r.status_code == 200:
            self.liked = False
            return True
        log.error("Unlike failed")
        return False

    def toggle_like(self):
        if self.liked:
            return self.unlike()
        else:
            return self.like()


class Page(Content):
    pass


class Blogpost(Page):
    pass


class Comment(Content):
    def __init__(self, data):
        super().__init__(data)

        date = self._data['history']['createdDate']
        self.url = data['_links']['webui']
        date = convert_date(date)
        self.blacklisted = False
        username = self.versionby.display_name
        if ("UserBlacklist" in config and
                self.versionby.username in config["UserBlacklist"]):
            self.blacklisted = True
            username = "<blocked user>"
        self.head = '%s, %s' % (username, date)
        self.ref = None
        try:
            extensions = self._data['extensions']
            inline_properties = extensions['inlineProperties']
            self.ref = inline_properties['originalSelection']
            self.head += " (inline comment)"
        except KeyError:
            pass

    def get_title(self):
        return self.title

    def get_columns(self):
        content = self._data
        lastUpdated = content['history']['lastUpdated']
        result = [
            self.type[0].upper(),
            self.space.key if self.space else '?',
            self.versionby.display_name,
            convert_date(lastUpdated['when'], 'friendly'),
            self.get_title(),
        ]
        return result

    def get_head(self):
        return self.head

    def get_content(self):
        #  log.debug(self._data)
        if self.blacklisted:
            return ""
        comment = html_to_text(
            self._data['body']['view']['value'],
            replace_emoticons=True,
        )
        if self.ref:
            # TODO set in italics
            comment = f"> {self.ref}\n\n{comment}"
        return comment

    def send_reply(self, text):
        page_id = self._data['_expandable']['container']
        page_id = re.search(r'/([^/]*$)', page_id).groups()[0]
        url = (f'/rest/tinymce/1/content/{page_id}/'
               f'comments/{self.id}/comment')
        params = {'actions': 'true'}
        answer = md_to_html(text, url_encode='html')
        uuid = str(uuid4())
        headers = {
            'X-Atlassian-Token': 'no-check',
        }

        data = f'{answer}&watch=false&uuid={uuid}'
        r = make_request(url, params, method='POST', data=data,
                         headers=headers, no_token=True)
        if r.status_code == 200:
            return True
        return False

    def match(self, search_string):
        try:
            return (
                re.search(search_string, self.get_title())
                or re.search(search_string, self.get_content())
            )
        except KeyError:
            return re.search(search_string, self.title)


class Attachment(Content):
    pass


class User(ConfluenceObject):
    def __init__(self, data):
        super().__init__(data)
        self.type = "user"

        self._data = data
        self.date = '?'
        #  log.debug(self.get_json())
        self.display_name = self._data['displayName']
        self.username = self._data['username']

    def get_title(self):
        return self.display_name

    def get_columns(self):
        return [
            self.type[0].upper(),
            '',
            self.display_name,
            self.date,
            '',
        ]


class Space(ConfluenceObject):
    def __init__(self, data):
        super().__init__(data)

        try:
            self.key = self._data['key']
            self.name = self._data['name']
        except KeyError:
            self.key = self._data['space']['key']
            self.name = self._data['space']['name']

    def get_title(self):
        return self.name

    def get_columns(self):
        return [
            self.type[0].upper(),
            self.key,
            self.name,
            convert_date(self._data['timestamp'], 'friendly'),
            '',
        ]

    def match(self, search_string):
        return re.search(search_string, self.name)


class Generic(ConfluenceObject):
    def __init__(self, data):
        super().__init__(data)
        log.debug(json.dumps(data, indent=2))
        try:
            self.title = self._data['title']
        except KeyError:
            self.title = "Generic object"

    def get_title(self):
        return self.title

    def get_columns(self):
        return [
            '?',
            '?',
            '?',
            '?',
            self.title,
        ]


class ContentWrapper(object):
    """Class for content wrapper objects

    This is only for pages, blog posts, attachments and comments
    """

    type_map = {
        'page': Page,
        'blogpost': Blogpost,
        'comment': Comment,
        'attachment': Attachment,
        'space': Space,
        'personal': Space,
        'user': User,
    }

    def __init__(self, data):
        """Constructor

        :data: a json object representing the object
        """

        self._data = data
        #  log.debug(json.dumps(data, indent=2))
        content_data = data[data['entityType']]
        self.type = content_data['type']
        try:
            self.content = self.type_map[self.type](content_data)
        except KeyError:
            log.error("Unknown entity type: %s" % self.type)
            self.content = Generic(content_data)

        self.title = self.content.get_title()

    def get_title(self):
        return self.content.get_title()

    def get_columns(self):
        return self.content.get_columns()

    def get_head(self):
        return self.content.get_head()

    def match(self, search_string):
        return re.search(search_string, self.title)

    def get_content(self):
        # TODO load content if not in object already
        #  return self._data['content']['_expandable']['container']
        return self.content.get_content()

    def get_json(self):
        return json.dumps(self._data, indent=2, sort_keys=True)
