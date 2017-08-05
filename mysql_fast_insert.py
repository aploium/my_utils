#!/usr/bin/env python3
# coding=utf-8
"""
MySQL快速Insert辅助器
author: 零日
python3 only
"""
import threading
import traceback
import logging
import datetime
import time
import os
import multiprocessing

try:
    import MySQLdb
    import MySQLdb.cursors
except ImportError:
    try:
        import pymysql
        
        pymysql.install_as_MySQLdb()
        
        import MySQLdb
    except:
        raise ImportError("you should install mysqlclient(recommend) or pymysql")

DEFAULT_CONCURRENCY = 12
DEFAULT_QUEUE_SIZE = DEFAULT_CONCURRENCY * 2 + 10
# SUGGESTED_BATCH_SIZE = 1000

log = logging.getLogger(__name__)


class MysqlFastInsert(object):
    MODE_EXECUTEMANY = 1
    MODE_MERGED = 2
    MODE_BLACKHOLE = 3
    
    def __init__(
            self, conn_kwargs, base_sql=None,
            queue_size=DEFAULT_QUEUE_SIZE,
            concurrency=DEFAULT_CONCURRENCY,
            processed=False,
            mode=MODE_MERGED,
            statistic_interval=10,
            error_dump=True, dump_folder="sqldump"
    ):
        """
        :param conn_kwargs: 传到 MySQLdb.connect() 中的参数, dict
        :param base_sql: 基础sql, 例如:
                        '''
                            INSERT INTO `some_table`
                            (`id`, `name`, `phone`)
                            VALUES  -- 注意! VALUES后面的 (%s, %s, %s) 部分 <不要有>, 会自动生成
                        '''
        :param queue_size: 队列大小, 必须大于零, 建议的值是 concurrency*[2~5]
        :param concurrency: 并发数 并发数比较小的时候, 提升并发数能提升性能, 但是并发数过大后边际收益很小
        :param processed: 是否在独立子进程中运行mysql insert任务
                             若为False, 则在主进程中的子线程 (线程模式)
                             若为True, 则会放到一个单独的子进程中 (进程模式) (子进程中仍然会有一些工作线程)
                             进程模式会多消耗约20%的CPU, 速度比线程模式慢10%左右, 但是线程模式不能利用多核, 所以看情况取舍.
                             最好两种模式都跑一下, 然后看哪个更适合
        :param mode:    插入模式
                             MODE_EXECUTEMANY: 使用 cursor 的 .executemany() 来插入, 无注入风险, 但是比较慢
                             MODE_MERGED:      用字符串拼接的方式来插入, 比 MODE_EXECUTEMANY 快得多, 但有很小的注入风险
                                                  拼接前会自动使用 sql_escape() 来转义
                                                  拼接插入失败时会 fallback 到 MODE_EXECUTEMANY
                             MODE_BLACKHOLE:   什么都不做, 丢弃所有结果, 一般用来测速什么的
        :param error_dump: 当sql插入出现问题时, 会把这条sql dump到文件夹中, 默认文件夹是当前目录的 sqldump
        :
        """
        _conn_kw = dict(
            use_unicode=True,
            charset="utf8",
        )
        _conn_kw.update(conn_kwargs)
        self.conn_kwargs = _conn_kw
        self.concurrency = concurrency
        self.processed = processed
        self.mode = mode
        self.base_sql = base_sql
        self.statistic_interval = statistic_interval
        self.error_dump = error_dump
        
        if queue_size == 0:
            raise ValueError(
                "queue_size should not be 0, "
                "because the queue must be blocked when something goes wrong"
            )
        else:
            self.queue_size = queue_size
        
        if self.processed:
            import multiprocessing
            self._multiprocessing = multiprocessing
        else:
            import multiprocessing.dummy as multiprocessing_dummy
            self._multiprocessing = multiprocessing_dummy
        
        if self.mode == self.MODE_MERGED:
            self.insert_function = self._insert_merged
        elif self.mode == self.MODE_EXECUTEMANY:
            self.insert_function = self._insert_executemany
        elif self.mode == self.MODE_BLACKHOLE:
            self.insert_function = self._insert_blackhole
        else:
            raise ValueError("wrong mode: {}".format(self.mode))
        
        self.queue = self._multiprocessing.JoinableQueue(self.queue_size)
        self.subprocess = None
        
        self.checkpoint = time.time()
        
        # self.count是进程间的共享内存变量, 用于跨进程计数
        self.count = self._multiprocessing.Value("i", 0, lock=False)
        self.count.value = 0
        
        # sqldump的文件夹
        self.dump_folder = os.path.abspath(dump_folder)
        if not os.path.exists(self.dump_folder):
            try:
                os.makedirs(self.dump_folder)
            except:
                log.warning("cannot create folder: {}, bad sql dump is disabled".format(
                    self.dump_folder
                ))
                self.error_dump = False
                self.dump_folder = None
        
        log.info("MysqlFastInsert init complete")
    
    def start(self):
        self.subprocess = self._multiprocessing.Process(target=self._run_keeper)
        self.subprocess.daemon = True
        self.subprocess.start()
    
    def join(self):
        if self.subprocess is None:
            raise RuntimeError("You must start() before join()")
        else:
            self.queue.join()
    
    def insert_many(self, rows, block=True, timeout=None):
        """
        插入多条记录(几百条)
        :param rows:
         格式如下, 每行与上面 base_sql 中的VALUES对应:
            [
                (id, name, phone, ...),
                (id, name, phone, ...),
                (id, name, phone, ...),
            ]
        """
        if not rows:
            return
        
        self.queue.put(rows, block=block, timeout=timeout)
        
        self.print_statistic()
    
    def print_statistic(self):
        now = time.time()
        if now - self.checkpoint > self.statistic_interval:
            count = self.count.value
            self.count.value = 0
            delta = now - self.checkpoint
            self.checkpoint = now
            if now - self.checkpoint > 3 * self.statistic_interval:
                # 间隔过长, 统计数据无意义, 不打印带有速率的回显, 只打印数量
                log.info("inserted {} rows in the past {}s".format(count, round(delta, 3)))
            else:
                log.info(
                    "delta:{}s count:{} speed:{}/s qsize:{} qfull:{} P:{} Th:{}".format(
                        round(delta, 3), count, round(count / delta, 2),
                        self.queue.qsize(), self.queue.full(),
                        multiprocessing.current_process().name,
                        threading.current_thread().name,
                    ))
    
    def _insert_executemany(self, cur, rows):
        sql_values_placeholder = "(" + "%s," * (len(rows[0]) - 1) + "%s)"
        sql = self.base_sql + sql_values_placeholder
        try:
            return cur.executemany(sql, rows)
        except:
            log.error("mysql语句在MODE_EXECUEMANY执行失败", extra={"sql": sql}, exc_info=True, )
            raise
    
    def _insert_blackhole(self, cur, rows):
        return len(rows)
    
    def sql_escape(self, value):
        if isinstance(value, str):
            return MySQLdb.escape_string(value).decode("utf-8")
        elif isinstance(value, bytes):
            try:
                return self.sql_escape(value.decode("utf-8"))
            except:
                return value
        else:
            return value
    
    def _insert_merged(self, cur, rows):
        sql_values = ",".join(
            "({})".format(",".join(
                "\"{}\"".format(self.sql_escape(x)) for x in row
            ))
            for row in rows
        )
        
        sql = self.base_sql + sql_values
        
        try:
            return cur.execute(sql)
            # return len(rows)
        except:
            try:
                self._insert_executemany(cur, rows)
            except:
                raise
            else:
                log.warning(
                    "mysql语句在MODE_MERGED执行出错, 但在MODE_EXECUEMANY执行成功, sql已dump供分析",
                    extra={"sql": sql},
                    exc_info=True,
                )
            finally:
                self.sql_dump(sql, traceback.format_exc())
            
            raise
    
    def _get_connection(self):
        """不断尝试连接mysql, 因为程序会长期运行, 中间可能会有mysql的短暂宕机"""
        sleep_interval = 1
        while True:
            try:
                conn = MySQLdb.connect(**self.conn_kwargs)  # type: MySQLdb.connections.Connection
                
                cur = conn.cursor()  # type: MySQLdb.cursors.Cursor
                cur.execute('SET NAMES UTF8')
            except:
                log.error("无法连接mysql", exc_info=True)
                time.sleep(sleep_interval)
                sleep_interval += 10
            else:
                return conn, cur
    
    def re_connect(self, conn):
        try:
            conn.close()
        except:
            pass
        return self._get_connection()
    
    def _queue_submitting(self):
        log.info("MysqlFastInsert thread:{} start".format(threading.current_thread()))
        
        conn, cur = self._get_connection()
        
        while True:
            try:
                lines = self.queue.get()
            except:
                log.error("mysql-inserter unable to get queue", exc_info=True)
                time.sleep(6)
                continue
            
            # log.debug("line:", len(lines), lines[:3])
            start_time = time.time()
            try:
                row_count = self.insert_function(cur, lines)
                # row_count = len(lines)
            except MySQLdb.ProgrammingError:
                # 例如: 表不存在, 语法错误等
                log.error(
                    "mysql执行错误 MySQLdb.ProgrammingError! process:{} cursor:{}".format(
                        self._multiprocessing.current_process(),
                        cur),
                    exc_info=True)
                # 不需要重连
            
            except:
                log.error(
                    "mysql insert error! process:{} cursor:{}".format(
                        self._multiprocessing.current_process(),
                        cur),
                    exc_info=True)
                
                conn, cur = self.re_connect(conn)
            
            else:
                try:
                    conn.commit()
                except:
                    log.error("commit error!", exc_info=True)
                    
                    conn, cur = self.re_connect(conn)
                else:
                    log.debug("mysql successfully inserted: {} rows in {}ms".format(
                        row_count, round((time.time() - start_time) * 1000, 2)))
                    
                    self.count.value += row_count  # 用于跨进程计数
            
            finally:
                self.queue.task_done()
    
    def _run_keeper(self):
        log.debug("run keeper running at {}".format(self._multiprocessing.current_process()))
        pool = []
        for i in range(self.concurrency):
            p = threading.Thread(
                target=self._queue_submitting,
            )
            p.daemon = True
            p.start()
            pool.append(p)
        for p in pool:
            p.join()
    
    def sql_dump(self, sql, msg=None):
        if not self.error_dump:
            return
        
        dump_prefix = os.path.join(
            self.dump_folder,
            "sqldump_{}".format(
                datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
            )
        )
        
        try:
            with open(dump_prefix + ".sql", "w", encoding="utf-8") as fw:
                fw.write(sql)
            
            if msg:
                with open(dump_prefix + ".meta.txt", "w", encoding="utf-8") as fw:
                    fw.write(msg)
        except:
            log.warning("unable to dump bad sql", exc_info=True)
        
        else:
            log.warning("bad sql has been dumped to {}".format(dump_prefix + ".sql"))


def main():
    conn_kwargs = dict(
        host="",
        user="",
        passwd="",
        db="",
        use_unicode=True,
        charset="utf8",
    )
    
    inserter = MysqlFastInsert(
        conn_kwargs,
        base_sql="aaaaaaaaa"
    )
    inserter.start()
    inserter.join()


if __name__ == '__main__':
    main()
