#!/usr/bin/env python3
# coding=utf-8
"""Construct a requests.Response from raw http response bytes(including headers)"""
import io

__author__ = "Aploium <i@z.codes>"


class FakeSocket:
    def __init__(self, data=None):
        self.bytes_io = io.BytesIO(data)
    
    def close(self):
        pass
    
    def makefile(self, *args, **kwargs):
        return self.bytes_io


def bytes2response(data, level=3,
                   method=None, url="http://example.com", req_headers=None, req_files=None,
                   req_data=None, req_auth=None, req_json=None
                   ):
    """
    Construct a requests.Response from raw http response bytes(including headers)

    Warning: although we could decode raw bytes to response object,
        this is not the right way these library were designed to,
        this decode may cause unexpected bugs.

    :param data: raw http response bytes data, including headers
    :type data: bytes
    :param level:
        level=0: decode as http.client.HTTPResponse
        level=1: decode as requests.packages.urllib3.response.HTTPResponse
        level=2: decode to requests.Response (default)

    :rtype: requests.Response
    """
    # These imports can be moved outside to gain slight performance improvement
    #   they are placed here by default to avoid compatible issues
    import http.client
    import requests.packages
    import requests.adapters
    
    fake_socket = FakeSocket(data)
    resp_builtin = http.client.HTTPResponse(fake_socket, method=method, url=url)  # type: http.client.HTTPResponse
    resp_builtin.begin()
    if level == 0:
        return resp_builtin, resp_builtin.read()  # type: http.client.HTTPResponse,bytes
    
    # resolve to the requests builtin urllib3 HTTPResponse
    resp_requests_basic = requests.packages.urllib3.response.HTTPResponse.from_httplib(resp_builtin)
    if level == 1:
        return resp_requests_basic  # type: requests.packages.urllib3.response.HTTPResponse
    
    # fake Request
    req = requests.Request(
        method=method, url=url, headers=req_headers, files=req_files,
        data=req_data, auth=req_auth, json=req_json
    )
    req = req.prepare()
    
    # fake adapter, which is necessarily for response construct
    adapter = requests.adapters.HTTPAdapter()
    
    # resolve to the wellknown/often-see requests.Response
    wellknown_resp = adapter.build_response(req, resp_requests_basic)
    wellknown_resp._content = resp_requests_basic.data
    
    return wellknown_resp  # type: requests.Response
