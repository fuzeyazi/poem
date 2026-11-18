package com.fuze.potryservice.service.impl;

import com.fuze.context.BaseContext;
import com.fuze.potryservice.mapper.PoemLunTanMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DeadlockLoserDataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * 验证点赞 toggle 的幂等契约(PoemLunTanServiceimpl.toggleLike,经公开入口 dianzan 驱动):
 * 1. 原子占位:ZADD 返回值决定方向,并发首点只有一个成功;
 * 2. 事实源:blog_like 明细表 affected>0 才动计数列——Redis 丢数据时自动拦截重复计数;
 * 3. 降级:Redis 异常直走 DB 明细判重,链路对 Redis 故障零感知;
 * 4. 死锁:InnoDB 死锁回滚 victim 后重试至多 4 次,重试体天然幂等。
 */
@ExtendWith(MockitoExtension.class)
class PoemLunTanServiceLikeTest {

    private static final String KEY = "blog:like42";
    private static final int USER = 1;
    private static final int BLOG = 42;

    @Mock
    private PoemLunTanMapper poemLunTanMapper;
    @Mock
    private TransactionTemplate transactionTemplate;
    @Mock
    private StringRedisTemplate stringRedisTemplate;
    @Mock
    private ZSetOperations<String, String> zSetOps;
    @InjectMocks
    private PoemLunTanServiceimpl service;

    @BeforeEach
    void setUp() {
        BaseContext.setCurrentId((long) USER);
        lenient().when(stringRedisTemplate.opsForZSet()).thenReturn(zSetOps);
        // 让编程式事务直接执行回调体(单测无真实事务管理器)
        lenient().when(transactionTemplate.execute(any()))
                .thenAnswer(inv -> ((TransactionCallback<Boolean>) inv.getArgument(0)).doInTransaction(null));
    }

    @AfterEach
    void tearDown() {
        BaseContext.removeAll();
    }

    @Test
    @DisplayName("首次点赞:ZADD 占位成功→明细插入 affected=1→计数+1,返回 true")
    void firstLike_incrementsCounter() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(true);
        when(poemLunTanMapper.insertBlogLike(USER, BLOG)).thenReturn(1);

        boolean liked = service.dianzan(BLOG);

        assertTrue(liked);
        verify(poemLunTanMapper).insertBlogLike(USER, BLOG);
        verify(poemLunTanMapper).updatedianzan(BLOG);
        verify(poemLunTanMapper, never()).updatequxiaodianzan(anyInt());
    }

    @Test
    @DisplayName("计数防刷:Redis 占位成功但明细已存在(affected=0)→计数不动(Redis 丢数据后自愈路径)")
    void redisLostData_counterBlocked() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(true);
        when(poemLunTanMapper.insertBlogLike(USER, BLOG)).thenReturn(0);

        boolean liked = service.dianzan(BLOG);

        assertTrue(liked);
        verify(poemLunTanMapper, never()).updatedianzan(anyInt());
    }

    @Test
    @DisplayName("取消点赞:ZADD 失败→ZREM 成功→明细删除 affected=1→计数-1,返回 false")
    void unlike_decrementsCounter() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(false);
        when(zSetOps.remove(eq(KEY), anyString())).thenReturn(1L);
        when(poemLunTanMapper.deleteBlogLike(USER, BLOG)).thenReturn(1);

        boolean liked = service.dianzan(BLOG);

        assertFalse(liked);
        verify(poemLunTanMapper).deleteBlogLike(USER, BLOG);
        verify(poemLunTanMapper).updatequxiaodianzan(BLOG);
        verify(poemLunTanMapper, never()).updatedianzan(anyInt());
    }

    @Test
    @DisplayName("取消但明细已不在(affected=0)→计数不扣,返回 false")
    void unlike_detailGone_counterUntouched() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(false);
        when(zSetOps.remove(eq(KEY), anyString())).thenReturn(1L);
        when(poemLunTanMapper.deleteBlogLike(USER, BLOG)).thenReturn(0);

        boolean liked = service.dianzan(BLOG);

        assertFalse(liked);
        verify(poemLunTanMapper, never()).updatequxiaodianzan(anyInt());
    }

    @Test
    @DisplayName("仅剩占位残留(ZREM=0,明细已随事务回滚)→直接 false,不进事务")
    void placeholderOnly_noTransaction() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(false);
        when(zSetOps.remove(eq(KEY), anyString())).thenReturn(0L);

        boolean liked = service.dianzan(BLOG);

        assertFalse(liked);
        verify(poemLunTanMapper, never()).deleteBlogLike(anyInt(), anyInt());
        verify(transactionTemplate, never()).execute(any());
    }

    @Test
    @DisplayName("Redis 全挂:降级走 DB 明细判重,点赞仍成功(链路对 Redis 故障零感知)")
    void redisDown_degradesToDbDetail() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenThrow(new RuntimeException("redis down"));
        when(poemLunTanMapper.insertBlogLike(USER, BLOG)).thenReturn(1);

        boolean liked = service.dianzan(BLOG);

        assertTrue(liked);
        verify(poemLunTanMapper).updatedianzan(BLOG);
        verify(zSetOps, never()).remove(anyString(), anyString());
    }

    @Test
    @DisplayName("Redis 挂+已点过赞:降级路径 insert=0→转 delete=1→取消点赞")
    void redisDown_unlikePath() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenThrow(new RuntimeException("redis down"));
        when(poemLunTanMapper.insertBlogLike(USER, BLOG)).thenReturn(0);
        when(poemLunTanMapper.deleteBlogLike(USER, BLOG)).thenReturn(1);

        boolean liked = service.dianzan(BLOG);

        assertFalse(liked);
        verify(poemLunTanMapper).updatequxiaodianzan(BLOG);
    }

    @Test
    @DisplayName("InnoDB 死锁:victim 回滚后重试,第 3 次成功(共 3 次事务)")
    void deadlock_retriesThenSucceeds() {
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(true);
        AtomicInteger attempts = new AtomicInteger();
        when(poemLunTanMapper.insertBlogLike(USER, BLOG)).thenAnswer(inv -> {
            if (attempts.incrementAndGet() <= 2) {
                throw new DeadlockLoserDataAccessException("deadlock", null);
            }
            return 1;
        });

        boolean liked = service.dianzan(BLOG);

        assertTrue(liked);
        verify(transactionTemplate, times(3)).execute(any());
        verify(poemLunTanMapper, times(1)).updatedianzan(BLOG);
    }

    @Test
    @DisplayName("死锁连续 5 次未成:耗尽异常被 toggleLike 的 catch(Exception) 吞掉→再走降级路径重试一轮(共 10 次事务)后上抛")
    void deadlock_exhausted_throws() {
        // ⚠️ 固化现状的测试:catch(Exception) 本意是 Redis 降级,但也会吞掉死锁耗尽的 DB 异常,
        // 导致 ZADD 成功路径的死锁耗尽额外经历一整轮"降级重试"(5+5=10 次)。
        // 若修复为 catch(RedisSystemException) 等窄化类型,本断言应改为 times(5)。
        when(zSetOps.add(eq(KEY), anyString(), anyDouble())).thenReturn(true);
        when(poemLunTanMapper.insertBlogLike(USER, BLOG))
                .thenThrow(new DeadlockLoserDataAccessException("deadlock", null));

        assertThrows(DeadlockLoserDataAccessException.class, () -> service.dianzan(BLOG));

        verify(transactionTemplate, times(10)).execute(any());
        verify(poemLunTanMapper, never()).updatedianzan(anyInt());
    }
}
