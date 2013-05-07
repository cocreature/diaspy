import json
from diaspy.models import Post

"""Docstrings for this module are taken from:
https://gist.github.com/MrZYX/01c93096c30dc44caf71

Documentation for D* JSON API taken from:
http://pad.spored.de/ro/r.qWmvhSZg7rk4OQam
"""

class Generic:
    """Object representing generic stream. Used in Tag(),
    Stream(), Activity() etc.
    """
    def __init__(self, connection, location=''):
        """
        :param connection: Connection() object
        :type connection: diaspy.connection.Connection
        :param location: location of json
        :type location: str
        """
        self._connection = connection
        self._setlocation()
        if location: self._location = location
        self._stream = []
        self.fill()

    def __contains__(self, post):
        """Returns True if stream contains given post.
        """
        if type(post) is not Post:
            raise TypeError('stream can contain only posts: checked for {0}'.format(type(post)))
        return post in self._stream

    def __iter__(self):
        """Provides iterable interface for stream.
        """
        return iter(self._stream)

    def __getitem__(self, n):
        """Returns n-th item in Stream.
        """
        return self._stream[n]

    def __len__(self):
        """Returns length of the Stream.
        """
        return len(self._stream)

    def _setlocation(self):
        """Sets location of the stream.
        Location defaults to 'stream.json'

        NOTICE: inheriting objects should override this method
        and set their own value to the `location`.
        However, it is possible to override default location by
        passing the desired one to the constructor.
        For example:

            def _setlocation(self):
                self._location = 'foo.json'


        :param location: url of the stream
        :type location: str

        :returns: str
        """
        self._location = 'stream.json'

    def _obtain(self):
        """Obtains stream from pod.
        """
        request = self._connection.get(self._location)
        if request.status_code != 200:
            raise Exception('wrong status code: {0}'.format(request.status_code))
        return [Post(str(post['id']), self._connection) for post in request.json()]

    def clear(self):
        """Removes all posts from stream.
        """
        self._stream = []

    def purge(self):
        """Removes all unexistent posts from stream.
        """
        stream = []
        for post in self._stream:
            deleted = False
            try:
                post.get_data()
                stream.append(post)
            except Exception:
                deleted = True
            finally:
                if not deleted: stream.append(post)
        self._stream = stream

    def update(self):
        """Updates stream.
        """
        new_stream = self._obtain()
        ids = [post.post_id for post in self._stream]

        stream = self._stream
        for i in range(len(new_stream)):
            if new_stream[-i].post_id not in ids:
                stream = [new_stream[-i]] + stream
                ids.append(new_stream[-i].post_id)

        self._stream = stream

    def fill(self):
        """Fills the stream with posts.
        """
        self._stream = self._obtain()


class Outer(Generic):
    """Object used by diaspy.models.User to represent
    stream of other user.
    """
    def _obtain(self):
        """Obtains stream of other user.
        """
        request = self._connection.get(self._location)
        if request.status_code != 200:
            raise Exception('wrong status code: {0}'.format(request.status_code))
        return [Post(str(post['id']), self._connection) for post in request.json()]


class Stream(Generic):
    """The main stream containing the combined posts of the 
    followed users and tags and the community spotlights posts 
    if the user enabled those.
    """
    def _setlocation(self):
        self._location = 'stream.json'

    def post(self, text, aspect_ids='public', photos=None):
        """This function sends a post to an aspect

        :param text: Text to post.
        :type text: str
        :param aspect_ids: Aspect ids to send post to.
        :type aspect_ids: str

        :returns: diaspy.models.Post -- the Post which has been created
        """
        data = {}
        data['aspect_ids'] = aspect_ids
        data['status_message'] = {'text': text}
        if photos: data['photos'] = photos
        request = self._connection.post('status_messages',
                                        data=json.dumps(data),
                                        headers={'content-type': 'application/json',
                                                 'accept': 'application/json',
                                                 'x-csrf-token': self._connection.get_token()})
        if request.status_code != 201:
            raise Exception('{0}: Post could not be posted.'.format(
                            request.status_code))

        post = Post(str(request.json()['id']), self._connection)
        return post

    def _photoupload(self, filename):
        """Uploads picture to the pod.

        :param filename: path to picture file
        :type filename: str

        :returns: id of the photo being uploaded
        """
        data = open(filename, 'rb')
        image = data.read()
        data.close()

        params = {}
        params['photo[pending]'] = 'true'
        params['set_profile_image'] = ''
        params['qqfile'] = filename
        aspects = self._connection.getUserInfo()['aspects']
        for i, aspect in enumerate(aspects):
            params['photo[aspect_ids][{0}]'.format(i)] = aspect['id']

        headers = {'content-type': 'application/octet-stream',
                   'x-csrf-token': self._connection.get_token(),
                   'x-file-name': filename}

        request = self._connection.post('photos', data=image, params=params, headers=headers)
        if request.status_code != 200:
            raise Exception('wrong error code: {0}'.format(request.status_code))
        return request.json()['data']['photo']['id']

    def _photopost(self, id, text, aspect_ids):
        """Posts a photo after it has been uploaded.
        """
        post = self.post(text=text, aspect_ids=aspect_ids, photos=id)
        return post

    def post_picture(self, filename, text='', aspect_ids='public'):
        """This method posts a picture to D*.

        :param filename: path to picture file
        :type filename: str

        :returns: Post object
        """
        id = self._photoupload(filename)
        return self._photopost(id, text, aspect_ids)


