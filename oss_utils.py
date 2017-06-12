#!/usr/bin/env python3
# coding=utf-8

import os
import json
import logging
import time
import traceback
import oss2

log = logging.getLogger(__name__)


class ListedBucket(oss2.Bucket):
    def __init__(self, accesskey, secretkey, endpoint, bucket_name, is_cname=False, session=None, connect_timeout=None,
                 app_name='',
                 enable_crc=True):
        self._auth = oss2.Auth(accesskey, secretkey)
        super().__init__(self._auth, endpoint, bucket_name, is_cname, session, connect_timeout, app_name, enable_crc)

    def put_file_to_listed_folder(self, key, filename, skip_exist=False, max_retries=5, **kwargs):
        """
        将文件上传到OSS上, 并且更新对应的 list.json
        详情请看README.md中 OSS存储备忘录 一节
        """
        key = key.lstrip("/")

        if skip_exist and self.object_exists(key):
            file_size = os.path.getsize(filename)
            meta = self.get_object_meta(key)

            if meta.content_length == file_size:
                log.info("skip: {}".format(key))
                return True
            else:
                log.info("remote file exist but not same, overwrite. len:{} local: len:{}".format(
                    meta.content_length, file_size,
                ))

        log.info("OSS: uploading {} to {}".format(filename, key))

        for i in range(max_retries):
            try:
                result = self.put_object_from_file(key, filename, **kwargs)
                assert result.status == 200
            except:
                if i == max_retries - 1:
                    raise
                traceback.print_exc()
                time.sleep(1)
            else:
                break

        dir_name = os.path.dirname(key)
        base_name = os.path.basename(key)
        modify_time = int(os.path.getmtime(filename))

        # 下载 list.json
        list_json_key = "{}/list.json".format(dir_name.rstrip("/"))
        for i in range(max_retries):
            try:
                list_json = self.get_object(list_json_key).read().decode("utf-8")
                files = json.loads(list_json)  # type: dict
            except oss2.exceptions.NoSuchKey:
                files = {}
                break
            except:
                if i == max_retries - 1:
                    raise
                traceback.print_exc()
                time.sleep(1)
            else:
                break

        # 更新 list.json
        file_dic = files.get(base_name, {})
        file_dic["timestamp"] = modify_time
        files[base_name] = file_dic

        # 把更新后的list.json传回OSS
        for i in range(max_retries):
            try:
                _result = self.put_object(list_json_key, json.dumps(files).encode("utf-8"))
                assert _result.status == 200
            except:
                if i == max_retries - 1:
                    raise
                traceback.print_exc()
                time.sleep(1)
            else:
                break

        return result


def upload_folder_to_oss(bucket_obj, folder, key_prefix="", **kwargs):
    """

    :type bucket_obj: ListedBucket
    """
    for dirpath, dirnames, filenames in os.walk(folder):
        reldirpath = os.path.relpath(dirpath, folder)
        if reldirpath == ".":
            reldirpath = ""
        this_key_prefix = os.path.join(key_prefix, reldirpath)

        for filename in filenames:
            key = os.path.join(this_key_prefix, filename)
            file = os.path.join(dirpath, filename)
            bucket_obj.put_file_to_listed_folder(key, file, **kwargs)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        format="[%(levelname)s %(asctime)s %(module)s.%(funcName)s#%(lineno)d] %(message)s",
        level=logging.INFO
    )
    if len(sys.argv) < 2:
        log.error("You must give at least one folder!")
        exit(1)

    accesskey = os.getenv("OSS_ACCESS_KEY")
    secretkey = os.getenv("OSS_SECRET_KEY")
    endpoint = os.getenv("OSS_ENDPOINT")
    bucket_name = os.getenv("OSS_BUCKET")
    prefix = os.getenv("OSS_PREFIX", "")
    skip_exist = os.getenv("OSS_SKIP_EXIST", False)

    if not (accesskey and accesskey and endpoint and bucket_name):
        log.error("you must set OSS_ACCESS_KEY OSS_SECRET_KEY OSS_ENDPOINT OSS_BUCKET environment value")
        exit(2)

    bucket_obj = ListedBucket(accesskey, secretkey, endpoint, bucket_name)

    for folder in sys.argv[1:]:
        log.info("uploading: {}".format(folder))
        upload_folder_to_oss(bucket_obj, folder, key_prefix=prefix, skip_exist=skip_exist)

    log.info("done!")
