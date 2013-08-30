import re
import json
import requests

class Client():
    _token_regex = re.compile(r'content="(.*?)"\s+name="csrf-token')

    def __init__(self, pod, username, password):
        self.session = requests.Session()
        self.pod = pod
        response = self.session.post("{0}/users/sign_in".format(self.pod),
                                     data={'user[username]': username,
                                           'user[password]': password,
                                           'authenticity_token': self._fetch_token()},
                                     allow_redirects=False)
        if response.status_code != 302:
            raise Exception("Invalid status code: {0}".format(response.status_code))


    def _fetch_token(self):
        response = self.session.get("{0}/stream".format(self.pod))
        return self._token_regex.search(response.text).group(1)

    def post(self, text, aspect_ids='public'):
        response = self.session.post("{0}/status_messages".format(self.pod),
                                     data=json.dumps({'status_message': {'text': text},
                                                      'aspect_ids': aspect_ids}),
                                     headers={'content-type': 'application/json',
                                              'accept': 'application/json',
                                              'x-csrf-token': self._fetch_token()})
        if response.status_code != 201:
            raise Exception("Invalid status code: {0}".format(response.status_code))