class Activity(Generic):
    """Stream representing user's activity.
    """
    def _setlocation(self):
        self._location = 'activity.json'

    def _delid(self, id):
        """Deletes post with given id.
        """
        post = None
        for p in self._stream:
            if p['id'] == id:
                post = p
                break
        if post is not None: post.delete()

    def delete(self, post):
        """Deletes post from users activity.
        `post` can be either post id or Post()
        object which will be identified and deleted.
        After deleting post the stream will be filled.

        :param post: post identifier
        :type post: str, diaspy.models.Post
        """
        if type(post) == str: self._delid(post)
        elif type(post) == Post: post.delete()
        else:
            raise TypeError('this method accepts only int, str or Post: {0} given')
        self.fill()


class Aspects(Generic):
    """This stream contains the posts filtered by 
    the specified aspect IDs. You can choose the aspect IDs with 
    the parameter `aspect_ids` which value should be 
    a comma seperated list of aspect IDs. 
    If the parameter is ommitted all aspects are assumed. 
    An example call would be `aspects.json?aspect_ids=23,5,42`
    """
    def _setlocation(self):
        self._location = 'aspects.json'

    def add(self, aspect_name, visible=0):
        """This function adds a new aspect.
        """
        data = {'authenticity_token': self._connection.get_token(),
                'aspect[name]': aspect_name,
                'aspect[contacts_visible]': visible}

        r = self._connection.post('aspects', data=data)
        if r.status_code != 200:
            raise Exception('wrong status code: {0}'.format(r.status_code))

    def remove(self, aspect_id):
        """This method removes an aspect.
        """
        data = {'authenticity_token': self.connection.get_token()}
        r = self.connection.delete('aspects/{}'.format(aspect_id),
                                   data=data)
        if r.status_code != 404:
            raise Exception('wrong status code: {0}'.format(r.status_code))


class Commented(Generic):
    """This stream contains all posts 
    the user has made a comment on.
    """
    def _setlocation(self):
        self._location = 'commented.json'


class Liked(Generic):
    """This stream contains all posts the user liked.
    """
    def _setlocation(self):
        self._location = 'liked.json'


class Mentions(Generic):
    """This stream contains all posts 
    the user is mentioned in.
    """
    def _setlocation(self):
        self._location = 'mentions.json'


class FollowedTags(Generic):
    """This stream contains all posts 
    containing tags the user is following.
    """
    def _setlocation(self):
        self._location = 'followed_tags.json'

    def remove(self, tag_id):
        """Stop following a tag.

        :param tag_id: tag id
        :type tag_id: int
        """
        data = {'authenticity_token':self._connection.get_token()}
        request = self._connection.delete('tag_followings/{0}'.format(tag_id), data=data)
        if request.status_code != 404:
            raise Exception('wrong status code: {0}'.format(request.status_code))

    def add(self, tag_name):
        """Follow new tag.
        Error code 403 is accepted because pods respod with it when request 
        is sent to follow a tag that a user already follows.

        :param tag_name: tag name
        :type tag_name: str
        :returns: int (response code)
        """
        data = {'name':tag_name,
                'authenticity_token':self._connection.get_token(),
               }
        headers={'content-type': 'application/json',
                 'x-csrf-token': self._connection.get_token(),
                 'accept': 'application/json'}

        request = self._connection.post('tag_followings', data=json.dumps(data), headers=headers)

        if request.status_code not in [201, 403]:
            raise Exception('wrong error code: {0}'.format(request.status_code))
        return request.status_code
