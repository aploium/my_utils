# coding=utf-8
"""
本模块提供了一个线程安全的 keep-alive 链接池

requests的连接在每个session中是自动 keep-alive 的,
    在 `connection_keep_alive` 关闭时, 每次请求都会创建一个新的session,
        并发起一次新的请求, 则会带来相当大的连接开销(时间上)
    通过保持并复用 requests 的session, 可以极大地减少requests在请求远程服务器时的连接延迟

以前的版本是线程不安全, 当并发数大时会出现 ConnectionResetError
"""
import time
import requests
import threading
from decorator import contextmanager
import six.moves.urllib.parse as urllib_parse

SESSION_TTL = 30  # 在清除过期session时, 会丢弃所有x秒未活动的session
_gc_checkpoint = time.time()

# session池
pool = {
    "example.com": [
        # 每个域名下都有一堆session,
        # session的获取遵循 LIFO(后进先出) 原则,
        #    即优先获取最近使用过的 session
        # 这样可以增加 keep-alive 的存活几率
        {
            "domain": "example.com",
            "session": requests.Session(),
            "active": time.time(),
        },
    ],
}
cleaning_lock = threading.Lock()
locked_session = threading.local()  # 这是一个 thread-local 变量


def get_session(domain_or_url):
    """
    获取一个此域名的 keep-alive 的session
    :param domain_or_url: 域名
    :type domain_or_url: str
    :rtype: requests.Session
    """
    domain = urllib_parse.urlsplit(domain_or_url).netloc or domain_or_url
    
    if domain not in pool:
        pool[domain] = []
    
    if not hasattr(locked_session, "sessdicts"):
        # 这个变量用于存储本线程中被锁定的session
        # 当一个session被拿出来使用时, 会从 pool 中被移除, 加入到下面这个变量中
        # 当线程结束后, 需要调用 release_lock() 来释放被锁定的session
        #    此时被锁定的session会重新进入session池
        locked_session.sessdicts = []
    
    if not pool[domain]:
        # 线程池空, 新建一个 session
        sessdict = {
            "domain": domain,
            "sessobj": requests.Session(),
        }
    else:
        # 从线程池中取出最近的一个
        sessdict = pool[domain].pop()
    
    sessdict["active"] = time.time()
    
    locked_session.sessdicts.append(sessdict)
    
    if _gc_checkpoint < time.time() - SESSION_TTL:
        with cleaning_lock:
            clear()
    
    return sessdict["sessobj"]  # type: requests.Session


@contextmanager
def session(domain_or_url):
    sess = get_session(domain_or_url)
    yield sess
    release_lock(sess)


def release_lock(session=None):
    if not hasattr(locked_session, "sessdicts"):
        if session is not None:
            raise ValueError("You DONT have this session!")
        return
    
    if session is not None:
        for _sessdict in locked_session.sessdicts:
            if _sessdict["sessobj"] == session:
                sessdict = _sessdict
                break
        else:
            raise ValueError("You DONT have this session: {}".format(session))
        
        locked_session.sessdicts.remove(sessdict)
        pool[sessdict["domain"]].append(sessdict)
    
    for sessdict in locked_session.sessdicts:  # type: dict
        pool[sessdict["domain"]].append(sessdict)


def clear(force_flush=False):
    if force_flush:
        pool.clear()
    else:
        for domain in list(pool.keys()):
            pool[domain] = [s for s in pool[domain] if s["active"] > time.time() - SESSION_TTL]
